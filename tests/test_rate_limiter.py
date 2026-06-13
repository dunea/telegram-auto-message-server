import time
from unittest.mock import patch
import pytest
from app.common.rate_limiter import InMemorySlidingWindowRateLimiter
from app.config import Settings, get_settings


def test_rate_limiter_basic_flow():
    """测试限速器的基本功能，包含 1分钟内限制 3 次。"""
    limiter = InMemorySlidingWindowRateLimiter(rules=[
        (60, 3, "1分钟"),
        (900, 5, "15分钟"),
    ])
    
    ip = "127.0.0.1"
    
    # 前3次应当通过
    allowed, msg = limiter.check_and_record(ip)
    assert allowed is True
    assert msg == ""
    
    allowed, msg = limiter.check_and_record(ip)
    assert allowed is True
    
    allowed, msg = limiter.check_and_record(ip)
    assert allowed is True
    
    # 第4次应当被拦截
    allowed, msg = limiter.check_and_record(ip)
    assert allowed is False
    assert "1分钟内最多允许3次" in msg


def test_rate_limiter_sliding_window_expiry():
    """测试滑动窗口随时间推移释放配额。"""
    limiter = InMemorySlidingWindowRateLimiter(rules=[
        (10, 2, "10秒"),  # 10秒内最多允许2次
    ])
    
    ip = "192.168.1.1"
    start_time = 1700000000.0
    
    with patch("time.time") as mock_time:
        mock_time.return_value = start_time
        
        # 第一次请求
        allowed, _ = limiter.check_and_record(ip)
        assert allowed is True
        
        # 0.5秒后第二次请求
        mock_time.return_value = start_time + 0.5
        allowed, _ = limiter.check_and_record(ip)
        assert allowed is True
        
        # 1.0秒后第三次请求，应当被限速
        mock_time.return_value = start_time + 1.0
        allowed, msg = limiter.check_and_record(ip)
        assert allowed is False
        assert "请在9秒后再试" in msg or "请在10秒后再试" in msg
        
        # 10.1秒后再次请求（距离第一次已过去 10.1秒，释放 1 个配额）
        mock_time.return_value = start_time + 10.1
        allowed, _ = limiter.check_and_record(ip)
        assert allowed is True  # 此时应允许通过
        
        # 接着请求应当又被限速，因为此时 10秒窗口里有 start_time+0.5 (距离当前9.6秒) 和 start_time+10.1 (距离当前0秒)
        mock_time.return_value = start_time + 10.2
        allowed, _ = limiter.check_and_record(ip)
        assert allowed is False


def test_rate_limiter_memory_cleanup():
    """测试内存清理机制，防止字典无限膨胀。"""
    limiter = InMemorySlidingWindowRateLimiter(rules=[
        (10, 1, "10秒"),
    ])
    
    # 模拟写入 6000 个 IP
    for i in range(6000):
        limiter._history[f"10.0.0.{i}"].append(time.time() - 20)  # 时间全部已过期
        
    assert len(limiter._history) == 6000
    
    # 触发一次新的检查，应触发清理
    allowed, _ = limiter.check_and_record("192.168.1.1")
    assert allowed is True
    
    # 清理后长度应该大幅缩减（只剩下活跃/未过期的 IP，这里应该大部分被清理）
    assert len(limiter._history) < 100
