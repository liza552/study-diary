import os
import hashlib
import datetime as dt

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()
SECRET = os.environ["SECRET"]


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def current_user_id(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нужна авторизация")
    try:
        data = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
        return int(data["sub"])
    except Exception:
        raise HTTPException(401, "Сессия истекла, войдите снова")