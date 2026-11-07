"""RBAC 验证脚本：无 token 401、越权 403、正确角色 200。

用法：python scripts/verify_rbac.py
使用 TestClient，无需启动服务。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASSWORD = os.environ.get("HIS_DEMO_PASSWORD", "His@123456")


def login(client, username):
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def check(name, actual, expected):
    ok = actual == expected
    print(("[PASS] " if ok else "[FAIL] ") + "%s：期望 %s，实际 %s" % (name, expected, actual))
    return ok


def main():
    passed = True
    with TestClient(app) as client:
        passed &= check("未登录访问审计接口", client.get("/api/audit").status_code, 401)
        cashier = login(client, "cashier")
        passed &= check(
            "收费员访问仅管理员接口", client.get("/api/audit", headers={"Authorization": "Bearer " + cashier}).status_code, 403
        )
        admin = login(client, "admin")
        passed &= check(
            "管理员访问审计接口", client.get("/api/audit", headers={"Authorization": "Bearer " + admin}).status_code, 200
        )
        passed &= check(
            "管理员访问审计页面", client.get("/audit", headers={"Authorization": "Bearer " + admin}).status_code, 200
        )
        pharmacist = login(client, "pharmacist")
        passed &= check(
            "药师访问收费台（应 403）",
            client.get("/cashier", headers={"Authorization": "Bearer " + pharmacist}).status_code,
            403,
        )
        passed &= check(
            "药师访问药房页面", client.get("/pharmacy", headers={"Authorization": "Bearer " + pharmacist}).status_code, 200
        )
    print("\n结果：", "全部通过" if passed else "存在失败项")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
