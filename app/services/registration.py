"""挂号业务服务：事务内完成扣减号源与生成挂号单，防止并发超号。"""
from datetime import datetime

from app import db
from app.services.errors import BusinessError


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def gen_medical_record_no(conn):
    prefix = "MR" + datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM patient WHERE medical_record_no LIKE ?", (prefix + "%",)
    ).fetchone()
    return "%s%04d" % (prefix, row["c"] + 1)


def gen_reg_no(conn):
    prefix = "GH" + datetime.now().strftime("%Y%m%d") + "A"
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM registration WHERE reg_no LIKE ?", (prefix + "%",)
    ).fetchone()
    return "%s%03d" % (prefix, row["c"] + 1)


def next_queue_no(conn, schedule_id):
    row = conn.execute(
        "SELECT COALESCE(MAX(queue_no), 0) AS m FROM registration WHERE schedule_id = ?",
        (schedule_id,),
    ).fetchone()
    return int(row["m"]) + 1


def derive_gender(id_card: str):
    if len(id_card) == 18 and id_card[16].isdigit():
        return "男" if int(id_card[16]) % 2 == 1 else "女"
    return "男"


def _load_schedule(conn, schedule_id):
    schedule = conn.execute(
        "SELECT s.*, d.doctor_name, dep.dept_name, lv.level_name, "
        "       (lv.reg_fee + lv.diagnosis_fee) AS total_fee "
        "FROM doctor_schedule s "
        "JOIN doctor d ON d.doctor_id = s.doctor_id "
        "JOIN department dep ON dep.dept_id = s.dept_id "
        "JOIN registration_level lv ON lv.level_id = s.level_id "
        "WHERE s.schedule_id = ?",
        (schedule_id,),
    ).fetchone()
    if not schedule:
        raise BusinessError("排班不存在", 404)
    if schedule["status"] != "正常":
        raise BusinessError("该号源已停诊，无法挂号", 409)
    if schedule["used_quota"] >= schedule["total_quota"]:
        raise BusinessError("号源已满", 409)
    return schedule


def _insert_registration(conn, schedule, patient_id, reg_type, operator_id):
    reg_no = gen_reg_no(conn)
    queue_no = next_queue_no(conn, schedule["schedule_id"])
    cur = conn.execute(
        "INSERT INTO registration (reg_no, patient_id, dept_id, doctor_id, schedule_id, "
        "level_id, reg_type, queue_no, status, fee, operator_id) "
        "VALUES (?,?,?,?,?,?,?,?,'已挂号',?,?)",
        (
            reg_no,
            patient_id,
            schedule["dept_id"],
            schedule["doctor_id"],
            schedule["schedule_id"],
            schedule["level_id"],
            reg_type,
            queue_no,
            schedule["total_fee"],
            operator_id,
        ),
    )
    conn.execute(
        "UPDATE doctor_schedule SET used_quota = used_quota + 1 WHERE schedule_id = ?",
        (schedule["schedule_id"],),
    )
    return {
        "reg_id": cur.lastrowid,
        "reg_no": reg_no,
        "queue_no": queue_no,
        "fee": schedule["total_fee"],
        "patient_id": patient_id,
    }


def create_registration(schedule_id, patient_id, reg_type, operator_id):
    conn = db.transaction()
    try:
        schedule = _load_schedule(conn, schedule_id)
        patient = conn.execute(
            "SELECT * FROM patient WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            raise BusinessError("患者不存在", 404)
        result = _insert_registration(conn, schedule, patient_id, reg_type, operator_id)
        conn.commit()
        result["schedule"] = dict(schedule)
        result["patient"] = dict(patient)
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_registration_with_patient(schedule_id, name, id_card, phone, operator_id):
    """JSON 接口：按身份证号复用档案，不存在则自动建档。"""
    conn = db.transaction()
    try:
        schedule = _load_schedule(conn, schedule_id)
        patient = conn.execute(
            "SELECT * FROM patient WHERE id_card = ?", (id_card,)
        ).fetchone()
        if patient:
            patient_id = patient["patient_id"]
        else:
            mr_no = gen_medical_record_no(conn)
            cur = conn.execute(
                "INSERT INTO patient (medical_record_no, name, gender, id_card, phone) "
                "VALUES (?,?,?,?,?)",
                (mr_no, name, derive_gender(id_card), id_card, phone),
            )
            patient_id = cur.lastrowid
            patient = conn.execute(
                "SELECT * FROM patient WHERE patient_id = ?", (patient_id,)
            ).fetchone()

        result = _insert_registration(conn, schedule, patient_id, "现场", operator_id)
        conn.commit()
        result["schedule"] = dict(schedule)
        result["patient"] = dict(patient)
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_registration(reg_id, operator_id):
    conn = db.transaction()
    try:
        reg = conn.execute("SELECT * FROM registration WHERE reg_id = ?", (reg_id,)).fetchone()
        if not reg:
            raise BusinessError("挂号记录不存在", 404)
        if reg["status"] != "已挂号":
            raise BusinessError("仅“已挂号”状态可退号", 409)

        presc = conn.execute(
            "SELECT presc_no, status FROM prescription WHERE reg_id = ? "
            "AND status IN ('待收费', '已收费', '已发药') ORDER BY presc_id LIMIT 1",
            (reg_id,),
        ).fetchone()
        if presc:
            raise BusinessError(
                "该挂号单已有处方（%s，%s），请先处理处方再退号" % (presc["presc_no"], presc["status"]),
                409,
            )

        conn.execute("UPDATE registration SET status = '已退号' WHERE reg_id = ?", (reg_id,))
        conn.execute(
            "UPDATE doctor_schedule SET used_quota = MAX(used_quota - 1, 0) "
            "WHERE schedule_id = ?",
            (reg["schedule_id"],),
        )
        payment = conn.execute("SELECT * FROM payment WHERE reg_id = ?", (reg_id,)).fetchone()
        if payment and payment["status"] == "已支付":
            conn.execute("UPDATE payment SET status = '已退费' WHERE reg_id = ?", (reg_id,))
        conn.commit()
        return dict(reg)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def pay_registration(reg_id, pay_type, operator_id):
    conn = db.transaction()
    try:
        reg = conn.execute(
            "SELECT r.*, p.patient_type, p.insurance_no, p.name AS patient_name "
            "FROM registration r JOIN patient p ON p.patient_id = r.patient_id "
            "WHERE r.reg_id = ?",
            (reg_id,),
        ).fetchone()
        if not reg:
            raise BusinessError("挂号记录不存在", 404)
        if reg["status"] == "已退号":
            raise BusinessError("已退号记录不可收费", 409)
        if conn.execute("SELECT 1 FROM payment WHERE reg_id = ?", (reg_id,)).fetchone():
            raise BusinessError("该挂号单已收费", 409)
        if reg["patient_type"] == "医保" and not reg["insurance_no"]:
            raise BusinessError("医保患者缺少医保号，无法医保结算", 400)

        conn.execute(
            "INSERT INTO payment (reg_id, amount, pay_type, status, operator_id) "
            "VALUES (?,?,?,'已支付',?)",
            (reg_id, reg["fee"], pay_type, operator_id),
        )
        conn.commit()
        return dict(reg)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
