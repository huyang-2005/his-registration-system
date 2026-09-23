"""初始化 SQLite 数据库：重建表结构并写入模拟数据。

用法：
    python init_db.py
"""
from db import DB_PATH, init_database

if __name__ == "__main__":
    init_database()
    print("数据库初始化完成：", DB_PATH)
