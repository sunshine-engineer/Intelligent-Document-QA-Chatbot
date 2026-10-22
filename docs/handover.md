<!--
File: docs/handover.md
Purpose: Maintainer handover.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Maintainer handover

## Scope and baseline

This handover covers the single-user, local text-PDF QA prototype at runtime
commit `8824d96` on `main`, reviewed on 22 October 2026. PR #45 was verified as
merged. The application version in `pyproject.toml` is `0.1.0`; no published
release/tag or deployed environment was verified during this review.

The 23 October project-consistency update retains that runtime baseline
while adding documented configuration overrides, source documentation and the
new layout. See [change record](project-consistency-review.md) for validation.

Reading order: [README](../README.md) -> [configuration](configuration.md) ->
[operations](local-operations.md) -> [quality checks](quality-gates.md).
Use the [document map](index.md) to distinguish current guides from proposals.

## What is being handed over

A Streamlit process discovers PDFs, builds or loads a FAISS index using Ollama
embeddings, retrieves evidence, and streams Groq-generated answers. Source IDs
map to evidence panels with document/page/excerpt details. Low-scoring or absent
evidence produces a fixed refusal. Pronoun follow-ups use heuristic history
expansion; this is not a general conversational reasoning guarantee.

Indexing is synchronous and rebuilds the whole collection when document content,
embedding model name, or chunk settings change. Unchanged session vectors are
reused; another session/restart loads verified artifacts from disk. Legacy
snapshots lacking chunk configuration rebuild once. The local index includes a
pickle document store and must come from an application-controlled, trusted path.

Chat is session-only. There is no API service, worker, upload UI, database-backed
history, authentication, per-user storage, or concurrent indexing lock.
PostgreSQL is only an optional unused Compose service. No cloud infrastructure
from the planning documents is implemented in this checkout.

## Code orientation

| Path | Responsibility |
|---|---|
| `app.py` | Streamlit UI, session chat, startup and refresh error boundaries |
| `settings.py` | Environment parsing, validation and safe provider guidance |
| `app_composition.py` | Real provider clients, loaders, splitter, FAISS and query wiring |
| `app_runtime.py` | Discovery, compatible generation reuse, load/rebuild decisions |
| `app_services.py` | Index build/load orchestration and indexing configuration identity |
| `index_metadata.py` | Document identity, manifests, artifact checksums, snapshot persistence |
| `query_services.py` | Retrieval, thresholds, deduplication, clarification and streaming |
| `app_logging.py` | Correlation IDs and rotated application logs |
| `app_errors.py` | Error taxonomy/helper utilities; not every UI error uses these helpers |
| `tests/` | Provider-free regression, composition, Streamlit and FAISS checks |
| `evaluation/` | Synthetic fixture and threshold-enforcing offline evaluator |
| `scripts/` | Provider-free application/server smoke and opt-in provider connectivity smoke |

## Prerequisites and first run

1. Use Bash/WSL for the shell snippets in these guides. On Windows, configure
   Docker Desktop's Linux-container/WSL integration first. Native Windows
   PowerShell equivalents are not separately validated here.
2. Install Git, Docker with Compose v2 for the container path, or Python 3.12,
   uv and Ollama for the native path. The image and CI pin uv `0.12.5`.
3. Clone the repository using the README commands. Run all commands from its root.
   Check `git rev-parse HEAD` and `git status --short`; do not discard someone
   else's changes while preparing the environment.
4. Copy `.env.sample` to `.env` only when `.env` does not already exist. Configure
   your own Groq credential privately. Do not commit it or send it through chat.
5. Choose readable text PDFs that you may use and share with Groq. For a clean
   handover, move the bundled sample PDFs aside if their permissions are unresolved.
6. Run `docker compose up --build`. Initialization pulls the configured embedding
   model before the app starts. `docker compose ps -a` shows init exit status;
   `ollama-init` completing with exit code 0 is expected.
7. Open <http://localhost:8501> unless `STREAMLIT_PORT` changes it. Opening the UI
   triggers indexing. A missing Groq key permits indexing but disables answers.
8. Confirm document/chunk counts and retrieve an answer from a known passage.
   Check the answer against the PDF, rather than accepting a source panel as proof.

For native development, follow the README's Python/Ollama instructions and use
`OLLAMA_HOST=http://localhost:11434`. For Dev Containers, follow
[container architecture](container-architecture.md); actual editor lifecycle has
not been verified. Do not run native and container applications concurrently
against the same index directory.

## Routine operation

- Add, replace, or remove top-level text PDFs in the configured input directory.
  On the next Streamlit interaction or page reload, discovery reconciles changes.
  There is no background file watcher. Hidden PDFs and nested folders are excluded.
- Refresh Knowledge Base forces full re-embedding. Load Saved Index bypasses the
  session's cached vectors but still checks compatibility; it can rebuild rather
  than load when saved state is invalid or the collection changed.
- Keep one indexing writer. Avoid overlapping refreshes across browser sessions.
- Clear Chat after changing the corpus for a clean demonstration. Old answers keep
  their original excerpts; they are not automatically regenerated or version-linked
  to the new PDF contents.
- Removing the last PDF, or pointing at an empty/missing directory, discards the
  configured generated index. Preserve original PDFs independently of that index.
- Use [operations](local-operations.md) for outages, backups and recovery.

## Acceptance and current evidence

| Check | Evidence/status |
|---|---|
| Original bug-fix quality gates | PR #45 CI was verified successful on its reviewed head; live-provider job skipped |
| Local tests, fresh documentation review | See [documentation audit](documentation-audit.md) for commands and results |
| Docker image without host mounts | Historical provider-free build/AppTest/server smoke passed on 21 October |
| Canonical/Dev Container Compose configuration | Validated configuration; does not prove actual VS Code startup |
| Live PDF -> Ollama -> FAISS -> Groq answers | Outstanding |
| Real-corpus answer faithfulness and retrieval calibration | Outstanding |
| Sample PDF permissions | Outstanding |
| Fresh maintainer installation and backup/restore rehearsal | Must be recorded by the recipient; procedures alone do not establish success |

Before accepting the handover, run the [demo checklist](prototype-demo.md) with
permitted documents and record corpus/configuration, observed quality, restart
reuse and failure recovery. Prepare approximately 20–30 reviewed questions before
making interview quality claims. The existing offline evaluator uses fake
retrieval/generation and cannot measure live quality by swapping in PDF questions.

## Open decisions and responsibilities

No operational contact, new maintainer, deployment owner or service account
transfer was supplied or verified. Complete this table with the recipient; do
not infer ownership from Git author names.

| Item | Handover action | Current status |
|---|---|---|
| Maintainer and support contact | Record who accepts bugs and who may change releases | Unassigned |
| Repository access and branch rules | Grant appropriate access; verify review/CI requirements in GitHub settings | Not audited in this review |
| Groq account and quota ownership | Recipient creates/uses their own key; review quota and permitted document sharing | Account-specific, not transferred |
| PDF provenance and corpus owner | Record title/source/permission for each demo file | Bundled-file provenance unresolved |
| Backup custody and retention | Choose private storage, retention and restore owner | No managed backup configured |
| Runtime/resource budget | Measure first indexing, query latency, memory and provider usage | No representative benchmark |
| Acceptance evidence | Record exact commit, recipient, date, checks and unresolved issues | Awaiting recipient/live validation |

## Limits of this handover

This is enough documentation to orient a maintainer and reproduce provider-free
checks. Full operational sign-off still depends on successful live setup, verified
PDF permissions and an explicitly assigned owner. The API and GCP proposals are
optional future work and are not prerequisites for handing over this local prototype.
