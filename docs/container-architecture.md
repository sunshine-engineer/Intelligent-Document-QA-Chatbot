# Container architecture

`docker-compose.yml` is the canonical local stack. It starts Ollama, performs
an idempotent `nomic-embed-text` model initialization, and starts the FAISS
Streamlit application. PostgreSQL is available only with the `persistence`
profile because the current application does not use it.

```bash
cp .env.sample .env
docker compose up --build
```

The application is available at <http://localhost:8501>. Add PDFs under
`research_papers/`; the directory, `vector_store/`, and `faiss_index/` are
bind-mounted so rebuilds do not remove documents or indexes. Inside the
container, the replaceable FAISS directory is `/app/faiss-data/index`, below
the bind-mount root, which allows atomic directory replacement. Ollama data is
kept in the named `ollama-data` volume.

The Dev Container combines the canonical stack with
`docker-compose.devcontainer.yml`, which adds only the workspace bind mount.
It does not define another image or dependency installation path.

Use the optional database profile only when developing future persistence:

```bash
docker compose --profile persistence up --build
```

Stop services while retaining data with `docker compose down`. Do not use
`docker compose down -v` unless you intentionally want to delete Ollama and
PostgreSQL data volumes.
