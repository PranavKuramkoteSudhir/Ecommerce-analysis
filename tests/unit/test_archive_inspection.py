"""Synthetic archives only; never network, install or execute artifacts."""

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "inspect_pyspark_archive", ROOT / "scripts" / "inspect_pyspark_archive.py"
)
assert SPEC is not None and SPEC.loader is not None
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


def fixture_jar():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Implementation-Version: 3.4.1\n")
        jar.writestr("META-INF/maven/org.apache.hadoop/hadoop-client-api/pom.properties", "version=3.4.1\n")
        jar.writestr("software/amazon/awssdk/example/Test.class", b"synthetic, not executable")
    return data.getvalue()


def fixture_archive(name, data=b"", symlink=False):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as archive:
        info = tarfile.TarInfo(name)
        if symlink:
            info.type = tarfile.SYMTYPE
            info.linkname = "elsewhere.jar"
        else:
            info.size = len(data)
        archive.addfile(info, None if symlink else io.BytesIO(data))
    result.seek(0)
    return result


class ArchiveInspectionTests(unittest.TestCase):
    def test_independent_download_scratch_and_disk_limits(self):
        CHECKS.check_capacity(CHECKS.CAP, CHECKS.CAP, CHECKS.MIN_FREE)
        for downloaded, scratch, free, incoming in [
            (CHECKS.CAP, 0, CHECKS.MIN_FREE + 1, 1),
            (0, CHECKS.CAP, CHECKS.MIN_FREE + 1, 1),
            (0, 0, CHECKS.MIN_FREE - 1, 0),
            (0, 0, CHECKS.MIN_FREE, 1),
        ]:
            with self.subTest(values=(downloaded, scratch, free, incoming)):
                with self.assertRaises(ValueError):
                    CHECKS.check_capacity(downloaded, scratch, free, incoming)

    def test_sha256_mismatch_stops_inspection(self):
        data = b"synthetic archive hash fixture"
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        self.assertEqual(CHECKS.verified_digest(io.BytesIO(data), expected), expected)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            CHECKS.verified_digest(io.BytesIO(data + b"changed"), expected)

    def test_rejects_traversal_absolute_paths_and_jar_links(self):
        for name in ["../bad.jar", "/absolute.jar", "root/../../bad.jar", "root\\bad.jar"]:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    CHECKS.inspect_archive(fixture_archive(name))
        with self.assertRaisesRegex(ValueError, "regular file"):
            CHECKS.inspect_archive(fixture_archive("root/link.jar", symlink=True))

    def test_stream_inventory_and_embedded_metadata(self):
        name = "pyspark/jars/hadoop-client-api-3.4.1.jar"
        result = CHECKS.inspect_archive(fixture_archive(name, fixture_jar()))
        self.assertEqual(result["jar_count"], 1)
        self.assertEqual(result["jar_paths"], [name])
        record = result["relevant_jars"][0]
        self.assertEqual(record["metadata_status"], "stream_inspected_not_executed")
        self.assertIn("Implementation-Version: 3.4.1", record["metadata"]["META-INF/MANIFEST.MF"])
        self.assertEqual(record["aws_sdk_v2_class_entries"], 1)
        self.assertEqual(record["aws_sdk_v1_class_entries"], 0)

    def test_report_symlink_is_replaced_without_touching_external_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            scratch = root / "reports" / "runtime"
            scratch.mkdir(parents=True)
            archive = fixture_archive("pyspark/jars/hadoop-test.jar", fixture_jar()).getvalue()
            filename = "pyspark-4.0.3.tar.gz"
            (scratch / filename).write_bytes(archive)
            config = {"python_artifacts": [{
                "name": "pyspark", "version": "4.0.3", "filename": filename,
                "url": "https://files.pythonhosted.org/packages/synthetic/" + filename,
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
            }]}
            (root / "infra").mkdir()
            (root / "infra" / "candidate-lock.json").write_text(json.dumps(config))
            outside = root / "outside-scratch.json"
            outside.write_bytes(b"external content must survive")
            destination = scratch / "pyspark-inspection.json"
            destination.symlink_to(outside)
            with patch.object(CHECKS, "ROOT", root), patch.object(CHECKS, "SCRATCH", scratch), \
                    patch.object(CHECKS.shutil, "disk_usage", return_value=SimpleNamespace(free=CHECKS.MIN_FREE + CHECKS.CAP)), \
                    patch.object(CHECKS.urllib.request, "urlopen", side_effect=AssertionError("no network")) as network, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(CHECKS.main(), 0)
            network.assert_not_called()
            self.assertEqual(outside.read_bytes(), b"external content must survive")
            self.assertFalse(destination.is_symlink())
            report = json.loads(destination.read_text())
            self.assertEqual(report["jar_count"], 1)
            self.assertEqual(report["downloaded_payload_bytes_this_run"], 0)
            self.assertEqual(list(scratch.glob(".pyspark-inspection-*.tmp")), [])

    def test_failed_report_replace_cleans_temp_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory).resolve()
            destination = scratch / "pyspark-inspection.json"
            destination.write_bytes(b"previous report")
            with patch.object(CHECKS, "SCRATCH", scratch), \
                    patch.object(CHECKS.os, "replace", side_effect=OSError("synthetic failure")):
                with self.assertRaisesRegex(OSError, "synthetic failure"):
                    CHECKS.write_report_atomic(b"new report")
            self.assertEqual(destination.read_bytes(), b"previous report")
            self.assertEqual(list(scratch.glob(".pyspark-inspection-*.tmp")), [])

    def test_oversized_jar_is_inventoried_without_buffering(self):
        with patch.object(CHECKS, "MAX_JAR_MEMORY", 16):
            result = CHECKS.inspect_archive(fixture_archive("pyspark/jars/hadoop-test.jar", fixture_jar()))
        record = result["relevant_jars"][0]
        self.assertEqual(record["metadata_status"], "not_inspected_exceeds_64MiB_memory_bound")
        self.assertNotIn("sha256", record)


if __name__ == "__main__":
    unittest.main()
