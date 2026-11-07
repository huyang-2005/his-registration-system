"""003 重建用户表：角色编码化 + bcrypt 密码哈希（修复明文密码）。"""
import bcrypt

from app import config

VERSION = 3
NAME = "auth_rbac"

USERNAME_MAP = {"guahao": "cashier", "shoufei": "cashier2"}
ROLE_MAP = {
    "挂号员": "cashier",
    "收费员": "cashier",
    "管理员": "admin",
    "医生": "doctor",
    "药师": "pharmacist",
}

DDL = """
CREATE TABLE sys_user_new (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    real_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'cashier', 'pharmacist')),
    status        TEXT NOT NULL DEFAULT '启用' CHECK (status IN ('启用', '停用'))
);
"""


def _hash(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def up(conn):
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    old_rows = conn.execute("SELECT * FROM sys_user ORDER BY user_id").fetchall()

    used_names = set()
    mapped = []
    for row in old_rows:
        username = USERNAME_MAP.get(row["username"], row["username"])
        if username in used_names:
            username = username + "_" + str(row["user_id"])
        used_names.add(username)
        mapped.append(
            {
                "user_id": row["user_id"],
                "username": username,
                "real_name": row["real_name"],
                "role": ROLE_MAP.get(row["role"], "cashier"),
                "status": "停用" if username == "cashier2" else "启用",
            }
        )

    accounts = [
        ("doctor", "张伟", "doctor"),
        ("pharmacist", "王药师", "pharmacist"),
    ]
    next_id = max([m["user_id"] for m in mapped] or [0]) + 1
    existing_roles = {m["role"] for m in mapped}
    for username, real_name, role in accounts:
        if role in existing_roles:
            continue
        mapped.append(
            {
                "user_id": next_id,
                "username": username,
                "real_name": real_name,
                "role": role,
                "status": "启用",
            }
        )
        next_id += 1

    conn.executescript(DDL)
    for item in mapped:
        conn.execute(
            "INSERT INTO sys_user_new (user_id, username, password_hash, real_name, role, status) "
            "VALUES (?,?,?,?,?,?)",
            (
                item["user_id"],
                item["username"],
                _hash(config.DEMO_PASSWORD),
                item["real_name"],
                item["role"],
                item["status"],
            ),
        )
    conn.execute("DROP TABLE sys_user")
    conn.execute("ALTER TABLE sys_user_new RENAME TO sys_user")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
