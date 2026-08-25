FROM python:3.12-slim

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir "uv==0.12.5" \
    && uv sync --frozen --no-dev

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
