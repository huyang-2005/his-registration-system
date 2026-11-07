"""首页看板。"""
from fastapi import APIRouter, Depends, Request

from app import db, web
from app.deps import require_roles
from app.services.registration import _today

router = APIRouter()


@router.get("/")
def index(request: Request, user=Depends(require_roles("admin", "doctor", "cashier", "pharmacist"))):
    today = _today()
    stats = {
        "today_reg": db.query_one(
            "SELECT COUNT(*) AS c FROM registration WHERE date(reg_time) = ?", (today,)
        )["c"],
        "today_refund": db.query_one(
            "SELECT COUNT(*) AS c FROM registration WHERE date(reg_time) = ? AND status = '已退号'",
            (today,),
        )["c"],
        "today_income": db.query_one(
            "SELECT COALESCE(SUM(p.amount),0) AS s FROM payment p "
            "JOIN registration r ON r.reg_id = p.reg_id "
            "WHERE date(r.reg_time) = ? AND p.status = '已支付'",
            (today,),
        )["s"],
        "presc_income": db.query_one(
            "SELECT COALESCE(SUM(amount),0) AS s FROM presc_payment "
            "WHERE date(pay_time) = ? AND status = '已支付'",
            (today,),
        )["s"],
        "patient_total": db.query_one("SELECT COUNT(*) AS c FROM patient")["c"],
        "schedule_today": db.query_one(
            "SELECT COUNT(*) AS c FROM doctor_schedule WHERE work_date = ?", (today,)
        )["c"],
        "pending_presc": db.query_one(
            "SELECT COUNT(*) AS c FROM prescription WHERE status = '待收费'"
        )["c"],
        "pending_dispense": db.query_one(
            "SELECT COUNT(*) AS c FROM prescription WHERE status = '已收费'"
        )["c"],
    }
    return web.render(request, "index.html", stats=stats, today=today)
