# PulseCart

A local-first, production-oriented streaming commerce lakehouse: durable commerce transactions, real-time activity processing, Delta Lake analytics, and explainable flash deals.

**Current scope:** development foundation only. No application services or data infrastructure are implemented yet. Planning documents and agent handoffs are intentionally private and are not included in this repository.

## Prerequisites and checks

- Python **3.12** (`python3.12`), Git, and Make.
- Docker Desktop will be required for infrastructure stages, not foundation checks.

```sh
make check
# Equivalent without Make:
python3.12 scripts/check_foundation.py
```

Foundation checks run standard-library unit tests, parse Python source for syntax errors, and reject tracked private planning/local-secret paths. They require no installed Python dependencies. This is a path-policy check, not a comprehensive secret scanner.

There is no application startup command yet. Checks on a clean clone do not require private planning files. CI is configured to run the same foundation command on pushes and pull requests; an actual CI result is pending the first code push.

## Progress

| Stage | Code | Verification | Status |
|---|---|---|---|
| S00 Development foundation | Local setup implemented | Local checks passed; commit and GitHub CI pending | In progress |
| S01 Local platform feasibility | Not started | Not run | Planned |
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

## Limits

No throughput, recovery, availability, cloud compatibility, or 8 GB full-stack fit has been demonstrated. CI currently verifies only the foundation; application, integration, browser, and failure suites will be added alongside their implementations.
