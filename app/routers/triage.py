"""AI 智能分诊页面与接口（仅辅助，不决策）。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request

from app import web
from app.deps import require_roles
from app.schemas import TriageModel
from app.services import triage as triage_service

router = APIRouter()


@router.get("/triage")
def triage_page(request: Request, user=Depends(require_roles("admin", "doctor", "cashier", "pharmacist"))):
    return web.render(request, "triage.html", result=None, symptoms="")


@router.post("/triage")
def triage_form(
    request: Request,
    data: Annotated[TriageModel, Form()],
    user=Depends(require_roles("admin", "doctor", "cashier", "pharmacist")),
):
    result = triage_service.triage(data.symptoms)
    return web.render(request, "triage.html", result=result, symptoms=data.symptoms)


@router.post("/api/triage")
def triage_api(
    data: TriageModel,
    user=Depends(require_roles("admin", "doctor", "cashier", "pharmacist")),
):
    result = triage_service.triage(data.symptoms)
    return {"code": 200, "data": result}
