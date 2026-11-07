"""pytest 公共夹具：每个用例独立数据库，避免污染 his.db。"""
import os
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
TEST_DIR = tempfile.mkdtemp(prefix="his_test_")
os.environ["HIS_DB_PATH"] = os.path.join(TEST_DIR, "his_test.db")
os.environ["HIS_DATA_DIR"] = TEST_DIR
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-prod"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config, db  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "His@123456"


@pytest.fixture()
def client():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    db.init_database()
    with TestClient(app) as test_client:
        yield test_client


def login(client, username):
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


@pytest.fixture()
def admin_token(client):
    return login(client, "admin")


@pytest.fixture()
def cashier_token(client):
    return login(client, "cashier")


@pytest.fixture()
def doctor_token(client):
    return login(client, "doctor")


@pytest.fixture()
def pharmacist_token(client):
    return login(client, "pharmacist")


@pytest.fixture()
def today():
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


@pytest.fixture()
def schedule(client):
    from datetime import datetime, timedelta

    work_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    doctor = db.query_one("SELECT doctor_id, dept_id FROM doctor LIMIT 1")
    return db.execute(
        "INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, level_id, "
        "total_quota, used_quota, status) VALUES (?,?,?,?,?,?,0,'正常')",
        (doctor["doctor_id"], doctor["dept_id"], work_date, "上午", 1, 5),
    )


@pytest.fixture()
def drug(client):
    drug_id = db.execute(
        "INSERT INTO drug (drug_code, generic_name, spec, dosage_form, unit, price, "
        "insurance_category) VALUES ('P001','测试药品','10mg*10片','片剂','盒',10.00,'甲类')"
    )
    db.execute(
        "INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) "
        "VALUES (?,?,?,?)",
        (drug_id, "B001", 10, "2028-12-31"),
    )
    return drug_id
