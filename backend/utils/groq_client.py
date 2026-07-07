"""Reusable Groq client helper with retry logic for rate limits."""

from __future__ import annotations

import logging
import os
import time

from groq import Groq, RateLimitError


logger = logging.getLogger(__name__)


def groq_call(prompt: str, model: str = "llama3-8b-8192", max_tokens: int = 1000) -> str:
    """Call Groq with retry handling for rate limits and return response text."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    client = Groq(api_key=api_key)
    retries = 3
    wait = 2

    last_error: RateLimitError | None = None
    for attempt in range(retries):
        try:
            message = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.choices[0].message.content.strip()
        except RateLimitError as error:
            last_error = error
            if attempt == retries - 1:
                raise
            logger.warning(
                "Groq rate limit hit. Retry %s/%s after %ss",
                attempt + 1,
                retries,
                wait,
            )
            time.sleep(wait)
            wait *= 2

    if last_error is not None:
        raise last_error

    raise RuntimeError("Groq call failed unexpectedly.")
