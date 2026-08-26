# Quality gates and evaluation

Every pull request runs frozen dependency installation, Black, Ruff, MyPy,
pytest with a 70% core-module coverage threshold, and the deterministic offline
retrieval evaluation. CI uploads `coverage.xml` and `evaluation-results.json`
as artifacts.

Run the same checks locally:

```bash
uv sync --all-groups --frozen
uv run black --check .
uv run ruff check .
uv run mypy
uv run python -m pytest --cov
uv run python evaluation/run_offline.py --output evaluation-results.json
```

The versioned dataset is deliberately synthetic and provider-free. Its metrics
measure regression safety for retrieval wiring and citations, not real-world
model quality. Live Groq and Ollama checks are disabled by default and run in
CI only when `RUN_LIVE_PROVIDER_CHECKS=true`, `GROQ_API_KEY`, and
`OLLAMA_SMOKE_URL` are configured as repository variables/secrets.

CI also starts Streamlit against an empty temporary knowledge base and waits
for its health endpoint. This proves that a no-credential, no-document startup
state remains usable without contacting either provider.

To demonstrate a blocked change, temporarily introduce an unused import or
change an expected evaluation source, run the commands above, and observe Ruff
or pytest fail. Revert the intentional change before committing. `main` must
require the GitHub check named `Quality gates / quality` before merge; configure
that rule in the repository branch protection settings after the first passing
run.
