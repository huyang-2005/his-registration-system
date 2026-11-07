"""演示数据预热：确保今天有排班、药品库存和完整业务链数据。

可重复执行：已存在的数据不会重复插入。
用法：python scripts/refresh_demo_data.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, db  # noqa: E402
from app.services import pharmacy, registration  # noqa: E402

TODAY = datetime.now().strftime("%Y-%m-%d")

DRUGS = [
    ("DEMO001", "阿莫西林胶囊", "0.25g*24粒", "胶囊", "盒", 12.50, "甲类"),
    ("DEMO002", "布洛芬缓释胶囊", "0.3g*20粒", "胶囊", "盒", 18.00, "甲类"),
    ("DEMO003", "头孢克肟分散片", "0.1g*12片", "片剂", "盒", 26.80, "乙类"),
    ("DEMO004", "复方感冒灵颗粒", "10g*9袋", "颗粒剂", "盒", 15.60, "甲类"),
    ("DEMO005", "蒙脱石散", "3g*10袋", "散剂", "盒", 9.80, "甲类"),
    ("DEMO006", "奥美拉唑肠溶胶囊", "20mg*14粒", "胶囊", "盒", 22.40, "乙类"),
    ("DEMO007", "氯雷他定片", "10mg*10片", "片剂", "盒", 13.20, "甲类"),
    ("DEMO008", "阿奇霉素分散片", "0.25g*6片", "片剂", "盒", 29.90, "乙类"),
    ("DEMO009", "维生素C片", "100mg*100片", "片剂", "瓶", 6.50, "甲类"),
    ("DEMO010", "生理盐水", "500ml", "注射剂", "瓶", 4.20, "甲类"),
    ("DEMO011", "云南白药气雾剂", "85g", "气雾剂", "瓶", 38.00, "自费"),
    ("DEMO012", "小儿氨酚黄那敏颗粒", "6g*10袋", "颗粒剂", "盒", 11.50, "甲类"),
]

SICKNESS = ["上呼吸道感染", "急性胃肠炎", "过敏性鼻炎", "急性咽炎", "偏头痛"]


def ensure_drugs():
    created = 0
    for code, name, spec, form, unit, price, category in DRUGS:
        row = db.query_one("SELECT drug_id FROM drug WHERE drug_code = ?", (code,))
        if row:
            drug_id = row["drug_id"]
        else:
            drug_id = db.execute(
                "INSERT INTO drug (drug_code, generic_name, spec, dosage_form, unit, price, "
                "insurance_category) VALUES (?,?,?,?,?,?,?)",
                (code, name, spec, form, unit, price, category),
            )
            created += 1
        stock = db.query_one(
            "SELECT COALESCE(SUM(quantity),0) AS q FROM drug_inventory WHERE drug_id = ?",
            (drug_id,),
        )["q"]
        if stock < 50:
            db.execute(
                "INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) "
                "VALUES (?,?,?,?)",
                (drug_id, "DEMO202611", 200 - stock, (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d")),
            )
    return created


def ensure_schedules():
    created = 0
    doctors = db.query("SELECT * FROM doctor ORDER BY doctor_id")
    levels = db.query("SELECT * FROM registration_level ORDER BY level_id")
    for doctor in doctors:
        for period in ("上午", "下午"):
            exists = db.query_one(
                "SELECT 1 FROM doctor_schedule WHERE doctor_id=? AND work_date=? AND time_period=?",
                (doctor["doctor_id"], TODAY, period),
            )
            if exists:
                continue
            level_id = levels[(doctor["doctor_id"] - 1) % len(levels)]["level_id"]
            db.execute(
                "INSERT INTO doctor_schedule (doctor_id, dept_id, work_date, time_period, "
                "level_id, total_quota, used_quota, status) VALUES (?,?,?,?,?,30,0,'正常')",
                (doctor["doctor_id"], doctor["dept_id"], TODAY, period, level_id),
            )
            created += 1
    return created


def ensure_registrations():
    today_count = db.query_one(
        "SELECT COUNT(*) AS c FROM registration WHERE date(reg_time) = ?", (TODAY,)
    )["c"]
    if today_count >= 6:
        return 0

    cashier = db.query_one("SELECT user_id FROM sys_user WHERE username='cashier'")
    patients = db.query("SELECT * FROM patient ORDER BY patient_id LIMIT 8")
    schedules = db.query(
        "SELECT * FROM doctor_schedule WHERE work_date = ? AND status = '正常' "
        "AND used_quota < total_quota ORDER BY schedule_id",
        (TODAY,),
    )
    created = 0
    for index, schedule in enumerate(schedules[:6]):
        patient = patients[index % len(patients)]
        result = registration.create_registration(
            schedule["schedule_id"], patient["patient_id"], "现场", cashier["user_id"]
        )
        if index < 3:
            registration.pay_registration(result["reg_id"], "现金", cashier["user_id"])
        created += 1
    return created


def ensure_prescriptions():
    today_count = db.query_one(
        "SELECT COUNT(*) AS c FROM prescription WHERE date(created_at) = ?", (TODAY,)
    )["c"]
    if today_count > 0:
        return 0

    cashier = db.query_one("SELECT user_id FROM sys_user WHERE username='cashier'")
    doctor = db.query_one("SELECT user_id FROM sys_user WHERE username='doctor'")
    pharmacist = db.query_one("SELECT user_id FROM sys_user WHERE username='pharmacist'")
    regs = db.query(
        "SELECT * FROM registration WHERE date(reg_time) = ? AND status = '已挂号' "
        "ORDER BY reg_id LIMIT 3",
        (TODAY,),
    )
    drugs = {row["generic_name"]: row["drug_id"] for row in db.query("SELECT * FROM drug")}
    plans = [
        (0, [("阿莫西林胶囊", 2), ("布洛芬缓释胶囊", 1)], False, False),
        (1, [("头孢克肟分散片", 1)], True, False),
        (2, [("蒙脱石散", 2), ("奥美拉唑肠溶胶囊", 1)], True, True),
    ]
    created = 0
    for index, items, paid, dispensed in plans:
        if index >= len(regs):
            break
        reg = regs[index]
        try:
            presc = pharmacy.create_prescription(
                reg["reg_id"],
                SICKNESS[index % len(SICKNESS)],
                [{"drug_id": drugs[name], "quantity": qty} for name, qty in items],
                doctor["user_id"],
            )
        except Exception as exc:
            print("跳过开方：", exc)
            continue
        created += 1
        if paid:
            pharmacy.charge_prescription(presc["presc_id"], "现金", cashier["user_id"])
        if dispensed:
            pharmacy.dispense_prescription(presc["presc_id"], pharmacist["user_id"])
    return created


def main():
    if not os.path.exists(config.DB_PATH):
        db.init_database()
    else:
        db.run_migrations()
    print("数据库：", config.DB_PATH)
    print("药品新增：", ensure_drugs())
    print("排班新增：", ensure_schedules())
    print("挂号新增：", ensure_registrations())
    print("处方新增：", ensure_prescriptions())
    print("数据预热完成。今天 =", TODAY)


if __name__ == "__main__":
    main()
