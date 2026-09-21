"""
COPL-253 - manual test that the Qwen3/Ollama service works end to end.

Run from the repository root, with the venv active and Ollama running:

    python test_llm_service.py
"""

from llm import (
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMResponseError,
    LLMTimeoutError,
    QwenService,
)

service = QwenService()
print(f"Model: {service.model}")
print(f"Base URL: {service.base_url}")
print("Sending test prompt...")

try:
    result = service.generate(
        "Reply with a single short sentence confirming you're working."
    )
except LLMConnectionError as exc:
    print(f"CONNECTION ERROR: {exc}")
    raise SystemExit(1)
except LLMModelNotFoundError as exc:
    print(f"MODEL NOT FOUND: {exc}")
    raise SystemExit(1)
except LLMTimeoutError as exc:
    print(f"TIMEOUT: {exc}")
    raise SystemExit(1)
except LLMResponseError as exc:
    print(f"RESPONSE ERROR: {exc}")
    raise SystemExit(1)

print()
print(f"Response: {result['text']}")
print(f"Latency: {result['latency_seconds']}s")
print(f"Prompt tokens: {result['prompt_eval_count']}, Response tokens: {result['eval_count']}")
