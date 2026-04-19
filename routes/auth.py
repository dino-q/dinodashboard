"""
Auth routes — login / logout / first-run setup / register / decorators / helpers.
"""
import os
from functools import wraps

from flask import Blueprint, request, render_template, redirect, url_for, session, make_response

from data.auth import (
    has_any_user, has_admin, create_user, verify, get_user,
)

bp = Blueprint("auth", __name__)


# ---------- env flags ----------
def _env_flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def is_private_mode() -> bool:
    """If True, the main dashboard requires login (use for cloud deployment)."""
    return _env_flag("PRIVATE_MODE", False)


def is_registration_open() -> bool:
    """If True, /register is available (default: open)."""
    return _env_flag("ALLOW_REGISTRATION", True)


# ---------- session / role helpers ----------
def current_user() -> dict | None:
    uname = session.get("username")
    if not uname:
        return None
    return get_user(uname)


def is_logged_in() -> bool:
    return bool(session.get("logged_in")) and current_user() is not None


def current_role() -> str | None:
    u = current_user()
    return u.get("role") if u else None


def is_admin() -> bool:
    return current_role() == "admin"


def is_editor() -> bool:
    return current_role() in ("admin", "editor")


def is_viewer() -> bool:
    return current_role() in ("admin", "editor", "viewer")


# ---------- decorators ----------
def _deny(hx_redirect_to: str | None = None, status: int = 401):
    """Return an appropriate response for denied requests."""
    if request.headers.get("HX-Request"):
        resp = make_response("", status)
        if hx_redirect_to:
            resp.headers["HX-Redirect"] = hx_redirect_to
        return resp
    if hx_redirect_to:
        return redirect(hx_redirect_to)
    return make_response("Forbidden", 403)


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not is_logged_in():
            return _deny(url_for("auth.login_page"), 401)
        return f(*args, **kwargs)
    return wrap


def editor_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not is_logged_in():
            return _deny(url_for("auth.login_page"), 401)
        if not is_editor():
            return _deny(None, 403)
        return f(*args, **kwargs)
    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not is_logged_in():
            return _deny(url_for("auth.login_page"), 401)
        if not is_admin():
            return _deny(url_for("main.index"), 403)
        return f(*args, **kwargs)
    return wrap


# ---------- routes ----------
@bp.route("/setup", methods=["GET", "POST"])
def setup():
    if has_admin():
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()
        if not username or not password:
            return render_template("auth.html", mode="setup", error="請填寫帳號和密碼")
        if password != confirm:
            return render_template("auth.html", mode="setup", error="密碼不一致")
        if len(password) < 4:
            return render_template("auth.html", mode="setup", error="密碼至少 4 個字元")
        u = create_user(username, password, role="admin", approved=True)
        if not u:
            return render_template("auth.html", mode="setup", error="帳號已存在")
        session["logged_in"] = True
        session["username"] = u["username"]
        return redirect(url_for("main.index"))
    return render_template("auth.html", mode="setup", error=None)


@bp.route("/login", methods=["GET", "POST"])
def login_page():
    if not has_admin():
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        u = verify(username, password)
        if u:
            session["logged_in"] = True
            session["username"] = u["username"]
            return redirect(url_for("main.index"))
        existing = get_user(username)
        if existing and not existing.get("approved"):
            err = "您的帳號尚未核准，請等管理員核准"
        else:
            err = "帳號或密碼錯誤"
        return render_template("auth.html", mode="login", error=err,
                               allow_register=is_registration_open())
    return render_template("auth.html", mode="login", error=None,
                           allow_register=is_registration_open())


@bp.route("/register", methods=["GET", "POST"])
def register_page():
    if not is_registration_open():
        return redirect(url_for("auth.login_page"))
    if not has_admin():
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()
        if not username or not password:
            return render_template("auth.html", mode="register", error="請填寫帳號和密碼")
        if password != confirm:
            return render_template("auth.html", mode="register", error="密碼不一致")
        if len(password) < 4:
            return render_template("auth.html", mode="register", error="密碼至少 4 個字元")
        u = create_user(username, password, role="viewer", approved=False)
        if not u:
            return render_template("auth.html", mode="register", error="帳號已存在")
        return render_template("auth.html", mode="register_done", error=None,
                               registered_username=u["username"])
    return render_template("auth.html", mode="register", error=None)


@bp.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
    return redirect(url_for("main.index"))
