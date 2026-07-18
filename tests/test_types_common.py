import dataclasses

import pytest

from greentechhub_core.types import Err, FlashMessage, Ok, Result, UnwrapError

# FlashMessage


def test_flash_message_kind_defaults_to_success():
    flash = FlashMessage(message="Saved.")
    assert flash.kind == "success"


def test_flash_message_explicit_kind():
    flash = FlashMessage(message="Something went wrong.", kind="danger")
    assert flash.kind == "danger"


def test_flash_message_construction_requires_keyword_args():
    FlashMessage(message="Saved.", kind="success")
    with pytest.raises(TypeError):
        FlashMessage("Saved.", "success")


def test_flash_message_is_frozen():
    flash = FlashMessage(message="Saved.")
    with pytest.raises(dataclasses.FrozenInstanceError):
        flash.message = "Changed."


# Ok


def test_ok_is_ok():
    result = Ok[int, str](value=5)
    assert result.is_ok() is True
    assert result.is_err() is False


def test_ok_unwrap_returns_value():
    assert Ok[int, str](value=5).unwrap() == 5


def test_ok_unwrap_or_returns_value_not_default():
    assert Ok[int, str](value=5).unwrap_or(0) == 5


def test_ok_construction_requires_keyword_args():
    Ok[int, str](value=5)
    with pytest.raises(TypeError):
        Ok[int, str](5)


def test_ok_is_frozen():
    result = Ok[int, str](value=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.value = 6


def test_ok_is_a_result():
    assert isinstance(Ok[int, str](value=5), Result)


# Err


def test_err_is_err():
    result = Err[int, str](error="bad input")
    assert result.is_ok() is False
    assert result.is_err() is True


def test_err_unwrap_or_returns_default():
    assert Err[int, str](error="bad input").unwrap_or(0) == 0


def test_err_unwrap_with_non_exception_error_raises_unwrap_error():
    result = Err[int, str](error="bad input")
    with pytest.raises(UnwrapError) as exc_info:
        result.unwrap()
    assert exc_info.value.error == "bad input"


def test_err_unwrap_with_exception_error_reraises_it_directly():
    original = ValueError("boom")
    result: Err[int, ValueError] = Err(error=original)
    with pytest.raises(ValueError) as exc_info:
        result.unwrap()
    assert exc_info.value is original


def test_err_construction_requires_keyword_args():
    Err[int, str](error="bad input")
    with pytest.raises(TypeError):
        Err[int, str]("bad input")


def test_err_is_frozen():
    result = Err[int, str](error="bad input")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.error = "other"


def test_err_is_a_result():
    assert isinstance(Err[int, str](error="bad input"), Result)


# Result


def test_result_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Result()
