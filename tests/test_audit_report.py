"""审计日志与统计报表测试。"""
from app import db
from tests.conftest import auth


def test_audit_records_write_operations(client, cashier_token, admin_token, schedule):
    client.post(
        "/api/register",
        json={
            "schedule_id": schedule,
            "patient_name": "审计测试",
            "patient_id_card": "110101199001014567",
            "phone": "13700000000",
        },
        headers=auth(cashier_token),
    )
    response = client.get("/api/audit?action=挂号", headers=auth(admin_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert items[0]["action"] == "挂号"
    assert items[0]["username"] == "cashier"
    assert items[0]["ip"]


def test_audit_does_not_store_password(client):
    client.post("/api/auth/login", json={"username": "admin", "password": "His@123456"})
    client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass-xyz"})
    rows = db.query("SELECT detail FROM audit_log")
    assert all("wrong-pass-xyz" not in (row["detail"] or "") for row in rows)
    assert all("His@123456" not in (row["detail"] or "") for row in rows)


def test_audit_filter_by_user(client, admin_token, cashier_token):
    client.get("/api/audit", headers=auth(admin_token))
    rows = client.get("/api/audit?user_id=1", headers=auth(admin_token)).json()["items"]
    assert all(row["user_id"] == 1 for row in rows)


def test_report_today_income(client, cashier_token, admin_token, schedule):
    register = client.post(
        "/api/register",
        json={
            "schedule_id": schedule,
            "patient_name": "报表测试",
            "patient_id_card": "110101199001015678",
            "phone": "13600000000",
        },
        headers=auth(cashier_token),
    )
    reg_id = register.json()["data"]["reg_id"]
    client.post(
        f"/registrations/{reg_id}/pay", data={"pay_type": "现金"}, headers=auth(cashier_token)
    )
    report = client.get("/api/report/today", headers=auth(admin_token)).json()
    assert report["total"] >= 1
    assert report["income"] > 0
    assert report["by_dept"]
