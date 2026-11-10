"""Offline plan invariants and negative tests; no Docker or network access."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_platform_plan", ROOT / "scripts" / "check_platform_plan.py"
)
assert SPEC is not None and SPEC.loader is not None
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


class PlatformPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / "infra" / "candidate-lock.json").read_text())

    def changed(self, path, value):
        plan = deepcopy(self.plan)
        target = plan
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return plan

    def test_candidate_is_internally_consistent(self):
        self.assertEqual(CHECKS.validate(self.plan), [])

    def test_rejects_mutable_or_non_arm_image(self):
        for path, value in [
            (("images", "seaweedfs", "arm64_digest"), "sha256:unverified"),
            (("images", "postgres", "pinned_reference"), "postgres:latest"),
            (("images", "python", "platform"), "linux/amd64"),
            (("images", "redpanda", "verification"), "locally_tested"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_rejects_incompatible_runtime_and_dependency_drift(self):
        for path, value in [
            (("runtime", "scala_binary"), "2.12"),
            (("runtime", "java_major"), 11),
            (("runtime", "spark_version"), "4.1.0"),
            (("runtime", "hadoop_version"), "3.3.4"),
            (("sdk_review", "hadoop_managed_bundle_version"), "1.12.262"),
            (("sdk_review", "spark_declared_sdk_v2_version"), "2.24.6"),
            (("python_artifacts", 0, "version"), "4.1.0"),
            (("maven_artifacts", 0, "coordinate"), "io.delta:delta-spark_2.12"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_unresolved_sdk_cannot_be_selected_or_accepted(self):
        for path, value in [
            (("sdk_review", "selected_bundle_version"), "2.24.6"),
            (("sdk_review", "selected_bundle_version"), "2.25.53"),
            (("sdk_review", "selected_bundle_version"), "1.12.262"),
            (("sdk_review", "accepted"), True),
            (("sdk_review", "status"), "compatible"),
            (("sdk_review", "effective_classpath_verified"), True),
            (("sdk_review", "compatibility_tested"), True),
            (("maven_artifacts", 3, "status"), "approved"),
        ]:
            with self.subTest(path=path, value=value):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_sdk_declarations_retain_primary_source_context(self):
        declarations = self.plan["sdk_review"]["declarations"]
        for suffix in ["apache/spark/v4.0.3/pom.xml", "apache/spark/v4.0.3/hadoop-cloud/pom.xml"]:
            self.assertTrue(any(d["source_url"].endswith(suffix) for d in declarations))
        self.assertTrue(CHECKS.validate(self.changed(("sdk_review", "declarations"), [])))

    def test_rejects_jdk_artifact_identity_drift(self):
        original = self.plan["runtime"]["jdk"]
        java11 = deepcopy(original)
        java11.update(
            version="11.0.29+7",
            filename="OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.29_7.tar.gz",
            url="https://github.com/adoptium/temurin11-binaries/releases/download/"
            "jdk-11.0.29%2B7/OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.29_7.tar.gz",
        )
        self.assertIn(
            "JDK artifact Java major mismatch",
            CHECKS.validate(self.changed(("runtime", "jdk"), java11)),
        )
        x86 = deepcopy(original)
        x86.update(
            platform="linux/x86_64",
            filename=original["filename"].replace("aarch64", "x64"),
            url=original["url"].replace("aarch64", "x64"),
        )
        self.assertIn(
            "JDK must target native Linux AArch64",
            CHECKS.validate(self.changed(("runtime", "jdk"), x86)),
        )
        for field, value, error in [
            ("filename", original["filename"].replace("17.0.21", "17.0.20"),
             "JDK filename does not match release/platform"),
            ("url", original["url"].replace("17.0.21", "17.0.20"),
             "JDK URL does not match canonical release artifact"),
            ("url", original["url"].replace("github.com", "example.invalid"),
             "JDK URL does not match canonical release artifact"),
            ("version", "not-a-release", "invalid JDK release version"),
        ]:
            with self.subTest(field=field, value=value):
                self.assertIn(error, CHECKS.validate(self.changed(("runtime", "jdk", field), value)))

    def test_rejects_coordinated_maven_url_and_sidecar_drift(self):
        for index, artifact in enumerate(self.plan["maven_artifacts"]):
            with self.subTest(coordinate=artifact["coordinate"]):
                plan = deepcopy(self.plan)
                changed = plan["maven_artifacts"][index]
                wrong_version = "4.0.0" if artifact["version"] == "4.0.1" else "0.0.0"
                changed["url"] = artifact["url"].replace(artifact["version"], wrong_version)
                changed["checksum_url"] = changed["url"] + ".sha1"
                errors = CHECKS.validate(plan)
                self.assertIn("Maven URL does not match coordinate/version", errors)
                self.assertIn("Maven checksum source mismatch", errors)

    def test_rejects_missing_or_duplicate_jvm_dependencies(self):
        for artifacts in [self.plan["maven_artifacts"][:-1], self.plan["maven_artifacts"] * 2]:
            self.assertTrue(CHECKS.validate(self.changed(("maven_artifacts",), artifacts)))

    def test_rejects_insufficient_or_incorrect_headroom(self):
        for path, value in [
            (("resources", "docker_allocation_bytes"), 6 * 1024**3),
            (("resources", "headroom_bytes"), 2 * 1024**3),
            (("resources", "limits_mib", "spark"), 4096),
            (("resources", "baseline_minutes"), 5),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_headroom_minimum_is_independent_of_manifest_declaration(self):
        for actual_mib in [0, 1024, 1535]:
            for declared_mib in [0, actual_mib, 1536]:
                with self.subTest(actual_mib=actual_mib, declared_mib=declared_mib):
                    plan = deepcopy(self.plan)
                    resources = plan["resources"]
                    resources["headroom_bytes"] = actual_mib * 1024**2
                    resources["docker_allocation_bytes"] = (
                        resources["total_limit_bytes"] + resources["headroom_bytes"]
                    )
                    resources["minimum_headroom_mib"] = declared_mib
                    errors = CHECKS.validate(plan)
                    self.assertNotIn("headroom arithmetic mismatch", errors)
                    self.assertIn(
                        "insufficient Docker headroom: independent 1536 MiB minimum", errors
                    )
        self.assertIn(
            "declared headroom floor cannot be lowered below 1536 MiB",
            CHECKS.validate(self.changed(("resources", "minimum_headroom_mib"), 0)),
        )
        boundary = deepcopy(self.plan)
        boundary["resources"]["headroom_bytes"] = 1536 * 1024**2
        boundary["resources"]["docker_allocation_bytes"] = (
            boundary["resources"]["total_limit_bytes"] + 1536 * 1024**2
        )
        self.assertEqual(CHECKS.validate(boundary), [])

    def test_rejects_unsafe_storage_and_transport_claims(self):
        for path, value in [
            (("safety", "max_spark_drivers_per_table_checkpoint"), 2),
            (("safety", "seaweed_persistent_root"), "/data/chunks"),
            (("safety", "seaweed_persisted_state"), ["volume"]),
            (("safety", "published_bind_address"), "0.0.0.0"),
            (("safety", "dedicated_network"), False),
            (("safety", "authentication_required"), False),
            (("safety", "unauthenticated_probe_expected"), "allow"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_archive_inspection_is_bound_to_pin_and_not_runtime_proof(self):
        for path, value in [
            (("archive_inspection", "archive_digest"), "sha256:" + "0" * 64),
            (("archive_inspection", "artifact"), "pyspark-4.0.0.tar.gz"),
            (("archive_inspection", "status"), "runtime_accepted"),
            (("archive_inspection", "runtime_verification"), "passed"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))

    def test_cannot_promote_metadata_to_execution_evidence(self):
        for path, value in [
            (("runtime_verification",), "passed"),
            (("b01_gate",), "complete"),
            (("resources", "measurement_status"), "passed"),
            (("dependency_lock_scope",), "fully_resolved_build"),
        ]:
            with self.subTest(path=path):
                self.assertTrue(CHECKS.validate(self.changed(path, value)))


if __name__ == "__main__":
    unittest.main()
