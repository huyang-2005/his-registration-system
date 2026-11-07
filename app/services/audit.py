"""审计服务：写操作自动留痕，可按用户/动作/时间检索。"""
import re

from app import db

WRITE_RULES = [
    (r"^/patients/create$", "建档", "patient"),
    (r"^/base-data/departments$", "科室维护", "department"),
    (r"^/base-data/departments/(\d+)/toggle$", "科室维护", "department"),
    (r"^/base-data/doctors$", "医生维护", "doctor"),
    (r"^/base-data/doctors/(\d+)/toggle$", "医生维护", "doctor"),
    (r"^/register/submit$", "挂号", "registration"),
    (r"^/api/register$", "挂号", "registration"),
    (r"^/registrations/(\d+)/cancel$", "退号", "registration"),
    (r"^/registrations/(\d+)/pay$", "挂号收费", "registration"),
    (r"^/schedules/create$", "排班", "schedule"),
    (r"^/schedules/(\d+)/stop$", "停诊", "schedule"),
    (r"^/drugs/create$", "药品维护", "drug"),
    (r"^/drugs/(\d+)/inventory$", "库存入库", "drug"),
    (r"^/drugs/import$", "药品导入", "drug"),
    (r"^/prescriptions/create$", "开方", "prescription"),
    (r"^/api/prescriptions$", "开方", "prescription"),
    (r"^/prescriptions/(\d+)/pay$", "处方收费", "prescription"),
    (r"^/api/prescriptions/(\d+)/pay$", "处方收费", "prescription"),
    (r"^/prescriptions/(\d+)/dispense$", "发药", "prescription"),
    (r"^/api/prescriptions/(\d+)/dispense$", "发药", "prescription"),
    (r"^/api/triage$", "AI分诊", "triage"),
    (r"^/triage$", "AI分诊", "triage"),
    (r"^/audit$", "审计查询", "audit"),
]


def classify(path: str):
    for pattern, action, object_type in WRITE_RULES:
        match = re.match(pattern, path)
        if match:
            object_id = match.group(1) if match.groups() else None
            return action, object_type, object_id
    return None


def record(user, action, object_type=None, object_id=None, detail="", ip=None):
    db.execute(
        "INSERT INTO audit_log (user_id, username, action, object_type, object_id, detail, ip) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            user["user_id"] if user else None,
            user["username"] if user else None,
            action,
            object_type,
            str(object_id) if object_id is not None else None,
            detail,
            ip,
        ),
    )
