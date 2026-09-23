"""门诊挂号分系统 - FastAPI 应用入口。

依据卫生部《医院信息系统基本功能规范》实现门诊挂号核心业务：
建档、挂号、退号、排班号源、收费、查询、统计。
"""
from datetime import datetime
from typing import Annotated, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from db import execute, query, query_one

app = FastAPI(title="门诊挂号分系统")
app.add_middleware(SessionMiddleware, secret_key="his-outpatient-registration-demo")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

router = APIRouter()

# 演示用固定操作员（真实系统应取自登录会话）
OP_REGISTRAR = 1   # 挂号员
OP_CASHIER = 2     # 收费员
OP_ADMIN = 3       # 管理员


# ------------------------------------------------------------------
# pydantic 表单模型
# ------------------------------------------------------------------
class PatientCreateModel(BaseModel):
    name: str = ""
    gender: str = ""
    birth_date: str = ""
    id_card: str = ""
    phone: str = ""
    address: str = ""
    patient_type: str = "自费"
    insurance_no: str = ""


class RegisterSubmitModel(BaseModel):
    schedule_id: str = ""
    patient_id: str = ""
    reg_type: str = "现场"


class RegistrationPayModel(BaseModel):
    pay_type: str = "现金"


class ScheduleCreateModel(BaseModel):
    doctor_id: str = ""
    work_date: str = ""
    time_period: str = ""
    level_id: str = ""
    total_quota: str = "0"


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def gen_medical_record_no():
    prefix = "MR" + datetime.now().strftime("%Y%m%d")
    row = query_one(
        "SELECT COUNT(*) AS c FROM patient WHERE medical_record_no LIKE ?",
        (prefix + "%",),
    )
    return "%s%04d" % (prefix, row["c"] + 1)


def gen_reg_no():
    prefix = "GH" + datetime.now().strftime("%Y%m%d") + "A"
    row = query_one(
        "SELECT COUNT(*) AS c FROM registration WHERE reg_no LIKE ?",
        (prefix + "%",),
    )
    return "%s%03d" % (prefix, row["c"] + 1)


def next_queue_no(schedule_id):
    row = query_one(
        "SELECT COALESCE(MAX(queue_no), 0) AS m FROM registration WHERE schedule_id = ?",
        (schedule_id,),
    )
    return row["m"] + 1


def add_log(user_id, action, target, detail):
    execute(
        "INSERT INTO operation_log (user_id, action, target, detail) VALUES (?,?,?,?)",
        (user_id, action, target, detail),
    )


# ------------------------------------------------------------------
# 兼容层：url_for / flash / redirect / render
# ------------------------------------------------------------------
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


def flash(request: Request, message: str, category: str):
    request.session.setdefault("_flashes", []).append((category, message))


def get_flashed_messages(request: Request):
    return request.session.pop("_flashes", [])


def redirect(url):
    return RedirectResponse(url, status_code=303)


def render(request: Request, template_name: str, **context):
    context.setdefault("request", request)
    context["url_for"] = lambda name, **params: url_for(request, name, **params)
    context["get_flashed_messages"] = lambda with_categories=False: get_flashed_messages(request)
    return templates.TemplateResponse(request, template_name, context)


# ------------------------------------------------------------------
# 首页看板
# ------------------------------------------------------------------
@router.get("/")
def index(request: Request):
    t = today_str()
    stats = {
        "today_reg": query_one(
            "SELECT COUNT(*) AS c FROM registration WHERE date(reg_time) = ?", (t,)
        )["c"],
        "today_refund": query_one(
            "SELECT COUNT(*) AS c FROM registration "
            "WHERE date(reg_time) = ? AND status = '已退号'",
            (t,),
        )["c"],
        "today_income": query_one(
            "SELECT COALESCE(SUM(p.amount),0) AS s FROM payment p "
            "JOIN registration r ON r.reg_id = p.reg_id "
            "WHERE date(r.reg_time) = ? AND p.status = '已支付'",
            (t,),
        )["s"],
        "patient_total": query_one("SELECT COUNT(*) AS c FROM patient")["c"],
        "schedule_today": query_one(
            "SELECT COUNT(*) AS c FROM doctor_schedule WHERE work_date = ?", (t,)
        )["c"],
    }
    return render(request, "index.html", stats=stats, today=t)


