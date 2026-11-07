"""应用配置：全部通过环境变量注入，禁止硬编码密钥。"""
import os
import secrets

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATA_DIR = os.environ.get("HIS_DATA_DIR", os.path.join(BASE_DIR, "data"))

DB_PATH = os.environ.get("HIS_DB_PATH", os.path.join(BASE_DIR, "his.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SEED_PATH = os.path.join(BASE_DIR, "seed_data.sql")


def _load_or_create_secret_key() -> str:
    """优先读环境变量；开发环境落盘生成随机密钥，避免硬编码。"""
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key
    os.makedirs(DATA_DIR, exist_ok=True)
    key_file = os.path.join(DATA_DIR, ".secret_key")
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    with open(key_file, "w", encoding="utf-8") as f:
        f.write(key)
    return key


SECRET_KEY = _load_or_create_secret_key()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

# 演示账号统一密码，仅在初始化/迁移时使用，写入数据库前会做 bcrypt 哈希
DEMO_PASSWORD = os.environ.get("HIS_DEMO_PASSWORD", "His@123456")

# AI 分诊（实验十一）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
TRIAGE_TIMEOUT_SECONDS = float(os.environ.get("TRIAGE_TIMEOUT_SECONDS", "10"))

ROLE_NAMES = {
    "admin": "管理员",
    "doctor": "医生",
    "cashier": "收费员",
    "pharmacist": "药师",
}
