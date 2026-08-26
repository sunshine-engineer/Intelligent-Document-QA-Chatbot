# FastAPI Backend v1 GitHub Backlog

## Goal

Make FastAPI the canonical backend and Streamlit an API client while retaining FAISS for vectors, PostgreSQL for metadata and durable workflow state, a separate ingestion worker, API-key authentication, and SSE answer streaming.

## Explicit exclusions

pgvector, user registration, multi-tenancy, object storage, and distributed message brokers.

## Milestone

`FastAPI Backend v1` — no due date until a delivery schedule is agreed.

## Epic

`[EPIC] Build the FastAPI Backend v1`

Completion requires every child issue closed, protected CI passing, Docker Compose E2E proof, current documentation, and a protected `main` branch.

## Ordered implementation issues

1. **[API-01] Establish the FastAPI application foundation and security contract**
   - Add the application factory, lifespan, versioned `/v1` routers, live/ready health checks, API-key dependency, correlation IDs, problem-details errors, redacted settings, and OpenAPI.
   - Test import safety, 401 behavior, lifecycle, health distinction, and redaction.
   - Depends on: none.
2. **[API-02] Add PostgreSQL persistence and reproducible migrations**
   - Add async SQLAlchemy, PostgreSQL driver, Alembic, initial schema for documents, jobs, conversations, messages, evaluations, request events, and active index generation.
   - Prove upgrade/downgrade/re-upgrade and state constraints; do not store embeddings or enable pgvector.
   - Depends on: API-01.
3. **[API-03] Build the durable PostgreSQL job queue and worker**
   - Add a separate worker, row-locked claiming, leases, heartbeats, stale recovery, bounded retries, cancellation, safe errors, and an indexing-writer lock.
   - Prove competing workers, restart recovery, retry limits, and graceful shutdown.
   - Depends on: API-02.
4. **[API-04] Add the validated PDF document API and content-addressed storage**
   - Add upload/list/detail/queued-delete endpoints, checksum-addressed immutable storage, size/MIME/header/PDF validation, duplicate detection, and filename sanitization.
   - Return 202 with document/job IDs; never expose paths or content.
   - Depends on: API-02 and API-03.
5. **[API-05] Connect ingestion jobs to verified atomic FAISS snapshots**
   - Add worker parsing, chunking, embedding, candidate verification, atomic promotion, active-generation records, rebuild/delete reconciliation, and previous-snapshot retention.
   - Prove failure preservation, serialized indexing, restart consistency, and safe legacy migration.
   - Depends on: API-03 and API-04.
6. **[API-06] Add the grounded query and conversation API**
   - Add `POST /v1/queries`, typed bounded Top-K/citation/rewrite/timing responses, PostgreSQL conversation/message persistence, safe refusal/clarification behavior, and configurable disabled-by-default message retention.
   - Preserve the original question as generation input and prevent sensitive logging.
   - Depends on: API-01, API-02, and API-05.
7. **[API-07] Add server-sent-event response streaming**
   - Add `POST /v1/queries/stream` with typed `metadata`, `citation`, `token`, `complete`, and `error` events, disconnect handling, and final persistence policy.
   - Keep sync and streaming retrieval decisions identical.
   - Depends on: API-06.
8. **[API-08] Migrate Streamlit into a FastAPI API client**
   - Add HTTP/SSE clients, hidden API-key configuration, upload/job polling, citation rendering, streamed tokens, and safe failure recovery.
   - Remove direct Streamlit access to FAISS, PostgreSQL, providers, PDFs, and indexing.
   - Depends on: API-04, API-06, and API-07.
9. **[API-09] Add evaluation, status, metrics, and redacted observability**
   - Add durable evaluation and result endpoints, worker-driven evaluation, `/v1/status`, Prometheus metrics, and sanitized request events.
   - Report Recall@K, MRR, citation/refusal/clarification accuracy, latency, and dataset version without sensitive payloads.
   - Depends on: API-03, API-05, API-06, and API-07.
10. **[API-10] Deliver the Docker Compose E2E workflow and release documentation**
    - Add `api`, `worker`, `streamlit`, `postgres`, `ollama`, and `ollama-init` services with health checks, volumes, configurable ports, restart E2E, API/worker smoke checks, and current architecture/config/recovery documentation.
    - Depends on: API-01 through API-09.

## GitHub creation/closure rules

- Create the epic and all ten issues under the milestone.
- Apply `enhancement` to API-01 through API-09; apply `enhancement` and `documentation` to API-10.
- Replace dependency placeholders with actual issue links after creation.
- One focused branch and pull request per issue.
- Close only after protected CI passes and the pull request merges.
- Do not create an implementation branch until the issue audit passes.
