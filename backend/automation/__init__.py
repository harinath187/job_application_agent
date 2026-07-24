"""
Application Autofill Assist.

This package fills known applicant fields (name, email, phone, resume,
cover letter, LinkedIn) into a job application form using Playwright, for a
small, explicitly supported set of ATS platforms (Greenhouse and Lever).

Scope boundaries (intentional, not temporary limitations):
  - Only Greenhouse and Lever are supported. Any other platform is reported
    as unsupported rather than attempting to guess at an unknown form.
  - The browser never clicks the final submit button. A human always
    reviews the filled form and submits it manually.
  - The browser always runs non-headless so the user can see and control it.
  - No CAPTCHA solving, no login automation, no anti-bot bypass. If either
    is encountered, the run stops and reports it.
  - Open-ended text questions and legal/eligibility questions (e.g. work
    authorization, sponsorship) are never auto-answered; they are left
    blank and flagged in `FillResult.fields_skipped`.

This package is structurally independent of `backend/agents/` (the LLM-based
agents): it has fundamentally different dependencies (Playwright vs. LLM
calls) and failure modes (selector drift vs. model output validation).
"""