# ------------------------------------------------------------------
# 患者建档 / 查询
# ------------------------------------------------------------------
@router.get("/patients")
def patients(request: Request, keyword: str = Query("")):
    keyword = keyword.strip()
    if keyword:
        rows = query(
            "SELECT * FROM patient "
            "WHERE name LIKE ? OR medical_record_no LIKE ? OR id_card LIKE ? "
            "ORDER BY patient_id DESC",
            ("%" + keyword + "%", "%" + keyword + "%", "%" + keyword + "%"),
        )
    else:
        rows = query("SELECT * FROM patient ORDER BY patient_id DESC")
    return render(request, "patients.html", patients=rows, keyword=keyword)


@router.post("/patients/create")
def patient_create(request: Request, data: Annotated[PatientCreateModel, Form()]):
    name = data.name.strip()
    gender = data.gender.strip()
    birth_date = data.birth_date.strip()
    id_card = data.id_card.strip()
    phone = data.phone.strip()
    address = data.address.strip()
    patient_type = data.patient_type.strip()
    insurance_no = data.insurance_no.strip() or None

    if not name or gender not in ("男", "女"):
        flash(request, "姓名和性别为必填项", "error")
        return redirect(url_for(request, "patients"))

    if id_card:
        dup = query_one("SELECT medical_record_no FROM patient WHERE id_card = ?", (id_card,))
        if dup:
            flash(request, "该证件号已建档，病历号：" + dup["medical_record_no"], "error")
            return redirect(url_for(request, "patients"))

    if patient_type == "医保" and not insurance_no:
        flash(request, "医保患者必须填写医保号", "error")
        return redirect(url_for(request, "patients"))

    mr_no = gen_medical_record_no()
    execute(
        "INSERT INTO patient (medical_record_no, name, gender, birth_date, id_card, "
        "phone, address, patient_type, insurance_no) VALUES (?,?,?,?,?,?,?,?,?)",
        (mr_no, name, gender, birth_date, id_card or None, phone, address,
         patient_type, insurance_no),
    )
    add_log(OP_REGISTRAR, "建档", "patient:" + mr_no, "新建门诊档案 " + name)
    flash(request, "建档成功，病历号：" + mr_no, "success")
    return redirect(url_for(request, "patients"))


