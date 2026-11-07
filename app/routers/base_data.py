"""基础数据维护：科室与医生档案，仅管理员。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request

from app import db, web
from app.deps import require_roles
from app.schemas import DepartmentCreateModel, DoctorCreateModel

router = APIRouter()


@router.get("/base-data")
def base_data(request: Request, user=Depends(require_roles("admin"))):
    depts = db.query("SELECT * FROM department ORDER BY dept_id")
    doctors = db.query(
        "SELECT d.*, dep.dept_name FROM doctor d "
        "JOIN department dep ON dep.dept_id = d.dept_id ORDER BY d.doctor_id"
    )
    return web.render(request, "base_data.html", depts=depts, doctors=doctors)


@router.post("/base-data/departments")
def department_create(
    request: Request,
    data: Annotated[DepartmentCreateModel, Form()],
    user=Depends(require_roles("admin")),
):
    code = data.dept_code.strip()
    name = data.dept_name.strip()
    if not code or not name:
        web.flash(request, "科室编码与名称为必填项", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if data.dept_type not in ("门诊", "急诊"):
        web.flash(request, "科室类型不合法", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if db.query_one("SELECT 1 FROM department WHERE dept_code = ?", (code,)):
        web.flash(request, "科室编码已存在", "error")
        return web.redirect(web.url_for(request, "base_data"))
    db.execute(
        "INSERT INTO department (dept_code, dept_name, dept_type, location) VALUES (?,?,?,?)",
        (code, name, data.dept_type, data.location.strip() or None),
    )
    request.state.audit_detail = "新增科室 %s（%s）" % (code, name)
    web.flash(request, "科室新增成功：" + code, "success")
    return web.redirect(web.url_for(request, "base_data"))


@router.post("/base-data/departments/{dept_id}/toggle")
def department_toggle(
    request: Request, dept_id: int, user=Depends(require_roles("admin"))
):
    dept = db.query_one("SELECT * FROM department WHERE dept_id = ?", (dept_id,))
    if not dept:
        web.flash(request, "科室不存在", "error")
        return web.redirect(web.url_for(request, "base_data"))
    new_status = "停用" if dept["status"] == "启用" else "启用"
    db.execute("UPDATE department SET status = ? WHERE dept_id = ?", (new_status, dept_id))
    request.state.audit_detail = "科室 %s 状态改为 %s" % (dept["dept_name"], new_status)
    web.flash(request, "科室状态已更新为：" + new_status, "success")
    return web.redirect(web.url_for(request, "base_data"))


@router.post("/base-data/doctors")
def doctor_create(
    request: Request,
    data: Annotated[DoctorCreateModel, Form()],
    user=Depends(require_roles("admin")),
):
    code = data.doctor_code.strip()
    name = data.doctor_name.strip()
    try:
        dept_id = int(data.dept_id)
    except (TypeError, ValueError):
        web.flash(request, "请选择所属科室", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if not code or not name:
        web.flash(request, "医生编码与姓名为必填项", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if data.gender not in ("", "男", "女"):
        web.flash(request, "性别不合法", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if not db.query_one("SELECT 1 FROM department WHERE dept_id = ?", (dept_id,)):
        web.flash(request, "科室不存在", "error")
        return web.redirect(web.url_for(request, "base_data"))
    if db.query_one("SELECT 1 FROM doctor WHERE doctor_code = ?", (code,)):
        web.flash(request, "医生编码已存在", "error")
        return web.redirect(web.url_for(request, "base_data"))
    db.execute(
        "INSERT INTO doctor (doctor_code, doctor_name, dept_id, title, gender) VALUES (?,?,?,?,?)",
        (code, name, dept_id, data.title.strip() or None, data.gender or None),
    )
    request.state.audit_detail = "新增医生 %s（%s）" % (code, name)
    web.flash(request, "医生新增成功：" + code, "success")
    return web.redirect(web.url_for(request, "base_data"))


@router.post("/base-data/doctors/{doctor_id}/toggle")
def doctor_toggle(
    request: Request, doctor_id: int, user=Depends(require_roles("admin"))
):
    doctor = db.query_one("SELECT * FROM doctor WHERE doctor_id = ?", (doctor_id,))
    if not doctor:
        web.flash(request, "医生不存在", "error")
        return web.redirect(web.url_for(request, "base_data"))
    new_status = "离岗" if doctor["status"] == "在岗" else "在岗"
    db.execute("UPDATE doctor SET status = ? WHERE doctor_id = ?", (new_status, doctor_id))
    request.state.audit_detail = "医生 %s 状态改为 %s" % (doctor["doctor_name"], new_status)
    web.flash(request, "医生状态已更新为：" + new_status, "success")
    return web.redirect(web.url_for(request, "base_data"))
