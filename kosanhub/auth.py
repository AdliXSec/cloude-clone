"""Autentikasi admin tunggal berbasis session Flask.

Hanya ada satu peran: semua baris di tabel users adalah admin.
- Halaman admin (blueprint web, admin) wajib login.
- API /api/*: semua method wajib admin: session login (browser) atau
  HTTP Basic (curl -u / Jenkins).
- Portal publik (blueprint public): lihat properti/kamar, ajukan sewa, cek status
  tanpa login. Form POST tetap dijaga token CSRF.
- /health, /login, dan file static tetap terbuka.
"""
import hmac
import secrets

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    abort,
)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from kosanhub import db
from kosanhub.models import User

auth_bp = Blueprint("auth", __name__)

API_BLUEPRINTS = {"properties", "rooms", "tenants", "contracts", "bills", "payments", "jobs"}
LOGIN_REQUIRED_BLUEPRINTS = {"web", "admin"}
PUBLIC_BLUEPRINTS = {"public"}

# Hash tiruan: login dengan email tak dikenal tetap menghabiskan waktu yang sama.
_DUMMY_HASH = generate_password_hash("tidak-dipakai")
_USER_KEY = "kosanhub.current_user"


def normalize_email(email):
    return (email or "").strip().lower()


def ensure_admin(email, password):
    """Buat admin bila belum ada (idempoten). Tidak pernah menimpa password yang sudah ada."""
    email = normalize_email(email)
    if db.session.scalar(db.select(User.id).filter_by(email=email)) is not None:
        return False
    db.session.add(User(email=email, password_hash=generate_password_hash(password)))
    db.session.commit()
    return True


def change_password(user, new_password):
    """Ubah password user (dari profile atau admin). Tidak ada validasi kekuatan (dilakukan di route)."""
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()


def current_user():
    # Cache per request (environ), bukan di `g`: g bisa dipakai bersama antar request
    # kalau app context sudah aktif di luar request (mis. fixture tes).
    if _USER_KEY not in request.environ:
        user_id = session.get("user_id")
        request.environ[_USER_KEY] = db.session.get(User, user_id) if user_id else None
    return request.environ[_USER_KEY]


def _basic_auth_user():
    """Untuk klien API non-browser (Jenkins smoke test, curl -u email:password)."""
    auth = request.authorization
    if auth is None or auth.type != "basic" or not auth.username:
        return None
    user = db.session.scalar(db.select(User).filter_by(email=normalize_email(auth.username)))
    valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, auth.password or "")
    return user if user is not None and valid else None


def csrf_token():
    token = session.get("csrf")
    if not token:
        token = session["csrf"] = secrets.token_urlsafe(32)
    return token


def csrf_input():
    return Markup('<input type="hidden" name="csrf_token" value="{}">').format(csrf_token())


def _verify_csrf():
    sent = request.form.get("csrf_token", "").encode()
    expected = session.get("csrf", "").encode()
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, "CSRF token tidak valid")


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("web.dashboard")


def init_auth(app):
    app.add_template_global(current_user)
    app.add_template_global(csrf_input)

    @app.before_request
    def _guard():
        bp = request.blueprint
        if bp in API_BLUEPRINTS:
            if current_user() is None and _basic_auth_user() is None:
                resp = jsonify({"error": "Unauthorized", "message": "Login admin diperlukan"})
                resp.status_code = 401
                return resp
        elif bp in LOGIN_REQUIRED_BLUEPRINTS:
            if current_user() is None:
                return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
            if request.method == "POST":
                _verify_csrf()
        elif bp in PUBLIC_BLUEPRINTS:
            if request.method == "POST":
                _verify_csrf()
        return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("web.dashboard"))
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).filter_by(email=email))
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
        if user is not None and valid:
            session.clear()  # cegah session fixation
            session["user_id"] = user.id
            session.permanent = True
            return redirect(_safe_next(request.args.get("next")))
        flash("Email atau password salah.", "error")
        return render_template("login.html", email=email), 401
    return render_template("login.html", email=email)


@auth_bp.post("/logout")
def logout():
    _verify_csrf()
    session.clear()
    return redirect(url_for("auth.login"))
