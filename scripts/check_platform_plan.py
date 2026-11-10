"""Offline consistency checks for the S01 candidate plan, not a runtime probe."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "infra" / "candidate-lock.json"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
MINIMUM_HEADROOM_MIB = 1536


def validate(plan: dict) -> list[str]:
    """Return constraint violations; never treat metadata as execution evidence."""
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(plan["schema_version"] == 1, "unsupported schema")
    require(plan["status"] == "partial_metadata_verified_blocked", "partial blocked status required")
    require(plan["runtime_verification"] == "not_run", "runtime evidence absent")
    require(plan["b01_gate"] == "blocked_effective_classpath_and_execution", "B01 classpath/execution gate must remain open")
    images = plan["images"]
    require(set(images) == {"python", "postgres", "redpanda", "seaweedfs"}, "image set differs")
    for name, image in images.items():
        require(image["verification"] == "registry_metadata_only", f"{name}: metadata only")
        require(bool(DIGEST.fullmatch(image["index_digest"])), f"{name}: invalid index digest")
        require(bool(DIGEST.fullmatch(image["arm64_digest"])), f"{name}: invalid ARM digest")
        require(image["index_digest"] != image["arm64_digest"], f"{name}: index is not child manifest")
        require(image["platform"] == "linux/arm64", f"{name}: native ARM required")
        require(image["reference"].endswith(":" + image["tag"]), f"{name}: tag mismatch")
        require(image["pinned_reference"] == image["reference"] + "@" + image["index_digest"], f"{name}: mutable reference")
        require(image["metadata_url"].startswith("https://"), f"{name}: source missing")
        require(bool(image["license"]), f"{name}: license missing")

    runtime = plan["runtime"]
    require(runtime["python_series"] == "3.12", "Python foundation requires 3.12")
    require(images["python"]["tag"].startswith(runtime["python_version"] + "-"), "Python artifact mismatch")
    require(runtime["java_major"] == 17, "Spark 4 requires selected Java 17")
    jdk = runtime["jdk"]
    require(jdk["name"] == "Temurin", "selected JDK distribution mismatch")
    require(jdk["platform"] == "linux/aarch64", "JDK must target native Linux AArch64")
    version = re.fullmatch(r"(\d+)\.\d+\.\d+\+\d+", jdk["version"])
    require(version is not None, "invalid JDK release version")
    require(jdk["version"] == "17.0.21+9", "re-review Temurin release before upgrade")
    if version is not None:
        require(int(version[1]) == runtime["java_major"], "JDK artifact Java major mismatch")
        filename = (
            f"OpenJDK{version[1]}U-jdk_aarch64_linux_hotspot_"
            f"{jdk['version'].replace('+', '_')}.tar.gz"
        )
        release = jdk["version"].replace("+", "%2B")
        url = (
            f"https://github.com/adoptium/temurin{version[1]}-binaries/"
            f"releases/download/jdk-{release}/{filename}"
        )
        require(jdk["filename"] == filename, "JDK filename does not match release/platform")
        require(jdk["url"] == url, "JDK URL does not match canonical release artifact")
    require(runtime["scala_binary"] == "2.13", "Spark 4 requires Scala 2.13 artifacts")
    require(runtime["spark_version"].startswith("4.0."), "Delta 4.0 requires Spark 4.0.x")
    require(runtime["delta_version"].startswith("4.0."), "selected Delta family mismatch")
    require(runtime["hadoop_version"] == "3.4.1", "must match Spark v4.0.3 POM")
    sdk = plan["sdk_review"]
    require(sdk["hadoop_managed_bundle_version"] == "2.24.6", "Hadoop POM declaration drift")
    require(sdk["spark_declared_sdk_v2_version"] == "2.25.53", "Spark POM declaration drift")
    require(sdk["status"] == "unresolved_effective_classpath", "classpath blocker unresolved")
    require(sdk["selected_bundle_version"] is None, "no SDK approved or selected")
    require(sdk["accepted"] is False, "unverified SDK must not be accepted")
    require(sdk["effective_classpath_verified"] is False, "effective classpath not inspected")
    require(sdk["compatibility_tested"] is False, "compatibility not executed")
    require(len(sdk["declarations"]) == 4, "dependency declaration contexts missing")
    for declaration in sdk["declarations"]:
        require(declaration["source_url"].startswith("https://"), "SDK primary source missing")
        require(bool(declaration["context"]), "SDK dependency context missing")
    require(runtime["spark_version"] == "4.0.3", "re-review tagged Spark POM before upgrade")
    require(runtime["delta_version"] == "4.0.1", "re-review Delta release before upgrade")
    packages = {package["name"]: package for package in plan["python_artifacts"]}
    require(len(packages) == len(plan["python_artifacts"]), "duplicate Python packages")
    require(set(packages) == {"pyspark", "delta-spark", "py4j", "importlib-metadata", "zipp"}, "selected Python dependency set differs")
    for name, version in [("pyspark", runtime["spark_version"]), ("delta-spark", runtime["delta_version"]), ("py4j", "0.10.9.9"), ("importlib-metadata", "8.7.0"), ("zipp", "3.23.0")]:
        require(packages.get(name, {}).get("version") == version, f"{name}: version mismatch")
    for artifact in [*plan["python_artifacts"], runtime["jdk"]]:
        require(bool(DIGEST.fullmatch(artifact["digest"])), f"{artifact['name']}: invalid published checksum")
        require(artifact["url"].startswith("https://"), f"{artifact['name']}: source missing")
    inspection = plan["archive_inspection"]
    require(inspection["archive_digest"] == packages["pyspark"]["digest"], "archive evidence must match pinned PySpark")
    require(inspection["artifact"] == packages["pyspark"]["filename"], "archive evidence filename mismatch")
    require(inspection["status"] == "archive_inspected_not_executed", "archive inspection is not runtime proof")
    require(inspection["runtime_verification"] == "not_run", "archive inspection cannot verify runtime")
    expected = {
        "io.delta:delta-spark_2.13": runtime["delta_version"],
        "io.delta:delta-storage": runtime["delta_version"],
        "org.apache.hadoop:hadoop-aws": runtime["hadoop_version"],
        "software.amazon.awssdk:bundle": sdk["hadoop_managed_bundle_version"],
    }
    maven = {item["coordinate"]: item["version"] for item in plan["maven_artifacts"]}
    require(len(maven) == len(plan["maven_artifacts"]), "duplicate Maven artifacts")
    require(maven == expected, "Maven coordinates must match Spark/Delta/Hadoop; no SDK v1")
    for artifact in plan["maven_artifacts"]:
        expected_status = (
            "hadoop_managed_metadata_candidate_not_selected"
            if artifact["coordinate"] == "software.amazon.awssdk:bundle"
            else "metadata_candidate_not_executed"
        )
        require(artifact["status"] == expected_status, "Maven metadata is not approved execution evidence")
        require(bool(re.fullmatch(r"[0-9a-f]{40}", artifact["published_sha1"])), "invalid Maven metadata checksum")
        require(artifact["sha256"] is None, "JAR content SHA256 not measured in this block")
        group, name = artifact["coordinate"].split(":")
        version = artifact["version"]
        url = (
            f"https://repo.maven.apache.org/maven2/{group.replace('.', '/')}/"
            f"{name}/{version}/{name}-{version}.jar"
        )
        require(artifact["url"] == url, "Maven URL does not match coordinate/version")
        require(artifact["checksum_url"] == url + ".sha1", "Maven checksum source mismatch")
    require(plan["dependency_lock_scope"] == "candidate_direct_artifacts_not_resolved_build", "do not claim resolved JVM lock")

    resources = plan["resources"]
    limits = resources["limits_mib"]
    require(limits == {"postgres": 512, "redpanda": 1536, "seaweedfs": 1024, "spark": 3072}, "review required for budget changes")
    total = sum(limits.values()) * 1024**2
    require(total == resources["total_limit_bytes"], "resource sum mismatch")
    headroom = resources["docker_allocation_bytes"] - total
    require(headroom == resources["headroom_bytes"], "headroom arithmetic mismatch")
    require(resources["minimum_headroom_mib"] >= MINIMUM_HEADROOM_MIB, "declared headroom floor cannot be lowered below 1536 MiB")
    require(headroom >= MINIMUM_HEADROOM_MIB * 1024**2, "insufficient Docker headroom: independent 1536 MiB minimum")
    require(headroom >= resources["minimum_headroom_mib"] * 1024**2, "insufficient Docker headroom for declared minimum")
    require(resources["baseline_minutes"] >= 30, "baseline must run at least 30 minutes")
    require(resources["measurement_status"] == "not_run", "no resource measurements yet")
    safety = plan["safety"]
    require(safety["max_spark_drivers_per_table_checkpoint"] == 1, "no multi-driver S3 Delta claim")
    require(safety["seaweed_persistent_root"] == "/data", "persist all Seaweed metadata and chunks")
    require(set(safety["seaweed_persisted_state"]) == {"master", "volume", "filer_leveldb"}, "missing persistent state")
    require(safety["transport"] == "isolated_local_http", "owner-approved local transport only")
    require(safety["published_bind_address"] == "127.0.0.1", "no public/LAN binding")
    require(safety["dedicated_network"] is True, "isolation required")
    require(safety["authentication_required"] is True, "auth must not be optional")
    require(safety["credential_policy"] == "disposable_local_uncommitted", "no real credentials")
    require(safety["unauthenticated_probe_expected"] == "deny", "fail-closed negative auth probe required")
    return errors


def main() -> int:
    try:
        errors = validate(json.loads(LOCK.read_text(encoding="utf-8")))
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"Invalid candidate plan: {error}")
        return 1
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print("Candidate plan consistent; runtime compatibility and resource probes NOT RUN.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