# ------------------------------------------------------------------
# 现场 / 预约挂号
# ------------------------------------------------------------------
@router.get("/register")
def register(
    request: Request,
    reg_type: str = Query("现场"),
    work_date: Optional[str] = Query(None),
):
    work_date = today_str() if reg_type == "现场" else (work_date or today_str())
    schedules = query(
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
    patients = query("SELECT * FROM patient ORDER BY patient_id")
    return render(
        request, "register.html", schedules=schedules, patients=patients,
        reg_type=reg_type, work_date=work_date,
    )


@router.post("/register/submit")
def register_submit(request: Request, data: Annotated[RegisterSubmitModel, Form()]):
    schedule_id = data.schedule_id
    patient_id = data.patient_id
    reg_type = data.reg_type

    if not schedule_id or not patient_id:
        flash(request, "请选择患者与号源", "error")
        return redirect(url_for(request, "register", reg_type=reg_type))

    s = query_one(
        "SELECT s.*, (lv.reg_fee + lv.diagnosis_fee) AS total_fee "
        "FROM doctor_schedule s JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE s.schedule_id = ?",
        (schedule_id,),
    )
    if not s:
        flash(request, "号源不存在", "error")
        return redirect(url_for(request, "register", reg_type=reg_type))
    if s["status"] != "正常":
        flash(request, "该号源已停诊，无法挂号", "error")
        return redirect(url_for(request, "register", reg_type=reg_type))
    if s["used_quota"] >= s["total_quota"]:
        flash(request, "号源已满", "error")
        return redirect(url_for(request, "register", reg_type=reg_type))

    reg_no = gen_reg_no()
    queue_no = next_queue_no(schedule_id)
    execute(
        "INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, "
        "level_id, reg_type, queue_no, status, fee, operator_id) "
        "VALUES (?,?,?,?,?,?,?,?,'已挂号',?,?)",
        (reg_no, patient_id, s["dept_id"], s["doctor_id"], schedule_id,
         s["level_id"], reg_type, queue_no, s["total_fee"], OP_REGISTRAR),
    )
    execute(
        "UPDATE doctor_schedule SET used_quota = used_quota + 1 WHERE schedule_id = ?",
        (schedule_id,),
    )
    add_log(OP_REGISTRAR, "挂号", "reg:" + reg_no,
            "号别:%s 序号:%d" % (s["level_id"], queue_no))
    flash(request, "挂号成功，挂号单号 %s，排队序号 %d" % (reg_no, queue_no), "success")
    return redirect(url_for(request, "registrations"))


# ------------------------------------------------------------------
# 挂号记录查询
# ------------------------------------------------------------------
@router.get("/registrations")
def registrations(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    dept_id: str = Query(""),
    doctor_id: str = Query(""),
    keyword: str = Query(""),
    status: str = Query(""),
):
    start = start or today_str()
    end = end or today_str()
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

    rows = query(sql, params)
    depts = query("SELECT * FROM department ORDER BY dept_id")
    doctors = query("SELECT * FROM doctor ORDER BY doctor_id")
    return render(
        request, "registrations.html", regs=rows, depts=depts, doctors=doctors,
        start=start, end=end, dept_id=dept_id, doctor_id=doctor_id,
        keyword=keyword, status=status,
    )


@router.post("/registrations/{reg_id}/cancel")
def registration_cancel(request: Request, reg_id: int):
    r = query_one("SELECT * FROM registration WHERE reg_id = ?", (reg_id,))
    if not r:
        flash(request, "挂号记录不存在", "error")
        return redirect(url_for(request, "registrations"))
    if r["status"] != "已挂号":
        flash(request, "仅“已挂号”状态可退号", "error")
        return redirect(url_for(request, "registrations"))

    execute("UPDATE registration SET status = '已退号' WHERE reg_id = ?", (reg_id,))
    execute(
        "UPDATE doctor_schedule SET used_quota = MAX(used_quota - 1, 0) "
        "WHERE schedule_id = ?",
        (r["schedule_id"],),
    )
    pay = query_one("SELECT * FROM payment WHERE reg_id = ?", (reg_id,))
    if pay and pay["status"] == "已支付":
        execute("UPDATE payment SET status = '已退费' WHERE reg_id = ?", (reg_id,))
    add_log(OP_REGISTRAR, "退号", "reg:" + r["reg_no"], "退号并释放号源")
    flash(request, "退号成功：" + r["reg_no"], "success")
    return redirect(url_for(request, "registrations"))


@router.post("/registrations/{reg_id}/pay")
def registration_pay(
    request: Request,
    reg_id: int,
    data: Annotated[RegistrationPayModel, Form()],
):
    r = query_one(
        "SELECT r.*, p.patient_type, p.insurance_no, p.name AS patient_name "
        "FROM registration r JOIN patient p ON p.patient_id = r.patient_id "
        "WHERE r.reg_id = ?",
        (reg_id,),
    )
    if not r:
        flash(request, "挂号记录不存在", "error")
        return redirect(url_for(request, "registrations"))
    if r["status"] == "已退号":
        flash(request, "已退号记录不可收费", "error")
        return redirect(url_for(request, "registrations"))
    if query_one("SELECT 1 FROM payment WHERE reg_id = ?", (reg_id,)):
        flash(request, "该挂号单已收费", "error")
        return redirect(url_for(request, "registrations"))

    pay_type = data.pay_type
    if r["patient_type"] == "医保" and not r["insurance_no"]:
        flash(request, "医保患者缺少医保号，无法医保结算", "error")
        return redirect(url_for(request, "registrations"))

    execute(
        "INSERT INTO payment (reg_id, amount, pay_type, status, operator_id) "
        "VALUES (?,?,?,'已支付',?)",
        (reg_id, r["fee"], pay_type, OP_CASHIER),
    )
    add_log(OP_CASHIER, "收费", "reg:" + r["reg_no"],
            "%s 支付 %.2f 元" % (pay_type, r["fee"]))
    flash(request, "收费成功：%.2f 元" % r["fee"], "success")
    return redirect(url_for(request, "registrations"))


# ------------------------------------------------------------------
# 排班与号源维护
# ------------------------------------------------------------------
@router.get("/schedules")
def schedules(request: Request, work_date: Optional[str] = Query(None)):
    work_date = work_date or today_str()
    rows = query(
        "SELECT s.*, d.doctor_name, dep.dept_name, lv.level_name, "
        "       (s.total_quota - s.used_quota) AS remaining "
        "FROM doctor_schedule s "
        "JOIN doctor d ON d.doctor_id = s.doctor_id "
        "JOIN department dep ON dep.dept_id = s.dept_id "
        "JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE s.work_date = ? ORDER BY s.dept_id, s.time_period",
        (work_date,),
    )
    doctors = query(
        "SELECT d.*, dep.dept_name FROM doctor d "
        "JOIN department dep ON dep.dept_id = d.dept_id ORDER BY d.dept_id"
    )
    levels = query("SELECT * FROM registration_level ORDER BY level_id")
    return render(
        request, "schedules.html", schedules=rows, doctors=doctors, levels=levels,
        work_date=work_date,
    )


@router.post("/schedules/create")
def schedule_create(request: Request, data: Annotated[ScheduleCreateModel, Form()]):
    doctor_id = data.doctor_id
    work_date = data.work_date.strip()
    time_period = data.time_period.strip()
    level_id = data.level_id
    total_quota = data.total_quota.strip()

    if not (doctor_id and work_date and time_period and level_id):
        flash(request, "排班信息不完整", "error")
        return redirect(url_for(request, "schedules", work_date=work_date))
    try:
        total_quota = int(total_quota)
    except ValueError:
        flash(request, "总号源必须为整数", "error")
        return redirect(url_for(request, "schedules", work_date=work_date))
    if total_quota <= 0:
        flash(request, "总号源必须为正整数", "error")
        return redirect(url_for(request, "schedules", work_date=work_date))

    doctor = query_one("SELECT * FROM doctor WHERE doctor_id = ?", (doctor_id,))
    if not doctor:
        flash(request, "医生不存在", "error")
        return redirect(url_for(request, "schedules", work_date=work_date))

    if query_one(
        "SELECT 1 FROM doctor_schedule WHERE doctor_id=? AND work_date=? AND time_period=?",
        (doctor_id, work_date, time_period),
    ):
        flash(request, "同一医生同一时段已有排班，不可重复", "error")
        return redirect(url_for(request, "schedules", work_date=work_date))

    execute(
        "INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, "
        "level_id, total_quota, used_quota, status) VALUES (?,?,?,?,?,?,0,'正常')",
        (doctor_id, doctor["dept_id"], work_date, time_period, level_id, total_quota),
    )
    add_log(OP_ADMIN, "排班", "doctor:%s" % doctor_id,
            "%s %s 号源%d" % (work_date, time_period, total_quota))
    flash(request, "排班新增成功", "success")
    return redirect(url_for(request, "schedules", work_date=work_date))


@router.post("/schedules/{schedule_id}/stop")
def schedule_stop(request: Request, schedule_id: int):
    s = query_one("SELECT * FROM doctor_schedule WHERE schedule_id = ?", (schedule_id,))
    if not s:
        flash(request, "排班不存在", "error")
        return redirect(url_for(request, "schedules"))
    new_status = "正常" if s["status"] == "停诊" else "停诊"
    execute("UPDATE doctor_schedule SET status = ? WHERE schedule_id = ?",
            (new_status, schedule_id))
    add_log(OP_ADMIN, "排班", "schedule:%d" % schedule_id, "状态改为" + new_status)
    flash(request, "排班状态已更新为：" + new_status, "success")
    return redirect(url_for(request, "schedules", work_date=s["work_date"]))


# ------------------------------------------------------------------
# 排班号源查询接口（JSON）
# ------------------------------------------------------------------
@router.get("/api/schedule/department")
def api_schedule_department(
    dept_name: str = Query(""),
    date: str = Query(""),
):
    dept_name = dept_name.strip()
    date = date.strip()

    if not dept_name:
        raise HTTPException(status_code=400, detail="dept_name 参数不能为空")
    if not date:
        raise HTTPException(status_code=400, detail="date 参数不能为空")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date 格式错误，应为 YYYY-MM-DD")

    dept = query_one("SELECT * FROM department WHERE dept_name = ?", (dept_name,))
    if not dept:
        raise HTTPException(status_code=404, detail="科室不存在：" + dept_name)

    rows = query(
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
    for r in rows:
        remaining = r["remaining"] if r["status"] == "正常" else 0
        if r["doctor_id"] not in doctors:
            doctors[r["doctor_id"]] = {
                "doctor_id": r["doctor_id"],
                "doctor_name": r["doctor_name"],
                "title": r["title"],
                "total_remaining": 0,
                "schedules": [],
            }
            order.append(r["doctor_id"])
        if r["status"] == "正常":
            doctors[r["doctor_id"]]["total_remaining"] += remaining
        doctors[r["doctor_id"]]["schedules"].append({
            "schedule_id": r["schedule_id"],
            "time_period": r["time_period"],
            "level_name": r["level_name"],
            "total_quota": r["total_quota"],
            "used_quota": r["used_quota"],
            "remaining": remaining,
            "status": r["status"],
        })

    return {
        "dept_name": dept_name,
        "date": date,
        "doctor_count": len(order),
        "doctors": [doctors[d] for d in order],
    }


# ------------------------------------------------------------------
# 门诊量统计报表
# ------------------------------------------------------------------
@router.get("/report")
def report(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    start = start or today_str()
    end = end or today_str()

    by_dept = query(
        "SELECT dep.dept_name, "
        "  COUNT(r.reg_id) AS total, "
        "  SUM(CASE WHEN r.status = '已退号' THEN 1 ELSE 0 END) AS refund, "
        "  COALESCE(SUM(CASE WHEN pay.status = '已支付' THEN pay.amount ELSE 0 END),0) AS income "
        "FROM registration r "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "LEFT JOIN payment pay ON pay.reg_id = r.reg_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? "
        "GROUP BY dep.dept_id ORDER BY dep.dept_id",
        (start, end),
    )
    by_doctor = query(
        "SELECT d.doctor_name, dep.dept_name, COUNT(r.reg_id) AS total "
        "FROM registration r "
        "JOIN doctor d ON d.doctor_id = r.doctor_id "
        "JOIN department dep ON dep.dept_id = d.dept_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? AND r.status <> '已退号' "
        "GROUP BY d.doctor_id ORDER BY total DESC",
        (start, end),
    )
    overall = query_one(
        "SELECT COUNT(*) AS total, "
        "  SUM(CASE WHEN status = '已退号' THEN 1 ELSE 0 END) AS refund "
        "FROM registration WHERE date(reg_time) BETWEEN ? AND ?",
        (start, end),
    )
    total = overall["total"] or 0
    refund = overall["refund"] or 0
    refund_rate = round(refund * 100.0 / total, 2) if total else 0.0
    income = query_one(
        "SELECT COALESCE(SUM(p.amount),0) AS s FROM payment p "
        "JOIN registration r ON r.reg_id = p.reg_id "
        "WHERE date(r.reg_time) BETWEEN ? AND ? AND p.status = '已支付'",
        (start, end),
    )["s"]

    return render(
        request, "report.html", by_dept=by_dept, by_doctor=by_doctor,
        start=start, end=end, total=total, refund=refund,
        refund_rate=refund_rate, income=income,
    )


app.include_router(router)


if __name__ == "__main__":
    import os

    import uvicorn

    if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "his.db")):
        from db import init_database

        init_database()
        print("未发现数据库，已自动初始化。")
    uvicorn.run(app, host="127.0.0.1", port=5000)
