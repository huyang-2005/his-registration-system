"""挂号接口与事务测试：401、400、409、并发边界。"""
from app import db
from tests.conftest import auth


def _register(client, token, schedule_id, name="测试患者", id_card="110101199001011234"):
    return client.post(
        "/api/register",
        json={
            "schedule_id": schedule_id,
            "patient_name": name,
            "patient_id_card": id_card,
            "phone": "13800000000",
        },
        headers=auth(token),
    )


def test_register_requires_login(client, schedule):
    assert client.post("/api/register", json={"schedule_id": schedule}).status_code == 401


def test_register_success_decrements_quota(client, cashier_token, schedule):
    response = _register(client, cashier_token, schedule)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["queue_no"] == 1
    assert data["schedule"]["remaining"] == 4
    assert data["status"] == "已挂号"
    used = db.query_one("SELECT used_quota FROM doctor_schedule WHERE schedule_id=?", (schedule,))
    assert used["used_quota"] == 1


def test_register_reuses_patient_by_id_card(client, cashier_token, schedule):
    first = _register(client, cashier_token, schedule, id_card="110101199001011234")
    second = _register(client, cashier_token, schedule, id_card="110101199001011234")
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["patient"]["patient_id"] == second.json()["data"]["patient"]["patient_id"]


def test_register_rejects_invalid_id_card(client, cashier_token, schedule):
    response = _register(client, cashier_token, schedule, id_card="123")
    assert response.status_code == 400


def test_register_quota_exhausted_returns_409(client, cashier_token):
    from datetime import datetime, timedelta

    work_date = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    doctor = db.query_one("SELECT doctor_id, dept_id FROM doctor LIMIT 1")
    schedule_id = db.execute(
        "INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, level_id, "
        "total_quota, used_quota, status) VALUES (?,?,?,?,?,1,0,'正常')",
        (doctor["doctor_id"], doctor["dept_id"], work_date, "下午", 1),
    )
    first = _register(client, cashier_token, schedule_id, id_card="110101199001011111")
    second = _register(client, cashier_token, schedule_id, id_card="110101199001012222")
    assert first.status_code == 200
    assert second.status_code == 409
    assert "号源已满" in second.json()["message"]


def test_register_pay_twice_returns_conflict(client, cashier_token, schedule):
    response = _register(client, cashier_token, schedule)
    reg_id = response.json()["data"]["reg_id"]
    first = client.post(
        f"/registrations/{reg_id}/pay", data={"pay_type": "现金"},
        headers=auth(cashier_token), follow_redirects=False,
    )
    second = client.post(
        f"/registrations/{reg_id}/pay", data={"pay_type": "现金"},
        headers=auth(cashier_token), follow_redirects=False,
    )
    assert first.status_code == 303
    assert second.status_code == 303
    count = db.query_one("SELECT COUNT(*) AS c FROM payment WHERE reg_id=?", (reg_id,))["c"]
    assert count == 1


def test_cancel_refunds_quota(client, cashier_token, schedule):
    response = _register(client, cashier_token, schedule)
    reg_id = response.json()["data"]["reg_id"]
    client.post(
        f"/registrations/{reg_id}/pay", data={"pay_type": "现金"},
        headers=auth(cashier_token), follow_redirects=False,
    )
    cancel = client.post(
        f"/registrations/{reg_id}/cancel", headers=auth(cashier_token), follow_redirects=False
    )
    assert cancel.status_code == 303
    reg = db.query_one("SELECT status FROM registration WHERE reg_id=?", (reg_id,))
    assert reg["status"] == "已退号"
    used = db.query_one("SELECT used_quota FROM doctor_schedule WHERE schedule_id=?", (schedule,))
    assert used["used_quota"] == 0
    pay = db.query_one("SELECT status FROM payment WHERE reg_id=?", (reg_id,))
    assert pay["status"] == "已退费"
