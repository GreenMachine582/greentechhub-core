import pytest

from greentechhub_core.types import (
    ApplicationError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

# ApplicationError (base)


def test_application_error_is_raisable_and_catchable():
    with pytest.raises(ApplicationError):
        raise ApplicationError("something went wrong")


def test_application_error_exposes_message_code_details():
    err = ApplicationError("something went wrong", details={"foo": "bar"})
    assert err.message == "something went wrong"
    assert err.code == "application_error"
    assert err.details == {"foo": "bar"}


def test_application_error_details_defaults_to_none():
    err = ApplicationError("something went wrong")
    assert err.details is None


def test_application_error_str_is_message():
    err = ApplicationError("something went wrong")
    assert str(err) == "something went wrong"


def test_application_error_code_overridable_at_construction():
    err = ApplicationError("custom", code="custom_code")
    assert err.code == "custom_code"


# Subclass default codes


@pytest.mark.parametrize(
    ("error_cls", "expected_code"),
    [
        (NotFoundError, "not_found"),
        (ValidationError, "validation_error"),
        (ConflictError, "conflict"),
        (UnauthorizedError, "unauthorized"),
        (ForbiddenError, "forbidden"),
        (BadRequestError, "bad_request"),
    ],
)
def test_subclass_default_code(error_cls, expected_code):
    err = error_cls("message")
    assert err.code == expected_code


@pytest.mark.parametrize(
    "error_cls",
    [NotFoundError, ValidationError, ConflictError, UnauthorizedError, ForbiddenError,
     BadRequestError],
)
def test_subclass_is_an_application_error(error_cls):
    assert isinstance(error_cls("message"), ApplicationError)


@pytest.mark.parametrize(
    "error_cls",
    [NotFoundError, ValidationError, ConflictError, UnauthorizedError, ForbiddenError,
     BadRequestError],
)
def test_subclass_catchable_as_application_error(error_cls):
    with pytest.raises(ApplicationError):
        raise error_cls("message")


def test_subclass_can_override_code_and_details_at_construction():
    err = NotFoundError("missing", code="user_not_found", details={"id": 42})
    assert err.code == "user_not_found"
    assert err.details == {"id": 42}


def test_validation_error_details_carries_field_errors():
    err = ValidationError("invalid input", details={"email": ["not a valid email"]})
    assert err.details == {"email": ["not a valid email"]}


# status_code: an optional HTTP status hint for adapters


@pytest.mark.parametrize(
    "error_cls",
    [ApplicationError, NotFoundError, ValidationError, ConflictError, UnauthorizedError,
     ForbiddenError, BadRequestError],
)
def test_status_code_defaults_to_none(error_cls):
    # None leaves an adapter's own type -> status mapping in charge.
    assert error_cls("message").status_code is None


def test_status_code_set_per_instance():
    err = ApplicationError("mailbox unreachable", code="email_sync_failed", status_code=503)
    assert err.status_code == 503
    assert err.code == "email_sync_failed" and err.message == "mailbox unreachable"
    assert str(err) == "mailbox unreachable" and err.details is None


def test_status_code_set_by_a_subclass_and_overridable():
    class UpstreamError(ApplicationError):
        code = "upstream_failed"
        status_code = 502

    assert UpstreamError("down").status_code == 502
    assert UpstreamError("busy", status_code=503).status_code == 503
    assert ApplicationError("base").status_code is None  # the subclass didn't leak upward
