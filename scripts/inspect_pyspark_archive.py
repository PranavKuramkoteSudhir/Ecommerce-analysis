"""Opt-in bounded PySpark archive inspection; no install, extraction or execution."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "reports" / "runtime"
CAP = 1024**3
MIN_FREE = 2 * 1024**3
CHUNK = 1024**2
MAX_JAR_MEMORY = 64 * 1024**2


def check_capacity(downloaded: int, scratch: int, free: int, incoming: int = 0):
    """Independent byte limits; incoming writes must retain the free-disk floor."""
    if downloaded + incoming > CAP:
        raise ValueError("cumulative download exceeds 1 GiB")
    if scratch + incoming > CAP:
        raise ValueError("scratch exceeds 1 GiB")
    if free - incoming < MIN_FREE:
        raise ValueError("less than 2 GiB free disk would remain")


def verified_digest(stream, expected: str, guard=lambda: None) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        guard()
        digest.update(chunk)
    actual = "sha256:" + digest.hexdigest()
    if actual != expected:
        raise ValueError("archive SHA256 does not match recorded candidate")
    return actual


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def relevant_jar(name: str) -> bool:
    return any(term in name.lower() for term in ("hadoop", "aws", "amazon", "bundle-2."))


def jar_metadata(data: bytes) -> dict:
    """Read bounded embedded text and class names, never execute or extract JARs."""
    with zipfile.ZipFile(io.BytesIO(data)) as jar:
        names = jar.namelist()
        selected = [name for name in names if name == "META-INF/MANIFEST.MF" or (
            name.startswith("META-INF/maven/org.apache.hadoop/") and name.endswith("/pom.properties")
        )]
        metadata = {}
        for name in selected:
            entry = jar.getinfo(name)
            if entry.file_size > CHUNK:
                raise ValueError("embedded metadata exceeds 1 MiB")
            metadata[name] = jar.read(entry).decode("utf-8", errors="replace")
        return {
            "metadata": metadata,
            "aws_sdk_v2_class_entries": sum("software/amazon/awssdk/" in name and name.endswith(".class") for name in names),
            "aws_sdk_v1_class_entries": sum("com/amazonaws/" in name and name.endswith(".class") for name in names),
            "s3a_filesystem_class_entries": sum(name.endswith("org/apache/hadoop/fs/s3a/S3AFileSystem.class") for name in names),
        }


def inspect_archive(stream, guard=lambda: None) -> dict:
    jars = []
    relevant = []
    with tarfile.open(fileobj=stream, mode="r|gz") as archive:
        for member in archive:
            guard()
            if not safe_member(member.name):
                raise ValueError("unsafe archive member path")
            if not member.name.endswith(".jar"):
                continue
            if not member.isfile():
                raise ValueError("JAR archive member is not a regular file")
            jars.append(member.name)
            if not relevant_jar(PurePosixPath(member.name).name):
                continue
            record = {"path": member.name, "size_bytes": member.size}
            if member.size > MAX_JAR_MEMORY:
                record["metadata_status"] = "not_inspected_exceeds_64MiB_memory_bound"
            else:
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("cannot stream JAR member")
                data = source.read(MAX_JAR_MEMORY + 1)
                if len(data) != member.size or len(data) > MAX_JAR_MEMORY:
                    raise ValueError("invalid or oversized JAR member")
                record["sha256"] = hashlib.sha256(data).hexdigest()
                record.update(jar_metadata(data))
                record["metadata_status"] = "stream_inspected_not_executed"
            relevant.append(record)
    return {"jar_count": len(jars), "jar_paths": sorted(jars), "relevant_jars": relevant}


def write_report_atomic(encoded: bytes, guard=lambda incoming=0: None):
    """Replace the destination entry, never open/follow a report symlink."""
    temporary = None
    try:
        guard(len(encoded))
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=SCRATCH, prefix=".pyspark-inspection-",
            suffix=".tmp", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(encoded)
            output.flush()
            guard()
        os.replace(temporary, SCRATCH / "pyspark-inspection.json")
        guard()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    artifact = next(item for item in json.loads((ROOT / "infra/candidate-lock.json").read_text())["python_artifacts"] if item["name"] == "pyspark")
    if SCRATCH.resolve() != SCRATCH:
        raise ValueError("scratch path must not traverse symlinks")
    if artifact["filename"] != f"pyspark-{artifact['version']}.tar.gz":
        raise ValueError("unexpected PySpark archive filename")
    if not artifact["url"].startswith("https://files.pythonhosted.org/packages/") or not artifact["url"].endswith("/" + artifact["filename"]):
        raise ValueError("unexpected PySpark artifact URL")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    archive_path = SCRATCH / artifact["filename"]
    partial = archive_path.with_suffix(archive_path.suffix + ".partial")
    if archive_path.is_symlink() or partial.is_symlink():
        raise ValueError("archive paths must not be symlinks")
    downloaded = 0
    min_free = shutil.disk_usage(SCRATCH).free
    peak_scratch = 0

    def guard(incoming=0):
        nonlocal min_free, peak_scratch
        used = sum(
            path.lstat().st_size for path in SCRATCH.rglob("*")
            if path.is_symlink() or path.is_file()
        )
        free = shutil.disk_usage(SCRATCH).free
        check_capacity(downloaded, used, free, incoming)
        min_free = min(min_free, free - incoming)
        peak_scratch = max(peak_scratch, used + incoming)

    guard()
    if not archive_path.exists():
        if partial.exists():
            raise ValueError("partial archive exists; inspect/remove explicitly before retry")
        request = urllib.request.Request(artifact["url"], method="HEAD")
        with urllib.request.urlopen(request, timeout=30) as response:
            length = int(response.headers["Content-Length"])
        guard(length)
        with urllib.request.urlopen(artifact["url"], timeout=60) as response:
            if int(response.headers["Content-Length"]) != length:
                raise ValueError("archive size changed after preflight")
            with partial.open("xb") as target:
                while downloaded < length:
                    chunk = response.read(min(CHUNK, length - downloaded))
                    if not chunk:
                        raise ValueError("truncated archive transfer")
                    guard(len(chunk))
                    target.write(chunk)
                    downloaded += len(chunk)
                    guard()
        with partial.open("rb") as source:
            verified_digest(source, artifact["digest"], guard)
        partial.rename(archive_path)
    with archive_path.open("rb") as source:
        digest = verified_digest(source, artifact["digest"], guard)
    with archive_path.open("rb") as source:
        inventory = inspect_archive(source, guard)
    report = {
        "artifact_url": artifact["url"], "sha256": digest,
        "archive_size_bytes": archive_path.stat().st_size,
        "downloaded_payload_bytes_this_run": downloaded,
        "download_cap_bytes": CAP, "scratch_cap_bytes": CAP,
        "minimum_free_required_bytes": MIN_FREE,
        "minimum_free_observed_or_reserved_bytes": min_free,
        "peak_scratch_observed_or_reserved_bytes": peak_scratch,
        "method": "recorded SHA256 verified; tar stream; bounded JAR bytes in memory; ZIP text/class-name inspection; no extraction/install/execution",
        "runtime_verification": "not_run", **inventory,
    }
    encoded = (json.dumps(report, indent=2) + "\n").encode()
    guard(len(encoded))
    report["minimum_free_observed_or_reserved_bytes"] = min_free
    report["peak_scratch_observed_or_reserved_bytes"] = peak_scratch
    encoded = (json.dumps(report, indent=2) + "\n").encode()
    guard(len(encoded))
    write_report_atomic(encoded, guard)
    guard()
    print(json.dumps({key: value for key, value in report.items() if key != "jar_paths"}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise SystemExit(f"Inspection stopped: {error}") from error
