<!--
File: docs/file-inventory.md
Purpose: Record every project-owned file and its format-aware review disposition.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Project file inventory

Reviewed on 23 October 2026 with the requested default maintainer
`sunshine-engineer`. That maintenance default is not an assertion of original
authorship or ownership of third-party content. Runtime-generated/ignored files
are outside source scope; they are described in README and operations instead.

The consistency checker requires a row for every existing tracked/unignored file.
Strict JSON, legal text, generated lock files and binary assets use this inventory
as their metadata record instead of an unsafe in-file header.

| File | Type | Purpose | Review disposition |
|---|---|---|---|
| `.devcontainer/devcontainer.json` | Strict JSON | VS Code lifecycle, workspace, interpreter and extension configuration. | Schema preserved; metadata recorded here. |
| `.devcontainer/setup.sh` | sh | Linux development environment creation, dependency sync and startup checks. | Format-compatible header, LF and purpose reviewed. |
| `.dockerignore` | Configuration | Image-context exclusions for private/generated files. | Format-compatible header, LF and purpose reviewed. |
| `.editorconfig` | Configuration | Shared file-type-specific encoding and whitespace conventions. | Format-compatible header, LF and purpose reviewed. |
| `.env.sample` | sample | Nonsecret defaults and adjustable provider, context and logging limits. | Format-compatible header, LF and purpose reviewed. |
| `.gitattributes` | Configuration | LF text normalization and binary PDF/PNG preservation. | Format-compatible header, LF and purpose reviewed. |
| `.github/workflows/quality.yml` | yml | Quality workflow including consistency checks and opt-in live connectivity. | Format-compatible header, LF and purpose reviewed. |
| `.gitignore` | Configuration | Local secrets, runtime data, virtual environments and cache exclusions. | Format-compatible header, LF and purpose reviewed. |
| `.streamlit/config.toml` | toml | Public Streamlit theme configuration. | Format-compatible header, LF and purpose reviewed. |
| `.streamlit/style.css` | css | Public dashboard/evidence control styles. | Format-compatible header, LF and purpose reviewed. |
| `Dockerfile` | Configuration | Frozen Python production image build and Streamlit launch contract. | Format-compatible header, LF and purpose reviewed. |
| `LICENSE` | License | MIT terms for project code; no new legal or author metadata inserted. | Legal text preserved unchanged. |
| `README.md` | Markdown | User entry point, directory map and setup/validation navigation. | Header, links and current/historical/proposal classification reviewed. |
| `app.py` | Python | Render the single-user Streamlit document-QA interface and safe recovery controls. | Header, complete explicit-definition docs, import/format checks. |
| `app_composition.py` | Python | Compose provider clients, document processing and history-aware retrieval services. | Header, complete explicit-definition docs, import/format checks. |
| `app_errors.py` | Python | Define application error categories and safe user-facing recovery messages. | Header, complete explicit-definition docs, import/format checks. |
| `app_logging.py` | Python | Configure correlated, rotated application logging without raw exception payloads. | Header, complete explicit-definition docs, import/format checks. |
| `app_runtime.py` | Python | Synchronize a session with the compatible persisted knowledge-base generation. | Header, complete explicit-definition docs, import/format checks. |
| `app_services.py` | Python | Build and load verified FAISS indexes through injectable infrastructure adapters. | Header, complete explicit-definition docs, import/format checks. |
| `assets/CHAT.png` | Binary | Historical UI screenshot; original author/ownership not established by this review. | Bytes preserved; no inserted metadata. |
| `assets/HOME.png` | Binary | Historical UI screenshot; original author/ownership not established by this review. | Bytes preserved; no inserted metadata. |
| `assets/Sources.png` | Binary | Historical UI screenshot; original author/ownership not established by this review. | Bytes preserved; no inserted metadata. |
| `docker-compose.devcontainer.yml` | yml | Workspace mount, development environment target and interpreter PATH. | Format-compatible header, LF and purpose reviewed. |
| `docker-compose.yml` | yml | Local application, Ollama initialization and optional unused PostgreSQL profile. | Format-compatible header, LF and purpose reviewed. |
| `docs/configuration.md` | Markdown | Configuration reference. | Header, links and current/historical/proposal classification reviewed. |
| `docs/container-architecture.md` | Markdown | Container architecture. | Header, links and current/historical/proposal classification reviewed. |
| `docs/contributing.md` | Markdown | Contributor conventions. | Header, links and current/historical/proposal classification reviewed. |
| `docs/dependency-management.md` | Markdown | Dependency management. | Header, links and current/historical/proposal classification reviewed. |
| `docs/documentation-audit.md` | Markdown | Documentation handover audit. | Header, links and current/historical/proposal classification reviewed. |
| `docs/fastapi-backend-v1-github-backlog.md` | Markdown | FastAPI Backend v1 GitHub Backlog. | Header, links and current/historical/proposal classification reviewed. |
| `docs/file-inventory.md` | Markdown | Project file inventory. | Header, links and current/historical/proposal classification reviewed. |
| `docs/gcp-production-style-deployment-v1-plan.md` | Markdown | GCP Production-Style Deployment v1 Plan. | Header, links and current/historical/proposal classification reviewed. |
| `docs/handover.md` | Markdown | Maintainer handover. | Header, links and current/historical/proposal classification reviewed. |
| `docs/history/portfolio-fix-status.md` | Markdown | Portfolio review fix status. | Header, links and current/historical/proposal classification reviewed. |
| `docs/history/portfolio-readiness-review.md` | Markdown | Historical portfolio prototype readiness review. | Header, links and current/historical/proposal classification reviewed. |
| `docs/index.md` | Markdown | Documentation map. | Header, links and current/historical/proposal classification reviewed. |
| `docs/local-operations.md` | Markdown | Local operation and recovery. | Header, links and current/historical/proposal classification reviewed. |
| `docs/project-consistency-review.md` | Markdown | Project-wide consistency review. | Header, links and current/historical/proposal classification reviewed. |
| `docs/prototype-demo.md` | Markdown | Reproducible prototype demonstration. | Header, links and current/historical/proposal classification reviewed. |
| `docs/quality-gates.md` | Markdown | Quality gates and evaluation. | Header, links and current/historical/proposal classification reviewed. |
| `evaluation/dataset.v1.json` | Strict JSON | Historical pre-fix synthetic evaluation cases. | Schema preserved; metadata recorded here. |
| `evaluation/dataset.v2.json` | Strict JSON | Current deterministic cases with explicit clarification expectations. | Schema preserved; metadata recorded here. |
| `evaluation/run_offline.py` | Python | Evaluate the versioned synthetic retrieval fixture and enforce metric thresholds. | Header, complete explicit-definition docs, import/format checks. |
| `index_metadata.py` | Python | Track PDF content identity and persist integrity-checked index generations. | Header, complete explicit-definition docs, import/format checks. |
| `pyproject.toml` | toml | Python/dependency metadata and shared testing/formatting/lint/type settings. | Format-compatible header, LF and purpose reviewed. |
| `query_services.py` | Python | Retrieve, filter and cite evidence for synchronous and streamed document answers. | Header, complete explicit-definition docs, import/format checks. |
| `research_papers/Attention.pdf` | Binary | Bundled PDF input; provenance and sharing/redistribution permissions remain unverified. | Bytes preserved; no inserted metadata. |
| `research_papers/LLM.pdf` | Binary | Bundled PDF input; provenance and sharing/redistribution permissions remain unverified. | Bytes preserved; no inserted metadata. |
| `research_papers/README.md` | Markdown | Sample document rights and provenance. | Header, links and current/historical/proposal classification reviewed. |
| `scripts/check_project_consistency.py` | Python | Check documented source contracts and file coverage without importing the app. | Header, complete explicit-definition docs, import/format checks. |
| `scripts/live_provider_smoke.py` | Python | Check live Ollama and Groq response shapes using explicitly supplied credentials. | Header, complete explicit-definition docs, import/format checks. |
| `scripts/streamlit_smoke.py` | Python | Exercise provider-free Streamlit execution and health in a temporary workspace. | Header, complete explicit-definition docs, import/format checks. |
| `settings.py` | Python | Parse, validate and summarize environment-based application configuration. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_app_composition.py` | Python | Regression tests for app composition. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_app_errors.py` | Python | Regression tests for app errors. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_app_services.py` | Python | Regression tests for app services. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_configuration_limits.py` | Python | Verify configurable client, context, UI and logging limits preserve defaults. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_index_manifest.py` | Python | Regression tests for index manifest. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_index_metadata.py` | Python | Regression tests for index metadata. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_integration_workflows.py` | Python | Regression tests for integration workflows. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_offline_evaluation.py` | Python | Regression tests for offline evaluation. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_project_consistency.py` | Python | Verify the repository audit catches missing documentation and broken file links. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_query_services.py` | Python | Regression tests for query services. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_readiness_regressions.py` | Python | Regression tests for readiness regressions. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_settings.py` | Python | Regression tests for settings. | Header, complete explicit-definition docs, import/format checks. |
| `tests/test_streamlit_app.py` | Python | Regression tests for streamlit app. | Header, complete explicit-definition docs, import/format checks. |
| `uv.lock` | Generated TOML | Generated dependency resolutions; direct Pydantic metadata added, versions retained. | Regenerated through uv; package versions unchanged. |
