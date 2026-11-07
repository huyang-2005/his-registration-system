"""中间件：把登录用户挂到 request.state，并自动记录写操作审计日志。"""
from starlette.middleware.base import BaseHTTPMiddleware

from app.deps import get_optional_user
from app.services import audit


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = None
        if not request.url.path.startswith("/static"):
            request.state.user = get_optional_user(request)
        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response
        if request.url.path.startswith("/static"):
            return response
        if request.url.path.startswith("/api/auth/login") or request.url.path == "/login":
            return response

        classified = audit.classify(request.url.path)
        if not classified:
            return response
        action, object_type, path_id = classified
        user = getattr(request.state, "user", None)
        detail = getattr(request.state, "audit_detail", None) or (
            "%s %s -> %d" % (request.method, request.url.path, response.status_code)
        )
        if response.status_code in (401, 403):
            detail = "被拒绝：" + detail
        audit.record(user, action, object_type, path_id, detail, client_ip(request))
        return response
