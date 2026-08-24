FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:/opt/venv/bin:/root/.local/bin:$PATH

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Keep the environment bootstrap reproducible. The project environment itself
# is created after the repository is bind-mounted by setup.sh.
RUN pip install --no-cache-dir "uv==0.12.5"

# Install the runtime dependencies into an image-local environment. The
# Dev Container setup also creates /app/.venv after the repository is mounted.
COPY pyproject.toml uv.lock /tmp/
RUN cd /tmp \
    && UV_PROJECT_ENVIRONMENT=/tmp/.venv uv sync --frozen --no-dev \
    && cp -a /tmp/.venv /opt/venv \
    && rm -rf /tmp/.venv /tmp/pyproject.toml /tmp/uv.lock

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
