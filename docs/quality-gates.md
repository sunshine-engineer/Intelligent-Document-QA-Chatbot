<!--
File: docs/quality-gates.md
Purpose: Quality gates and evaluation.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Quality gates and evaluation

## Reproduce the required checks

From the repository root, with Python 3.12 and uv 0.12.5:

```bash
uv sync --all-groups --frozen
uv run python scripts/check_project_consistency.py
uv run black --check .
uv run ruff check .
uv run mypy
uv run python -m pytest --cov --cov-report=term-missing --cov-report=xml:coverage.xml
uv run python scripts/streamlit_smoke.py
uv run python evaluation/run_offline.py --output evaluation-results.json
```

These commands match `.github/workflows/quality.yml`. All pull requests, pushes
to `main`, and manual workflow dispatch run the `quality` job. The coverage gate
is 70% across the eight configured core modules in `pyproject.toml`. MyPy checks
those same eight core source files; it is not an exhaustive type check of every
UI/test/script line. A provider-free run requires no Groq secret or Ollama server.

The workflow attempts to upload `coverage.xml` and `evaluation-results.json` as
`quality-evidence` even after a failure. A file can be missing if an earlier step
failed before producing it. Retrieve artifacts from that run's GitHub Actions
page or with `gh run download RUN_ID --name quality-evidence --dir ./quality-evidence`
after substituting the actual run ID. Check results for the exact commit being
handed over; historical counts are recorded in [fix status](history/portfolio-fix-status.md).

## What the checks prove

Tests execute real Streamlit AppTest sessions, answer evidence after reruns,
invalid configuration, manual refresh failures, failed streams, history-aware
composition, and actual FAISS persistence/search with deterministic embeddings.
The smoke script executes an empty-knowledge-base app session, verifies no script
exception and disabled questions, then separately checks the server health URL.
It needs permission to bind a temporary localhost port; restricted sandboxes can
block that independently of application correctness.

These checks do not establish live provider availability, PDF answer faithfulness,
public deployment, VS Code lifecycle behavior, concurrency safety or PDF permissions.

## Synthetic evaluation definitions

The default dataset is `evaluation/dataset.v2.json` with five cases. v1 remains
historical input and should not be used as the current passing baseline. The
runner uses word-overlap retrieval and returns fixture text rather than calling
Ollama/FAISS/Groq. A perfect result is a regression baseline, not a live benchmark.

| JSON field | Meaning and denominator |
|---|---|
| `recall_at_k` | Fraction of expected source identities retrieved, averaged over cases with nonempty expected sources (three current cases) |
| `mrr` | Reciprocal rank of the first expected source, averaged over those same cases |
| `citation_correctness` | Precision of retrieved unique `(document, page)` pairs against expected pairs; average over retrieval cases; not semantic claim support |
| `refusal_accuracy` | Correct answer-versus-refusal-versus-clarification decision over all five cases; does not judge answer factuality |
| `clarification_accuracy` | Correct clarification over cases with `clarification_expected=true` (one current case) |
| `mean_latency_ms` | Synthetic in-process fixture timing, not application/provider latency |

Input document pages are zero-based; expected/displayed pages are one-based.
`expected_sources` and `expected_pages` are parallel arrays zipped into pairs,
not independent sets. Provide a source again for each additional expected page.
For source recall, source identities are deduplicated. The runner's max results
is four and its threshold is 0.1; it does not read application Top K/threshold
settings. Version and review any changed fixture and expected evidence.

The CLI defaults to minimum 1.0 for all five quality metrics. It writes the result
JSON and exits with code 1 when any threshold fails. Overrides are explicit, e.g.:

```bash
uv run python evaluation/run_offline.py --dataset evaluation/dataset.v2.json --min-recall-at-k 0.9
```

Changing the JSON to real PDF questions does not turn this runner into a live
quality evaluator. Use the [manual evaluation record](prototype-demo.md) until a
real-provider evaluation harness exists.

## Optional live connectivity smoke

This script checks response shapes for one embedding request and one Groq
completion; it does not ingest/query a PDF. In CI configure:

- Repository variable `RUN_LIVE_PROVIDER_CHECKS=true` (exact text).
- Repository secrets `GROQ_API_KEY` and `OLLAMA_SMOKE_URL`.
- Optional repository variables `LLM_MODEL`, `EMBEDDING_MODEL`,
  `GROQ_API_BASE_URL` and `SMOKE_TIMEOUT_SECONDS`.

The GitHub-hosted runner must reach the supplied Ollama endpoint; its localhost
is not your laptop. Do not publish an unauthenticated local Ollama just to enable
CI. Leave the job disabled or use an appropriately controlled reachable runtime.
The model must already exist on the remote Ollama instance.

For a local Bash/WSL check with your own key entered privately:

```bash
read -r -s -p 'Groq API key: ' GROQ_API_KEY
printf '\n'
export GROQ_API_KEY
export OLLAMA_SMOKE_URL=http://localhost:11434
# Set LLM_MODEL and EMBEDDING_MODEL explicitly if using nondefault models.
uv run python scripts/live_provider_smoke.py
unset GROQ_API_KEY
```

The script reads process environment, not `.env` automatically. Its requests default to
20-second timeouts, configurable with `SMOKE_TIMEOUT_SECONDS`; these are separate
from the application client settings. This
check contacts providers and uses your account quota. Do not store keys in shell
history or share provider response payloads containing confidential content.

## Merge controls

The required job in this workflow is named `quality` under workflow `Quality gates`.
Configure branch rules to require its actual check context as shown by GitHub.
Workflow YAML alone does not enforce branch protection, required reviews or prevent
merging without checks. Repository rule configuration was not audited here.
