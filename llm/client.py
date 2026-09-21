"""
Project Lex - COPL-253
Reusable backend client for local Qwen3 generation via Ollama.

Import and reuse this class rather than calling Ollama's HTTP API
directly from views or other backend code, so the model, timeout, and
error handling stay defined in one place.

Basic usage:

    from llm import QwenService

    service = QwenService()
    result = service.generate("Summarise this in one sentence: ...")
    print(result["text"])
    print(result["latency_seconds"])

In Django code that will be called on every request, wrap construction
in @lru_cache(maxsize=1) the same way api/views.py does for
PolicyRetriever, so the client isn't rebuilt per-request:

    from functools import lru_cache
    from llm import QwenService

    @lru_cache(maxsize=1)
    def get_qwen_service():
        return QwenService()
"""

import time

import requests

from llm.config import (
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)
from llm.exceptions import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMResponseError,
    LLMTimeoutError,
)


class QwenService:
    """Thin, reusable client around Ollama's /api/generate endpoint."""

    def __init__(
        self,
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        keep_alive=OLLAMA_KEEP_ALIVE,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.keep_alive = keep_alive

    def generate(self, prompt, system=None, think=False, response_format=None, options=None):
        """
        Submit a prompt to the configured Qwen3 model and return the
        response.

        Args:
            prompt: The user-facing prompt text.
            system: Optional system instruction (e.g. tone/format rules).
            think: Whether to enable Qwen3's thinking mode. Left off by
                default for lower latency on straightforward generation
                tasks; enable for prompts that need multi-step reasoning.
            response_format: Optional Ollama JSON schema or "json" format.
            options: Optional inference settings, such as temperature and seed.

        Returns:
            dict with keys: text, model, latency_seconds, done,
            prompt_eval_count, eval_count (the last two are token counts
            Ollama reports, useful for observing behaviour per subtask 6).

        Raises:
            LLMConnectionError: Ollama isn't running or isn't reachable
                at the configured base_url.
            LLMModelNotFoundError: the configured model tag hasn't been
                pulled yet.
            LLMTimeoutError: the request exceeded timeout_seconds.
            LLMResponseError: Ollama responded but the payload was
                malformed or reported a failure.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": think,
            "keep_alive": self.keep_alive,
        }
        if response_format is not None:
            payload["format"] = response_format
        if options is not None:
            payload["options"] = options
        if system:
            payload["system"] = system

        start = time.monotonic()
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise LLMTimeoutError(
                f"Ollama did not respond within {self.timeout_seconds}s "
                f"(model={self.model})."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise LLMConnectionError(
                f"Could not reach Ollama at {self.base_url}. "
                "Confirm Ollama is running (`ollama serve` or the Ollama "
                "app) and OLLAMA_BASE_URL is correct."
            ) from exc

        latency_seconds = time.monotonic() - start

        if response.status_code == 404:
            raise LLMModelNotFoundError(
                f"Model '{self.model}' is not available on this Ollama "
                f"instance. Pull it first: ollama pull {self.model}"
            )
        if response.status_code != 200:
            raise LLMResponseError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseError("Ollama response was not valid JSON.") from exc

        if not isinstance(data, dict) or not isinstance(data.get("response"), str):
            raise LLMResponseError(f"Unexpected Ollama response shape: {data}")

        return {
            "text": data["response"],
            "model": data.get("model", self.model),
            "latency_seconds": round(latency_seconds, 3),
            "done": data.get("done", True),
            "done_reason": data.get("done_reason"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
        }


def fallback_response(prompt, reason):
    """
    A safe, structured response to return instead of a generation result
    when Qwen3 is unavailable - mirrors retrieval.fallback_response so
    callers that combine both services get a consistent shape.
    """
    return {
        "text": None,
        "model": None,
        "prompt": prompt,
        "reason": reason,
        "message": "Generation is temporarily unavailable. Please try again shortly.",
    }

