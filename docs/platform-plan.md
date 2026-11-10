# S01 local platform: candidate compatibility and resource plan

## Status and scope

**Partial metadata evidence verified; B01 BLOCKED on unresolved effective SDK
classpath and unexecuted compatibility tests. No SDK selected or approved.**
This is a candidate plan, not a working platform or a claim of measured
compatibility. No services, Compose file, image build, dependency
installation, or startup command are provided by this block. The
[machine-readable candidate lock](../infra/candidate-lock.json) records exact
upstream artifact identities, sources, constraints and limits. It is not an
installed environment lock: Maven's full transitive closure, base-image package
inventory and final built image digest still need capture in the implementation
block. Do not install or deploy from a mutable tag instead of its recorded digest.

Evidence was checked on **2026-11-10 UTC**. Registry index manifests and their
Linux ARM64 child manifests were inspected read-only, not image layers pulled.
After the validator fixes passed 18 tests, the owner separately approved bounded
download/inspection of the pinned PySpark archive. That inspection is recorded
below; it is not installation or runtime execution.
Registry existence, upstream compatibility documentation and a passing offline
consistency test do **not** establish runtime behavior, provenance signatures,
absence of vulnerabilities, or vendor support for this exact combination.
Patches were selected as candidates, not claimed to be the newest releases.
Future updates require fresh metadata, compatibility and execution evidence.

## Candidate matrix

| Component | Exact candidate | Compatibility / distribution / license review |
|---|---|---|
| Python runtime image | `python:3.12.16-slim-bookworm` | Official image; native `linux/arm64/v8`; Python PSF license, Debian packages carry their own licenses. Host checks remain Python 3.12.15, not this image. |
| JDK | Eclipse Temurin **17.0.21+9**, Linux AArch64 HotSpot JDK | Java 17 selected for Spark 4; glibc-based Linux distribution for Debian Bookworm, not macOS or x86. OpenJDK GPLv2 with Classpath Exception; audit bundled notices when building. |
| Spark / Python bridge | `pyspark==4.0.3`, `py4j==0.10.9.9` | Spark 4.0.3 supports Java 17/21, Python 3.9+, Scala **2.13**. Apache-2.0 / BSD-3-Clause respectively. Native dependencies still need ARM runtime verification. |
| Delta | `delta-spark==4.0.1`; JVM `io.delta:delta-spark_2.13:4.0.1`, `io.delta:delta-storage:4.0.1` | Delta 4.0.x supports Spark 4.0.x. Apache-2.0. The Python package alone does not provide the needed JVM artifacts. Do not use `_2.12` or an unqualified latest JVM version. |
| S3A / SDK review **BLOCKED** | `org.apache.hadoop:hadoop-aws:3.4.1`; Hadoop-managed bundle candidate **2.24.6**, versus Spark-declared SDK v2 **2.25.53** | Apache-2.0. These are distinct upstream declarations, **not an approved runtime selection**. Effective bundled/resolved classpath is unknown. Do not mix Hadoop releases, SDK v1 or duplicate SDK bundles; see blocker below. |
| PostgreSQL | `postgres:17.11-bookworm` | Official image, native Linux ARM64; PostgreSQL License plus base-image licenses. Single-instance persistent database, not HA. |
| Broker | `docker.redpanda.com/redpandadata/redpanda:v26.2.6` | Native Linux ARM64 manifest. Redpanda Community is source-available BSL 1.1, **not OSI open source**; commercial/enterprise feature terms are separate. Kafka compatibility is not proof of every Kafka API or entitlement. |
| Object store | `chrislusf/seaweedfs:4.53` | Owner-selected SeaweedFS with S3 enabled; native Linux ARM64 manifest; Apache-2.0 community project. S3 compatibility is not AWS S3 parity or proof of Delta semantics. Garage is only a fallback if a material blocker is demonstrated, not a parallel implementation. |

