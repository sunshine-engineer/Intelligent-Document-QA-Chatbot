<!--
File: docs/project-consistency-review.md
Purpose: Record the focused project consistency refactor and its validation boundary.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Project-wide consistency review

## Scope

Runtime baseline: `8824d96` on `main`. Branch: `CXOED/project-consistency-handover`.
The uncommitted handover-documentation work from 22 October was preserved and
included in this focused change; the earlier PR #45 is already merged.

## Changes

- Added format-compatible file path/purpose/maintainer/date metadata to maintained
  text sources, public configuration, scripts, tests and guides. The default
  maintainer comes from the user's instruction; original authorship is not inferred.
- Added purpose, parameter, return/yield and relevant exception documentation for
  every explicit Python class/callable, including nested helpers and test fixtures.
- Kept the small flat runtime module layout; moved Streamlit execution into main(),
  organized imports with Ruff and formatted Python with Black.
- Renamed root `readme.md` to `README.md`, added the directory map, and moved dated
  review/fix reports to `docs/history/`. Updated relative links and added conventions.
- Exposed provider base URL, timeout/retry/output limits, UI/history/context limits
  and log retention through validated settings, preserving the previous defaults.
- Added nonsecret example entries, updated configuration/operations guidance, and
  gave the live connectivity smoke configurable endpoint/timeout settings.
- Declared Pydantic directly because runtime composition already imports SecretStr.
  The uv-generated lock change records that dependency without upgrading packages.
- Added editor/Git whitespace conventions, Ruff import/docstring rules and a CI
  consistency checker requiring source docs, valid metadata and a complete inventory.

## File-type boundaries

[File inventory](file-inventory.md) records every nonignored project file. JSON
stays strict JSON with no fabricated comment keys. PNG/PDF bytes and LICENSE text
are unchanged. The generated uv lock is edited only by uv for the manifest change.
No PDF authors, distribution permissions, contacts or deployed ownership are invented.
Historical evidence retains its original dates/meaning and is visibly historical.

Adjustable deployment parameters belong in Settings/environment or Compose.
Schema/file names, protocol invariants and synthetic test inputs remain legitimate
constants. No new retrieval technique, endpoint, database workflow, authentication,
upload feature or cloud deployment is part of this PR.

## Validation

- Frozen Python 3.12.14 environment synchronized and lock freshness checked.
- Complete suite: **67 passed**, **87.76% core coverage**, including default/custom
  client limits, UI caps, log retention and audit failure cases.
- Black: 26 modules unchanged by check; Ruff import/docstring/error checks passed.
- MyPy: no issues in all eight configured core source files.
- Consistency inventory: 67 project files, 26 Python modules, 36 classes and 171
  explicit functions/methods with no missing docstrings or parameter documentation.
- Internal documentation: 65 local file targets and 17 Bash blocks checked;
  all 23 application environment settings are documented and example settings validate.
- Default synthetic v2 evaluation passes all five metric thresholds at 1.0.
- Provider-free Streamlit application/server smoke passed locally.
- Both canonical and combined development Compose configurations validated.
- PDF/PNG and LICENSE bytes match baseline; strict JSON data, theme/CSS semantics,
  Compose data and existing effective shell/image/ignore instructions are preserved.
- The executable AST of index metadata, query services, index runtime/services and
  error utilities matches baseline after removing docstrings/import organization.
- Lock comparison confirms no package version upgrades; direct Pydantic metadata
  is the only regenerated dependency change.
- Docker production image built on Python 3.12.8; the provider-free AppTest/server
  smoke passed inside the image without host mounts or external network access.

Provider-free test results do not establish live-provider answer quality.
Real Groq/Ollama corpus evaluation, semantic claim support, actual editor lifecycle,
PDF permissions and recipient operational acceptance remain separate open items.

## Continuation after the validation interruption

The project files were preserved when temporary tooling was cleared. Python
3.12.14 and uv 0.12.5 were restored for final checks before publication. The Docker
build and isolated smoke above completed before the interruption. They could not
be repeated in the resumed environment because Docker Desktop WSL integration
was unavailable; this is an environment limitation, not a new passing Docker run.
