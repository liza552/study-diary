import os

os.environ.setdefault("SECRET", "test-secret")

import pytest
from fastapi import HTTPException

from app.security import hash_password, create_token, current_user_id


def test_hash_is_stable_and_salted():
    assert hash_password("1234", "salt") == hash_password("1234", "salt")
    assert hash_password("1234", "salt") != hash_password("1234", "other")
    assert hash_password("1234", "salt") != hash_password("4321", "salt")


def test_token_roundtrip():
    token = create_token(7)
    assert current_user_id(f"Bearer {token}") == 7


def test_missing_header_is_401():
    with pytest.raises(HTTPException) as e:
        current_user_id(None)
    assert e.value.status_code == 401


def test_bad_token_is_401():
    with pytest.raises(HTTPException) as e:
        current_user_id("Bearer not-a-token")
    assert e.value.status_code == 401