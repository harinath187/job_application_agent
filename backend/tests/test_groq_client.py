import types

import pytest

from utils.groq_client import GroqCallFailedError, call_groq_with_retry


class DummyRateLimitError(Exception):
    def __init__(self, message="rate limited", status_code=429):
        super().__init__(message)
        self.status_code = status_code
        self.response = types.SimpleNamespace(headers={"Retry-After": "2"})


class DummyClient:
    def __init__(self, excs):
        self._excs = list(excs)
        self.calls = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        if self._excs:
            exc = self._excs.pop(0)
            raise exc
        return {"ok": True}


def test_call_groq_with_retry_retries_and_raises_clear_error(monkeypatch):
    client = DummyClient([DummyRateLimitError(), DummyRateLimitError(), DummyRateLimitError(), DummyRateLimitError()])
    sleep_calls = []
    monkeypatch.setattr("utils.groq_client.time.sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(GroqCallFailedError):
        call_groq_with_retry(client, model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert client.calls == 4
    assert sleep_calls == [2, 2, 2]
