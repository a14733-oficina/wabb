"""Autenticação local do WABB: palavras-passe com scrypt e sessão assinada."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SECRET = os.getenv("WABB_SECRET", "wabb-local-secret-change-me").encode("utf-8")
SESSION_SECONDS = 60 * 60 * 24 * 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_text, digest_text = stored.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _encode(data: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return raw + "." + signature


def _decode(token: str) -> dict | None:
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode((raw + "===").encode()))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def create_session(user_id: int, username: str) -> str:
    return _encode({"sub": user_id, "username": username, "exp": int(time.time()) + SESSION_SECONDS})


def read_session(token: str | None) -> dict | None:
    return _decode(token) if token else None
