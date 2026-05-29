"""http_errors 工具测试。"""

import pytest
from fastapi import HTTPException

from app.api.http_errors import map_http_exceptions


def test_map_value_error_to_http_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        with map_http_exceptions((ValueError, 400)):
            raise ValueError("bad value")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "bad value"


def test_map_permission_error_to_http_403() -> None:
    with pytest.raises(HTTPException) as exc_info:
        with map_http_exceptions((PermissionError, 403)):
            raise PermissionError("forbidden")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "forbidden"


def test_unmapped_exception_should_be_raised_as_is() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with map_http_exceptions((ValueError, 400)):
            raise RuntimeError("boom")


def test_no_exception_should_pass_through() -> None:
    with map_http_exceptions((ValueError, 400), (PermissionError, 403)):
        pass


def test_exact_type_mapping_should_override_parent_mapping_order() -> None:
    with pytest.raises(HTTPException) as exc_info:
        with map_http_exceptions((Exception, 500), (ValueError, 400)):
            raise ValueError("bad value")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "bad value"
