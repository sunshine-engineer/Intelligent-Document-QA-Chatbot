<!--
File: docs/dependency-management.md
Purpose: Dependency management.
Maintainer: sunshine-engineer
Modified: 2026-10-23
-->

# Dependency management

## Supported runtime

`pyproject.toml` requires Python `>=3.12,<3.13`. The image pins Python 3.12.8;
CI and the image pin uv 0.12.5. The prior local validation used Python 3.12.14.
Those facts describe different environments; they do not establish support for
Python 3.13/3.14 or an arbitrary uv version.

The project depends on Streamlit, LangChain integrations, FAISS, pypdf, dotenv,
Ollama and Groq clients. Inspect `pyproject.toml` for direct dependency ranges and
`uv.lock` for the exact resolved versions. The default dev group contains pytest,
coverage, Black, Ruff and MyPy. No LangChain or provider service installation is
implied by having their Python clients installed.

## Reproduce the environment

Run from the repository root:

```bash
uv --version
uv sync --all-groups --frozen
uv run python --version
uv run python -c "import sys; print(sys.executable)"
```

For consistency, use uv 0.12.5 as in CI. uv can provision Python 3.12 when needed,
which requires an initial download; use an existing suitable interpreter when
operating without network access. The ordinary native environment is `.venv`,
the image installs production-only packages at `/opt/venv`, and the Dev Container
installs development packages at `/app/.venv`. See [containers](container-architecture.md).

Always use `uv run` for commands rather than an unrelated system `python`.
`uv sync --frozen` also includes the default dev group, while the image explicitly
uses `--no-dev`. Do not install untracked packages interactively into the image
and assume another maintainer can reproduce them.

## Deliberate dependency changes

1. Change direct requirements in `pyproject.toml` only when needed.
2. Run `uv lock` and inspect both the manifest and lock-file diffs. A broad
   dependency upgrade is separate from a documentation or bug-only change.
3. Run `uv sync --all-groups --frozen`.
4. Run all [quality commands](quality-gates.md), not only unittest discovery.
5. Rebuild/test the image and smoke the affected real integration when a provider
   or LangChain dependency changed. Record exactly which live checks were run.
6. Commit both manifest and lock changes when resolution changed.

Frozen synchronization uses the existing lock and does not resolve dependency
updates. To explicitly check whether the lock matches the project, run
`uv lock --check`; do not rely on `--frozen` alone as a lock-freshness audit.

Do not copy a virtual environment across operating systems. Recreate it from the
lock file instead. Client imports and provider-free tests do not prove current
provider model availability, API credentials, network access or answer quality.
