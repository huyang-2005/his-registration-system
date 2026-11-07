"""医生排班与号源维护。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Request

from app import db, web
from app.deps import require_roles
from app.schemas import ScheduleCreateModel
from app.services.registration import _today

router = APIRouter()


@router.get("/schedules")
def schedules(
    request: Request,
    work_date: Optional[str] = Query(None),
    user=Depends(require_roles("admin", "cashier")),
):
    work_date = work_date or _today()
    rows = db.query(
        "SELECT s.*, d.doctor_name, dep.dept_name, lv.level_name, "
        "       (s.total_quota - s.used_quota) AS remaining "
        "FROM doctor_schedule s "
        "JOIN doctor d ON d.doctor_id = s.doctor_id "
        "JOIN department dep ON dep.dept_id = s.dept_id "
        "JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE s.work_date = ? ORDER BY s.dept_id, s.time_period",
        (work_date,),
    )
    doctors = db.query(
        "SELECT d.*, dep.dept_name FROM doctor d "
        "JOIN department dep ON dep.dept_id = d.dept_id ORDER BY d.dept_id"
    )
    levels = db.query("SELECT * FROM registration_level ORDER BY level_id")
    return web.render(
        request, "schedules.html", schedules=rows, doctors=doctors, levels=levels,
        work_date=work_date,
    )


@router.post("/schedules/create")
def schedule_create(
    request: Request,
    data: Annotated[ScheduleCreateModel, Form()],
    user=Depends(require_roles("admin")),
):
    doctor_id = data.doctor_id
    work_date = data.work_date.strip()
    time_period = data.time_period.strip()
    level_id = data.level_id
    total_quota = data.total_quota.strip()

    if not (doctor_id and work_date and time_period and level_id):
        web.flash(request, "排班信息不完整", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))
    try:
        total_quota = int(total_quota)
    except ValueError:
        web.flash(request, "总号源必须为整数", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))
    if total_quota <= 0:
        web.flash(request, "总号源必须为正整数", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))
    if time_period not in ("上午", "下午", "夜班"):
        web.flash(request, "时段不合法", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))

    doctor = db.query_one("SELECT * FROM doctor WHERE doctor_id = ?", (doctor_id,))
    if not doctor:
        web.flash(request, "医生不存在", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))
    if db.query_one(
        "SELECT 1 FROM doctor_schedule WHERE doctor_id=? AND work_date=? AND time_period=?",
        (doctor_id, work_date, time_period),
    ):
        web.flash(request, "同一医生同一时段已有排班，不可重复", "error")
        return web.redirect(web.url_for(request, "schedules", work_date=work_date))

    db.execute(
        "INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, "
        "level_id, total_quota, used_quota, status) VALUES (?,?,?,?,?,?,0,'正常')",
        (doctor_id, doctor["dept_id"], work_date, time_period, level_id, total_quota),
    )
    request.state.audit_detail = "%s %s 号源 %d（%s）" % (work_date, time_period, total_quota, doctor["doctor_name"])
    web.flash(request, "排班新增成功", "success")
    return web.redirect(web.url_for(request, "schedules", work_date=work_date))


@router.post("/schedules/{schedule_id}/stop")
def schedule_stop(
    request: Request, schedule_id: int, user=Depends(require_roles("admin"))
):
    schedule = db.query_one("SELECT * FROM doctor_schedule WHERE schedule_id = ?", (schedule_id,))
    if not schedule:
        web.flash(request, "排班不存在", "error")
        return web.redirect(web.url_for(request, "schedules"))
    new_status = "正常" if schedule["status"] == "停诊" else "停诊"
    db.execute("UPDATE doctor_schedule SET status = ? WHERE schedule_id = ?", (new_status, schedule_id))
    request.state.audit_detail = "排班 %d 状态改为 %s" % (schedule_id, new_status)
    web.flash(request, "排班状态已更新为：" + new_status, "success")
    return web.redirect(web.url_for(request, "schedules", work_date=schedule["work_date"]))
