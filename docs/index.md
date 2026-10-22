<!--
File: docs/index.md
Purpose: Documentation map.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Documentation map

Review date: 22 October 2026. Runtime baseline: `8824d96` on `main` (merged PR #45).
The 23 October consistency changes add configuration overrides and reorganize
documentation/source conventions while preserving the baseline defaults.
See [change record](project-consistency-review.md).

Start with [handover](handover.md) for a new maintainer, or the
[repository README](../README.md) for a quick start.

| Document | Classification | Purpose |
|---|---|---|
| [README](../README.md) | Current | Scope, setup, data flow, configuration summary, limits |
| [Handover](handover.md) | Current | Maintainer orientation, operating workflow, acceptance and open decisions |
| [Contributor conventions](contributing.md) | Current | File metadata, docstrings, formatting and configuration policy |
| [File inventory](file-inventory.md) | Current | Purpose and review disposition of every project-owned file |
| [Consistency review](project-consistency-review.md) | Current change record | Scope, validation and preserved-file boundaries |
| [Configuration reference](configuration.md) | Current | Application, Compose, development, and CI variables and precedence |
| [Container architecture](container-architecture.md) | Current | Services, mounts, image versus development environments |
| [Dependency management](dependency-management.md) | Current | Python/uv versions, frozen installs, deliberate dependency updates |
| [Local operations](local-operations.md) | Current | Diagnostics, document changes, backup/restore, reset and recovery |
| [Quality gates](quality-gates.md) | Current | Exact CI commands, evaluation definitions and live-check setup |
| [Prototype demonstration](prototype-demo.md) | Current checklist; live execution outstanding | Manual acceptance and interview rehearsal |
| [Portfolio fix status](history/portfolio-fix-status.md) | Historical execution evidence plus known gaps | Original review IDs, fixes and limits of the 21 October checks |
| [Readiness review](history/portfolio-readiness-review.md) | Historical | Findings against pre-fix commit `9e0947c`; not a current defect list |
| [Sample document notes](../research_papers/README.md) | Current unresolved provenance record | Code license does not cover bundled PDF rights |
| [Code license](../LICENSE) | Current | MIT terms for project code |
| [FastAPI backlog](fastapi-backend-v1-github-backlog.md) | Future proposal, not implemented | Optional backend/worker/database expansion |
| [GCP plan](gcp-production-style-deployment-v1-plan.md) | Future proposal, not implemented | Optional cloud infrastructure and operations expansion |
| [Documentation audit](documentation-audit.md) | Current review record | Corrections, verification scope and remaining sign-off conditions |

A guide marked current describes inspected repository behavior, not evidence of
successful live-provider operation. No document establishes production readiness.
