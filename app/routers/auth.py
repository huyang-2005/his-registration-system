"""登录、登出与 /me 接口。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import JSONResponse

from app import config, db, security, web
from app.deps import COOKIE_NAME, get_current_user
from app.middleware import client_ip
from app.schemas import LoginModel
from app.services import audit

router = APIRouter()


def authenticate(username: str, password: str):
    user = db.query_one("SELECT * FROM sys_user WHERE username = ?", (username.strip(),))
    if not user or user["status"] != "启用":
        return None
    if not security.verify_password(password, user["password_hash"]):
        return None
    return dict(user)


def _issue(request: Request, user):
    token = security.create_access_token(user)
    request.session["username"] = user["username"]
    return token


@router.get("/login")
def login_page(request: Request, next: str = Query("/")):
    if getattr(request.state, "user", None):
        return web.redirect("/")
    return web.render(request, "login.html", next=next, error=None)


@router.post("/login")
def login_submit(
    request: Request, data: Annotated[LoginModel, Form()], next: str = Query("/")
):
    user = authenticate(data.username, data.password)
    if not user:
        audit.record(None, "登录失败", "user", data.username, "用户名或密码错误", client_ip(request))
        return web.render(
            request, "login.html", next=next, error="用户名或密码错误，或账号已停用"
        )
    audit.record(user, "登录", "user", user["user_id"], "登录成功", client_ip(request))
    response = web.redirect(next or "/")
    response.set_cookie(
        COOKIE_NAME,
        _issue(request, user),
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=config.COOKIE_SECURE,
    )
    return response


@router.post("/api/auth/login")
def api_login(request: Request, data: LoginModel):
    user = authenticate(data.username, data.password)
    if not user:
        audit.record(None, "登录失败", "user", data.username, "用户名或密码错误", client_ip(request))
        return JSONResponse(status_code=401, content={"code": 401, "message": "用户名或密码错误"})
    audit.record(user, "登录", "user", user["user_id"], "API 登录成功", client_ip(request))
    token = _issue(request, user)
    return {
        "code": 200,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "real_name": user["real_name"],
            "role": user["role"],
            "role_name": config.ROLE_NAMES.get(user["role"], user["role"]),
        },
    }


@router.get("/api/auth/me")
def api_me(user=Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "real_name": user["real_name"],
        "role": user["role"],
        "role_name": config.ROLE_NAMES.get(user["role"], user["role"]),
    }


@router.post("/logout")
def logout(request: Request):
    user = getattr(request.state, "user", None)
    if user:
        audit.record(user, "登出", "user", user["user_id"], "退出登录", client_ip(request))
    request.session.clear()
    response = web.redirect("/login")
    response.delete_cookie(COOKIE_NAME)
    return response
