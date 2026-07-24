import asyncio
from unittest.mock import AsyncMock, MagicMock

import automation.runner as runner_module
from automation.adapters.base import ApplicantData


def _run(coro):
    return asyncio.run(coro)


class _FakePage:
    async def goto(self, url, wait_until=None):
        pass


class _FakeBrowser:
    def __init__(self, page):
        self._page = page

    async def new_page(self):
        return self._page

    async def close(self):
        pass


class _FakeChromium:
    def __init__(self, browser):
        self._browser = browser

    async def launch(self, headless=False):
        return self._browser


class _FakePlaywright:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)


class _FakePlaywrightContextManager:
    def __init__(self, browser):
        self._browser = browser

    async def __aenter__(self):
        return _FakePlaywright(self._browser)

    async def __aexit__(self, *exc_info):
        return False


def test_run_autofill_returns_unsupported_result_without_launching_browser(monkeypatch):
    launch_called = MagicMock()
    monkeypatch.setattr(runner_module, "async_playwright", lambda: launch_called())

    result = _run(runner_module.run_autofill(
        "https://www.indeed.com/viewjob?jk=abc123",
        ApplicantData(name="Ada Lovelace", email="ada@example.com"),
    ))

    assert result.success is False
    assert "unsupported" in result.error.lower()
    launch_called.assert_not_called()


def test_run_autofill_handles_missing_selector_gracefully(monkeypatch):
    page = _FakePage()
    browser = _FakeBrowser(page)
    monkeypatch.setattr(runner_module, "async_playwright", lambda: _FakePlaywrightContextManager(browser))

    async def fake_fill_application(self, page, applicant_data):
        raise Exception("Timeout waiting for selector #first_name: form structure changed")

    monkeypatch.setattr(runner_module.GreenhouseAdapter, "fill_application", fake_fill_application)

    result = _run(runner_module.run_autofill(
        "https://boards.greenhouse.io/acme/jobs/123",
        ApplicantData(name="Ada Lovelace", email="ada@example.com"),
    ))

    assert result.success is False
    assert result.error is not None
    assert result.fields_filled == []


def test_run_autofill_succeeds_and_leaves_browser_open(monkeypatch):
    page = _FakePage()
    browser = _FakeBrowser(page)
    browser.close = AsyncMock()
    monkeypatch.setattr(runner_module, "async_playwright", lambda: _FakePlaywrightContextManager(browser))

    from automation.adapters.base import FillResult

    async def fake_fill_application(self, page, applicant_data):
        return FillResult(fields_filled=["email"], fields_skipped=[], success=True)

    monkeypatch.setattr(runner_module.GreenhouseAdapter, "fill_application", fake_fill_application)

    result = _run(runner_module.run_autofill(
        "https://boards.greenhouse.io/acme/jobs/123",
        ApplicantData(name="Ada Lovelace", email="ada@example.com"),
    ))

    assert result.success is True
    assert result.fields_filled == ["email"]
    browser.close.assert_not_called()
