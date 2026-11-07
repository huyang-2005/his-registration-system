"""手动执行数据库迁移（部署/升级时使用）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, db  # noqa: E402


def main():
    if not os.path.exists(config.DB_PATH):
        print("数据库不存在，执行初始化：", config.DB_PATH)
        db.init_database()
        return
    db.run_migrations()
    print("迁移完成：", config.DB_PATH)


if __name__ == "__main__":
    main()
