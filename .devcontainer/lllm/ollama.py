"""Load the configured Ollama model before an ADK turn starts.

A cold load returns no tokens until the weights are resident. Doing that
inside the turn makes --timeout look like a hung agent.
"""

import json
import os
import sys
import urllib.error
import urllib.request


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def model_is_loaded(base_url: str, model_name: str) -> bool:
    with urllib.request.urlopen(f"{base_url}/api/ps", timeout=5) as response:
        payload = json.load(response)
    for running_model in payload.get("models") or []:
        running_name = running_model.get("name") or running_model.get("model") or ""
        if running_name == model_name or running_name.startswith(f"{model_name}:"):
            return True
    return False


def ensure_model_loaded(
    *,
    base_url: str | None = None,
    model_name: str | None = None,
    keep_alive: str | None = None,
) -> None:
    resolved_model_name = model_name or os.environ.get("GEMMA_MODEL")
    if not resolved_model_name:
        return
    resolved_base_url = base_url or ollama_base_url()
    try:
        if model_is_loaded(resolved_base_url, resolved_model_name):
            return
    except (OSError, ValueError, json.JSONDecodeError):
        return
    print(f"lllm: loading {resolved_model_name}", file=sys.stderr, flush=True)
    request = urllib.request.Request(
        f"{resolved_base_url}/api/generate",
        data=json.dumps(
            {
                "model": resolved_model_name,
                "prompt": "ok",
                "stream": False,
                "keep_alive": keep_alive or os.environ.get("OLLAMA_KEEP_ALIVE", "5m"),
                "options": {"num_predict": 1},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            response.read()
    except (OSError, urllib.error.URLError) as error:
        print(f"lllm: could not load {resolved_model_name}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
