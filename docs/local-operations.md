# Local operation and recovery

1. Start with `docker compose up --build`, or follow the native README workflow.
2. Check `docker compose ps` and `docker compose logs --tail=100 rag_chatbot ollama-init`.
   Container health checks confirm server responsiveness; they do not prove a
   document query succeeds.
3. Verify Ollama with `docker compose exec ollama ollama list`. If the model is
   missing, run `docker compose run --rm ollama-init`. A first pull can take time.
4. Configure the Groq key in `.env`, then recreate the application with
   `docker compose up -d --force-recreate rag_chatbot`. Never paste keys into logs.
5. For an indexing failure, inspect PDF read permissions and confirm text can be
   selected. Remove problematic/scanned/encrypted files from the input collection
   and select Refresh Knowledge Base. No OCR or per-file isolation is provided.
6. Unchanged PDFs reuse the index. PDF content, embedding model, chunk size or
   overlap changes require rebuilding. If a mutable embedding model tag changes
   its underlying weights, force a refresh; the application compares model names.
7. For a corrupt index, select Refresh Knowledge Base. If necessary, stop the app
   and move the generated `faiss_index/` directory aside before restarting. Compose
   stores its active index at host `faiss_index/index/`; native execution uses the
   configured `INDEX_DIRECTORY`. Preserve `research_papers/` and `.env`.
8. On failed refresh, the last persisted snapshot is retained and queries are
   disabled for that run to avoid using stale evidence. Fix the cause and retry.
9. Clear Chat clears the current session conversation. It does not delete PDFs,
   index data, or rotated `logs/app.log` files. Stop the app before manual cleanup.
10. `docker compose down` retains named data volumes. `down -v` deletes named
    Ollama/PostgreSQL volumes; use only when intentional. Back up your PDFs and
    configuration securely; indexes can be rebuilt.

Exception logs retain correlation IDs and exception types, not raw provider
exception payloads or tracebacks. Use the reference displayed in the UI when
investigating failures. Latency in the UI is per query; no representative memory,
throughput, cost, or real-provider quality benchmark has been published yet.
