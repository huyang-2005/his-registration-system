"""增量迁移集合。禁止删库重建，每个迁移都需可重复执行或带存在性检查。"""
from app.migrations import m001_pharmacy, m002_insurance_category, m003_auth_rbac, m004_audit_log

_MODULES = [m001_pharmacy, m002_insurance_category, m003_auth_rbac, m004_audit_log]


def list_migrations():
    return sorted(_MODULES, key=lambda m: m.VERSION)
