"""数据库连接工具。"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "his.db")


def get_conn():
    """获取数据库连接，开启外键约束并返回字典风格的行。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        return cur.fetchall()
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


def init_database():
    """执行 schema.sql 与 seed_data.sql 重建数据库。"""
    conn = get_conn()
    try:
        with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        with open(os.path.join(BASE_DIR, "seed_data.sql"), "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("数据库初始化完成：", DB_PATH)
