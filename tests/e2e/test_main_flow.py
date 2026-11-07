"""Playwright E2E：登录→建档→挂号→开方→收费→发药→报表。

运行前置：
1) pip install -r requirements-dev.txt
2) playwright install chromium
3) 启动服务：uvicorn main:app --port 8000
4) 设置 RUN_E2E=1 后执行：pytest tests/e2e -q
"""
import os
import time

import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
RUN_E2E = os.environ.get("RUN_E2E") == "1"

pytestmark = pytest.mark.skipif(not RUN_E2E, reason="未设置 RUN_E2E=1，跳过浏览器端到端测试")

playwright_sync = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402


def login(page, username):
    page.goto(BASE_URL + "/login")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", "His@123456")
    page.click("button[type=submit]")
    page.wait_for_url(BASE_URL + "/")


def test_full_outpatient_flow():
    from playwright.sync_api import sync_playwright

    suffix = str(int(time.time()))[-6:]
    patient_name = "E2E患者" + suffix
    id_card = "11010119900101" + suffix

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        login(page, "cashier")
        page.goto(BASE_URL + "/patients")
        page.fill("input[name=name]", patient_name)
        page.select_option("select[name=gender]", "男")
        page.fill("input[name=id_card]", id_card)
        page.fill("input[name=phone]", "13500000000")
        page.click("button[type=submit]")
        expect(page.locator(".flash-success")).to_contain_text("建档成功")

        page.goto(BASE_URL + "/register")
        page.select_option("select[name=schedule_id]", index=1)
        page.select_option("select[name=patient_id]", label=str([o for o in page.locator("select[name=patient_id] option").all() if patient_name in o.inner_text()][0].inner_text()))
        page.click("button[type=submit]")
        expect(page.locator(".flash-success")).to_contain_text("挂号成功")

        context.clear_cookies()
        login(page, "doctor")
        page.goto(BASE_URL + "/prescriptions/new")
        page.select_option("select[name=reg_id]", index=1)
        page.fill("input[name=diagnosis]", "上呼吸道感染")
        page.select_option("select[name=drug_id]", index=1)
        page.fill("input[name=quantity]", "2")
        page.click("button[type=submit]")
        expect(page.locator(".flash-success")).to_contain_text("开方成功")

        context.clear_cookies()
        login(page, "cashier")
        page.goto(BASE_URL + "/cashier")
        page.locator("button:has-text('确认收费')").first.click()
        expect(page.locator(".flash-success")).to_contain_text("处方收费成功")

        context.clear_cookies()
        login(page, "pharmacist")
        page.goto(BASE_URL + "/pharmacy")
        page.locator("button:has-text('确认发药')").first.click()
        expect(page.locator(".flash-success")).to_contain_text("发药成功")

        context.clear_cookies()
        login(page, "admin")
        page.goto(BASE_URL + "/report")
        expect(page.locator("h2")).to_contain_text("门诊量")

        browser.close()
