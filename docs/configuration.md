<!--
File: docs/configuration.md
Purpose: Configuration reference.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Configuration reference

Reviewed against `settings.py`, `app_composition.py`, Compose, `.env.sample`, the
Dev Container and CI workflow at baseline `8824d96` plus the 23 October
project-consistency changes. Newly adjustable limits retain baseline defaults.

## Application variables

Set these in root `.env` for normal use. Native `load_dotenv()` does not replace
already-exported process values. Paths are relative to the application's current
working directory unless absolute. Run native commands from the repository root.

| Variable | Application default | Constraint / behavior |
|---|---|---|
| `GROQ_API_KEY` | unset | Required for generated answers; indexing can work without it |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Nonempty name sent to Groq; availability is account-specific |
| `EMBEDDING_MODEL` | `nomic-embed-text:latest` | Nonempty Ollama name; change triggers reindexing |
| `OLLAMA_HOST` | `http://ollama:11434` | Nonempty base URL; native execution normally uses `http://localhost:11434` |
| `PDF_DIRECTORY` | `research_papers` | Top-level non-hidden files ending in `.pdf`, case insensitive; no recursive scan |
| `INDEX_DIRECTORY` | `faiss_index` | Trusted generated state; Compose fixes this to `/app/faiss-data/index` |
| `CHUNK_SIZE` | `1000` | Integer > 0, character-based splitter limit |
| `CHUNK_OVERLAP` | `200` | Integer >= 0 and less than chunk size |
| `DEFAULT_TOP_K` | `4` | Integer between 1 and `MAX_TOP_K` |
| `MAX_TOP_K` | `10` | Integer >= 1 |
| `RETRIEVAL_RELEVANCE_THRESHOLD` | `0.35` | Number between 0 and 1; heuristic cutoff, not a probability or faithfulness score |

Chunk size/overlap changes invalidate the persisted index. Model-name changes
invalidate it, but changing weights behind the same mutable model tag does not;
force a refresh after such changes. Model availability is not established by
nonempty configuration validation.

Compose reads `.env` for interpolation and supplies it through the application
`env_file`. Explicit Compose environment entries override that file:
`OLLAMA_HOST=http://ollama:11434` and `INDEX_DIRECTORY=/app/faiss-data/index`.
Changing those two entries in `.env` does not change the Compose application's
values. The PDF bind mount remains `/app/research_papers`; use its default path
or deliberately update the mount and container path together.

Avoid conflicting exported shell values: shell interpolation values can override
Compose's `.env` values, while the application still reads its `env_file`. In
particular, keep the embedding model used by `ollama-init` and the app aligned.

## Compose-only variables

These are not validated by `Settings`. Port conflicts, unavailable images, invalid
Compose values or model downloads fail at the container/runtime layer.

| Variable | Compose fallback | Effect |
|---|---|---|
| `STREAMLIT_PORT` | `8501` | Host UI port; container port stays 8501 |
| `OLLAMA_PORT` | `11434` | Host Ollama port; internal app URL stays `http://ollama:11434` |
| `OLLAMA_KEEP_ALIVE` | `10m` | Ollama model lifetime; `.env.sample` overrides this to `1m` |
| `POSTGRES_DB` | `chatbot` | Optional unused database profile name |
| `POSTGRES_USER` | `chatbot` | Optional profile database user |
| `POSTGRES_PASSWORD` | `chatbot` | Optional profile local-development password; not a public-hosting credential |
| `POSTGRES_PORT` | `5432` | Optional profile host port |

Default port mappings publish on all host interfaces, not only loopback. Restrict
host access or change bindings before use on a shared/network-accessible host.
There is no built-in authentication or TLS protection for Streamlit/Ollama.

## Adjustable client, context and log limits

| Setting | Current implementation |
|---|---|
| Groq generation | 30-second client timeout, two configured retries, 1,024 output tokens |
| Ollama embeddings | 60-second client timeout |
| User question | UI cap of 4,000 characters |
| Generation history | Most recent ten messages, then last 6,000 characters |
| Evidence | Up to 16,000 text characters divided among retrieved documents, plus source labels |
| Displayed evidence excerpt | First 500 characters per retrieved passage; generation may receive more |
| Logs | `logs/app.log`, 5 MiB rotation threshold, three backups, plus stderr |

All values in this section now come from `Settings.from_env()`; defaults retain
the previous behavior. Copy the corresponding entries in `.env.sample` to `.env`
and recreate the app after changes.

| Environment variable | Default | Validation / purpose |
|---|---|---|
| `GROQ_API_BASE_URL` | `https://api.groq.com/openai/v1` | Nonempty Groq-compatible API root, without completion suffix |
| `GROQ_TIMEOUT_SECONDS` | `30` | Positive finite request timeout |
| `GROQ_MAX_RETRIES` | `2` | Nonnegative retry count |
| `MAX_OUTPUT_TOKENS` | `1024` | Positive maximum generated token count |
| `EMBEDDING_TIMEOUT_SECONDS` | `60` | Positive finite request timeout |
| `MAX_QUESTION_CHARACTERS` | `4000` | Positive question character cap |
| `MAX_HISTORY_MESSAGES` | `10` | Positive recent-message count before text clipping |
| `MAX_HISTORY_CHARACTERS` | `6000` | Positive history character cap |
| `MAX_CONTEXT_CHARACTERS` | `16000` | Positive shared evidence-text budget before labels |
| `LOG_DIRECTORY` | `logs` | Directory for application logs; adjust Compose mounts too if changing it |
| `LOG_MAX_BYTES` | `5242880` | Positive rotation threshold (5 MiB by default) |
| `LOG_BACKUP_COUNT` | `3` | Nonnegative rotated-backup count |

Store credentials only in the dedicated key setting, not inside URLs. Test-only
synthetic keys and fixture URLs are intentional isolated inputs, not deployment
configuration. Fixed snapshot filenames/schema versions, one-based displayed
pages and the synthetic evaluator's reference constants remain in code because
they define file/data contracts rather than environment tuning.

Timeouts are request settings rather than a complete workflow deadline; retries,
multiple embedding batches, parsing and synchronous indexing can take longer.
The character limits are not tokenizer budgets. Failed partial answers are not
committed to conversation history.

## Development and CI

`UV_PROJECT_ENVIRONMENT=/opt/venv` and PATH are set in the production image.
The Dev Container overrides the target to `/app/.venv` and prepends its bin path;
`.devcontainer/setup.sh` runs `uv sync --frozen` in that workspace. Do not copy a
Windows or host virtual environment into a Linux container.

| CI value | Location | Purpose |
|---|---|---|
| `RUN_LIVE_PROVIDER_CHECKS` | Repository variable, exact text `true` | Opt in to the live-provider smoke job |
| `GROQ_API_KEY` | Repository secret | Credential for the smoke completion request |
| `OLLAMA_SMOKE_URL` | Repository secret | Ollama base URL reachable from the GitHub-hosted runner |
| `LLM_MODEL` | Optional repository variable | Smoke generation model; empty falls back to the application default |
| `EMBEDDING_MODEL` | Optional repository variable | Smoke embedding model; empty falls back to the application default |
| `GROQ_API_BASE_URL` | Optional repository variable | Same API root used by the smoke completion request |
| `SMOKE_TIMEOUT_SECONDS` | Optional repository variable or local process environment | Positive finite timeout for each smoke request; default 20 seconds |

The live smoke checks embedding/completion response shapes only; it does not
validate real document QA. A GitHub-hosted runner cannot reach your laptop's
localhost Ollama service. Do not expose an unauthenticated local service just to
make that check reachable. See [quality gates](quality-gates.md) for safer local use.
