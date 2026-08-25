#!/usr/bin/env bash

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly VENV_ACTIVATE="${PROJECT_ROOT}/.venv/bin/activate"

log() {
    printf '\n==> %s\n' "$1"
}

trap 'printf "\nSetup failed at line %s.\n" "$LINENO" >&2' ERR

cd "${PROJECT_ROOT}"

log "Validating project files"
if [[ ! -f pyproject.toml || ! -f uv.lock || ! -f app.py ]]; then
    printf 'pyproject.toml, uv.lock, and app.py must exist in %s\n' "${PROJECT_ROOT}" >&2
    exit 1
fi

if [[ ! -f .env && -f .env.sample ]]; then
    cp .env.sample .env
    printf 'Created .env from .env.sample.\n'
fi

log "Configuring repository-local Git behavior"
if ! git config --global --get-all safe.directory | grep -Fqx "${PROJECT_ROOT}"; then
    git config --global --add safe.directory "${PROJECT_ROOT}"
fi
git config --local core.autocrlf false
git config --local core.fileMode false

log "Creating the uv environment"
if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    printf 'Reusing existing uv environment at %s\n' "${PROJECT_ROOT}/.venv"
elif [[ -e "${PROJECT_ROOT}/.venv" ]]; then
    printf 'Replacing incomplete uv environment at %s\n' "${PROJECT_ROOT}/.venv"
    uv venv --clear "${PROJECT_ROOT}/.venv"
else
    uv venv "${PROJECT_ROOT}/.venv"
fi

log "Installing locked Python dependencies"
uv sync --frozen

if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    printf 'uv did not create the expected environment at %s\n' \
        "${PROJECT_ROOT}/.venv" >&2
    exit 1
fi

# Activation is needed for the remaining setup commands. VS Code also uses the
# same interpreter for newly opened terminals.
# shellcheck disable=SC1090
source "${VENV_ACTIVATE}"

log "Creating runtime directories"
mkdir -p \
    research_papers \
    vector_store \
    logs \
    tmp

log "Validating the environment"
python --version
uv --version
python -c "import sys; print(f'Python executable: {sys.executable}')"
python -c "import streamlit; print('Streamlit import: OK')"
python -c "from langchain_ollama import OllamaEmbeddings; print('Ollama integration import: OK')"

printf '\nDevelopment environment ready at %s\n' "${PROJECT_ROOT}"
