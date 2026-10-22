<!--
File: docs/local-operations.md
Purpose: Local operation and recovery.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Local operation and recovery

## Normal startup and diagnostics

Run commands from the repository root using Bash/WSL. Start with
`docker compose up --build`, or follow the native README workflow. Check:

```bash
docker compose ps -a
docker compose logs --tail=100 rag_chatbot ollama-init
docker compose exec ollama ollama list
```

`ollama-init` exiting successfully is expected. Container health checks confirm
server responsiveness; they do not prove a PDF query succeeds. Opening a browser
session runs the application. There is no background PDF watcher: use a UI
interaction, reload the page, or select Refresh Knowledge Base after file changes.

| Symptom | Check / recovery |
|---|---|
| Port already allocated | Stop the conflicting service or set `STREAMLIT_PORT` / `OLLAMA_PORT` in `.env`, then recreate services; see configuration |
| Ollama model absent or initial download failed | Inspect `ollama-init` logs; retry `docker compose run --rm ollama-init` after resolving network/model settings |
| Answers disabled | Set your own `GROQ_API_KEY` privately in `.env`, then recreate the application |
| Groq authentication, unavailable model, quota or rate error | Verify your account/key/model and quota; wait before retrying rate-limited requests |
| Indexing fails | Check input path/read permissions, PDF validity and selectable text, then embedding service; remove a problematic file and refresh |
| Scanned, encrypted or zero-text PDF | Use a readable text PDF; no OCR/per-file fault isolation exists |
| Provider timeout | Check provider reachability; request timeout/retries are not an overall indexing deadline |
| No evidence/refusal for a supported question | Inspect sources, Top K, document extraction and configured relevance threshold; evaluate before changing retrieval settings |
| Corrupt/legacy index | Reload or refresh; invalid or incompatible persisted state can trigger a rebuild |
| Failed stream | Partial turn is not saved; retry after fixing the provider problem |

After editing `.env`, recreate rather than only restart a running Compose service:

```bash
docker compose up -d --force-recreate rag_chatbot
```

After changing `EMBEDDING_MODEL`, also rerun initialization:

```bash
docker compose run --rm ollama-init
docker compose up -d --force-recreate rag_chatbot
```

For native execution, restart `uv run streamlit run app.py` after environment
changes. Avoid conflicting already-exported shell variables; native dotenv does
not overwrite them. Model-name/chunk changes rebuild the index. Changing weights
behind the same model tag requires a manual refresh.

## Data locations and retention

| Data | Default location | Retention / recovery |
|---|---|---|
| Original PDFs | Host `research_papers/` | Authoritative input; back up independently |
| Active Compose index | Host `faiss_index/index/` | Generated, rebuildable; app replaces snapshots |
| Active native index | `INDEX_DIRECTORY`, default `faiss_index/` | Generated, rebuildable; never share with another active writer |
| Snapshot metadata | Inside active index as `index_snapshot.json` | Includes content identity, configuration, artifact checksums and metrics |
| Legacy metadata | `vector_store/` | Compatibility artifacts; not the active snapshot |
| Chat and answer metadata | Streamlit session memory | Lost with the session; Clear Chat affects this session only |
| Application logs | Host `logs/app.log` for Compose/native root | 5 MiB per file, three rotated backups; may include file paths and metrics |
| Ollama models | Named `ollama-data` volume | Cached downloads; can be pulled again |
| Optional database | Named `postgres-data` volume | Unused by current application; not covered by the corpus backup below |
| Credential | Root `.env` or process environment | Keep private; manage separately from source/data archives |

Application exception logs retain correlation IDs and exception types, not raw
provider exception messages or tracebacks. Use the UI reference to find an error
in `logs/app.log` or container logs. This does not guarantee that every external
library diagnostic is sanitized. Latency shown in the UI is a per-query timing,
not a representative resource, throughput or cost benchmark.

Removing the last PDF, or configuring an empty/missing input directory, causes
the app to discard the configured generated index. A missing input directory is
not a backup mechanism. Prior answer excerpts remain from the time they were
retrieved; Clear Chat after a corpus replacement if you need a clean session.

## Backup and restore

These Bash commands cover the default Compose corpus only. Choose a private
backup destination and stop all app/indexing writers and PDF edits first. The
archive can contain sensitive document text; apply your own storage/access policy.

```bash
docker compose stop rag_chatbot
git rev-parse HEAD > ../rag-backup-runtime.txt
tar -czf ../rag-corpus-backup.tar.gz research_papers
docker compose up -d rag_chatbot
```

Record nonsecret configuration (model names, chunk settings, paths and threshold)
with the backup. Manage the Groq key separately; obtain a new recipient-owned key
rather than putting `.env` in the archive. The index is deliberately excluded
because it can be rebuilt; Ollama model volumes and optional PostgreSQL data are
not included. This is a manual procedure, not a scheduled backup service.

Restore a self-created backup into staging, preserving current PDFs first:

```bash
docker compose stop rag_chatbot
mkdir -p ../rag-restore-staging
tar -tzf ../rag-corpus-backup.tar.gz
tar -xzf ../rag-corpus-backup.tar.gz -C ../rag-restore-staging
mv research_papers "../research_papers-before-restore-$(date +%Y%m%d-%H%M%S)"
cp -a ../rag-restore-staging/research_papers ./research_papers
docker compose up -d --force-recreate rag_chatbot
```

Restore nonsecret settings, configure your own credential, and open a new UI
session. Verify document/chunk counts and a known-answer PDF question. The index
is reused only if restored content/configuration still matches; otherwise the
app rebuilds it. Repeat this procedure with a disposable corpus before signing
handover acceptance. No restore rehearsal was executed in the documentation audit.
For native operation, stop the foreground Streamlit process and substitute its
startup command for the Docker stop/start commands.

## Reset and shutdown

For unrecoverable index state, stop the app and move the generated index directory
to a backup location; preserve PDFs and `.env`. Compose expects the index under
`faiss_index/index/`, whereas native execution uses the configured path. Restart
and refresh after confirming Ollama is available. Do not rename/remove the host
bind-mount root while a container is running.

`docker compose down` retains named data volumes. `docker compose down -v` deletes
named Ollama/PostgreSQL volumes; host-mounted PDFs/indexes/logs are separate.
Manual cleanup and Clear Chat do not erase copies held in your own backups or
provider systems. Do not run multiple sessions that can index concurrently; no
writer coordination or formal crash-recovery guarantee has been established.
