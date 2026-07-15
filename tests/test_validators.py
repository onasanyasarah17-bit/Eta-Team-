import pytest

from app.utils.validators import (
    ValidationError,
    decode_start_key,
    encode_start_key,
    parse_page_limit,
    validate_employee_id,
)


def test_validate_employee_id_accepts_normal_ids():
    assert validate_employee_id(" EMP001 ") == "EMP001"


@pytest.mark.parametrize(
    "value",
    ["", "   ", "bad id", "EMP@1", "x" * 65],
)
def test_validate_employee_id_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        validate_employee_id(value)


def test_parse_page_limit_defaults_and_bounds():
    assert parse_page_limit(None) is None
    assert parse_page_limit("25") == 25
    with pytest.raises(ValidationError):
        parse_page_limit("0")
    with pytest.raises(ValidationError):
        parse_page_limit("abc")


def test_start_key_round_trip():
    original = {"employeeId": "EMP001"}
    token = encode_start_key(original)
    assert decode_start_key(token) == original
    assert encode_start_key(None) is None
    with pytest.raises(ValidationError):
        decode_start_key("not-a-valid-token")
