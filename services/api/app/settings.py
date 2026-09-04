from dataclasses import dataclass
from os import environ


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str | None
    cookie_signing_key: str | None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    resend_api_key: str | None = None
    mail_from: str | None = None
    public_base_url: str | None = None
    admin_setup_token: str | None = None
    admin_recovery_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=environ.get("DATABASE_URL") or None,
            cookie_signing_key=environ.get("COOKIE_SIGNING_KEY") or None,
            razorpay_key_id=environ.get("RAZORPAY_KEY_ID") or None,
            razorpay_key_secret=environ.get("RAZORPAY_KEY_SECRET") or None,
            razorpay_webhook_secret=environ.get("RAZORPAY_WEBHOOK_SECRET") or None,
            resend_api_key=environ.get("RESEND_API_KEY") or None,
            mail_from=environ.get("MAIL_FROM") or None,
            public_base_url=environ.get("PUBLIC_BASE_URL") or None,
            admin_setup_token=environ.get("ADMIN_SETUP_TOKEN") or None,
            admin_recovery_token=environ.get("ADMIN_RECOVERY_TOKEN") or None,
        )
