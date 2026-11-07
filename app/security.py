"""密码哈希与 JWT 签发/校验。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app import config


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user["user_id"]),
        "username": user["username"],
        "role": user["role"],
        "real_name": user["real_name"],
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str):
    """校验失败返回 None，不抛出异常，便于统一 401 处理。"""
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
