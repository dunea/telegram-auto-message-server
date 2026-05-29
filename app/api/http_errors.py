"""路由层异常映射工具。"""

from contextlib import contextmanager
from typing import TypeAlias

from fastapi import HTTPException

ExceptionMapping: TypeAlias = tuple[type[Exception], int]


@contextmanager
def map_http_exceptions(*mappings: ExceptionMapping):
    """将业务异常映射为 HTTPException。

    说明：
    1. mappings 使用 (异常类型, 状态码) 形式；
    2. 未命中映射的异常会继续向上抛出。
    """
    try:
        yield
    except Exception as exc:
        # 先做精确类型匹配，避免父类映射提前吞掉子类映射。
        for exc_type, status_code in mappings:
            if type(exc) is exc_type:
                raise HTTPException(status_code=status_code, detail=str(exc)) from exc

        # 再做 isinstance 兜底，兼容仅配置父类映射的场景。
        for exc_type, status_code in mappings:
            if isinstance(exc, exc_type):
                raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        raise
