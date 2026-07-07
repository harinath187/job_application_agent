import pytest

from backend.utils.input_validator import validate_inputs


@pytest.mark.parametrize(
    "role, location",
    [
        ("Software Engineer", "Chennai"),
        ("Data Analyst", "Bangalore"),
        ("ENGINEER", "remote"),
    ],
)
def test_validate_inputs_accepts_valid_pairs(role, location):
    is_valid, message = validate_inputs(role, location)
    assert is_valid is True
    assert message == ""


@pytest.mark.parametrize(
    "role, location",
    [
        ("Chennai", "Software Engineer"),
        ("Mumbai", "Data Scientist"),
    ],
)
def test_validate_inputs_rejects_swapped_pairs(role, location):
    is_valid, message = validate_inputs(role, location)
    assert is_valid is False
    assert "swapped" in message.lower()


@pytest.mark.parametrize(
    "role, location",
    [
        ("Product Lead", "North Zone"),
        ("People Ops", "Hybrid"),
    ],
)
def test_validate_inputs_allows_unknown_pairs(role, location):
    is_valid, message = validate_inputs(role, location)
    assert is_valid is True
    assert message == ""


def test_validate_inputs_is_case_insensitive():
    is_valid, message = validate_inputs("software engineer", "chennai")
    assert is_valid is True
    assert message == ""
