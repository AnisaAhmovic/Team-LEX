# COPL-253: Qwen3 (Ollama) Local Generation Service Setup

Covers: confirming the Qwen3 model/version, installing Ollama, pulling
the model, recording configuration, testing inference (CLI, raw API, and
Python), and the reusable `llm` service other backend code should call.

**Important - per requirement 14 of COPL-253:** Qwen3 is a generation
layer only. It is never the source of policy facts - validated retrieval
(the `retrieval` package, COPL-183/onward) remains the sole source of
policy evidence. Any prompt that needs policy content must have that
content supplied directly in the prompt (e.g. retrieved chunks appended
to it), not recalled from the model's own knowledge.

## 1. Confirm model/version and hardware fit

Qwen3 ships in several sizes. The two realistic options for a laptop
running Ollama locally:

| Tag | Approx. RAM needed | Notes |
|---|---|---|
| `qwen3:4b` | ~8GB, no GPU required | **Default for this project.** Runs on any team laptop, including the modest hardware some of us are on. |
| `qwen3:8b` | ~16GB, or a GPU with ~5GB VRAM | Noticeably better quality. Only use if your machine comfortably has the RAM to spare. |

Before assuming a size will work, check your actual available RAM:

- Windows: Task Manager → Performance → Memory
- Mac: Apple menu → About This Mac → Memory

**Default for the team: `qwen3:4b`.** This is set in `llm/config.py` and
overridable per-machine via `.env` (see step 4) - if your machine can
comfortably run `qwen3:8b`, set that locally without needing to change
code. Confirm as a team in the ticket if a different shared default is
wanted before merging.

## 2. Install Ollama

- **Windows/Mac:** download the installer from https://ollama.com/download
  and run it. Ollama runs as a background service after install.
- **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`

Verify it's installed and running:

```bash
ollama --version
```

## 3. Pull the model

```bash
ollama pull qwen3:4b
```

This downloads roughly 2.5GB. If your machine can run the larger model
instead:

```bash
ollama pull qwen3:8b
```

Check it's available locally:

```bash
ollama list
```

## 4. Configure environment variables

Add these lines to your `.env` (copy from `.env.example` if you haven't
already per `docs/SETUP.md`):

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_KEEP_ALIVE=5m
```

Only change `OLLAMA_MODEL` if you've pulled a different tag in step 3
and confirmed your machine can run it well.

Install the one additional Python dependency:

```bash
pip install -r requirements.txt -r requirements-llm.txt
```

## 5. Record the configuration

```bash
python -m llm.config
```

This prints the active configuration and writes it to `llm/llm_config.json`
as a timestamped evidence record - the exact model, base URL, timeout,
and keep-alive setting in use.

## 6. Run a simple local prompt and observe behaviour/latency

Quick sanity check straight from the CLI:

```bash
ollama run qwen3:4b "Say hello in one sentence."
```

The first prompt after Ollama starts (or after the model has been idle)
is noticeably slower, since the model has to load into memory first.
Note down what you observe as an initial latency record for the ticket,
e.g.:

- First prompt (cold start): ~X seconds
- Second prompt (model already loaded): ~Y seconds

This is expected behaviour, not a bug - `OLLAMA_KEEP_ALIVE` controls how
long the model stays loaded in memory between requests (default `5m`
here) so back-to-back requests stay fast.

## 7. Test Ollama's local API directly

```bash
curl http://localhost:11434/api/generate -d "{\"model\": \"qwen3:4b\", \"prompt\": \"Say hello in one sentence.\", \"stream\": false}"
```

A JSON response containing a `"response"` field with generated text
confirms the API is reachable and working, independent of any Python
code.

## 8. Test the Python client

```bash
python test_llm_service.py
```

Expected output: the model name, base URL, then a generated response,
its latency, and token counts. If Ollama isn't running, you should see
a clear `CONNECTION ERROR` message rather than a raw traceback - that's
the error handling from step 9 working as intended.

## 9. The reusable service

All Ollama calls go through `llm/client.py`'s `QwenService` class rather
than being scattered across views - the same pattern the `retrieval`
package uses for Qdrant/BGE-M3.

```python
from llm import QwenService

service = QwenService()
result = service.generate("Your prompt here")
print(result["text"])
```

In Django code called per-request, cache the instance the same way
`api/views.py` does for `PolicyRetriever`:

```python
from functools import lru_cache
from llm import QwenService

@lru_cache(maxsize=1)
def get_qwen_service():
    return QwenService()
```

Wiring this into an actual API endpoint (e.g. combining it with
`retrieval` for a full ask/answer flow) is intentionally left for a
follow-up ticket, to keep this PR focused on the generation service
itself per COPL-253's scope.

## 10. Error handling

`QwenService.generate()` raises one of four specific exceptions instead
of letting raw `requests` errors or malformed responses propagate:

| Exception | When it's raised |
|---|---|
| `LLMConnectionError` | Ollama isn't running, or `OLLAMA_BASE_URL` is wrong |
| `LLMModelNotFoundError` | The configured model tag hasn't been pulled |
| `LLMTimeoutError` | No response within `OLLAMA_TIMEOUT_SECONDS` |
| `LLMResponseError` | Ollama responded, but the payload was malformed or reported failure |

`llm.fallback_response(prompt, reason)` gives a safe, structured
placeholder to return to a caller when generation isn't available,
matching the shape `retrieval.fallback_response` already uses.

To manually confirm each error path:

- **Connection failure:** stop Ollama (`ollama stop` or quit the app),
  then run `python test_llm_service.py` - expect a clear
  `CONNECTION ERROR` message.
- **Model not found:** temporarily set `OLLAMA_MODEL=qwen3:99b` (an
  unpulled tag) in `.env` and re-run - expect `MODEL NOT FOUND`. Revert
  the env var afterwards.
- **Timeout:** temporarily set `OLLAMA_TIMEOUT_SECONDS=0.01` and re-run -
  expect `TIMEOUT`. Revert afterwards.

## 11. Files added for this ticket

```
llm/__init__.py
llm/config.py
llm/client.py
llm/exceptions.py
requirements-llm.txt
test_llm_service.py
docs/COPL-253_QWEN3_OLLAMA_SETUP.md
```

Plus two new lines added to `.env.example` (see step 4) and two to
`.gitignore`:

```
llm/llm_config.json
```

(the recorded-config file is machine-specific evidence, not something
to commit - regenerate it locally with `python -m llm.config`.)

## 12. Evidence to link on COPL-253

- Output of `ollama list` showing the pulled model.
- `python -m llm.config` output (or the generated `llm_config.json`
  contents pasted into the ticket).
- The cold-start vs warm latency observation from step 6.
- The `curl` response from step 7.
- The full terminal output of `python test_llm_service.py` from step 8.
- Terminal output from testing at least one error path in step 10 (e.g.
  the connection-failure test), to demonstrate failure handling works,
  not just the happy path.
