"""Configuration Flask."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    FERNET_KEY = os.environ.get("FERNET_KEY", "")

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'balsp.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload logos
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "logos"
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 Mo
    ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

    # Admin initial
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")
