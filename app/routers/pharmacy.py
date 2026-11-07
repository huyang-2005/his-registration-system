"""药品、库存、处方、收费台与发药台。"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app import db, web
from app.deps import require_roles
from app.schemas import (
    DrugCreateModel,
    InventoryCreateModel,
    PrescriptionApiModel,
    PrescriptionPayModel,
)
from app.services import csv_import, pharmacy as pharmacy_service
from app.services.errors import BusinessError
from app.services.registration import _today

router = APIRouter()


def _drugs_with_stock(keyword=""):
    sql = (
        "SELECT d.*, COALESCE(SUM(i.quantity), 0) AS stock "
        "FROM drug d LEFT JOIN drug_inventory i ON i.drug_id = d.drug_id "
    )
    params = ()
    if keyword:
        sql += "WHERE d.generic_name LIKE ? OR d.drug_code LIKE ? OR d.trade_name LIKE ? "
        params = ("%" + keyword + "%",) * 3
    sql += "GROUP BY d.drug_id ORDER BY d.drug_id"
    return db.query(sql, params)


def _items_for(presc_ids):
    if not presc_ids:
        return {}
    placeholders = ",".join("?" * len(presc_ids))
    rows = db.query(
        "SELECT * FROM prescription_item WHERE presc_id IN (%s) ORDER BY item_id" % placeholders,
        tuple(presc_ids),
    )
    result = {}
    for row in rows:
        result.setdefault(row["presc_id"], []).append(dict(row))
    return result


@router.get("/drugs")
def drugs(
    request: Request,
    keyword: str = "",
    user=Depends(require_roles("admin", "pharmacist", "doctor")),
):
    rows = _drugs_with_stock(keyword.strip())
    return web.render(request, "drugs.html", drugs=rows, keyword=keyword, today=_today())


@router.post("/drugs/create")
def drug_create(
    request: Request,
    data: Annotated[DrugCreateModel, Form()],
    user=Depends(require_roles("admin")),
):
    generic = data.generic_name.strip()
    spec = data.spec.strip()
    code = data.drug_code.strip()
    try:
        price = float(data.price)
    except ValueError:
        web.flash(request, "单价格式不正确", "error")
        return web.redirect(web.url_for(request, "drugs"))
    if not generic or not spec:
        web.flash(request, "通用名与规格为必填项", "error")
        return web.redirect(web.url_for(request, "drugs"))
    if price < 0:
        web.flash(request, "单价不能为负数", "error")
        return web.redirect(web.url_for(request, "drugs"))
    if data.insurance_category not in ("甲类", "乙类", "丙类", "自费"):
        web.flash(request, "医保类别不合法", "error")
        return web.redirect(web.url_for(request, "drugs"))

    if not code:
        row = db.query_one("SELECT COUNT(*) AS c FROM drug")
        code = "D%06d" % (row["c"] + 1)
    if db.query_one("SELECT 1 FROM drug WHERE drug_code = ?", (code,)):
        web.flash(request, "药品编码已存在", "error")
        return web.redirect(web.url_for(request, "drugs"))
    if db.query_one(
        "SELECT 1 FROM drug WHERE generic_name = ? AND spec = ?", (generic, spec)
    ):
        web.flash(request, "同名同规格药品已存在", "error")
        return web.redirect(web.url_for(request, "drugs"))

    db.execute(
        "INSERT INTO drug (drug_code, generic_name, trade_name, spec, dosage_form, unit, "
        "price, insurance_category, manufacturer) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            code,
            generic,
            data.trade_name.strip() or None,
            spec,
            data.dosage_form.strip() or None,
            data.unit.strip() or "盒",
            price,
            data.insurance_category,
            data.manufacturer.strip() or None,
        ),
    )
    request.state.audit_detail = "新增药品 %s（%s %s）" % (code, generic, spec)
    web.flash(request, "药品新增成功：" + code, "success")
    return web.redirect(web.url_for(request, "drugs"))


@router.post("/drugs/{drug_id}/inventory")
def inventory_add(
    request: Request,
    drug_id: int,
    data: Annotated[InventoryCreateModel, Form()],
    user=Depends(require_roles("admin", "pharmacist")),
):
    drug = db.query_one("SELECT * FROM drug WHERE drug_id = ?", (drug_id,))
    if not drug:
        web.flash(request, "药品不存在", "error")
        return web.redirect(web.url_for(request, "drugs"))
    try:
        quantity = int(data.quantity)
    except ValueError:
        web.flash(request, "入库数量必须为整数", "error")
        return web.redirect(web.url_for(request, "drugs"))
    if quantity <= 0:
        web.flash(request, "入库数量必须大于 0", "error")
        return web.redirect(web.url_for(request, "drugs"))
    batch_no = data.batch_no.strip()
    if not batch_no:
        web.flash(request, "批次号不能为空", "error")
        return web.redirect(web.url_for(request, "drugs"))

    existing = db.query_one(
        "SELECT * FROM drug_inventory WHERE drug_id = ? AND batch_no = ?", (drug_id, batch_no)
    )
    if existing:
        db.execute(
            "UPDATE drug_inventory SET quantity = quantity + ?, expiry_date = ? "
            "WHERE inventory_id = ?",
            (quantity, data.expiry_date or existing["expiry_date"], existing["inventory_id"]),
        )
    else:
        db.execute(
            "INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
            (drug_id, batch_no, quantity, data.expiry_date or None),
        )
    request.state.audit_detail = "%s 批次 %s 入库 %d" % (drug["generic_name"], batch_no, quantity)
    web.flash(request, "入库成功：%s +%d" % (drug["generic_name"], quantity), "success")
    return web.redirect(web.url_for(request, "drugs"))


@router.post("/drugs/import")
async def drug_import(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(require_roles("admin")),
):
    raw = await file.read()
    try:
        result = csv_import.import_drugs(raw, user["user_id"])
    except BusinessError as exc:
        web.flash(request, exc.message, "error")
        return web.redirect(web.url_for(request, "drugs"))

    request.state.audit_detail = "导入成功 %d 条，失败 %d 条" % (result["success"], result["failed"])
    return web.render(
        request,
        "import_result.html",
        result=result,
        filename=file.filename,
    )


@router.get("/prescriptions/new")
def prescription_new(
    request: Request,
    reg_id: str = "",
    user=Depends(require_roles("admin", "doctor")),
):
    registrations = db.query(
        "SELECT r.*, p.name AS patient_name, p.medical_record_no, d.doctor_name, "
        "       dep.dept_name, pay.status AS pay_status "
        "FROM registration r "
        "JOIN patient p ON p.patient_id = r.patient_id "
        "JOIN doctor d ON d.doctor_id = r.doctor_id "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "LEFT JOIN payment pay ON pay.reg_id = r.reg_id "
        "WHERE r.status <> '已退号' AND date(r.reg_time) = ? "
        "ORDER BY r.reg_id DESC",
        (_today(),),
    )
    drugs = [dict(row) for row in _drugs_with_stock()]
    return web.render(
        request, "prescription_new.html", registrations=registrations, drugs=drugs,
        selected_reg=reg_id,
    )


@router.post("/prescriptions/create")
async def prescription_create(
    request: Request,
    user=Depends(require_roles("admin", "doctor")),
):
    form = await request.form()
    reg_id = str(form.get("reg_id", "")).strip()
    diagnosis = str(form.get("diagnosis", "")).strip()
    drug_ids = form.getlist("drug_id")
    quantities = form.getlist("quantity")
    if not reg_id:
        web.flash(request, "请选择挂号单", "error")
        return web.redirect(web.url_for(request, "prescription_new"))

    items = []
    for drug_id, quantity in zip(drug_ids, quantities):
        if not str(drug_id).strip() or not str(quantity).strip():
            continue
        try:
            items.append({"drug_id": int(drug_id), "quantity": int(quantity)})
        except ValueError:
            web.flash(request, "药品数量必须为整数", "error")
            return web.redirect(web.url_for(request, "prescription_new", reg_id=reg_id))

    try:
        result = pharmacy_service.create_prescription(
            int(reg_id), diagnosis, items, user["user_id"]
        )
    except (ValueError, BusinessError) as exc:
        message = exc.message if isinstance(exc, BusinessError) else "参数不合法"
        web.flash(request, message, "error")
        return web.redirect(web.url_for(request, "prescription_new", reg_id=reg_id))

    request.state.audit_detail = "处方 %s，金额 %.2f 元" % (
        result["presc_no"], result["total_amount"]
    )
    web.flash(request, "开方成功：%s，合计 %.2f 元" % (result["presc_no"], result["total_amount"]), "success")
    return web.redirect(web.url_for(request, "prescription_new"))


@router.get("/cashier")
def cashier(
    request: Request,
    user=Depends(require_roles("admin", "cashier")),
):
    rows = db.query(
        "SELECT pr.*, p.name AS patient_name, p.patient_type, r.reg_no, r.queue_no, "
        "       d.doctor_name, dep.dept_name "
        "FROM prescription pr "
        "JOIN patient p ON p.patient_id = pr.patient_id "
        "JOIN registration r ON r.reg_id = pr.reg_id "
        "JOIN doctor d ON d.doctor_id = pr.doctor_id "
        "JOIN department dep ON dep.dept_id = r.dept_id "
        "WHERE pr.status = '待收费' ORDER BY pr.presc_id"
    )
    items = _items_for([r["presc_id"] for r in rows])
    history = db.query(
        "SELECT sp.*, pr.presc_no, p.name AS patient_name "
        "FROM presc_payment sp JOIN prescription pr ON pr.presc_id = sp.presc_id "
        "JOIN patient p ON p.patient_id = pr.patient_id "
        "WHERE date(sp.pay_time) = ? ORDER BY sp.pay_id DESC",
        (_today(),),
    )
    return web.render(request, "cashier.html", prescriptions=rows, items=items, history=history)


@router.post("/prescriptions/{presc_id}/pay")
def prescription_pay(
    request: Request,
    presc_id: int,
    data: Annotated[PrescriptionPayModel, Form()],
    user=Depends(require_roles("admin", "cashier")),
):
    if data.pay_type not in ("现金", "医保", "微信", "支付宝"):
        web.flash(request, "支付方式不合法", "error")
        return web.redirect(web.url_for(request, "cashier"))
    try:
        presc = pharmacy_service.charge_prescription(presc_id, data.pay_type, user["user_id"])
    except BusinessError as exc:
        web.flash(request, exc.message, "error")
        return web.redirect(web.url_for(request, "cashier"))
    request.state.audit_detail = "处方 %s 收费 %.2f 元（%s）" % (
        presc["presc_no"], presc["total_amount"], data.pay_type
    )
    web.flash(request, "处方收费成功：%.2f 元" % presc["total_amount"], "success")
    return web.redirect(web.url_for(request, "cashier"))


@router.get("/pharmacy")
def pharmacy(
    request: Request,
    user=Depends(require_roles("admin", "pharmacist")),
):
    rows = db.query(
        "SELECT pr.*, p.name AS patient_name, r.reg_no, d.doctor_name "
        "FROM prescription pr "
        "JOIN patient p ON p.patient_id = pr.patient_id "
        "JOIN registration r ON r.reg_id = pr.reg_id "
        "JOIN doctor d ON d.doctor_id = pr.doctor_id "
        "WHERE pr.status = '已收费' ORDER BY pr.presc_id"
    )
    items = _items_for([r["presc_id"] for r in rows])
    low_stock = db.query(
        "SELECT d.generic_name, d.spec, COALESCE(SUM(i.quantity),0) AS stock "
        "FROM drug d LEFT JOIN drug_inventory i ON i.drug_id = d.drug_id "
        "GROUP BY d.drug_id HAVING stock < 10 ORDER BY stock"
    )
    dispensed = db.query(
        "SELECT dr.*, pr.presc_no, p.name AS patient_name "
        "FROM dispense_record dr JOIN prescription pr ON pr.presc_id = dr.presc_id "
        "JOIN patient p ON p.patient_id = pr.patient_id "
        "WHERE date(dr.dispensed_at) = ? ORDER BY dr.dispense_id DESC",
        (_today(),),
    )
    return web.render(
        request, "pharmacy.html", prescriptions=rows, items=items,
        low_stock=low_stock, dispensed=dispensed,
    )


@router.post("/prescriptions/{presc_id}/dispense")
def prescription_dispense(
    request: Request, presc_id: int, user=Depends(require_roles("admin", "pharmacist"))
):
    try:
        presc = pharmacy_service.dispense_prescription(presc_id, user["user_id"])
    except BusinessError as exc:
        web.flash(request, exc.message, "error")
        return web.redirect(web.url_for(request, "pharmacy"))
    request.state.audit_detail = "处方 %s 发药完成" % presc["presc_no"]
    web.flash(request, "发药成功：" + presc["presc_no"], "success")
    return web.redirect(web.url_for(request, "pharmacy"))


def _api_error(code: int, message: str):
    return JSONResponse(status_code=code, content={"code": code, "message": message})


@router.post("/api/prescriptions")
def api_create_prescription(
    data: PrescriptionApiModel,
    user=Depends(require_roles("admin", "doctor")),
):
    try:
        result = pharmacy_service.create_prescription(
            data.reg_id,
            data.diagnosis,
            [item.model_dump() for item in data.items],
            user["user_id"],
        )
    except BusinessError as exc:
        return _api_error(exc.status_code, exc.message)
    return {"code": 200, "message": "开方成功", "data": result}


@router.post("/api/prescriptions/{presc_id}/pay")
def api_pay_prescription(
    presc_id: int,
    data: PrescriptionPayModel,
    user=Depends(require_roles("admin", "cashier")),
):
    if data.pay_type not in ("现金", "医保", "微信", "支付宝"):
        return _api_error(400, "支付方式不合法")
    try:
        presc = pharmacy_service.charge_prescription(presc_id, data.pay_type, user["user_id"])
    except BusinessError as exc:
        return _api_error(exc.status_code, exc.message)
    return {
        "code": 200,
        "message": "收费成功",
        "data": {
            "presc_id": presc["presc_id"],
            "presc_no": presc["presc_no"],
            "amount": presc["total_amount"],
            "status": "已收费",
        },
    }


@router.post("/api/prescriptions/{presc_id}/dispense")
def api_dispense_prescription(
    presc_id: int,
    user=Depends(require_roles("admin", "pharmacist")),
):
    try:
        presc = pharmacy_service.dispense_prescription(presc_id, user["user_id"])
    except BusinessError as exc:
        return _api_error(exc.status_code, exc.message)
    return {
        "code": 200,
        "message": "发药成功",
        "data": {"presc_id": presc["presc_id"], "presc_no": presc["presc_no"], "status": "已发药"},
    }
