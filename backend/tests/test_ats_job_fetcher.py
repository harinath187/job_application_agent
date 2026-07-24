import pytest
import requests

from agents import ats_job_fetcher as fetcher


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, raise_error=None):
        self.status_code = status_code
        self._json_data = json_data
        self._raise_error = raise_error

    def raise_for_status(self):
        if self._raise_error:
            raise self._raise_error

    def json(self):
        return self._json_data


class _BadJsonResponse:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        raise ValueError("invalid json")


# --- detect_ats_source -------------------------------------------------

@pytest.mark.parametrize("url,expected_identifier,expected_posting_id", [
    ("https://boards.greenhouse.io/acme/jobs/1234567", "acme", "1234567"),
    ("https://job-boards.greenhouse.io/acme/jobs/1234567", "acme", "1234567"),
    ("https://boards.greenhouse.io/acme", "acme", None),
])
def test_detect_greenhouse_source(url, expected_identifier, expected_posting_id):
    result = fetcher.detect_ats_source(url)
    assert result["platform"] == "greenhouse"
    assert result["identifier"] == expected_identifier
    assert result["posting_id"] == expected_posting_id


@pytest.mark.parametrize("url,expected_identifier,expected_posting_id", [
    ("https://jobs.lever.co/acme/abcd-1234", "acme", "abcd-1234"),
    ("https://jobs.eu.lever.co/acme/abcd-1234", "acme", "abcd-1234"),
    ("https://jobs.lever.co/acme", "acme", None),
])
def test_detect_lever_source(url, expected_identifier, expected_posting_id):
    result = fetcher.detect_ats_source(url)
    assert result["platform"] == "lever"
    assert result["identifier"] == expected_identifier
    assert result["posting_id"] == expected_posting_id


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/1234567",
    "https://www.ziprecruiter.com/jobs/1234",
    "",
])
def test_detect_unsupported_source(url):
    result = fetcher.detect_ats_source(url)
    assert result["platform"] == "unsupported"
    assert result["identifier"] is None


# --- fetch_greenhouse_jobs ----------------------------------------------

def test_fetch_greenhouse_jobs_normalizes_response(monkeypatch):
    payload = {
        "jobs": [
            {
                "id": 1234567,
                "title": " Backend Engineer ",
                "location": {"name": "Remote"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/1234567",
                "content": "<p>Job description</p>",
                "departments": [{"name": "Engineering"}],
            }
        ]
    }
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    jobs = fetcher.fetch_greenhouse_jobs("acme")

    assert len(jobs) == 1
    assert jobs[0] == {
        "id": "1234567",
        "title": "Backend Engineer",
        "location": "Remote",
        "applyUrl": "https://boards.greenhouse.io/acme/jobs/1234567",
        "description": "<p>Job description</p>",
        "department": "Engineering",
    }


def test_fetch_greenhouse_jobs_returns_empty_on_404(monkeypatch):
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _FakeResponse(404))
    assert fetcher.fetch_greenhouse_jobs("does-not-exist") == []


def test_fetch_greenhouse_jobs_returns_empty_on_network_failure(monkeypatch):
    def fake_get(*a, **k):
        raise requests.RequestException("connection failed")
    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    assert fetcher.fetch_greenhouse_jobs("acme") == []


def test_fetch_greenhouse_jobs_returns_empty_on_invalid_json(monkeypatch):
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _BadJsonResponse())
    assert fetcher.fetch_greenhouse_jobs("acme") == []


# --- fetch_lever_jobs -----------------------------------------------------

def test_fetch_lever_jobs_normalizes_response(monkeypatch):
    payload = [
        {
            "id": "abcd-1234",
            "text": " Software Engineer ",
            "categories": {"location": "Bangalore", "department": "Engineering"},
            "hostedUrl": "https://jobs.lever.co/acme/abcd-1234",
            "descriptionPlain": "Job description text",
        }
    ]
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _FakeResponse(200, payload))

    jobs = fetcher.fetch_lever_jobs("acme")

    assert len(jobs) == 1
    assert jobs[0] == {
        "id": "abcd-1234",
        "title": "Software Engineer",
        "location": "Bangalore",
        "applyUrl": "https://jobs.lever.co/acme/abcd-1234",
        "description": "Job description text",
        "department": "Engineering",
    }


def test_fetch_lever_jobs_returns_empty_on_404(monkeypatch):
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _FakeResponse(404))
    assert fetcher.fetch_lever_jobs("does-not-exist") == []


def test_fetch_lever_jobs_returns_empty_on_network_failure(monkeypatch):
    def fake_get(*a, **k):
        raise requests.RequestException("connection failed")
    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    assert fetcher.fetch_lever_jobs("acme") == []


def test_fetch_lever_jobs_returns_empty_on_unexpected_shape(monkeypatch):
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _FakeResponse(200, {"unexpected": "shape"}))
    assert fetcher.fetch_lever_jobs("acme") == []


# --- get_job_details --------------------------------------------------------

def test_get_job_details_returns_matching_greenhouse_job(monkeypatch):
    jobs = [
        {"id": "1", "title": "A", "location": "", "applyUrl": "https://boards.greenhouse.io/acme/jobs/1", "description": "", "department": ""},
        {"id": "1234567", "title": "Backend Engineer", "location": "Remote", "applyUrl": "https://boards.greenhouse.io/acme/jobs/1234567", "description": "desc", "department": "Engineering"},
    ]
    monkeypatch.setattr(fetcher, "fetch_greenhouse_jobs", lambda token: jobs)

    result = fetcher.get_job_details("https://boards.greenhouse.io/acme/jobs/1234567")

    assert result["id"] == "1234567"
    assert result["title"] == "Backend Engineer"


def test_get_job_details_returns_matching_lever_job(monkeypatch):
    jobs = [
        {"id": "abcd-1234", "title": "Software Engineer", "location": "Bangalore", "applyUrl": "https://jobs.lever.co/acme/abcd-1234", "description": "desc", "department": "Engineering"},
    ]
    monkeypatch.setattr(fetcher, "fetch_lever_jobs", lambda slug: jobs)

    result = fetcher.get_job_details("https://jobs.lever.co/acme/abcd-1234")

    assert result["id"] == "abcd-1234"


def test_get_job_details_returns_none_for_unsupported_platform():
    assert fetcher.get_job_details("https://www.linkedin.com/jobs/view/123") is None


def test_get_job_details_returns_none_when_board_fetch_fails(monkeypatch):
    monkeypatch.setattr(fetcher, "fetch_greenhouse_jobs", lambda token: [])
    assert fetcher.get_job_details("https://boards.greenhouse.io/acme/jobs/1234567") is None


def test_get_job_details_returns_none_when_no_matching_posting(monkeypatch):
    jobs = [{"id": "999", "title": "Other", "location": "", "applyUrl": "https://boards.greenhouse.io/acme/jobs/999", "description": "", "department": ""}]
    monkeypatch.setattr(fetcher, "fetch_greenhouse_jobs", lambda token: jobs)
    assert fetcher.get_job_details("https://boards.greenhouse.io/acme/jobs/1234567") is None
