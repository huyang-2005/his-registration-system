"""FastAPI 应用工厂：中间件、路由与统一错误处理。"""
import os
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import config, db
from app.middleware import AuditMiddleware, AuthContextMiddleware
from app.routers import (
    audit,
    auth,
    base_data,
    dashboard,
    patients,
    pharmacy,
    registration,
    report,
    schedules,
    triage,
)
from app.web import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(config.DB_PATH):
        db.init_database()
    else:
        db.run_migrations()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="门诊挂号与收费发药分系统", lifespan=lifespan)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(AuthContextMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax")
    app.mount("/static", StaticFiles(directory=os.path.join(config.BASE_DIR, "static")), name="static")

    for module in (auth, dashboard, patients, schedules, registration, pharmacy, audit, report, triage, base_data):
        app.include_router(module.router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "请求失败"
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.status_code, "message": message},
            )
        if exc.status_code == 401:
            return RedirectResponse("/login?next=" + quote(request.url.path), status_code=303)
        from app import web

        response = web.render(request, "error.html", code=exc.status_code, message=message)
        response.status_code = exc.status_code
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": 422, "message": "请求参数校验失败", "errors": exc.errors()},
        )

    return app


app = create_app()
