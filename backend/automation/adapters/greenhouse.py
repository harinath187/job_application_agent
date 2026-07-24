"""
Greenhouse adapter for Application Autofill Assist.

Fills the standard Greenhouse "For Everyone" embedded application form
fields (name, email, phone, resume, cover letter, LinkedIn URL). Anything
Greenhouse renders beyond those standard fields is a company-specific custom
question, and is routed to `fields_skipped` rather than guessed at.

Greenhouse job boards render the application form directly on the page for
most postings, but some embeds (older `boards.greenhouse.io/embed/job_app`
widgets) place the form inside an iframe, so the adapter checks for that
frame before falling back to the main page.
"""
import logging

from playwright.async_api import Page

from automation.adapters.base import ApplicantData, ATSAdapter, FillResult, SkippedField

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Standard Greenhouse application form field ids.
FIRST_NAME_SELECTOR = "#first_name"
LAST_NAME_SELECTOR = "#last_name"
EMAIL_SELECTOR = "#email"
PHONE_SELECTOR = "#phone"
RESUME_UPLOAD_SELECTOR = "#resume input[type='file'], input#resume_fieldset input[type='file'], input[name='resume']"
COVER_LETTER_UPLOAD_SELECTOR = "#cover_letter input[type='file'], input[name='cover_letter']"
LINKEDIN_SELECTOR = "input[name*='urls[LinkedIn]'], input[id*='linked_in'], input[aria-label*='LinkedIn' i]"

# Custom, company-specific questions Greenhouse renders beyond the standard
# fields above. These are never auto-answered.
CUSTOM_QUESTION_CONTAINER_SELECTOR = "#custom_fields .field, .application-question"


async def _get_form_context(page: Page):
    """Return the frame containing the Greenhouse form (iframe or main page)."""
    for frame in page.frames:
        if await frame.locator(FIRST_NAME_SELECTOR).count() > 0:
            return frame
    return page


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


class GreenhouseAdapter(ATSAdapter):
    """Fills the standard Greenhouse application form fields."""

    async def fill_application(self, page: Page, applicant_data: ApplicantData) -> FillResult:
        fields_filled = []
        fields_skipped = []

        form = await _get_form_context(page)

        name_parts = applicant_data.name.strip().split(maxsplit=1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        if first_name and await _fill_if_present(form, FIRST_NAME_SELECTOR, first_name):
            fields_filled.append("first_name")
        else:
            fields_skipped.append(SkippedField(field_name="first_name", reason="field not found on form"))

        if last_name and await _fill_if_present(form, LAST_NAME_SELECTOR, last_name):
            fields_filled.append("last_name")
        else:
            fields_skipped.append(SkippedField(field_name="last_name", reason="field not found on form or name has no last name"))

        if await _fill_if_present(form, EMAIL_SELECTOR, applicant_data.email):
            fields_filled.append("email")
        else:
            fields_skipped.append(SkippedField(field_name="email", reason="field not found on form"))

        if applicant_data.phone:
            if await _fill_if_present(form, PHONE_SELECTOR, applicant_data.phone):
                fields_filled.append("phone")
            else:
                fields_skipped.append(SkippedField(field_name="phone", reason="field not found on form"))

        if applicant_data.resume_path:
            if await _set_file_if_present(form, RESUME_UPLOAD_SELECTOR, applicant_data.resume_path):
                fields_filled.append("resume")
            else:
                fields_skipped.append(SkippedField(field_name="resume", reason="upload field not found on form"))

        if applicant_data.cover_letter_path:
            if await _set_file_if_present(form, COVER_LETTER_UPLOAD_SELECTOR, applicant_data.cover_letter_path):
                fields_filled.append("cover_letter")
            else:
                fields_skipped.append(SkippedField(field_name="cover_letter", reason="no separate cover letter upload field on this form"))

        if applicant_data.linkedin_url:
            if await _fill_if_present(form, LINKEDIN_SELECTOR, applicant_data.linkedin_url):
                fields_filled.append("linkedin_url")
            else:
                fields_skipped.append(SkippedField(field_name="linkedin_url", reason="no LinkedIn field on this form"))

        custom_questions = form.locator(CUSTOM_QUESTION_CONTAINER_SELECTOR)
        custom_count = await custom_questions.count()
        for i in range(custom_count):
            label_text = await custom_questions.nth(i).inner_text()
            fields_skipped.append(SkippedField(
                field_name=(label_text.strip().splitlines()[0] if label_text.strip() else f"custom_question_{i}"),
                reason="requires manual input: company-specific question",
            ))

        return FillResult(fields_filled=fields_filled, fields_skipped=fields_skipped, success=True)
