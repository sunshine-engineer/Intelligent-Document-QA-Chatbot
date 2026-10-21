# Portfolio review fix status

The original `PORTFOLIO_READINESS_REVIEW.md` is a historical review of commit
`9e0947c`. This file tracks the subsequent bug-fix change. Completed code changes
are distinct from live-provider quality and deployment evidence.

## Ordered bug fixes

| Review ID | Change | Regression evidence |
|---|---|---|
| B01 | Stable content identity excludes mutable processing status; unchanged session vectors are reused | Lifecycle tests cover repeated reruns, restart, and changed configuration |
| B02 | Exception logging retains type and correlation ID, omitting raw payload/traceback | Full emitted chained-exception log checked for synthetic secret/document/prompt markers |
| B03 | Real query composition expands contextual retrieval with bounded history | Real LangChain composition tested with a deterministic local runnable |
| B04 | Recall uses the fraction of expected source identities retrieved | One of two sources scores 0.5 |
| B05 | Evidence precision matches document/page pairs together | Swapped document/page pairs score 0; semantic claim support remains manual |
| B06 | Evaluation CLI exits nonzero when configured thresholds fail | Degraded fixture fails and still writes its result artifact |
| B07 | Snapshot records splitter revision and chunk settings; incompatible/legacy state rebuilds | Load rejects changed chunk settings; lifecycle rebuild tested |
| B08 | Every assistant message retains citations, timings, and download controls | Streamlit answer followed by slider rerun retains evidence and download |
| B09 | Automatic/manual refresh share a safe failure boundary | Streamlit manual refresh failure leaves no uncaught exception |
| B10 | Required public Streamlit assets are included in image context; CSS path is module-relative and optional | Image built and provider-free AppTest/server smoke passed inside the standalone image without host mounts |
| B11 | Dev Container PATH explicitly selects `/app/.venv/bin` | Configuration corrected; actual VS Code container startup remains unverified |
| B12 | Configuration validates before provider construction; discovery and initialization are guarded | Streamlit invalid settings/provider/discovery failure cases execute safely |

The UI also commits a conversation turn only after successful stream completion,
handles MAX_TOP_K=1, and disables queries while synchronization has failed. Empty
text is rejected before replacing saved index state. Generation/embedding timeouts
and generation retry/output limits are explicit.

## Other findings

| Review IDs | Status |
|---|---|
| F01 | Outstanding: real Groq/Ollama corpus evaluation and measured answer faithfulness |
| F02 | Partial: source-ID prompt contract and evidence labels added; automated semantic support verification is not implemented |
| F03 | Improved: real Streamlit sessions, real FAISS round-trip/search, and standalone container smoke tests; live-provider document-to-answer E2E remains outstanding |
| F04 | Partial: empty-text guard and documented text-PDF limit; upload validation, resource limits, per-file isolation, and OCR remain outstanding |
| F05 | Partial: system instruction boundary and character caps added; tokenizer budgets and adversarial evaluation remain outstanding |
| F06 | Explicit deadlines/retry/output limits and rate-limit guidance added; provider failure behavior still needs live validation |
| F07 | Fixed-corpus demo workflow documented; upload UI/document viewer deferred |
| F08 | Unchanged session vectors reused and discovery duplication removed; full-corpus rebuilds remain intentional |
| F09–F12 | Deferred optional/conditional work: concurrency, durable/API/backend workflow, public hosting controls, advanced retrieval |
| D01 | Corrected metric definitions and clarification denominators; expected synthetic retrieval MRR is now 1.0 |
| D02–D04 | Setup commands, demo checklist, model/UI wording corrected; historical screenshots labeled and missing GIF claim removed |
| D05 | External data flow and trusted-pickle boundary documented |
| D06 | MIT code license added; bundled PDF provenance/redistribution permission explicitly remains unresolved |
| D07 | Local recovery/reset guide added; live performance/cost measurements and cloud operations proof remain outstanding |
| D08 | Generated tracked metadata removed; prototype scope and limitations made explicit |

Do not equate these bug fixes with production readiness or completed live quality
validation. The API/cloud backlog is separate and has not been implemented here.

## Executed checks

- Locked Python 3.12.14 development environment installed with `uv sync --all-groups --frozen`.
- Pytest: 57 passed; 86.90% coverage across eight core modules, including runtime and composition.
- Black formatting and Ruff lint checks passed.
- MyPy passed for all eight configured core source files. The check used an identical
  temporary source copy to avoid Windows-mounted filesystem overhead.
- Streamlit AppTest plus HTTP health smoke passed locally and in the standalone
  Docker image with no host mounts and external networking disabled.
- Docker image built with its frozen production dependencies on Python 3.12.8.
- Canonical and combined Dev Container Compose configurations validated.
- Version 2 synthetic evaluation passes all default thresholds at 1.0; version 1
  is retained as historical input. These are provider-free regression results.

No live Groq/Ollama calls, real-provider answer-quality results, actual VS Code
Dev Container startup, public deployment, or PDF permissions verification are claimed.
