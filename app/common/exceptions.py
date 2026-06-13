class DemoRestrictionError(Exception):
    """演示账号操作限制异常。"""
    def __init__(self, message: str = "演示账号限制操作，请先在个人中心修改您的邮箱！"):
        self.message = message
        super().__init__(self.message)


class RateLimitError(Exception):
    """请求限速异常。"""
    def __init__(self, message: str = "您的请求过于频繁，请稍后再试。"):
        self.message = message
        super().__init__(self.message)

