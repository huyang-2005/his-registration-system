"""药品字典 CSV 批量导入：编码识别、逐行校验、去重、错误行报告。"""
import csv
import io
from datetime import datetime

from app import db
from app.services.errors import BusinessError

REQUIRED_COLUMNS = ("通用名", "规格", "单价")
INSURANCE_CATEGORIES = ("甲类", "乙类", "丙类", "自费")


def decode_csv(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BusinessError("无法识别文件编码，请使用 UTF-8 或 GBK 编码的 CSV", 400)


def _next_drug_code(conn, offset):
    row = conn.execute("SELECT COUNT(*) AS c FROM drug").fetchone()
    return "D%06d" % (int(row["c"]) + offset + 1)


def import_drugs(raw: bytes, operator_id=None):
    text = decode_csv(raw)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BusinessError("CSV 缺少表头", 400)
    headers = [h.strip() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise BusinessError("CSV 缺少必需列：" + "、".join(missing), 400)

    conn = db.transaction()
    errors = []
    success = 0
    seen = set()
    batch_prefix = "IMP" + datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        for index, row in enumerate(reader, start=2):
            data = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            generic = data.get("通用名", "")
            spec = data.get("规格", "")
            if not generic:
                errors.append({"row": index, "reason": "通用名不能为空"})
                continue
            if not spec:
                errors.append({"row": index, "reason": "规格不能为空"})
                continue
            try:
                price = float(data.get("单价", ""))
            except ValueError:
                errors.append({"row": index, "reason": "单价不是合法数字"})
                continue
            if price < 0:
                errors.append({"row": index, "reason": "单价不能为负数"})
                continue
            try:
                quantity = int(data.get("库存数量") or 0)
            except ValueError:
                errors.append({"row": index, "reason": "库存数量必须为整数"})
                continue
            if quantity < 0:
                errors.append({"row": index, "reason": "库存数量不能为负数"})
                continue

            category = data.get("医保类别") or "甲类"
            if category not in INSURANCE_CATEGORIES:
                errors.append({"row": index, "reason": "医保类别非法：%s" % category})
                continue

            code = data.get("药品编码", "")
            key = code or (generic, spec)
            if key in seen:
                errors.append({"row": index, "reason": "文件内重复：%s / %s" % (generic, spec)})
                continue

            existing = None
            if code:
                existing = conn.execute(
                    "SELECT * FROM drug WHERE drug_code = ?", (code,)
                ).fetchone()
            if not existing:
                existing = conn.execute(
                    "SELECT * FROM drug WHERE generic_name = ? AND spec = ?", (generic, spec)
                ).fetchone()
            if existing:
                errors.append(
                    {"row": index, "reason": "已存在药品：%s（%s）" % (generic, spec)}
                )
                continue

            seen.add(key)
            drug_code = code or _next_drug_code(conn, success)
            try:
                cur = conn.execute(
                    "INSERT INTO drug (drug_code, generic_name, trade_name, spec, dosage_form, "
                    "unit, price, insurance_category, manufacturer) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        drug_code,
                        generic,
                        data.get("商品名") or None,
                        spec,
                        data.get("剂型") or None,
                        data.get("单位") or "盒",
                        price,
                        category,
                        data.get("生产厂家") or None,
                    ),
                )
            except Exception:
                errors.append({"row": index, "reason": "药品编码重复或数据非法"})
                continue

            if quantity > 0:
                conn.execute(
                    "INSERT INTO drug_inventory (drug_id, batch_no, quantity, expiry_date) "
                    "VALUES (?,?,?,?)",
                    (
                        cur.lastrowid,
                        "%s%03d" % (batch_prefix, index),
                        quantity,
                        data.get("效期") or None,
                    ),
                )
            success += 1

        conn.commit()
        return {"success": success, "failed": len(errors), "errors": errors}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
