"""门诊统计报表：挂号量、退号率、挂号与处方收入。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app import db, web
from app.deps import require_roles
from app.services.registration import _today

router = APIRouter()


def build_report(start, end):
    by_dept = db.query(
        "SELECT dep.dept_name, COUNT(r.reg_id) AS total, "
        "  SUM(CASE WHEN r.status = '已退号' THEN 1 ELSE 0 END) AS refund, "
        "  COALESCE(SUM(CASE WHEN pay.status = '已支付' THEN pay.amount ELSE 0 END),0) AS income "
        "FROM registration r "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "LEFT JOIN payment pay ON pay.reg_id = r.reg_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? "
        "GROUP BY dep.dept_id ORDER BY dep.dept_id",
        (start, end),
    )
    presc_by_dept = db.query(
        "SELECT dep.dept_name, COALESCE(SUM(sp.amount),0) AS presc_income "
        "FROM presc_payment sp "
        "JOIN prescription pr ON pr.presc_id = sp.presc_id "
        "JOIN registration r ON r.reg_id = pr.reg_id "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "WHERE date(sp.pay_time) BETWEEN ? AND ? AND sp.status = '已支付' "
        "GROUP BY dep.dept_id",
        (start, end),
    )
    presc_map = {row["dept_name"]: row["presc_income"] for row in presc_by_dept}
    by_dept_data = []
    for row in by_dept:
        item = dict(row)
        item["presc_income"] = presc_map.get(item["dept_name"], 0)
        by_dept_data.append(item)

    by_doctor = db.query(
        "SELECT d.doctor_name, dep.dept_name, COUNT(r.reg_id) AS total "
        "FROM registration r "
        "JOIN doctor d ON d.doctor_id = r.doctor_id "
        "JOIN department dep ON dep.dept_id = d.dept_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? AND r.status <> '已退号' "
        "GROUP BY d.doctor_id ORDER BY total DESC",
        (start, end),
    )
    overall = db.query_one(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN status = '已退号' THEN 1 ELSE 0 END) AS refund "
        "FROM registration WHERE date(reg_time) BETWEEN ? AND ?",
        (start, end),
    )
    total = overall["total"] or 0
    refund = overall["refund"] or 0
    refund_rate = round(refund * 100.0 / total, 2) if total else 0.0
    income = db.query_one(
        "SELECT COALESCE(SUM(p.amount),0) AS s FROM payment p "
        "JOIN registration r ON r.reg_id = p.reg_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? AND p.status = '已支付'",
        (start, end),
    )["s"]
    presc_income = db.query_one(
        "SELECT COALESCE(SUM(amount),0) AS s FROM presc_payment "
        "WHERE date(pay_time) BETWEEN ? AND ? AND status = '已支付'",
        (start, end),
    )["s"]
    presc_count = db.query_one(
        "SELECT COUNT(*) AS c FROM prescription WHERE date(created_at) BETWEEN ? AND ?",
        (start, end),
    )["c"]
    return {
        "by_dept": by_dept_data,
        "by_doctor": by_doctor,
        "total": total,
        "refund": refund,
        "refund_rate": refund_rate,
        "income": income,
        "presc_income": presc_income,
        "presc_count": presc_count,
    }


@router.get("/report")
def report(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(require_roles("admin", "cashier")),
):
    start = start or _today()
    end = end or _today()
    data = build_report(start, end)
    return web.render(request, "report.html", start=start, end=end, **data)


@router.get("/api/report/today")
def report_today(user=Depends(require_roles("admin", "cashier"))):
    today = _today()
    return {"date": today, **build_report(today, today)}
