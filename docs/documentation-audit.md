<!--
File: docs/documentation-audit.md
Purpose: Documentation handover audit.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Documentation handover audit

Review date: 22 October 2026. Runtime baseline: `8824d96` on remote `main`.
PR #45 was verified merged; its `quality` job was successful and its optional
live-provider job was skipped. This audit changes documentation and `.env.sample`
comments only. It does not add application features or claim a new release.

This is the historical 22 October documentation audit. The subsequent
[project consistency review](project-consistency-review.md) covers source
headers/docstrings, configurable limits and the current layout. Its results
supersede this audit where the later change modifies a documented contract.

## Conclusion

The previous documentation was not fully current or sufficient as a complete
handover pack. The corrections below make it suitable for maintainer orientation
and provider-free reproduction. Operational handover remains conditional on a
recipient completing live QA, permissions, restore rehearsal and ownership details.

## Coverage and corrections

| Area | Finding / correction | Current location |
|---|---|---|
| Entry point | Added one reading path and current/historical/proposed classification | `docs/index.md`, `docs/handover.md`, README |
| Version/release context | Recorded exact runtime commit and verified PR merge; no deployed release assumed | Handover scope |
| Current architecture | Corrected the outdated claim that Dev Container only adds a bind mount; it also changes PATH/environment target and synchronizes workspace dependencies | Container architecture |
| Setup | Added Bash/WSL and working-directory assumptions, non-overwriting `.env` creation, first-run/init status, and recipient acceptance | README, handover |
| Configuration | Covered all eleven application variables, eight interpolated Compose variables, CI values, fixed request limits, defaults and precedence | Configuration reference |
| Persistence | Distinguished Compose/native index paths, legacy metadata, session chat, model volumes, logs and credentials | Operations and configuration |
| Recovery | Added model-change handling, empty/missing-corpus behavior, restart/recreate distinction, troubleshooting and reset boundaries | Operations |
| Backup/restore | Added corpus-only backup, private credential handling, staged restore and recipient rehearsal requirement | Operations |
| Developer maintenance | Corrected the claim that `--frozen` checks lock freshness; added `uv lock --check`, pinned runtime context and environment-qualified commands | Dependency management |
| CI and evaluation | Added missing smoke command, exact commands, metric denominators, v2 fixture and artifact retrieval; explained live smoke configuration and limits | Quality gates |
| Evidence quality | Marked prior check results as historical, retained pre-fix findings without rewriting history, and added acceptance record | Fix status, historical review, demo |
| Future plans | Explicitly marked FastAPI and GCP as proposals with no implementation/operations proof or audited issue inventory | Respective planning documents |
| Access and responsibilities | Added an explicit unassigned ownership/account/backup/acceptance table rather than inventing contacts | Handover |
| Licensing/privacy | Rechecked MIT code license and unresolved PDF provenance note; clarified external Groq data flow and trusted-index scope | LICENSE, README, sample document notes |

## Fresh verification

- Inspected all repository Markdown guides plus LICENSE and the relevant runtime,
  configuration, Compose, Dockerfile, Dev Container, scripts and workflow files.
- Checked internal Markdown file targets and Bash-block syntax. External URLs were
  not availability-tested; shell syntax checks do not execute operational steps.
- Checked documented application/Compose variable coverage against source.
- Parsed Dev Container JSON and both Compose files structurally.
- `uv lock --check --offline` passed with uv 0.12.5 and the cached project dependencies.
- Pytest on Python 3.12.14: **57 passed**, **86.92% core coverage**. One dependency
  deprecation warning was emitted for the existing LangChain community integration;
  dependency migration is outside this documentation-only change.
- Default v2 offline evaluation passed all five thresholds at 1.0. This remains
  keyword/fake-generation fixture evidence, not live QA quality.
- Provider-free Streamlit AppTest/server smoke passed with temporary localhost access.
- Evaluation CLI help and uv flags were checked against the installed commands.
- `git diff --check` passed.

Fresh Docker Compose CLI/runtime validation could not be completed: the host
`/usr/bin/docker` invocation returned an input/output error. The Compose files
were structurally parsed; the image/Compose successes from 21 October remain
historical evidence, not a fresh Docker test. Application/Compose behavior was
not changed in this documentation review.

## Outstanding acceptance conditions

| Item | Why it remains open |
|---|---|
| Live PDF -> Ollama embeddings -> FAISS -> Groq answer workflow | Not executed in this review; recipient/account-specific setup still needed |
| Real-corpus faithfulness, refusals and latency | Synthetic tests cannot establish these results |
| PDF provenance/sharing permission | Not established for the bundled files; use appropriately permitted documents |
| Named maintainer, support contact and account ownership | Human assignments were not supplied |
| Private backup location, retention and restore evidence | Procedures are documented; no restore rehearsal or managed backup configured |
| Actual VS Code Dev Container lifecycle | Configuration review alone is insufficient |
| Branch access/rules, provider quota and public deployment | Not audited/configured; current scope is a controlled local prototype |

No unconditional operational sign-off is given. Complete the acceptance table in
`docs/prototype-demo.md` and responsibilities in `docs/handover.md` before recording
recipient acceptance. Documentation should be reviewed again after code, config,
provider-model, dependency, or deployment changes.
