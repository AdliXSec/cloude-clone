"""
Konfigurasi KosanHub. Semua nilai rahasia dibaca dari environment (.env), tidak ditulis di kode.
"""
import hashlib
import os
import secrets
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()  # baca .env lokal bila ada; env dari container/Azure tetap menang


def _database_uri():
    # DATABASE_URL (jika ada) menang, mis. untuk Azure di Tubes 2.
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = quote_plus(os.getenv("DB_USER", "kosanhub"))
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "kosanhub")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


def _secret_key():
    # Harus sama di semua worker gunicorn, kalau tidak session login saling tidak valid.
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    db_password = os.getenv("DB_PASSWORD")
    if db_password:
        return hashlib.sha256(f"kosanhub-session:{db_password}".encode()).hexdigest()
    return secrets.token_hex(32)  # tanpa konfigurasi: session hilang tiap restart


class Config:
    SECRET_KEY = _secret_key()
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    BILL_DUE_DAY = int(os.getenv("BILL_DUE_DAY", "10"))
    WORKER_POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "3"))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite://")
    SQLALCHEMY_ENGINE_OPTIONS = {}