Maintenance signals were checked, not assumed from a tag: PostgreSQL 17 is
supported through 2029-11-08 ([versioning policy](https://www.postgresql.org/support/versioning/));
Redpanda's 26.2 release documentation lists EOL 2027-07-28; SeaweedFS 4.53 is a
stable release published 2026-11-08 from an active project, with no fixed LTS/EOL
promise established here. Redpanda licensing evidence is its official current
licensing documentation/linked BSL text, not a verified exact-image license
inventory. Final image SBOM/license/notice and vulnerability review remain pending.

The lock carries both the multi-platform **index digest** (tag identity) and the
native **ARM64 child digest**. They are not interchangeable. Use the index pin
with an explicit `linux/arm64` platform, or the recorded child pin when building
that platform only. Digests prevent tag drift, not security defects. No emulation
or AMD64 acceptance is assumed. Runtime versions, image labels and executables
must be checked inside the eventual containers before promoting a candidate.

### Unresolved effective-classpath blocker (B01 remains blocked)

The primary sources establish different dependency contexts:

1. [Spark v4.0.3 root POM](https://raw.githubusercontent.com/apache/spark/v4.0.3/pom.xml)
   declares `hadoop.version=3.4.1`, `scala.version=2.13.16`,
   `scala.binary.version=2.13` and **`aws.java.sdk.v2.version=2.25.53`**.
   A root property alone does **not** establish which JARs are bundled or loaded.
2. [Spark v4.0.3 `hadoop-cloud/pom.xml`](https://raw.githubusercontent.com/apache/spark/v4.0.3/hadoop-cloud/pom.xml)
   declares `hadoop-aws` at `${hadoop.version}` with `${hadoop.deps.scope}` and a
   direct `software.amazon.awssdk:bundle` dependency at
   `${aws.java.sdk.v2.version}`, excluding its transitive dependencies. Whether
   this module/artifact is included in the eventual PySpark container, and which
   versions win dependency resolution/class loading, has **not** been inspected.
3. [Hadoop 3.4.1 dependency management](https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-project/3.4.1/hadoop-project-3.4.1.pom)
   declares **`aws-java-sdk-v2.version=2.24.6`**, managing
   `software.amazon.awssdk:bundle` at that version with wildcard exclusions.
   [The published `hadoop-aws:3.4.1` POM](https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.pom)
   lists that bundle as a **compile** dependency with no local version; Hadoop's
   dependency management supplies it.

Consequently **2.24.6 is recorded only as Hadoop-managed metadata**, not as the
selected Spark runtime SDK; **2.25.53 is separately recorded as Spark-declared**,
not automatically selected instead. This is an unresolved version-context
conflict, not proof of a loaded duplicate or demonstrated runtime incompatibility.
[Hadoop's S3A troubleshooting guidance](https://hadoop.apache.org/docs/r3.4.1/hadoop-aws/tools/hadoop-aws/troubleshooting_s3a.html)
warns against arbitrary SDK/Hadoop substitutions and mixing SDK JARs with a bundle.

The machine-readable `sdk_review` records both declarations, `accepted=false`,
`selected_bundle_version=null`, and unverified/untested flags. Offline tests
reject promotion of either declaration to an accepted selection without new
evidence and a deliberate plan/test revision. These tests protect the current
**blocked** state; they do not weaken B01's compatibility acceptance condition.
Closing this blocker later requires actual bundled-JAR inventory, effective
dependency tree and class-loading review (including duplicates), then tested
ARM64 Spark/Delta/S3A behavior. The separately approved archive inspection below
narrows the bundled-JAR uncertainty for that archive only. No runtime resolution,
build, installation, Java execution or service start was performed.

### Dependency chain and storage semantics

The intended minimal compute runtime is one Python 3.12 Bookworm container plus
the pinned Temurin JDK and PySpark/Delta artifacts; this is a proposal, not an
existing Dockerfile. The tagged Spark POM, Hadoop dependency management and Delta
release metadata are the source of version alignment, rather than independent
"latest" selections. The candidate lock pins selected artifacts, not a complete
resolved pip/Maven build. Before any reproducible build claim, resolve and hash
all transitive artifacts, inspect duplicate JARs in PySpark's distribution and
record the resulting image digest. Avoid silently resolving different versions
through `--packages` at each startup.

The Python base metadata also requires `importlib-metadata>=1.0.0` for Delta,
even on Python 3.12. Candidate `importlib-metadata==8.7.0` and `zipp==3.23.0`
cover that declared chain without introducing optional extras; they are older
bounded candidates, not latest-version claims. PySpark's base requirement permits
`py4j>=0.10.9.7,<0.10.9.10`; candidate 0.10.9.9 satisfies it. No SQL/Connect/ML,
test or documentation packaging extras are selected. Python artifact SHA-256
values originate in PyPI metadata; **PySpark's recorded SHA-256 was subsequently
verified against downloaded bytes**, while the other Python/JDK artifact hashes
remain publisher metadata only. PySpark is an sdist:
build requirements/tooling still need a separate resolved lock. For the recorded
Maven candidates, SHA-256/SHA-512 sidecars returned 404; recorded published SHA-1
sidecars are only metadata references, **not strong integrity/provenance checks**.
No separate Maven JARs were downloaded; their missing content SHA-256 values
remain `null`, not invented hashes. Bundled Hadoop JARs were inspected in memory
from the PySpark archive, as recorded below. The SDK JAR entry is specifically
marked not selected.

Delta's published JVM POM uses Scala 2.13.13 and provided-scope Spark 4.0.1
artifacts; its documented Spark 4.0.x compatibility covers the candidate 4.0.3
family, but does not clear the independent SDK/classpath blocker.

Future S3A probe configuration must explicitly select the isolated HTTP endpoint,
path-style addressing, region and credentials; do not assume AWS defaults apply
to SeaweedFS. Exact endpoint/region, credential bootstrap mechanism and named
volumes remain implementation proposals. The single local Spark process must own
its Delta table and checkpoint exclusively: **one driver per writable
table/checkpoint**, with no concurrent writers, checkpoint sharing, automatic
checkpoint deletion, or cross-system exactly-once claim. S3A/Delta log-store
assumptions must be exercised on the chosen store, not inferred from its S3 API.
No multi-driver safety or Databricks/AWS compatibility is certified here.

SeaweedFS is planned as a **single `weed server` running master, volume, filer
and S3**. Persist **all `/data`**, including master state, volume chunks/indexes and
the filer's LevelDB namespace metadata. Retaining chunks alone can leave intact
bytes without a recoverable S3 namespace. Future bootstrap must explicitly place
filer metadata under the persistent root, inspect the effective configuration,
and prove restart behavior. The 4.53 image config selects `leveldb2` at
`/data/filerldb2`; its default command is `mini -dir=/data`, **not** the scoped
four-role server. Override that default with an explicit `server` command in the
future implementation; do not invent a `server -filer.dir` flag. Normal stop must
retain every persistent volume; reset must be separate, destructive, explicit
and warned. Restart persistence is not a backup/restore demonstration.

## Bounded PySpark archive evidence (2026-11-10)

Only the pinned `pyspark-4.0.3.tar.gz` binary distribution archive was downloaded:
**434,225,451 bytes**, with computed SHA-256
`9ed23e8601d73afae857eb5f9e11050b59cd11bbe50777564fcc4923cb117c1c`,
matching the lock. Seven primary-source POM responses added **285,303 bytes**;
combined transferred payload was **434,510,754 bytes**, below the conservative
**1 GiB cumulative** download cap. Scratch was limited independently to 1 GiB;
archive plus JSON reports occupied **434,277,945 bytes** at inspection close.
Free space was checked before transfer and throughout chunked download, hashing,
archive iteration and POM reads: the archive loop's minimum observed/reserved
free space was **358,667,268,096 bytes**, with **358,666,108,928 bytes** free at
POM-inspection close, both well above the required **2 GiB** floor. Disk guards
are **sampled checks, not an atomic filesystem quota**: concurrent host writers
can change free space between checks. This is disk inspection evidence, not the
pending service-memory/resource baseline.

Method: `scripts/inspect_pyspark_archive.py` verifies the recorded hash before
inspection, streams tar members, records all **319 JAR names**, and reads only
relevant JARs of at most 64 MiB into raw buffers for ZIP manifests/properties/
class-name inspection. **64 MiB bounds a raw JAR buffer, not aggregate process
memory**: ZIP/parser structures, member-name lists, decoded metadata and temporary
copies consume additional memory and have no aggregate cap here. It writes no
extracted archive/JAR files, rejects unsafe member paths and JAR links, and performs
no installation or execution. Report publication uses an exclusive temporary file
inside scratch followed by atomic replacement of the destination entry; a report
symlink is replaced rather than followed, and failed writes/replacements clean up
the temporary file. The archive and
full inventory/POM reports remain ignored under `reports/runtime/`; public checks
use only synthetic in-memory fixtures and never download this archive.

| Observed archive member | SHA-256 of bundled JAR bytes | Finding |
|---|---|---|
| `hadoop-client-api-3.4.1.jar` | `a964d4daa054c9615bbafb4553efbb140fa7fb9ac6f358a24393f183a5703438` | Embedded Hadoop Maven properties identify 3.4.1, including shaded-in `hadoop-common`. |
| `hadoop-client-runtime-3.4.1.jar` | `f6a800a159f918670db533606d33560d6c13b7e13f14eda493280ae33b9eeb2f` | Filename identifies the client runtime; its manifest describes shaded Protobuf 1.3.0, **not** the Hadoop version, so do not infer Hadoop version from that manifest alone. |

The other Hadoop-named members are
`dropwizard-metrics-hadoop-metrics2-reporter-0.1.2.jar` and
`parquet-hadoop-1.15.2.jar`. **No JAR names for `hadoop-aws`, AWS SDK v1/v2,
`spark-hadoop-cloud`, `delta-spark` or `delta-storage` were present.** No duplicate
JAR basenames were found. The four Hadoop-related JARs scanned had no standard
AWS SDK v1/v2 or S3A filesystem class entries; this is **not** an exhaustive class
scan of all 319 JARs, proof against every shaded namespace, or class-loading proof.

Comparison with the primary POMs above (responses hashed in the ignored report):

- `hadoop-aws:3.4.1` declares provided Hadoop common/mapreduce artifacts, a compile
  SDK v2 bundle managed by Hadoop at **2.24.6**, and runtime
  `org.wildfly.openssl:wildfly-openssl` managed at **1.1.3.Final**. This runtime
  transitive dependency is not a resolved/approved addition yet; the candidate
  lock remains deliberately incomplete. Do not add a second standalone Hadoop
  common over the shaded client API simply because its name is absent.
- Spark's optional `hadoop-cloud` POM instead directly declares bundle **2.25.53**,
  WildFly OpenSSL **2.2.5.Final** and other cloud connectors. Its JAR is absent
  from this archive. Therefore the root property did **not** imply a bundled
  AWS SDK here. Adding that module later could introduce extra cloud dependencies
  and another SDK path; it is not proposed as a shortcut or silently selected.
- Delta's POM needs `delta-storage:4.0.1`, ANTLR **4.13.1** and Scala **2.13.13**;
  Spark 4.0.1 dependencies are provided. This archive already has
  `antlr4-runtime-4.13.1.jar` and `scala-library-2.13.16.jar`. Do not blindly add
  another ANTLR/Scala/Spark runtime. Delta storage's Hadoop common/AWS **3.4.0**
  dependencies are **provided**, not an instruction to download a second Hadoop
  release. Exact resolved/scoped dependencies still need review and testing.

Thus the minimal **investigation set**, not an approved install recipe, is the
missing Delta artifacts, Hadoop AWS 3.4.1, its reviewed runtime dependencies and
one yet-unselected SDK path. The observed archive has no named SDK duplicate,
but future additions/resolution/class loading can still introduce conflicts.
**No SDK selected or approved; B01 remains BLOCKED.** No Java/class loading, S3A,
Delta, checkpoint restart or auth/persistence runtime probe was executed.

## Approved local security boundary; bootstrap still pending

The owner approved this narrow S01 policy: **authenticated, isolated local HTTP
on a dedicated Docker network**, with **every published port bound only to
`127.0.0.1`**, mandatory authentication and **disposable, uncommitted local
credentials**. TLS is not required for these local probes. No public/LAN binding,
real credentials, or unauthenticated operation is approved. This exception does
not establish production transport policy. Prefer keeping internal/admin ports
unpublished; audit any host mappings and broker advertised addresses.

SeaweedFS S3 without an identity configuration defaults to allow-all. Thus an
open endpoint returning success is a **failure**, not readiness evidence. Future
probes must first prove absent/wrong credentials are denied and then prove the
configured identity can perform only the intended operations. Authentication
bootstrap for PostgreSQL, Redpanda and SeaweedFS, identity scope, secret-file
creation/permissions/rotation, bucket creation/idempotency and readiness ordering
remain proposals to validate during implementation. Never put generated or real
credentials in this lock, image layers, source, logs or public evidence. The
policy above does not approve an arbitrary admin identity or fail-open fallback.
The 4.53 implementation distinguishes missing config (possibly allow-all) from an
explicit empty identity config (deny-all); invalid/unreadable explicit config is
fatal. Future tests must cover those bootstrap paths too. PostgreSQL 17's data
volume belongs at `/var/lib/postgresql/data`; do not silently use `trust` auth,
and account for explicit shared-memory sizing. The broker log belongs at
`/var/lib/redpanda/data`.

## Resource envelope (proposed limits, not observed consumption)

Read-only host inspection: ARM64; Docker Engine **29.7.2**, Compose **v5.5.1**,
**10 CPUs**, Docker allocation **8,319,504,384 bytes = 7.748 GiB**. Host
`python3.12` is **3.12.15**, default `python3` is **3.15.2** and no host Java is
available. Host checks use `python3.12` explicitly. The allocation is not 8 GiB.

| Concurrent feasibility component | Hard memory envelope |
|---|---:|
| PostgreSQL | 512 MiB |
| Redpanda | 1,536 MiB |
| SeaweedFS (all four roles combined) | 1,024 MiB |
| Spark (driver, local execution, Python workers and JVM/native overhead combined) | 3,072 MiB |
| **Total** | **6,144 MiB = 6 GiB = 6,442,450,944 bytes** |
| **Unassigned Docker/OS/runtime headroom** | **1,877,053,440 bytes ≈ 1.748 GiB** |

The validator enforces an independent **1,536 MiB (1.5 GiB)** headroom floor;
lowering the manifest's declared minimum cannot bypass it. This is arithmetic, not proof that
Docker VM overhead/cache or a workload fits. Host macOS memory and free disk are
additional constraints, not included in this VM headroom. The envelope excludes
APIs, workers, Airflow, UI, monitoring and full commerce pipelines; do not silently
start them concurrently or extrapolate full-core fit.

Starting configuration proposals: bounded local Spark parallelism (for example
`local[2]`) and about 1 GiB JVM heap within its **total** 3 GiB container envelope;
a one-core development broker with bounded internal memory below its container
cap; small PostgreSQL connection/shared-buffer settings; minimal Seaweed volume
preallocation. Exact CLI flags, heap/off-heap split, CPU limits and volume growth
must be checked against these releases before implementation. In particular,
Redpanda development settings are not production sizing: production guidance is
at least two physical cores and 2 GB RAM/core. Its convenient `dev-container`
mode enables unsafe fsync bypass and write caching, so do not copy that mode
blindly or claim crash durability from an orderly restart. Safe fsync/write-cache
settings remain an explicit implementation review item. Avoid Enterprise-only
features: an automatic 30-day trial must not mask a license dependency. The
v26.2.6 container updates CA certificates; its Redpanda binaries are unchanged
from v26.2.5, so runtime version checks must account for that documented packaging
choice. Seaweed volume defaults/preallocation can consume unexpected disk; avoid
claiming that 1 GiB memory bounds disk usage. These budgets
may fail: report the failure and seek a plan revision rather than dropping a probe.

### Future 30-minute measurement and execution gates

No resource baseline or integration acceptance test was run in B01. After service
and Spark probe implementation, the declared simultaneous workload must run for
**at least 30 minutes** with PostgreSQL, broker, all Seaweed roles and bounded
Spark active. Record fixture size/rate, parallelism and profile, configured/effective
limits, idle/startup/steady peak and sampled per-container memory/CPU, Docker/host
headroom, volume/disk growth and available disk, OOM/restart counters, logs and
correctness invariants. Report measurement cadence and limitations (sampling can
miss peaks). Do not hide OOM by removing a required component or restarting it
without reconciliation.

| Gate | Current result / required next evidence |
|---|---|
| Artifact availability / ARM64 | **Passed, metadata only**: upstream release/PyPI metadata and native registry manifests recorded below/in lock. |
| Offline plan constraints | **PASSED**: `make check` (26 standard-library tests, syntax and tracked-path policy) and `python3.12 scripts/check_platform_plan.py`; no network, Docker or private plans required. Passing is not a runtime test. |
| Pinned PySpark archive inspection | **PASSED, inspection only**: SHA-256 matched; 319 JAR names inventoried under bounded download/scratch/free-disk guards. No class loading or runtime execution. |
| Exact runtime and connector combination | **BLOCKED / NOT RUN**: resolve the effective-classpath blocker before any SDK selection/compatibility acceptance; later verify actual ARM64 Java/Python/Spark/Delta/Hadoop/SDK classpath, authenticated S3A write/read, Delta exact rows/log and checkpoint restart. Root properties are not runtime evidence. |
| Persistence / isolation / negative authentication | **NOT RUN**: restart DB row, acknowledged broker log, S3 bytes/namespace, Delta table/checkpoint; absent/wrong credentials denied; inspect effective loopback bindings and isolated network. |
| Resource baseline / clean public reproduction | **NOT RUN**: 30-minute concurrent workload, resource/OOM/correctness evidence, ordinary stop versus explicit reset, clean-checkout run. |
| GitHub CI for this plan | **NOT OBSERVED**: do not inherit S00 CI success as evidence for new changes. |

Each service is a single point of failure on one machine. No SLA, HA, throughput,
recovery bound, independent backup restore or production-readiness claim follows
from this plan. A separate production topology would need database replication
and verified backups, broker quorum/replication, durable replicated object storage
and scheduled compute; it is not implemented or sized here.

## Evidence and reproduction of metadata checks

Registry checks used anonymous Registry V2 HTTPS GETs for tag/index and ARM64
child manifests (Python, PostgreSQL, SeaweedFS), with SHA-256 calculated over the
returned bytes and matched to registry header/descriptor digests. Redpanda direct
HTTP inspection hit a rate limit; Docker's read-only manifest inspector succeeded
for its tag and ARM64 child. **No layers were pulled and no services started.**
The lock records the observed digests; live metadata verification is deliberately
not part of `make check` (registries/tags/network can change).

For example, these are optional read-only checks, not platform startup commands:

```sh
docker buildx imagetools inspect chrislusf/seaweedfs:4.53
docker buildx imagetools inspect docker.redpanda.com/redpandadata/redpanda:v26.2.6
# Compare the reported index and linux/arm64 child against infra/candidate-lock.json.
python3.12 scripts/check_platform_plan.py
make check
```

Official evidence entry points (exact artifact URLs/checksums also in lock):

- [Python official image metadata](https://github.com/docker-library/official-images/blob/master/library/python), [PSF license](https://docs.python.org/3/license.html).
- [Adoptium release API](https://api.adoptium.net/v3/assets/version/17.0.21%2B9?architecture=aarch64&heap_size=normal&image_type=jdk&jvm_impl=hotspot&os=linux&vendor=eclipse).
- [PySpark 4.0.3 PyPI JSON](https://pypi.org/pypi/pyspark/4.0.3/json), [Delta 4.0.1 PyPI JSON](https://pypi.org/pypi/delta-spark/4.0.1/json), [Py4J](https://pypi.org/pypi/py4j/0.10.9.9/json), [importlib-metadata](https://pypi.org/pypi/importlib-metadata/8.7.0/json), [zipp](https://pypi.org/pypi/zipp/3.23.0/json).
- [Spark v4.0.3 tagged POM](https://github.com/apache/spark/blob/v4.0.3/pom.xml), [Spark 4.0.3 overview](https://spark.apache.org/docs/4.0.3/), [Delta compatibility table](https://docs.delta.io/releases/), [Delta 4.0.1 JVM POM](https://repo.maven.apache.org/maven2/io/delta/delta-spark_2.13/4.0.1/delta-spark_2.13-4.0.1.pom), [Delta storage POM](https://repo.maven.apache.org/maven2/io/delta/delta-storage/4.0.1/delta-storage-4.0.1.pom), [Hadoop-managed SDK candidate POM](https://repo.maven.apache.org/maven2/software/amazon/awssdk/bundle/2.24.6/bundle-2.24.6.pom).
- [Hadoop 3.4.1 AWS module POM](https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.pom), [Hadoop 3.4.1 dependency management](https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-project/3.4.1/hadoop-project-3.4.1.pom), [Hadoop S3A third-party stores](https://hadoop.apache.org/docs/r3.4.1/hadoop-aws/tools/hadoop-aws/third_party_stores.html).
- [PostgreSQL releases](https://www.postgresql.org/docs/release/), [official image](https://github.com/docker-library/postgres), [license](https://www.postgresql.org/about/licence/).
- [Redpanda release notes](https://docs.redpanda.com/streaming/current/reference/releases/redpanda/), [licensing overview](https://docs.redpanda.com/streaming/current/get-started/licensing/overview/), [BSL text](https://github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md), [development-mode flags](https://docs.redpanda.com/streaming/current/reference/rpk/rpk-redpanda/rpk-redpanda-start/).
- [SeaweedFS 4.53 release](https://github.com/seaweedfs/seaweedfs/releases/tag/4.53), [tagged server source](https://github.com/seaweedfs/seaweedfs/blob/4.53/weed/command/server.go), [S3 API](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API), [image filer config](https://github.com/seaweedfs/seaweedfs/blob/4.53/docker/filer.toml), [image Dockerfile](https://github.com/seaweedfs/seaweedfs/blob/4.53/docker/Dockerfile.go_build), [authentication implementation](https://github.com/seaweedfs/seaweedfs/blob/4.53/weed/s3api/auth_credentials.go), [license](https://github.com/seaweedfs/seaweedfs/blob/4.53/LICENSE).

Project tests check consistency and deliberately reject drift/unsafe claims.
Regression tests reject consistently recalculated but insufficient headroom,
including a lowered declared floor; actual JDK records with Java 11, x86 or
mismatched release filename/URL; and coordinated Maven JAR/sidecar URL changes
that no longer match the declared coordinates/version. The validator derives
canonical Temurin and HTTPS Maven artifact identities rather than trusting a
well-formed checksum or matching sidecar alone. These checks cannot attest
upstream contents or replace the pending execution gates.
