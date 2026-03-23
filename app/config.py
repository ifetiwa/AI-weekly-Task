"""Application configuration."""

import os

from cryptography.fernet import Fernet

# Load .env in local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(os.path.dirname(basedir), "instance")

# Vercel has a read-only filesystem; only create instance dir locally
try:
    os.makedirs(instance_dir, exist_ok=True)
except OSError:
    pass


def _fix_db_url(url: str) -> str:
    """Neon / Heroku give postgres:// but SQLAlchemy needs postgresql://."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(instance_dir, "app.db"),
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Neon requires SSL for connections
    _db_url = SQLALCHEMY_DATABASE_URI
    if _db_url and _db_url.startswith("postgresql"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {"sslmode": "require"},
            "pool_pre_ping": True,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # Encryption key for stored credentials
    _env_key = os.environ.get("ENCRYPTION_KEY")
    if _env_key:
        ENCRYPTION_KEY = (
            _env_key if isinstance(_env_key, bytes) else _env_key.encode()
        )
    else:
        _key_file = os.path.join(instance_dir, ".encryption_key")
        if os.path.exists(_key_file):
            with open(_key_file, "rb") as _f:
                ENCRYPTION_KEY = _f.read()
        else:
            ENCRYPTION_KEY = Fernet.generate_key()
            try:
                with open(_key_file, "wb") as _f:
                    _f.write(ENCRYPTION_KEY)
            except OSError:
                pass  # Read-only filesystem (Vercel)
