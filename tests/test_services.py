"""服务层单元测试：划价、库存 FIFO、审计映射、AI 兜底。"""
import pytest

from app import db
from app.services import audit, inventory, pricing, triage
from app.services.errors import BusinessError


def test_item_amount_and_rounding():
    assert pricing.item_amount(10, 3) == 30.00
    assert pricing.item_amount(0.1, 3) == 0.30
    assert pricing.item_amount(19.99, 2) == 39.98


def test_prescription_total():
    items = [
        {"unit_price": 10, "quantity": 2},
        {"unit_price": 4.55, "quantity": 1},
    ]
    assert pricing.prescription_total(items) == 24.55


def test_invalid_quantity_rejected():
    with pytest.raises(ValueError):
        pricing.item_amount(10, 0)


def test_inventory_fifo_deduction(client):
    drug_id = db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, unit, price) "
        "VALUES ('FIFO01','FIFO测试药','10mg','盒',1.00)"
    )
    db.execute("INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
               (drug_id, "B-2028", 5, "2028-01-01"))
    db.execute("INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
               (drug_id, "B-2027", 5, "2027-01-01"))
    conn = db.get_conn()
    try:
        allocations = inventory.deduct_stock(conn, drug_id, 6, "FIFO测试药")
        conn.commit()
        remaining = inventory.available_stock(conn, drug_id)
    finally:
        conn.close()
    assert allocations[0]["batch_no"] == "B-2027"
    assert allocations[0]["quantity"] == 5
    assert allocations[1]["batch_no"] == "B-2028"
    assert allocations[1]["quantity"] == 1
    assert remaining == 4


def test_inventory_insufficient_raises(client):
    drug_id = db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, unit, price) "
        "VALUES ('LOW02','不足测试药','10mg','盒',1.00)"
    )
    db.execute("INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
               (drug_id, "B1", 2, "2028-01-01"))
    conn = db.get_conn()
    try:
        with pytest.raises(BusinessError) as exc:
            inventory.deduct_stock(conn, drug_id, 3)
        assert exc.value.status_code == 400
        conn.rollback()
    finally:
        conn.close()


def test_inventory_exact_boundary(client):
    drug_id = db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, unit, price) "
        "VALUES ('EXACT1','边界测试药','10mg','盒',1.00)"
    )
    db.execute("INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
               (drug_id, "B1", 3, "2028-01-01"))
    conn = db.get_conn()
    try:
        inventory.deduct_stock(conn, drug_id, 3)
        conn.commit()
        remaining = inventory.available_stock(conn, drug_id)
    finally:
        conn.close()
    assert remaining == 0


def test_audit_classify():
    assert audit.classify("/patients/create") == ("建档", "patient", None)
    assert audit.classify("/registrations/12/pay") == ("挂号收费", "registration", "12")
    assert audit.classify("/api/prescriptions/9/dispense") == ("发药", "prescription", "9")
    assert audit.classify("/unknown") is None


def test_triage_fallback_for_empty_input():
    result = triage.triage("")
    assert result["source"] == "fallback"
    assert result["department"] == "全科门诊"
    assert result["disclaimer"]


def test_triage_fallback_without_api_key(monkeypatch):
    monkeypatch.setattr("app.config.DEEPSEEK_API_KEY", "")
    result = triage.triage("发烧两天")
    assert result["source"] == "fallback"
    assert "未配置" in result["note"]
