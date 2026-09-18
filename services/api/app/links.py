from hashlib import sha256
from hmac import compare_digest, new
from time import time


LINK_PURPOSE = "order-link-v1"
LINK_TTL_SECONDS = 7 * 24 * 60 * 60


def _signature(order_id: str, expires_at: int, secret: str) -> str:
    payload = f"{LINK_PURPOSE}:{order_id}:{expires_at}".encode()
    return new(secret.encode(), payload, sha256).hexdigest()


def create_order_link(order_id: str, secret: str, ttl_seconds: int = LINK_TTL_SECONDS) -> str:
    expires_at = int(time()) + ttl_seconds
    signature = _signature(order_id, expires_at, secret)
    return f"{order_id}?exp={expires_at}&sig={signature}"


def verify_order_link(order_id: str, expires_at: int | None, signature: str | None, secret: str) -> bool:
    if expires_at is None or expires_at <= int(time()) or not signature:
        return False
    if len(signature) != 64 or any(character not in "0123456789abcdefABCDEF" for character in signature):
        return False
    return compare_digest(_signature(order_id, expires_at, secret), signature.lower())
