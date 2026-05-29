"""鉴权测试占位。当前项目未启用鉴权，仅作未来迁移占位。"""

import pytest


@pytest.mark.skip(reason="当前项目未启用鉴权，仅作未来迁移占位")
def test_auth_required_placeholder() -> None:
    """占位：未来验证受保护接口在无 Authorization 时返回 401。"""
    pass


@pytest.mark.skip(reason="当前项目未启用鉴权，仅作未来迁移占位")
def test_auth_header_format_placeholder() -> None:
    """占位：未来验证 Authorization 头格式（如 Bearer token）校验逻辑。"""
    pass
