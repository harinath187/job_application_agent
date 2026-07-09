import logging
import time
from typing import Any

try:
    from groq import RateLimitError as GroqRateLimitError
except Exception:  # pragma: no cover - fallback for environments without the SDK
    GroqRateLimitError = None

logger = logging.getLogger(__name__)


class GroqCallFailedError(RuntimeError):
    """Raised when Groq requests repeatedly fail due to rate limiting or other retriable transport errors."""

    def __init__(self, message: str, attempts: int = 0, retry_after: int | None = None):
        super().__init__(message)
        self.attempts = attempts
        self.retry_after = retry_after


def _is_rate_limit_error(exc: Exception) -> bool:
    if GroqRateLimitError is not None and isinstance(exc, GroqRateLimitError):
        return True

    if isinstance(exc, Exception):
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return True

        response = getattr(exc, "response", None)
        if response is not None:
            response_status = getattr(response, "status_code", None)
            if response_status == 429:
                return True

        message = str(exc).lower()
        if "rate limit" in message or "too many requests" in message or "429" in message:
            return True

    return False


def _get_retry_after_seconds(exc: Exception, fallback_delay: int) -> int:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)

    if headers is not None:
        if hasattr(headers, "get"):
            value = headers.get("Retry-After") or headers.get("retry-after")
        elif isinstance(headers, dict):
            value = headers.get("Retry-After") or headers.get("retry-after")
        else:
            value = None

        if value is not None:
            try:
                return max(1, int(value))
            except (TypeError, ValueError):
                pass

    return fallback_delay


def call_groq_with_retry(client: Any, *, max_retries: int = 3, base_delay: int = 5, max_delay: int = 20, **kwargs: Any) -> Any:
    """Call the Groq SDK with exponential backoff for rate-limited requests."""
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions") or not hasattr(client.chat.completions, "create"):
        raise TypeError("Groq client does not expose chat.completions.create")

    attempts = 0
    while True:
        try:
            attempts += 1
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            if not _is_rate_limit_error(exc):
                raise

            if attempts > max_retries:
                raise GroqCallFailedError(
                    f"Groq request failed after {attempts} attempts due to rate limiting.",
                    attempts=attempts,
                ) from exc

            wait_seconds = min(max_delay, base_delay * (2 ** (attempts - 1)))
            retry_after = _get_retry_after_seconds(exc, fallback_delay=wait_seconds)
            if retry_after != wait_seconds:
                wait_seconds = retry_after

            logger.warning(
                "Groq rate limit hit on attempt %s/%s; waiting %s seconds before retry",
                attempts,
                max_retries + 1,
                wait_seconds,
            )
            time.sleep(wait_seconds)
