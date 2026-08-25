# Dependency management

The project uses `uv` and the committed `uv.lock` file. Python 3.12 is
required.

Install the exact development environment with:

```bash
uv sync --frozen
```

Refresh dependencies intentionally after editing `pyproject.toml`:

```bash
uv lock
uv sync --frozen
python -m unittest discover -s tests -v
```

Review the lock-file diff before committing. Docker and the Dev Container use
`uv sync --frozen`, so they fail instead of silently resolving versions when
`pyproject.toml` and `uv.lock` disagree.
