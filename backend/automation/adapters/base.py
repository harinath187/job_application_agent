"""
Adapter interface for Application Autofill Assist.

Each supported ATS platform (Greenhouse, Lever) implements `ATSAdapter`
against its own form structure. Adapters only fill known, unambiguous
fields; anything else (custom company questions, open-ended text, legal/
eligibility questions) is routed to `FillResult.fields_skipped` for the user
to complete manually. Adapters never click submit.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from playwright.async_api import Page
from pydantic import BaseModel, Field


class ApplicantData(BaseModel):
    """Known applicant fields available to fill into an application form."""

    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    linkedin_url: Optional[str] = None


class SkippedField(BaseModel):
    """A form field the adapter deliberately left untouched, and why."""

    field_name: str
    reason: str


class FillResult(BaseModel):
    """Outcome of an autofill attempt against a single application form."""

    fields_filled: List[str] = Field(default_factory=list)
    fields_skipped: List[SkippedField] = Field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


class ATSAdapter(ABC):
    """Base class every supported-platform adapter must implement."""

    @abstractmethod
    async def fill_application(self, page: Page, applicant_data: ApplicantData) -> FillResult:
        """
        Fill known fields into the application form loaded on `page`.

        Must not click any submit button. Fields the adapter can't fill with
        confidence (custom questions, open-ended text, eligibility/work-
        authorization questions) must be added to `FillResult.fields_skipped`
        instead of being guessed at.
        """
        raise NotImplementedError
