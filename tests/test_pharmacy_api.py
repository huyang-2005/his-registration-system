"""处方开立、收费扣库存、发药闭环测试。"""
from app import db
from tests.conftest import auth


def _register(client, token, schedule_id, id_card="110101199001013456"):
    response = client.post(
        "/api/register",
        json={
            "schedule_id": schedule_id,
            "patient_name": "处方测试患者",
            "patient_id_card": id_card,
            "phone": "13900000000",
        },
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["reg_id"]


def _create_prescription(client, token, reg_id, drug_id, quantity=3):
    return client.post(
        "/api/prescriptions",
        json={
            "reg_id": reg_id,
            "diagnosis": "上呼吸道感染",
            "items": [{"drug_id": drug_id, "quantity": quantity}],
        },
        headers=auth(token),
    )


def test_prescription_amount_is_server_side(client, cashier_token, doctor_token, schedule, drug):
    reg_id = _register(client, cashier_token, schedule)
    response = _create_prescription(client, doctor_token, reg_id, drug, quantity=3)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total_amount"] == 30.00
    item = db.query_one("SELECT * FROM prescription_item WHERE presc_id=?", (data["presc_id"],))
    assert item["unit_price"] == 10.00
    assert item["amount"] == 30.00


def test_charge_deducts_stock_and_marks_paid(client, cashier_token, doctor_token, schedule, drug):
    reg_id = _register(client, cashier_token, schedule)
    presc = _create_prescription(client, doctor_token, reg_id, drug, quantity=3).json()["data"]
    response = client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(cashier_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["amount"] == 30.00
    row = db.query_one("SELECT status FROM prescription WHERE presc_id=?", (presc["presc_id"],))
    assert row["status"] == "已收费"
    stock = db.query_one("SELECT SUM(quantity) AS q FROM drug_inventory WHERE drug_id=?", (drug,))
    assert stock["q"] == 7


def test_insufficient_stock_returns_400_and_rolls_back(client, cashier_token, doctor_token, schedule):
    low_drug = db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, unit, price) "
        "VALUES ('LOW001','低库存药','10mg*10片','盒',5.00)"
    )
    db.execute(
        "INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) VALUES (?,?,?,?)",
        (low_drug, "L001", 2, "2028-12-31"),
    )
    reg_id = _register(client, cashier_token, schedule)
    presc = _create_prescription(client, doctor_token, reg_id, low_drug, quantity=3).json()["data"]
    response = client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(cashier_token),
    )
    assert response.status_code == 400
    assert "库存不足" in response.json()["message"]
    assert db.query_one("SELECT status FROM prescription WHERE presc_id=?", (presc["presc_id"],))["status"] == "待收费"
    assert db.query_one("SELECT COUNT(*) AS c FROM presc_payment WHERE presc_id=?", (presc["presc_id"],))["c"] == 0
    assert db.query_one("SELECT SUM(quantity) AS q FROM drug_inventory WHERE drug_id=?", (low_drug,))["q"] == 2


def test_duplicate_charge_returns_409(client, cashier_token, doctor_token, schedule, drug):
    reg_id = _register(client, cashier_token, schedule)
    presc = _create_prescription(client, doctor_token, reg_id, drug, quantity=1).json()["data"]
    first = client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(cashier_token),
    )
    second = client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(cashier_token),
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_dispense_requires_paid_status(client, cashier_token, doctor_token, pharmacist_token, schedule, drug):
    reg_id = _register(client, cashier_token, schedule)
    presc = _create_prescription(client, doctor_token, reg_id, drug, quantity=1).json()["data"]
    response = client.post(
        f"/api/prescriptions/{presc['presc_id']}/dispense", headers=auth(pharmacist_token)
    )
    assert response.status_code == 409
    client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(cashier_token),
    )
    response = client.post(
        f"/api/prescriptions/{presc['presc_id']}/dispense", headers=auth(pharmacist_token)
    )
    assert response.status_code == 200
    assert db.query_one("SELECT status FROM prescription WHERE presc_id=?", (presc["presc_id"],))["status"] == "已发药"
    assert db.query_one("SELECT COUNT(*) AS c FROM dispense_record WHERE presc_id=?", (presc["presc_id"],))["c"] == 1


def test_cancel_registration_with_prescription_is_blocked(
    client, cashier_token, doctor_token, schedule, drug
):
    reg_id = _register(client, cashier_token, schedule)
    _create_prescription(client, doctor_token, reg_id, drug, quantity=1)
    response = client.post(
        f"/registrations/{reg_id}/cancel",
        headers=auth(cashier_token),
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one("SELECT status FROM registration WHERE reg_id=?", (reg_id,))
    assert row["status"] == "已挂号"


def test_doctor_cannot_charge(client, doctor_token, schedule, drug, cashier_token):
    reg_id = _register(client, cashier_token, schedule)
    presc = _create_prescription(client, doctor_token, reg_id, drug, quantity=1).json()["data"]
    response = client.post(
        f"/api/prescriptions/{presc['presc_id']}/pay",
        json={"pay_type": "现金"},
        headers=auth(doctor_token),
    )
    assert response.status_code == 403
