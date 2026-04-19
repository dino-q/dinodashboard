"""
Main route — GET / renders the dashboard.
"""
from flask import Blueprint, render_template, redirect, url_for

from data.tools import load_tools, load_categories, get_highlight_tool, tools_grouped_by_category
from routes.auth import is_private_mode, is_logged_in

bp = Blueprint("main", __name__)


# UptimeRobot 每 5 分鐘打一次，讓 Render 免費方案不會進入 sleep。
# 故意不查 DB、不渲染 template——回傳純文字最省資源也最快。
@bp.route("/ping")
def ping():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}


@bp.route("/")
def index():
    # Private mode gate (set via PRIVATE_MODE env var on cloud deploys)
    if is_private_mode() and not is_logged_in():
        return redirect(url_for("auth.login_page"))
    hero = get_highlight_tool()
    categories = load_categories()
    groups = tools_grouped_by_category()
    tools = load_tools()
    total = len(tools)
    # Stats
    all_tags = {tag for t in tools for tag in t.get("tags", [])}
    published = sum(1 for t in tools if t.get("url") or t.get("external_url"))
    return render_template(
        "dashboard.html",
        hero=hero,
        categories=categories,
        groups=groups,
        total=total,
        tech_count=len(all_tags),
        published=published,
        active_category=None,
        active_status=None,
    )
