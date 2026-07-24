"""
Lever adapter for Application Autofill Assist.

Fills the standard Lever "Apply for this job" form fields (name, email,
phone, resume, LinkedIn URL). Lever doesn't have a separate cover letter
upload on its standard form, so `cover_letter_path` is reported as skipped
when supplied. Anything Lever renders beyond the standard fields (Lever's
"Additional Information" custom questions) is routed to `fields_skipped`
rather than guessed at.
"""
import logging

from playwright.async_api import Page

from automation.adapters.base import ApplicantData, ATSAdapter, FillResult, SkippedField

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Standard Lever application form field names.
NAME_SELECTOR = "input[name='name']"
EMAIL_SELECTOR = "input[name='email']"
PHONE_SELECTOR = "input[name='phone']"
RESUME_UPLOAD_SELECTOR = "input[name='resume'], .application-file-input input[type='file']"
LINKEDIN_SELECTOR = "input[name='urls[LinkedIn]'], input[name*='LinkedIn' i]"

# Company-defined custom questions Lever renders under "Additional Information".
CUSTOM_QUESTION_CONTAINER_SELECTOR = ".application-question:not(:has(input[name='name'])):not(:has(input[name='email'])):not(:has(input[name='phone']))"


async def _fill_if_present(context, selector: str, value: str) -> bool:
    """Fill `selector` with `value` if it's present on the form; return whether it was filled."""
    locator = context.locator(selector).first
    if await locator.count() == 0:
        return False
    await locator.fill(value)
    return True


async def _set_file_if_present(context, selector: str, file_path: str) -> bool:
    locator = context.locator(selector).first
    if await locator.count() == 0:
        return False
    await locator.set_input_files(file_path)
    return True


class LeverAdapter(ATSAdapter):
    """Fills the standard Lever application form fields."""

    async def fill_application(self, page: Page, applicant_data: ApplicantData) -> FillResult:
        fields_filled = []
        fields_skipped = []

        if await _fill_if_present(page, NAME_SELECTOR, applicant_data.name):
            fields_filled.append("name")
        else:
            fields_skipped.append(SkippedField(field_name="name", reason="field not found on form"))

        if await _fill_if_present(page, EMAIL_SELECTOR, applicant_data.email):
            fields_filled.append("email")
        else:
            fields_skipped.append(SkippedField(field_name="email", reason="field not found on form"))

        if applicant_data.phone:
            if await _fill_if_present(page, PHONE_SELECTOR, applicant_data.phone):
                fields_filled.append("phone")
            else:
                fields_skipped.append(SkippedField(field_name="phone", reason="field not found on form"))

        if applicant_data.resume_path:
            if await _set_file_if_present(page, RESUME_UPLOAD_SELECTOR, applicant_data.resume_path):
                fields_filled.append("resume")
            else:
                fields_skipped.append(SkippedField(field_name="resume", reason="upload field not found on form"))

        if applicant_data.cover_letter_path:
            fields_skipped.append(SkippedField(field_name="cover_letter", reason="Lever's standard form has no separate cover letter upload field"))

        if applicant_data.linkedin_url:
            if await _fill_if_present(page, LINKEDIN_SELECTOR, applicant_data.linkedin_url):
                fields_filled.append("linkedin_url")
            else:
                fields_skipped.append(SkippedField(field_name="linkedin_url", reason="no LinkedIn field on this form"))

        custom_questions = page.locator(CUSTOM_QUESTION_CONTAINER_SELECTOR)
        custom_count = await custom_questions.count()
        for i in range(custom_count):
            label_text = await custom_questions.nth(i).inner_text()
            fields_skipped.append(SkippedField(
                field_name=(label_text.strip().splitlines()[0] if label_text.strip() else f"custom_question_{i}"),
                reason="requires manual input: company-specific question",
            ))

        return FillResult(fields_filled=fields_filled, fields_skipped=fields_skipped, success=True)
