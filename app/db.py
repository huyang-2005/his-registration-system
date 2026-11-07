"""数据库访问层：连接、查询、事务与迁移执行。"""
import os
import sqlite3

from app import config

DB_PATH = config.DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def init_database(force=False):
    """执行 schema.sql + seed_data.sql，再补齐增量迁移。"""
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    try:
        with open(config.SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        with open(config.SEED_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()
    run_migrations()


def _backup_database():
    if not os.path.exists(DB_PATH):
        return None
    backup_dir = os.path.join(config.DATA_DIR, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    from datetime import datetime

    target = os.path.join(backup_dir, "his_%s.db" % datetime.now().strftime("%Y%m%d%H%M%S"))
    with open(DB_PATH, "rb") as src, open(target, "wb") as dst:
        dst.write(src.read())
    return target


def run_migrations():
    """按版本顺序执行 app/migrations 下的迁移，已执行的记录在 schema_migrations。"""
    from app.migrations import list_migrations

    conn = get_conn()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime')))"
        )
        conn.commit()
        applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        pending = [m for m in list_migrations() if m.VERSION not in applied]
        if pending:
            _backup_database()
        for module in pending:
            module.up(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?,?)",
                (module.VERSION, module.NAME),
            )
            conn.commit()
            print("迁移已执行：%03d %s" % (module.VERSION, module.NAME))
    finally:
        conn.close()


def transaction(immediate=True):
    """返回一个手动管理的事务连接，调用方负责 commit/rollback/close。"""
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    return conn
