# PulseCart

A local-first, production-oriented streaming commerce lakehouse: durable commerce transactions, real-time activity processing, Delta Lake analytics, and explainable flash deals.

**Current scope:** development foundation plus a partial local-platform artifact/resource plan. No application services or data infrastructure are implemented yet. Internal backlog documents and agent handoffs remain private; the artifact/resource plan is public.

## Prerequisites and checks

- Python **3.12** (`python3.12`), Git, and Make.
- Docker Desktop will be required for infrastructure stages, not foundation checks.

```sh
make check
# Equivalent without Make:
python3.12 scripts/check_foundation.py
```

Checks run standard-library foundation and candidate-plan unit tests, parse Python source for syntax errors, and reject tracked private planning/local-secret paths. They require no installed Python dependencies. This is a path-policy check, not a comprehensive secret scanner.

There is no application startup command yet. Checks on a clean clone do not require private planning files. CI runs the same foundation command on pushes and pull requests. The [initial foundation run passed](https://github.com/PranavKuramkoteSudhir/Ecommerce-analysis/actions/runs/42556841872).

## Progress

| Stage | Code | Verification | Status |
|---|---|---|---|
| S00 Development foundation | Committed and pushed | Six unit tests, public-only reproduction, and GitHub CI passed | Complete |
| S01 Local platform feasibility | Partial artifact/resource plan; no services | Registry/release metadata checked; pinned PySpark archive inspected; runtime/classpath/resource probes not run | B01 blocked; see [candidate plan](docs/platform-plan.md) |
| S02 Account lifecycle | Not started | Not run | Planned |
| S03 Safe commerce transactions | Not started | Not run | Planned |
| S04 Activity ingestion and bronze | Not started | Not run | Planned |
| S05 Silver and customer enrichment | Not started | Not run | Planned |
| S06 Gold analytics and serving | Not started | Not run | Planned |
| S07 Flash-deal feedback loop | Not started | Not run | Planned |
| S08 Interactive demonstration | Not started | Not run | Planned |
| S09 Orchestration and repair | Not started | Not run | Planned |
| S10 Reliability and scale evidence | Not started | Not run | Planned |
| S11 Release and migration readiness | Not started | Not run | Planned |

## Local platform planning

The [public candidate plan](docs/platform-plan.md) and
[machine-readable candidate lock](infra/candidate-lock.json) record exact ARM64
artifact metadata, a proposed 6 GiB service envelope and the approved isolated,
authenticated local-HTTP boundary. They are **not a runnable or accepted platform**.
B01 remains blocked: Spark and Hadoop declare different AWS SDK versions in
different dependency contexts; the effective classpath and compatibility are
unverified, and **no SDK is selected or approved**. Offline tests enforce this
blocked status, not runtime success. No images were pulled or built and no
services started. The pinned PySpark archive's SHA-256 was verified and 319 JAR
names inventoried without installation or Java execution. Bootstrap details and
30-minute resource measurements remain
pending. Optional offline check: `python3.12 scripts/check_platform_plan.py`.

## Limits

No throughput, recovery, availability, cloud compatibility, or 8 GB full-stack fit has been demonstrated. CI is configured to run the offline checks; only the linked S00 run has been observed. New plan CI has not been observed. Application, integration, browser, and failure suites will be added alongside their implementations.
