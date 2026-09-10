"""
Configuration for Project Lex's local Qwen3 generation service (COPL-253).

Single source of truth for the Ollama connection and model settings, so
the client, any future callers, and the documented setup steps all agree
on the same values. Mirrors the pattern used in
ingestion/embedding_config.py for the embedding layer.

Model choice: Qwen3, served locally through Ollama.

Team hardware varies, so the exact tag is a deliberate, overridable
setting rather than hardcoded:

  qwen3:4b  - default. Runs on ~8GB RAM with no discrete GPU. Safest
              choice for a shared team default - everyone can run it.
  qwen3:8b  - noticeably better quality. Needs ~16GB RAM (or a GPU with
              ~5GB VRAM). Use this if your machine comfortably supports it
              by setting OLLAMA_MODEL=qwen3:8b in .env.

Confirm actual available RAM on your machine before assuming qwen3:8b
will run well - see docs/COPL-253_QWEN3_OLLAMA_SETUP.md step 1.

Per COPL-253 requirement 14: Qwen3 is a generation layer only. It is
never the source of policy facts - validated retrieval (the `retrieval`
package) remains the sole source of policy evidence. Any prompt sent to
this service that requires policy content must have that content
supplied in the prompt itself (e.g. retrieved chunks), not recalled by
the model.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "5m")

CONFIG_RECORD_PATH = Path("llm/llm_config.json")


def get_config():
    """Return the current LLM service configuration as a plain dict."""
    return {
        "provider": "ollama",
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }


def record_config(path=CONFIG_RECORD_PATH):
    """
    Write the current LLM configuration to disk with a timestamp, as a
    reviewable evidence artifact for COPL-253 (mirrors
    ingestion/embedding_config.py's record_config()).
    """
    record = get_config()
    record["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    output_path = record_config()
    print(f"LLM configuration recorded to {output_path}")
    print(json.dumps(get_config(), indent=2))
