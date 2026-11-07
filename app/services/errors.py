"""业务异常：由路由层转换为 HTTP 状态码。"""


class BusinessError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
