from app.common.error_classifier import classify_error_message, classify_exception
from app.models.enums import ErrorClass


def test_classify_exception_timeout_is_retryable() -> None:
    error_class, retryable, is_timeout = classify_exception(TimeoutError("request timeout"))
    assert error_class == ErrorClass.TIMEOUT
    assert retryable is True
    assert is_timeout is True


def test_classify_exception_auth_is_non_retryable() -> None:
    error_class, retryable, is_timeout = classify_exception(Exception("unauthorized session invalid"))
    assert error_class == ErrorClass.AUTH
    assert retryable is False
    assert is_timeout is False


def test_classify_exception_network_is_retryable() -> None:
    error_class, retryable, is_timeout = classify_exception(Exception("network connection reset by peer"))
    assert error_class == ErrorClass.NETWORK
    assert retryable is True
    assert is_timeout is False


def test_classify_exception_unknown_defaults_retryable() -> None:
    error_class, retryable, is_timeout = classify_exception(Exception("unexpected broken state"))
    assert error_class == ErrorClass.UNKNOWN
    assert retryable is True
    assert is_timeout is False


def test_classify_error_message_none() -> None:
    assert classify_error_message(None) == ErrorClass.NONE


def test_classify_error_message_auth() -> None:
    assert classify_error_message("forbidden by auth policy") == ErrorClass.AUTH


def test_classify_error_message_timeout() -> None:
    assert classify_error_message("operation timed out") == ErrorClass.TIMEOUT


def test_classify_error_message_unknown() -> None:
    assert classify_error_message("something strange happened") == ErrorClass.UNKNOWN
