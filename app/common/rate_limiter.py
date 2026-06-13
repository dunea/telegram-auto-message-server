import time
from collections import defaultdict
from typing import List, Tuple
from app.config import get_settings

class InMemorySlidingWindowRateLimiter:
    """基于内存滑动窗口的限速器。
    
    用于限制指定 IP 在各个时间窗口内的请求频次，防止接口被恶意刷量。
    """
    
    def __init__(self, rules: List[Tuple[int, int, str]] = None):
        # 存储结构：{ip: [timestamp1, timestamp2, ...]}
        self._history = defaultdict(list)
        self._rules = rules
        
    @property
    def rules(self) -> List[Tuple[int, int, str]]:
        """获取当前配置的限速规则。
        
        解析 Settings 中的 rate_limit_try_now_rules 配置。
        规则格式为：[(时间窗口秒数, 最大次数, 友好描述)]
        """
        if self._rules is not None:
            return self._rules
        settings = get_settings()
        raw_rules = getattr(settings, "rate_limit_try_now_rules", "60:3,900:5,3600:10,86400:20")
        rules = []
        for item in raw_rules.split(","):
            if not item.strip():
                continue
            parts = item.split(":")
            if len(parts) == 2:
                try:
                    duration = int(parts[0])
                    max_requests = int(parts[1])
                    # 生成友好的中文时间描述
                    if duration < 60:
                        desc = f"{duration}秒"
                    elif duration < 3600:
                        desc = f"{duration // 60}分钟"
                    elif duration < 86400:
                        desc = f"{duration // 3600}小时"
                    else:
                        desc = f"{duration // 86400}天"
                    rules.append((duration, max_requests, desc))
                except ValueError:
                    pass
        
        # 默认兜底配置
        if not rules:
            rules = [
                (60, 3, "1分钟"),
                (900, 5, "15分钟"),
                (3600, 10, "1小时"),
                (86400, 20, "24小时")
            ]
        return rules

    def check_and_record(self, ip: str) -> Tuple[bool, str]:
        """检查指定 IP 是否超出限速阈值。
        
        如果没有超出限制，则记录本次请求并返回 True；
        如果超出限制，则返回 False 以及对应的等待提示信息。
        """
        now = time.time()
        timestamps = self._history[ip]
        rules = self.rules
        
        # 1. 清理超过最大时间窗口的历史记录，避免内存膨胀
        max_window = max(rule[0] for rule in rules) if rules else 86400
        cutoff = now - max_window
        timestamps = [t for t in timestamps if t > cutoff]
        self._history[ip] = timestamps
        
        # 2. 内存清理机制：如果 IP 字典项过多，清理其他 IP 的过期项，避免恶意代理 IP 攻击导致内存泄漏
        if len(self._history) > 5000:
            inactive_ips = [k for k, v in self._history.items() if not v or max(v) <= cutoff]
            for k in inactive_ips:
                self._history.pop(k, None)
        
        # 3. 依次验证各个时间窗口的请求频次限制
        for duration, max_requests, desc in rules:
            window_start = now - duration
            count = sum(1 for t in timestamps if t > window_start)
            if count >= max_requests:
                # 计算需要等待多少时间以获得下一次请求配额
                window_timestamps = [t for t in timestamps if t > window_start]
                window_timestamps.sort()
                earliest_t = window_timestamps[0]
                wait_seconds = int(earliest_t + duration - now)
                if wait_seconds < 1:
                    wait_seconds = 1
                
                # 转换等待时间描述
                if wait_seconds < 60:
                    wait_desc = f"{wait_seconds}秒"
                elif wait_seconds < 3600:
                    wait_desc = f"{wait_seconds // 60}分钟"
                else:
                    wait_desc = f"{wait_seconds // 3600}小时"
                
                return False, f"免注册体验过于频繁。在{desc}内最多允许{max_requests}次，请在{wait_desc}后再试。"
                
        # 4. 校验通过，记录当前时间戳
        self._history[ip].append(now)
        return True, ""


# 全局唯一的限速器实例
rate_limiter = InMemorySlidingWindowRateLimiter()
