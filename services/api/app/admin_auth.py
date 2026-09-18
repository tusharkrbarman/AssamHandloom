"""Single-owner authentication for the FastAPI admin surface."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest, new
from json import dumps, loads
from secrets import token_bytes, token_urlsafe
from typing import Mapping

from fastapi import HTTPException, Request
from psycopg_pool import ConnectionPool

from .dependencies import require_same_origin
from .settings import Settings


COOKIE_NAME = "luit_admin"
PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
LOCKOUT_SECONDS = 15 * 60
MIN_SECRET_LENGTH = 32


@dataclass(frozen=True, slots=True)
class AdminSession:
    owner_id: str
    session_version: int
    expires_at: int
    csrf: str


@dataclass(frozen=True, slots=True)
class AuthenticatedOwner:
    owner: dict[str, object]
    session: AdminSession


@dataclass(frozen=True, slots=True)
class OwnerRecord:
    id: str
    email: str
    password_hash: str
    password_salt: str
    password_iterations: int
    session_version: int


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _secret(secret: str | None) -> str:
    value = (secret or "").strip()
    if len(value) < MIN_SECRET_LENGTH:
        raise _error(500, "invalid_configuration", "Authentication is unavailable.")
    return value


def _b64(value: bytes) -> str:
    return urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    if not value or len(value) > 4096 or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise ValueError("invalid_base64")
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signed_value(session: AdminSession, secret: str) -> str:
    payload = _b64(
        dumps(
            {
                "ownerId": session.owner_id,
                "sessionVersion": session.session_version,
                "expiresAt": session.expires_at,
                "csrf": session.csrf,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = new(_secret(secret).encode(), payload.encode(), sha256).digest()
    return f"{payload}.{_b64(signature)}"


def session_cookie(session: AdminSession, secret: str) -> str:
    if session.owner_id != "owner" or session.session_version < 1 or session.expires_at < 0 or len(session.csrf) < MIN_SECRET_LENGTH:
        raise _error(500, "invalid_configuration", "Authentication is unavailable.")
    return (
        f"{COOKIE_NAME}={_signed_value(session, secret)}; Path=/admin; Max-Age={SESSION_SECONDS}; "
        "HttpOnly; Secure; SameSite=Strict"
    )


def clear_session_cookie() -> str:
    return f"{COOKIE_NAME}=; Path=/admin; Max-Age=0; HttpOnly; Secure; SameSite=Strict"


def verify_session_cookie(value: str, secret: str) -> AdminSession:
    try:
        payload, encoded_signature = value.split(".", 1)
        if value.count(".") != 1:
            raise ValueError("invalid_segments")
        expected = new(_secret(secret).encode(), payload.encode(), sha256).digest()
        if not compare_digest(_b64(expected), encoded_signature):
            raise ValueError("invalid_signature")
        parsed = loads(_unb64(payload))
        if not isinstance(parsed, dict):
            raise ValueError("invalid_payload")
        owner_id = parsed.get("ownerId")
        session_version = parsed.get("sessionVersion")
        expires_at = parsed.get("expiresAt")
        csrf = parsed.get("csrf")
        if (
            owner_id != "owner"
            or isinstance(session_version, bool)
            or not isinstance(session_version, int)
            or session_version < 1
            or isinstance(expires_at, bool)
            or not isinstance(expires_at, int)
            or expires_at < 0
            or not isinstance(csrf, str)
            or len(csrf) < MIN_SECRET_LENGTH
        ):
            raise ValueError("invalid_payload")
        return AdminSession(owner_id, session_version, expires_at, csrf)
    except (ValueError, TypeError, UnicodeDecodeError, OverflowError, Base64Error):
        raise _error(401, "invalid_session", "Please sign in again.") from None


def _cookie_value(request: Request) -> str | None:
    header = request.headers.get("cookie", "")
    for part in header.split(";"):
        name, separator, value = part.strip().partition("=")
        if name == COOKIE_NAME and separator:
            return value or None
    return None


def _owner_record(connection) -> OwnerRecord | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, email, password_hash, password_salt,
              password_iterations, session_version
            FROM owner WHERE id = 'owner'
            """,
            (),
        )
        row = cursor.fetchone()
    return OwnerRecord(**row) if row else None


def require_owner(request: Request, pool: ConnectionPool, secret: str | None) -> AuthenticatedOwner:
    value = _cookie_value(request)
    if not value:
        raise _error(401, "authentication_required", "Please sign in.")
    session = verify_session_cookie(value, _secret(secret))
    if session.expires_at <= int(datetime.now(timezone.utc).timestamp()):
        raise _error(401, "session_expired", "Please sign in again.")
    with pool.connection() as connection:
        owner = _owner_record(connection)
    if not owner or owner.session_version != session.session_version:
        raise _error(401, "invalid_session", "Please sign in again.")
    return AuthenticatedOwner(
        {"id": owner.id, "email": owner.email, "sessionVersion": owner.session_version},
        session,
    )


