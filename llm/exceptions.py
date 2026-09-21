"""
Exceptions for Project Lex's local Qwen3 generation service (COPL-253).

Kept as distinct classes (rather than one generic error) so calling code
can decide how to react - e.g. surface a "model is starting up, retry
shortly" message for a timeout, versus "generation is temporarily
unavailable" for a connection failure.
"""


class LLMServiceError(Exception):
    """Base class for all LLM service errors."""


class LLMConnectionError(LLMServiceError):
    """Raised when Ollama cannot be reached at all (not running, wrong URL)."""


class LLMModelNotFoundError(LLMServiceError):
    """Raised when the configured model tag has not been pulled in Ollama."""


class LLMTimeoutError(LLMServiceError):
    """Raised when a request to Ollama does not complete within the timeout."""


class LLMResponseError(LLMServiceError):
    """Raised when Ollama responds, but the response is malformed or reports
    a generation failure."""
