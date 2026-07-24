import pytest

from automation.platform_detector import detect_ats_platform


@pytest.mark.parametrize("url", [
    "https://boards.greenhouse.io/acme/jobs/1234567",
    "https://job-boards.greenhouse.io/acme/jobs/1234567",
    "https://www.greenhouse.io/embed/job_app?token=abc123",
])
def test_detects_greenhouse(url):
    assert detect_ats_platform(url) == "greenhouse"


@pytest.mark.parametrize("url", [
    "https://jobs.lever.co/acme/abcd-1234",
    "https://jobs.eu.lever.co/acme/abcd-1234",
])
def test_detects_lever(url):
    assert detect_ats_platform(url) == "lever"


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/1234567",
    "https://careers.acme.com/jobs/1234",
    "https://www.indeed.com/viewjob?jk=abc123",
    "",
])
def test_unsupported_platform_returns_none(url):
    assert detect_ats_platform(url) is None


def test_html_fallback_detects_greenhouse_on_custom_domain():
    url = "https://careers.acme.com/jobs/1234"
    html = "<script src='https://boards.greenhouse.io/embed/job_app?for=acme'></script>"
    assert detect_ats_platform(url, page_html=html) == "greenhouse"


def test_html_fallback_detects_lever_on_custom_domain():
    url = "https://careers.acme.com/jobs/1234"
    html = "<div class='lever-jobs-partner' data-lever='acme'></div>"
    assert detect_ats_platform(url, page_html=html) == "lever"


def test_html_fallback_returns_none_when_no_markers_present():
    url = "https://careers.acme.com/jobs/1234"
    html = "<div>Custom in-house application form</div>"
    assert detect_ats_platform(url, page_html=html) is None
