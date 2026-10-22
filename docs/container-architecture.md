<!--
File: docs/container-architecture.md
Purpose: Container architecture.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Container architecture

## Current local stack

`docker-compose.yml` defines the implemented local stack. It starts Ollama,
waits for its health check, runs the one-shot `ollama-init` service to pull the
configured `EMBEDDING_MODEL`, then starts the Streamlit application. An exited
`ollama-init` with code 0 is normal. PostgreSQL runs only with the `persistence`
profile and is not used by the application.

From the repository root, create `.env` from `.env.sample` if it does not exist,
configure your own key, and run:

```bash
docker compose up --build
docker compose ps -a
```

Open <http://localhost:8501> unless `STREAMLIT_PORT` changes it. The health endpoint
reports server responsiveness; it does not prove an application session or a
real document query succeeded.

| Service | Role | State / host access |
|---|---|---|
| `ollama` | Embedding provider | Named `ollama-data` volume; default host port 11434 |
| `ollama-init` | Pull configured embedding model | One-shot process, no published port |
| `rag_chatbot` | Streamlit, parsing, FAISS, retrieval and Groq client | Default host port 8501; state mounts below |
| `postgres` | Unused future persistence development | Optional profile; named `postgres-data`; default host port 5432 |

The default mappings bind all interfaces. This stack has no authentication/TLS
front end and is intended for controlled local use, not direct public deployment.
Host `OLLAMA_PORT` does not change the app's internal Ollama address. See the
[complete configuration reference](configuration.md) for overrides and precedence.

## Image and filesystem contract

The Dockerfile uses `python:3.12.8-slim`, installs uv `0.12.5`, and installs frozen
production dependencies with `uv sync --frozen --no-dev` at `/opt/venv`. Public
Streamlit styling/config is packaged in the image; `.env`, Streamlit secrets,
generated indexes/logs and development caches are excluded from the build context.

| Host path | Container path | Purpose |
|---|---|---|
| `./research_papers` | `/app/research_papers` | Input PDFs |
| `./faiss_index` | `/app/faiss-data` | Active index is its child `/app/faiss-data/index` |
| `./vector_store` | `/app/vector_store` | Legacy metadata mount; not the active snapshot |
| `./.streamlit` | `/app/.streamlit` | Public UI style/config override for Compose |
| `./logs` | `/app/logs` | Rotated application logs |

The replaceable index must be below a mount root: directory promotion renames
it, which fails if the directory itself is a bind-mount boundary. The active
snapshot contains `index.faiss`, `index.pkl` and `index_snapshot.json` together.
Do not copy untrusted pickle/index artifacts into this directory.

A standalone image can start without Compose mounts; its defaults refer to the
bundled PDFs and native-relative index path. Use an explicitly empty temporary
input directory for a provider-free startup check. The image's Python dependency
installation does not include development tools such as pytest/Black/MyPy.

## Development container

VS Code reads `.devcontainer/devcontainer.json`, which combines the canonical
stack with `docker-compose.devcontainer.yml`. The override adds the workspace
mount at `/app`, sets `UV_PROJECT_ENVIRONMENT=/app/.venv`, and prepends
`/app/.venv/bin` to PATH. The post-create script creates/synchronizes that
workspace's development environment with `uv sync --frozen`; it is a separate
installation location from the image's production environment.

Use **Dev Containers: Reopen in Container** in VS Code. Do not reuse a host/Windows
virtual environment inside the Linux container. Verify in the container terminal:

```bash
uv run python -c "import sys; print(sys.executable)"
uv run python -m pytest --cov
```

The expected executable is `/app/.venv/bin/python`. A running Streamlit process
that started before the workspace environment existed can still be using the
image environment; restart the service after post-create setup when validating
that lifecycle. From the host:

```bash
docker compose -f docker-compose.yml -f docker-compose.devcontainer.yml restart rag_chatbot
```

The editor's real startup/restart lifecycle is not established by the Compose
configuration checks; this remains a recipient acceptance step.

## Optional profile and shutdown

```bash
docker compose --profile persistence up --build
docker compose down
```

`down` retains named volumes. `down -v` deletes named Ollama/PostgreSQL volumes;
PDFs, indexes and logs in host bind mounts remain separate. This is not a managed
backup system. See [operations](local-operations.md) before restoring or resetting.
