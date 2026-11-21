from flask import Blueprint, jsonify
from sqlalchemy import text

from kosanhub import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        # 503 supaya Smoke Test di pipeline gagal bila DB tidak terhubung.
        return jsonify({"status": "error", "database": "disconnected", "detail": exc.__class__.__name__}), 503
