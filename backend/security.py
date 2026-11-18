"""
security.py - Password hashing, signed session tokens and a login rate limiter.
Standard library only, so there is nothing extra to install.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque

import config

# ---------- Passwords ----------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
        )
        return hmac.compare_digest(expected, _unb64(digest))
    except Exception:
        return False


# ---------- Session tokens ----------

_secret_cache: bytes | None = None


def _secret() -> bytes:
    """SECRET_KEY from the environment, else a random key saved next to the code (dev only)."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    if config.SECRET_KEY:
        _secret_cache = config.SECRET_KEY.encode()
    else:
        key_file = config.BASE_DIR / ".secret_key"
        if not key_file.exists():
            key_file.write_text(secrets.token_urlsafe(48))
            try:
                key_file.chmod(0o600)
            except OSError:
                pass
            print("WARNING: SECRET_KEY is not set; generated backend/.secret_key. Set SECRET_KEY in production.")
        _secret_cache = key_file.read_text().strip().encode()
    return _secret_cache


def make_token(user_id: str, days: int | None = None) -> str:
    exp = int(time.time()) + 86400 * (days or config.SESSION_DAYS)
    body = _b64(json.dumps({"uid": user_id, "exp": exp}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token: str | None) -> str | None:
    """Return the user id if the token is genuine and not expired, else None."""
    if not token or "." not in token:
        return None
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            return None
        return payload["uid"]
    except Exception:
        return None


# ---------- Rate limiting (in memory, per server process) ----------

class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str) -> deque:
        q = self.hits[key]
        cutoff = time.time() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.limit

    def add(self, key: str) -> None:
        self._prune(key).append(time.time())

    def reset(self, key: str) -> None:
        self.hits.pop(key, None)


login_limiter = RateLimiter(limit=8, window_seconds=600)
signup_limiter = RateLimiter(limit=10, window_seconds=3600)
