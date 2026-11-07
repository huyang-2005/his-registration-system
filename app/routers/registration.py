"""挂号：现场/预约、查询、退号、收费及两个 JSON 接口。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import JSONResponse

from app import db, web
from app.deps import get_current_user, require_roles
from app.schemas import RegisterApiModel, RegisterSubmitModel, RegistrationPayModel
from app.services import registration as service
from app.services.errors import BusinessError
from app.services.registration import _today

router = APIRouter()


def _api_error(code: int, message: str):
    return JSONResponse(status_code=code, content={"code": code, "message": message})


@router.get("/register")
def register(
    request: Request,
    reg_type: str = Query("现场"),
    work_date: Optional[str] = Query(None),
    user=Depends(require_roles("admin", "cashier")),
):
    work_date = _today() if reg_type == "现场" else (work_date or _today())
    schedules = db.query(
        "SELECT s.*, d.doctor_name, d.title, dep.dept_name, lv.level_name, "
        "       (lv.reg_fee + lv.diagnosis_fee) AS total_fee, "
        "       (s.total_quota - s.used_quota) AS remaining "
        "FROM doctor_schedule s "
        "JOIN doctor d ON d.doctor_id = s.doctor_id "
        "JOIN department dep ON dep.dept_id = s.dept_id "
        "JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE s.work_date = ? AND s.status = '正常' AND s.used_quota < s.total_quota "
        "ORDER BY s.dept_id, s.time_period",
        (work_date,),
    )
    patients = db.query("SELECT * FROM patient ORDER BY patient_id")
    return web.render(
        request, "register.html", schedules=schedules, patients=patients,
        reg_type=reg_type, work_date=work_date,
    )


@router.post("/register/submit")
def register_submit(
    request: Request,
    data: Annotated[RegisterSubmitModel, Form()],
    user=Depends(require_roles("admin", "cashier")),
):
    if not data.schedule_id or not data.patient_id:
        web.flash(request, "请选择患者与号源", "error")
        return web.redirect(web.url_for(request, "register", reg_type=data.reg_type))
    try:
        result = service.create_registration(
            int(data.schedule_id), int(data.patient_id), data.reg_type, user["user_id"]
        )
    except (ValueError, BusinessError) as exc:
        message = exc.message if isinstance(exc, BusinessError) else "参数不合法"
        web.flash(request, message, "error")
        return web.redirect(web.url_for(request, "register", reg_type=data.reg_type))

    request.state.audit_detail = "挂号单 %s，排队号 %d，费用 %.2f 元" % (
        result["reg_no"], result["queue_no"], result["fee"]
    )
    web.flash(
        request,
        "挂号成功，挂号单号 %s，排队序号 %d" % (result["reg_no"], result["queue_no"]),
        "success",
    )
    return web.redirect(web.url_for(request, "registrations"))


@router.get("/registrations")
def registrations(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    dept_id: str = Query(""),
    doctor_id: str = Query(""),
    keyword: str = Query(""),
    status: str = Query(""),
    user=Depends(require_roles("admin", "cashier", "doctor")),
):
    start = start or _today()
    end = end or _today()
    keyword = keyword.strip()

    sql = (
        "SELECT r.*, p.name AS patient_name, p.medical_record_no, p.patient_type, "
        "       dep.dept_name, d.doctor_name, lv.level_name, "
        "       pay.status AS pay_status, pay.pay_type "
        "FROM registration r "
        "JOIN patient p ON p.patient_id = r.patient_id "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "JOIN doctor d ON d.doctor_id = r.doctor_id "
        "JOIN registration_level lv ON lv.level_id = r.level_id "
        "LEFT JOIN payment pay ON pay.reg_id = r.reg_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? "
    )
    params = [start, end]
    if dept_id:
        sql += " AND r.dept_id = ?"
        params.append(dept_id)
    if doctor_id:
        sql += " AND r.doctor_id = ?"
        params.append(doctor_id)
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if keyword:
        sql += " AND (p.name LIKE ? OR r.reg_no LIKE ? OR p.medical_record_no LIKE ?)"
        params += ["%" + keyword + "%"] * 3
    sql += " ORDER BY r.reg_id DESC"

    rows = db.query(sql, params)
    depts = db.query("SELECT * FROM department ORDER BY dept_id")
    doctors = db.query("SELECT * FROM doctor ORDER BY doctor_id")
    return web.render(
        request, "registrations.html", regs=rows, depts=depts, doctors=doctors,
        start=start, end=end, dept_id=dept_id, doctor_id=doctor_id,
        keyword=keyword, status=status,
    )


@router.post("/registrations/{reg_id}/cancel")
def registration_cancel(
    request: Request, reg_id: int, user=Depends(require_roles("admin", "cashier"))
):
    try:
        reg = service.cancel_registration(reg_id, user["user_id"])
    except BusinessError as exc:
        web.flash(request, exc.message, "error")
        return web.redirect(web.url_for(request, "registrations"))
    request.state.audit_detail = "退号 %s，释放号源" % reg["reg_no"]
    web.flash(request, "退号成功：" + reg["reg_no"], "success")
    return web.redirect(web.url_for(request, "registrations"))


@router.post("/registrations/{reg_id}/pay")
def registration_pay(
    request: Request,
    reg_id: int,
    data: Annotated[RegistrationPayModel, Form()],
    user=Depends(require_roles("admin", "cashier")),
):
    if data.pay_type not in ("现金", "医保", "微信", "支付宝"):
        web.flash(request, "支付方式不合法", "error")
        return web.redirect(web.url_for(request, "registrations"))
    try:
        reg = service.pay_registration(reg_id, data.pay_type, user["user_id"])
    except BusinessError as exc:
        web.flash(request, exc.message, "error")
        return web.redirect(web.url_for(request, "registrations"))
    request.state.audit_detail = "%s 收费 %.2f 元，单号 %s" % (
        data.pay_type, reg["fee"], reg["reg_no"]
    )
    web.flash(request, "收费成功：%.2f 元" % reg["fee"], "success")
    return web.redirect(web.url_for(request, "registrations"))


@router.get("/api/schedule/department")
def api_schedule_department(
    dept_name: str = Query(""),
    date: str = Query(""),
    user=Depends(get_current_user),
):
    dept_name = dept_name.strip()
    date = date.strip()
    if not dept_name:
        return _api_error(400, "dept_name 参数不能为空")
    if not date:
        return _api_error(400, "date 参数不能为空")
    from datetime import datetime as _dt

    try:
        _dt.strptime(date, "%Y-%m-%d")
    except ValueError:
        return _api_error(400, "date 格式错误，应为 YYYY-MM-DD")

    dept = db.query_one("SELECT * FROM department WHERE dept_name = ?", (dept_name,))
    if not dept:
        return _api_error(404, "科室不存在：" + dept_name)

    rows = db.query(
        "SELECT s.schedule_id, s.doctor_id, s.time_period, s.status, "
        "       s.total_quota, s.used_quota, (s.total_quota - s.used_quota) AS remaining, "
        "       d.doctor_name, d.title, dep.dept_name, lv.level_name "
        "FROM doctor_schedule s "
        "JOIN doctor d ON d.doctor_id = s.doctor_id "
        "JOIN department dep ON dep.dept_id = s.dept_id "
        "JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE dep.dept_name = ? AND s.work_date = ? "
        "ORDER BY s.doctor_id, s.time_period",
        (dept_name, date),
    )
    doctors = {}
    order = []
    for row in rows:
        remaining = row["remaining"] if row["status"] == "正常" else 0
        if row["doctor_id"] not in doctors:
            doctors[row["doctor_id"]] = {
                "doctor_id": row["doctor_id"],
                "doctor_name": row["doctor_name"],
                "title": row["title"],
                "total_remaining": 0,
                "schedules": [],
            }
            order.append(row["doctor_id"])
        if row["status"] == "正常":
            doctors[row["doctor_id"]]["total_remaining"] += remaining
        doctors[row["doctor_id"]]["schedules"].append(
            {
                "schedule_id": row["schedule_id"],
                "time_period": row["time_period"],
                "level_name": row["level_name"],
                "total_quota": row["total_quota"],
                "used_quota": row["used_quota"],
                "remaining": remaining,
                "status": row["status"],
            }
        )
    return {
        "dept_name": dept_name,
        "date": date,
        "doctor_count": len(order),
        "doctors": [doctors[d] for d in order],
    }


@router.post("/api/register")
def api_register(data: RegisterApiModel, user=Depends(require_roles("admin", "cashier"))):
    name = data.patient_name.strip()
    id_card = data.patient_id_card.strip()
    phone = data.phone.strip()
    if not name:
        return _api_error(400, "患者姓名不能为空")
    if not id_card or len(id_card) not in (15, 18):
        return _api_error(400, "身份证号格式不正确")
    if not phone:
        return _api_error(400, "手机号不能为空")

    try:
        result = service.create_registration_with_patient(
            data.schedule_id, name, id_card, phone, user["user_id"]
        )
    except BusinessError as exc:
        return _api_error(exc.status_code, exc.message)

    schedule = result["schedule"]
    patient = result["patient"]
    return {
        "code": 200,
        "message": "挂号成功",
        "data": {
            "reg_id": result["reg_id"],
            "reg_no": result["reg_no"],
            "queue_no": result["queue_no"],
            "reg_type": "现场",
            "fee": result["fee"],
            "status": "已挂号",
            "patient": {
                "patient_id": patient["patient_id"],
                "medical_record_no": patient["medical_record_no"],
                "name": patient["name"],
                "id_card": patient["id_card"],
                "phone": patient["phone"],
            },
            "schedule": {
                "schedule_id": schedule["schedule_id"],
                "doctor_id": schedule["doctor_id"],
                "doctor_name": schedule["doctor_name"],
                "dept_id": schedule["dept_id"],
                "dept_name": schedule["dept_name"],
                "work_date": schedule["work_date"],
                "time_period": schedule["time_period"],
                "level_name": schedule["level_name"],
                "total_quota": schedule["total_quota"],
                "used_quota": schedule["used_quota"] + 1,
                "remaining": schedule["total_quota"] - (schedule["used_quota"] + 1),
                "status": schedule["status"],
            },
        },
    }
