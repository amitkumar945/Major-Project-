"""
Configuration loaded from the environment.

Every secret (Mongo URI, JWT key, mail credentials) comes from the process
environment, which `python-dotenv` populates from the local `.env` file during
development. Nothing sensitive is hard-coded here; `.env.example` documents the
variables without carrying real values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load `.env` sitting next to this file. Values already present in the real
# environment win, so a production process manager can override the file.
load_dotenv(BASE_DIR / ".env", override=False)


def _int(name: str, default: int) -> int:
    """Read an integer variable, falling back when unset or malformed."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str) -> list:
    raw = os.environ.get(name) or default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _str(name: str, default: str) -> str:
    """Read a string variable, treating a blank value in `.env` as unset.

    `.env.example` ships keys like `FRONTEND_FOLDER=` with no value; without
    this, os.environ.get() would return "" and override a sensible default.
    """
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


class Config:
    """Base configuration shared by every environment."""

    # ------------------------------------------------------------- database
    MONGO_URI = _str("MONGO_URI", "mongodb://localhost:27017/grievance_management")
    MONGO_DB_NAME = _str("MONGO_DB_NAME", "")  # optional override

    # ------------------------------------------------------------------ jwt
    # No default secret: `app.py` refuses to start without JWT_SECRET_KEY so a
    # deployment can never accidentally run on a well-known signing key.
    JWT_SECRET_KEY = _str("JWT_SECRET_KEY", "")
    JWT_ALGORITHM = _str("JWT_ALGORITHM", "HS256")
    JWT_EXPIRY_HOURS = _int("JWT_EXPIRY_HOURS", 12)
    JWT_ISSUER = _str("JWT_ISSUER", "dsvv-gms")

    # Mobile sessions. A phone cannot ask the user to sign in twice a day, so
    # the app gets a SHORT access token plus a long-lived refresh token it can
    # exchange silently. The website keeps JWT_EXPIRY_HOURS above and never
    # touches either of these.
    MOBILE_ACCESS_TOKEN_MINUTES = _int("MOBILE_ACCESS_TOKEN_MINUTES", 60)
    REFRESH_TOKEN_DAYS = _int("REFRESH_TOKEN_DAYS", 30)

    # ---------------------------------------------------------------- files
    UPLOAD_FOLDER = _str("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    # Frontend caps uploads at 5 MB per file (UPLOAD_LIMITS in constants.js).
    MAX_FILE_SIZE = _int("MAX_FILE_SIZE", 5 * 1024 * 1024)
    MAX_FILES_PER_REQUEST = _int("MAX_FILES_PER_REQUEST", 5)
    # Flask's own guard covers the whole multipart body, so allow all files
    # plus a little headroom for the form fields around them.
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE * MAX_FILES_PER_REQUEST + (1024 * 1024)

    # ------------------------------------------------------------------ otp
    OTP_EXPIRY = _int("OTP_EXPIRY", 300)  # seconds
    OTP_LENGTH = _int("OTP_LENGTH", 6)
    OTP_MAX_ATTEMPTS = _int("OTP_MAX_ATTEMPTS", 5)
    OTP_RESEND_COOLDOWN = _int("OTP_RESEND_COOLDOWN", 30)  # seconds
    # In dev mode the OTP is returned in the API response instead of being
    # emailed. MUST be false once a real mail/SMS provider is configured.
    #
    # Defaults to FALSE: leaking a reset code is an account takeover, so the
    # unsafe behaviour has to be asked for explicitly rather than inherited by
    # a deployment whose .env simply never mentions the key. `TestConfig` and
    # `DevelopmentDefaults` below turn it back on for local work.
    #
    # This value is only a request. `is_otp_dev_mode()` decides the effective
    # setting and refuses to honour it outside development - see that function.
    OTP_DEV_MODE = _bool("OTP_DEV_MODE", False)
    # When true, registration requires a verified OTP before the account is
    # created. Off by default so the existing frontend register flow still works.
    OTP_REQUIRED_FOR_REGISTER = _bool("OTP_REQUIRED_FOR_REGISTER", False)

    # ----------------------------------------------------------------- cors
    # Explicit origins only - never "*" in production.
    CORS_ORIGINS = _list(
        "CORS_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:5000,http://127.0.0.1:5000",
    )

    # ----------------------------------------------------------------- push
    # Mobile push notifications (Firebase Cloud Messaging). Off by default:
    # the in-app notification feed is the source of truth and works without
    # any of this. No credential is ever hardcoded - FCM_CREDENTIALS_FILE
    # points at a service-account JSON kept OUTSIDE the repository.
    PUSH_ENABLED = _bool("PUSH_ENABLED", False)
    FCM_PROJECT_ID = _str("FCM_PROJECT_ID", "")
    FCM_CREDENTIALS_FILE = _str("FCM_CREDENTIALS_FILE", "")

    # ------------------------------------------------------------------ ocr
    # OCR is optional: complaint submission must keep working when it is off.
    OCR_ENABLED = _bool("OCR_ENABLED", False)
    OCR_ENGINE = _str("OCR_ENGINE", "tesseract")  # tesseract | easyocr
    TESSERACT_CMD = _str("TESSERACT_CMD", "")

    # -------------------------------------------------------- rate limiting
    RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
    RATE_LIMIT_AUTH = _int("RATE_LIMIT_AUTH", 10)        # requests per window
    RATE_LIMIT_OTP = _int("RATE_LIMIT_OTP", 5)
    RATE_LIMIT_WINDOW = _int("RATE_LIMIT_WINDOW", 60)    # seconds

    # ------------------------------------------------------------ behaviour
    SEED_ON_START = _bool("SEED_ON_START", True)
    FLASK_ENV = _str("FLASK_ENV", "development")
    DEBUG = _bool("FLASK_DEBUG", FLASK_ENV == "development")
    # True only for the test-suite's configuration; see `is_otp_dev_mode`.
    IS_TEST = False
    # Serve the existing frontend folder from Flask so one server runs everything.
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", True)
    FRONTEND_FOLDER = _str("FRONTEND_FOLDER", str(BASE_DIR.parent / "frontend"))


class TestConfig(Config):
    """Used by the test-suite: separate database, no seeding, OTP in dev mode."""

    MONGO_URI = _str("TEST_MONGO_URI", "mongodb://localhost:27017/grievance_management_test")
    JWT_SECRET_KEY = _str("JWT_SECRET_KEY", "") or "test-only-secret-not-for-production"
    SEED_ON_START = False
    OTP_DEV_MODE = True
    IS_TEST = True
    RATE_LIMIT_ENABLED = False
    DEBUG = False
    SERVE_FRONTEND = False


# Environments in which returning an OTP to the caller is acceptable.
NON_PRODUCTION_ENVS = {"development", "dev", "local", "test", "testing"}


def is_otp_dev_mode(config) -> bool:
    """The effective OTP dev-mode setting, which is NOT simply the flag.

    Returning a verification code in an API response hands anyone who knows an
    address the ability to reset that account's password. A single mistyped or
    forgotten line in a production `.env` must therefore not be enough to turn
    it on, so the flag is honoured only when the process is also demonstrably
    not in production: the test configuration, or Flask debug / a development
    FLASK_ENV.

    `config` is anything exposing the keys - a Flask `app.config` or a Config
    class - so callers can use whichever they hold.
    """
    get = config.get if hasattr(config, "get") else lambda key, default=None: getattr(config, key, default)

    if not get("OTP_DEV_MODE", False):
        return False
    if get("IS_TEST", False):
        return True
    return bool(get("DEBUG", False)) or str(get("FLASK_ENV", "")).lower() in NON_PRODUCTION_ENVS


def get_config(name: str = ""):
    return TestConfig if (name or os.environ.get("APP_CONFIG", "")).lower() == "test" else Config
