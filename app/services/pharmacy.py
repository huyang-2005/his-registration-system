"""处方业务：开方（后端划价）、收费（扣库存原子事务）、发药。"""
from datetime import datetime

from app import db
from app.services import inventory, pricing
from app.services.errors import BusinessError


def gen_presc_no(conn):
    prefix = "CF" + datetime.now().strftime("%Y%m%d") + "A"
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM prescription WHERE presc_no LIKE ?", (prefix + "%",)
    ).fetchone()
    return "%s%03d" % (prefix, row["c"] + 1)


def create_prescription(reg_id, diagnosis, items, operator_id):
    """items: [{'drug_id': int, 'quantity': int}]，单价全部从药品档案读取。"""
    diagnosis = (diagnosis or "").strip()
    if not diagnosis:
        raise BusinessError("诊断不能为空", 400)
    if not items:
        raise BusinessError("处方至少包含一种药品", 400)

    conn = db.transaction()
    try:
        reg = conn.execute(
            "SELECT r.*, p.name AS patient_name FROM registration r "
            "JOIN patient p ON p.patient_id = r.patient_id WHERE r.reg_id = ?",
            (reg_id,),
        ).fetchone()
        if not reg:
            raise BusinessError("挂号单不存在", 404)
        if reg["status"] == "已退号":
            raise BusinessError("已退号患者不可开方", 409)

        prepared = []
        for item in items:
            drug = conn.execute(
                "SELECT * FROM drug WHERE drug_id = ? AND status = '启用'",
                (item["drug_id"],),
            ).fetchone()
            if not drug:
                raise BusinessError("药品不存在或已停用：%s" % item["drug_id"], 400)
            quantity = int(item["quantity"])
            if quantity <= 0:
                raise BusinessError("药品数量必须大于 0", 400)
            amount = pricing.item_amount(drug["price"], quantity)
            prepared.append(
                {
                    "drug_id": drug["drug_id"],
                    "drug_name": drug["generic_name"],
                    "spec": drug["spec"],
                    "quantity": quantity,
                    "unit_price": drug["price"],
                    "amount": amount,
                }
            )

        total = pricing.prescription_total(prepared)
        presc_no = gen_presc_no(conn)
        cur = conn.execute(
            "INSERT INTO prescription (presc_no, reg_id, patient_id, doctor_id, diagnosis, "
            "status, total_amount, operator_id) VALUES (?,?,?,?,?,'待收费',?,?)",
            (presc_no, reg_id, reg["patient_id"], reg["doctor_id"], diagnosis, total, operator_id),
        )
        presc_id = cur.lastrowid
        for item in prepared:
            conn.execute(
                "INSERT INTO prescription_item (presc_id, drug_id, drug_name, spec, "
                "quantity, unit_price, amount) VALUES (?,?,?,?,?,?,?)",
                (
                    presc_id,
                    item["drug_id"],
                    item["drug_name"],
                    item["spec"],
                    item["quantity"],
                    item["unit_price"],
                    item["amount"],
                ),
            )
        conn.commit()
        return {
            "presc_id": presc_id,
            "presc_no": presc_no,
            "total_amount": total,
            "patient_name": reg["patient_name"],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def charge_prescription(presc_id, pay_type, operator_id):
    """收费事务：写收费单 + 处方置已收费 + 扣减库存，任一步失败全部回滚。"""
    conn = db.transaction()
    try:
        presc = conn.execute(
            "SELECT * FROM prescription WHERE presc_id = ?", (presc_id,)
        ).fetchone()
        if not presc:
            raise BusinessError("处方不存在", 404)
        if presc["status"] != "待收费":
            raise BusinessError("处方当前状态不可收费：%s" % presc["status"], 409)
        if conn.execute(
            "SELECT 1 FROM presc_payment WHERE presc_id = ?", (presc_id,)
        ).fetchone():
            raise BusinessError("该处方已收费", 409)

        items = conn.execute(
            "SELECT * FROM prescription_item WHERE presc_id = ?", (presc_id,)
        ).fetchall()
        if not items:
            raise BusinessError("处方无药品明细", 400)

        aggregated = {}
        for item in items:
            aggregated[item["drug_id"]] = aggregated.get(item["drug_id"], 0) + int(
                item["quantity"]
            )
        for drug_id, quantity in aggregated.items():
            drug = conn.execute(
                "SELECT generic_name FROM drug WHERE drug_id = ?", (drug_id,)
            ).fetchone()
            inventory.deduct_stock(conn, drug_id, quantity, drug["generic_name"] if drug else "")

        conn.execute(
            "INSERT INTO presc_payment (presc_id, amount, pay_type, status, operator_id) "
            "VALUES (?,?,?,'已支付',?)",
            (presc_id, presc["total_amount"], pay_type, operator_id),
        )
        conn.execute(
            "UPDATE prescription SET status = '已收费' WHERE presc_id = ?", (presc_id,)
        )
        conn.commit()
        return dict(presc)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dispense_prescription(presc_id, operator_id):
    conn = db.transaction()
    try:
        presc = conn.execute(
            "SELECT * FROM prescription WHERE presc_id = ?", (presc_id,)
        ).fetchone()
        if not presc:
            raise BusinessError("处方不存在", 404)
        if presc["status"] != "已收费":
            raise BusinessError("仅已收费处方可发药，当前状态：%s" % presc["status"], 409)
        conn.execute(
            "INSERT INTO dispense_record (presc_id, operator_id) VALUES (?,?)",
            (presc_id, operator_id),
        )
        conn.execute(
            "UPDATE prescription SET status = '已发药' WHERE presc_id = ?", (presc_id,)
        )
        conn.commit()
        return dict(presc)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
