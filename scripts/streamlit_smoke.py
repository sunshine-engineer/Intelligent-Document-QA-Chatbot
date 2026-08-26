"""Start the Streamlit app against an empty, provider-free workspace."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_health(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Streamlit exited before becoming healthy:\n{output}")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.5)
    raise TimeoutError("Streamlit did not become healthy within 30 seconds.")


def main() -> None:
    port = available_port()
    with tempfile.TemporaryDirectory(prefix="rag-startup-") as temporary_directory:
        workspace = Path(temporary_directory)
        (workspace / ".streamlit").mkdir()
        shutil.copy2(ROOT / ".streamlit" / "style.css", workspace / ".streamlit")
        (workspace / "empty-pdfs").mkdir()
        (workspace / "empty-index").mkdir()
        (workspace / "vector_store").mkdir()

        environment = os.environ.copy()
        environment.update(
            {
                "PDF_DIRECTORY": "empty-pdfs",
                "INDEX_DIRECTORY": "empty-index",
                "GROQ_API_KEY": "",
                "PYTHONPATH": str(ROOT),
            }
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "app.py"),
                "--server.headless=true",
                f"--server.port={port}",
                "--browser.gatherUsageStats=false",
            ],
            cwd=workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_health(f"http://127.0.0.1:{port}/_stcore/health", process)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
