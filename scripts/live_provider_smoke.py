"""Opt-in CI smoke check for the configured Groq and Ollama providers."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def request_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} must be configured when live provider checks are enabled."
        )
    return value


def main() -> None:
    groq_api_key = required("GROQ_API_KEY")
    ollama_url = required("OLLAMA_SMOKE_URL").rstrip("/")
    llm_model = os.environ.get("LLM_MODEL", "").strip() or "openai/gpt-oss-20b"
    embedding_model = (
        os.environ.get("EMBEDDING_MODEL", "").strip() or "nomic-embed-text:latest"
    )

    embedding_response = request_json(
        f"{ollama_url}/api/embed",
        {"model": embedding_model, "input": "CI provider health check"},
        {},
    )
    if not embedding_response.get("embeddings"):
        raise RuntimeError("Ollama embedding response did not contain embeddings.")

    completion_response = request_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": llm_model,
            "messages": [{"role": "user", "content": "Reply with: ok"}],
            "max_tokens": 2,
        },
        {"Authorization": f"Bearer {groq_api_key}"},
    )
    if not completion_response.get("choices"):
        raise RuntimeError("Groq completion response did not contain choices.")


if __name__ == "__main__":
    main()
