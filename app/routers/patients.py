"""患者建档与档案查询。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request

from app import db, web
from app.deps import require_roles
from app.schemas import PatientCreateModel

router = APIRouter()


def gen_medical_record_no():
    from datetime import datetime

    prefix = "MR" + datetime.now().strftime("%Y%m%d")
    row = db.query_one(
        "SELECT COUNT(*) AS c FROM patient WHERE medical_record_no LIKE ?", (prefix + "%",)
    )
    return "%s%04d" % (prefix, row["c"] + 1)


@router.get("/patients")
def patients(
    request: Request,
    keyword: str = Query(""),
    user=Depends(require_roles("admin", "cashier", "doctor")),
):
    keyword = keyword.strip()
    if keyword:
        rows = db.query(
            "SELECT * FROM patient WHERE name LIKE ? OR medical_record_no LIKE ? OR id_card LIKE ? "
            "ORDER BY patient_id DESC",
            ("%" + keyword + "%",) * 3,
        )
    else:
        rows = db.query("SELECT * FROM patient ORDER BY patient_id DESC")
    return web.render(request, "patients.html", patients=rows, keyword=keyword)


@router.post("/patients/create")
def patient_create(
    request: Request,
    data: Annotated[PatientCreateModel, Form()],
    user=Depends(require_roles("admin", "cashier")),
):
    name = data.name.strip()
    gender = data.gender.strip()
    birth_date = data.birth_date.strip()
    id_card = data.id_card.strip()
    phone = data.phone.strip()
    address = data.address.strip()
    patient_type = data.patient_type.strip()
    insurance_no = data.insurance_no.strip() or None

    if not name or len(name) > 50:
        web.flash(request, "姓名必填且不超过 50 字", "error")
        return web.redirect(web.url_for(request, "patients"))
    if gender not in ("男", "女"):
        web.flash(request, "性别必须为男或女", "error")
        return web.redirect(web.url_for(request, "patients"))
    if id_card and len(id_card) not in (15, 18):
        web.flash(request, "证件号长度不合法", "error")
        return web.redirect(web.url_for(request, "patients"))
    if id_card:
        dup = db.query_one("SELECT medical_record_no FROM patient WHERE id_card = ?", (id_card,))
        if dup:
            web.flash(request, "该证件号已建档，病历号：" + dup["medical_record_no"], "error")
            return web.redirect(web.url_for(request, "patients"))
    if patient_type == "医保" and not insurance_no:
        web.flash(request, "医保患者必须填写医保号", "error")
        return web.redirect(web.url_for(request, "patients"))
    if patient_type not in ("自费", "医保", "新农合"):
        web.flash(request, "患者类别不合法", "error")
        return web.redirect(web.url_for(request, "patients"))

    mr_no = gen_medical_record_no()
    db.execute(
        "INSERT INTO patient (medical_record_no, name, gender, birth_date, id_card, "
        "phone, address, patient_type, insurance_no) VALUES (?,?,?,?,?,?,?,?,?)",
        (mr_no, name, gender, birth_date, id_card or None, phone, address,
         patient_type, insurance_no),
    )
    request.state.audit_detail = "新建档案 %s（%s）" % (mr_no, name)
    web.flash(request, "建档成功，病历号：" + mr_no, "success")
    return web.redirect(web.url_for(request, "patients"))
