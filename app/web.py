"""模板渲染与 Flask 风格兼容工具（flash / redirect / url_for）。"""
import os
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import config

templates = Jinja2Templates(directory=os.path.join(config.BASE_DIR, "templates"))


def url_for(request: Request, name: str, **path_params):
    if name == "static":
        return "/static/" + path_params.get("filename", "")

    def find_path_keys(routes):
        for route in routes:
            if getattr(route, "name", None) == name:
                return set(getattr(route, "param_convertors", {}).keys())
            found = find_path_keys(getattr(route, "routes", []) or [])
            if found is not None:
                return found
            orig = getattr(route, "original_router", None)
            if orig is not None:
                found = find_path_keys(getattr(orig, "routes", []) or [])
                if found is not None:
                    return found
        return None

    path_keys = find_path_keys(request.app.routes) or set()
    url = request.app.url_path_for(
        name, **{k: v for k, v in path_params.items() if k in path_keys}
    )
    query = {k: v for k, v in path_params.items() if k not in path_keys}
    if query:
        url = str(url) + "?" + urlencode(query)
    return str(url)


def flash(request: Request, message: str, category: str = "success"):
    request.session.setdefault("_flashes", []).append((category, message))


def get_flashed_messages(request: Request):
    return request.session.pop("_flashes", [])


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


def render(request: Request, template_name: str, **context):
    context.setdefault("request", request)
    context["url_for"] = lambda name, **params: url_for(request, name, **params)
    context["get_flashed_messages"] = lambda with_categories=False: get_flashed_messages(request)
    context["current_user"] = getattr(request.state, "user", None)
    return templates.TemplateResponse(request, template_name, context)
