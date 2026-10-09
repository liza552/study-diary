from pydantic import BaseModel


class LoginIn(BaseModel):
    login: str
    password: str