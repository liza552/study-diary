from fastapi import APIRouter, HTTPException

from app.database import db
from app.schemas import LoginIn
from app.security import create_token, hash_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn):
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (body.login,)).fetchone()
    conn.close()
    if not user or hash_password(body.password, user["salt"]) != user["password_hash"]:
        raise HTTPException(401, "Неверный логин или пароль")
    return {"token": create_token(user["id"])}