def require_csrf(request: Request, session: AdminSession, form: Mapping[str, object]) -> None:
    require_same_origin(request)
    submitted = form.get("csrf")
    if not isinstance(submitted, str) or not submitted or not compare_digest(submitted, session.csrf):
        raise _error(403, "invalid_csrf", "The form has expired. Please try again.")


def normalised_email(value: str) -> str:
    email = value.strip().lower()
    parts = email.split("@")
    if len(email) < 3 or len(email) > 254 or len(parts) != 2 or not all(parts) or any(character.isspace() for character in email):
        raise _error(422, "invalid_email", "Enter a valid email address.")
    return email


def valid_password(value: str) -> str:
    if len(value) < 12 or len(value) > 128:
        raise _error(422, "invalid_password", "The password must contain between 12 and 128 characters.")
    return value


def _password_record(password: str) -> tuple[str, str, int]:
    salt = token_bytes(16)
    derived = pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS, dklen=32)
    return _b64(derived), _b64(salt), PASSWORD_ITERATIONS


def _password_matches(password: str, owner: OwnerRecord | None) -> bool:
    if owner:
        try:
            salt = _unb64(owner.password_salt)
            expected = _unb64(owner.password_hash)
            iterations = owner.password_iterations
        except ValueError:
            return False
    else:
        salt = b"\x00" * 16
        expected = b"\x00" * 32
        iterations = PASSWORD_ITERATIONS
    actual = pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=32)
    return compare_digest(actual, expected)


def secret_matches(value: str, expected: str | None) -> bool:
    left = sha256(value.encode()).digest()
    right = sha256((expected or "").encode()).digest()
    return compare_digest(left, right)


def new_session(session_version: int) -> AdminSession:
    return AdminSession(
        owner_id="owner",
        session_version=session_version,
        expires_at=int(datetime.now(timezone.utc).timestamp()) + SESSION_SECONDS,
        csrf=token_urlsafe(32),
    )


def lockout_key(request: Request, email: str) -> str:
    source = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "unknown")
    return _b64(sha256(f"admin\x00{email}\x00{source}".encode()).digest())


def check_lockout(connection, key: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT locked_until FROM login_lockouts WHERE key_hash = %s", (key,))
        row = cursor.fetchone()
    locked_until = row.get("locked_until") if row else None
    if isinstance(locked_until, str):
        try:
            locked_until = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
        except ValueError:
            return False
    if isinstance(locked_until, datetime) and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return bool(locked_until and locked_until > datetime.now(timezone.utc))


def record_failure(connection, key: str) -> None:
    now = datetime.now(timezone.utc)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT failed_count, locked_until FROM login_lockouts WHERE key_hash = %s FOR UPDATE",
            (key,),
        )
        current = cursor.fetchone()
        locked_until = current.get("locked_until") if current else None
        if isinstance(locked_until, str):
            try:
                locked_until = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
            except ValueError:
                locked_until = None
        if isinstance(locked_until, datetime) and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until and locked_until <= now:
            failures = 1
        else:
            failures = int(current.get("failed_count", 0)) + 1 if current else 1
        lock_until = now + timedelta(seconds=LOCKOUT_SECONDS) if failures >= 5 else None
        cursor.execute(
            """
            INSERT INTO login_lockouts (key_hash, failed_count, locked_until, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key_hash) DO UPDATE SET
              failed_count = excluded.failed_count,
              locked_until = excluded.locked_until,
              updated_at = excluded.updated_at
            """,
            (key, failures, lock_until, now),
        )


def password_matches(password: str, owner: OwnerRecord | None) -> bool:
    return _password_matches(password, owner)


def create_owner(connection, email: str, password: str) -> None:
    password_hash, password_salt, iterations = _password_record(password)
    now = datetime.now(timezone.utc)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO owner (
              id, email, password_hash, password_salt, password_iterations,
              session_version, created_at, updated_at
            ) VALUES ('owner', %s, %s, %s, %s, 1, %s, %s)
            """,
            (email, password_hash, password_salt, iterations, now, now),
        )


def reset_owner_password(connection, email: str, password: str) -> bool:
    password_hash, password_salt, iterations = _password_record(password)
    now = datetime.now(timezone.utc)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE owner
            SET password_hash = %s, password_salt = %s, password_iterations = %s,
              session_version = session_version + 1, updated_at = %s
            WHERE id = 'owner' AND email = %s
            """,
            (password_hash, password_salt, iterations, now, email),
        )
        return cursor.rowcount == 1


def owner_record(connection) -> OwnerRecord | None:
    return _owner_record(connection)


def form_value(form: Mapping[str, object], name: str) -> str:
    value = form.get(name)
    return value if isinstance(value, str) else ""
