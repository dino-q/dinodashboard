"""
Admin routes — user management (admin-only).
"""
from flask import Blueprint, render_template, request, redirect, url_for

from data.auth import (
    list_users, approve, set_role, delete_user, get_user,
)
from routes.auth import admin_required, current_user

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _count_admins() -> int:
    return sum(1 for u in list_users() if u.get("role") == "admin")


@bp.route("/users")
@admin_required
def users_page():
    users = list_users()
    # Pending first, then alpha by username
    users_sorted = sorted(users, key=lambda u: (u.get("approved", True), u.get("username", "")))
    return render_template("admin_users.html", users=users_sorted, current=current_user())


@bp.route("/users/<username>/approve", methods=["POST"])
@admin_required
def approve_user(username):
    role = request.form.get("role", "viewer")
    if role not in ("viewer", "editor"):
        role = "viewer"
    approve(username, role)
    return redirect(url_for("admin.users_page"))


@bp.route("/users/<username>/role", methods=["POST"])
@admin_required
def change_role(username):
    role = request.form.get("role", "viewer")
    if role not in ("admin", "editor", "viewer"):
        return ("Invalid role", 400)
    target = get_user(username)
    if not target:
        return ("Not found", 404)
    # Prevent demoting the last admin
    if target.get("role") == "admin" and role != "admin" and _count_admins() <= 1:
        return ("不能降級唯一的 admin", 400)
    set_role(username, role)
    return redirect(url_for("admin.users_page"))


@bp.route("/users/<username>/delete", methods=["POST"])
@admin_required
def delete_user_endpoint(username):
    me = current_user()
    if me and me["username"] == username:
        return ("不能刪除自己", 400)
    target = get_user(username)
    if target and target.get("role") == "admin" and _count_admins() <= 1:
        return ("不能刪除唯一的 admin", 400)
    delete_user(username)
    return redirect(url_for("admin.users_page"))
