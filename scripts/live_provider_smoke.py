"""Check live Ollama and Groq response shapes using explicitly supplied credentials.

File: scripts/live_provider_smoke.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import (  # noqa: E402
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_GROQ_API_BASE_URL,
    DEFAULT_GROQ_MODEL,
)

DEFAULT_SMOKE_TIMEOUT_SECONDS = 20.0


def request_json(
    url: str,
    payload: dict,
    headers: dict[str, str],
    *,
    timeout: float = DEFAULT_SMOKE_TIMEOUT_SECONDS,
) -> dict:
    """POST a JSON payload and decode the provider response within the request
    timeout.

    Args:
        url: Provider or server-health URL to contact.
        payload: JSON-serializable data to write or POST.
        headers: HTTP headers; caller-owned credentials must never be printed.
        timeout: Per-request timeout in seconds.

    Returns:
        Decoded JSON response from the requested provider endpoint.

    Raises:
        OSError: The network request fails, including HTTP/provider failures.
        ValueError: The response is not valid JSON.
    """
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def required(name: str) -> str:
    """Read a mandatory nonblank environment value without printing its contents.

    Args:
        name: Environment variable name to read.

    Returns:
        Stripped environment value; never included in a diagnostic message.

    Raises:
        RuntimeError: The named setting is absent or blank.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} must be configured when live provider checks are enabled."
        )
    return value


def main() -> None:
    """Read required environment values and exercise one embedding and completion
    request.

    Returns:
        None.

    Raises:
        Exception: Configuration, I/O or smoke-check failures propagate with a
            nonzero process status.
    """
    groq_api_key = required("GROQ_API_KEY")
    ollama_url = required("OLLAMA_SMOKE_URL").rstrip("/")
    llm_model = os.environ.get("LLM_MODEL", "").strip() or DEFAULT_GROQ_MODEL
    embedding_model = (
        os.environ.get("EMBEDDING_MODEL", "").strip() or DEFAULT_EMBEDDING_MODEL
    )

    groq_base_url = (
        os.environ.get("GROQ_API_BASE_URL", "").strip() or DEFAULT_GROQ_API_BASE_URL
    ).rstrip("/")
    timeout = float(
        os.environ.get("SMOKE_TIMEOUT_SECONDS", "").strip()
        or DEFAULT_SMOKE_TIMEOUT_SECONDS
    )
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("SMOKE_TIMEOUT_SECONDS must be finite and greater than zero")
    embedding_response = request_json(
        f"{ollama_url}/api/embed",
        {"model": embedding_model, "input": "CI provider health check"},
        {},
        timeout=timeout,
    )
    if not embedding_response.get("embeddings"):
        raise RuntimeError("Ollama embedding response did not contain embeddings.")

    completion_response = request_json(
        f"{groq_base_url}/chat/completions",
        {
            "model": llm_model,
            "messages": [{"role": "user", "content": "Reply with: ok"}],
            "max_tokens": 2,
        },
        {"Authorization": f"Bearer {groq_api_key}"},
        timeout=timeout,
    )
    if not completion_response.get("choices"):
        raise RuntimeError("Groq completion response did not contain choices.")


if __name__ == "__main__":
    main()
