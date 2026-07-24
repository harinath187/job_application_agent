import asyncio
from pathlib import Path

import pytest

from automation.adapters.base import ApplicantData
from automation.adapters.greenhouse import GreenhouseAdapter

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse_form.html"


def _run(coro):
    return asyncio.run(coro)


async def _fill_fixture_form(applicant_data: ApplicantData):
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"Playwright chromium browser not installed: {e}")
        try:
            page = await browser.new_page()
            await page.goto(FIXTURE_PATH.as_uri())
            adapter = GreenhouseAdapter()
            return await adapter.fill_application(page, applicant_data)
        finally:
            await browser.close()


def test_greenhouse_adapter_fills_standard_fields_and_skips_custom_questions():
    applicant_data = ApplicantData(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="555-0100",
        resume_path=str(FIXTURE_PATH),
        cover_letter_path=str(FIXTURE_PATH),
        linkedin_url="https://linkedin.com/in/ada",
    )

    result = _run(_fill_fixture_form(applicant_data))

    assert result.success is True
    for field in ("first_name", "last_name", "email", "phone", "resume", "cover_letter", "linkedin_url"):
        assert field in result.fields_filled

    skipped_names = [f.field_name for f in result.fields_skipped]
    assert any("relocate" in name.lower() for name in skipped_names)
    assert any("why do you want" in name.lower() for name in skipped_names)


def test_greenhouse_adapter_skips_optional_fields_not_supplied():
    applicant_data = ApplicantData(name="Ada Lovelace", email="ada@example.com")

    result = _run(_fill_fixture_form(applicant_data))

    assert result.success is True
    assert "phone" not in result.fields_filled
    assert "resume" not in result.fields_filled
    assert "cover_letter" not in result.fields_filled
    assert "linkedin_url" not in result.fields_filled
