import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, HTTPException, Response

from . import store

COOKIE_NAME = "taskflow_session"
SESSION_DAYS = 7  # DECISIONS D-011
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt, digest = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
    except ValueError:
        return False
    actual = hashlib.scrypt(password.encode(), salt=salt, dklen=len(digest), **_SCRYPT)
    return hmac.compare_digest(actual, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(response: Response, user_id: int) -> None:
    """무작위 토큰은 쿠키로만 나가고, DB에는 해시만 남긴다."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(days=SESSION_DAYS)
    store.create_session(_token_hash(token), user_id, expires.strftime("%Y-%m-%dT%H:%M:%S"))
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )


def end_session(response: Response, token: str | None) -> None:
    if token:
        store.delete_session(_token_hash(token))
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")


def current_user(taskflow_session: str | None = Cookie(default=None)) -> dict:
    user = store.get_session_user(_token_hash(taskflow_session)) if taskflow_session else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
