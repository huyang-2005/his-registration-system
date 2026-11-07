"""认证依赖：从 Authorization Bearer 或 HttpOnly Cookie 解析当前用户。"""
from fastapi import HTTPException, Request

from app import db
from app.security import decode_access_token

COOKIE_NAME = "access_token"


def _token_from_request(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def load_user_from_token(token: str):
    payload = decode_access_token(token)
    if not payload:
        return None
    user = db.query_one(
        "SELECT user_id, username, real_name, role, status FROM sys_user WHERE user_id = ?",
        (int(payload["sub"]),),
    )
    if not user or user["status"] != "启用":
        return None
    return dict(user)


def get_optional_user(request: Request):
    cached = getattr(request.state, "user", None)
    if cached:
        return cached
    token = _token_from_request(request)
    if not token:
        return None
    user = load_user_from_token(token)
    request.state.user = user
    return user


def get_current_user(request: Request):
    user = get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


def require_roles(*roles):
    """依赖注入式鉴权：不满足角色返回 403。"""

    def dependency(request: Request):
        user = get_current_user(request)
        if roles and user["role"] not in roles:
            raise HTTPException(status_code=403, detail="无权限访问该功能")
        return user

    return dependency
