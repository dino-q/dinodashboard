"""
Main route — GET / renders the dashboard.
"""
from flask import Blueprint, render_template, redirect, url_for

from data.auth import has_credentials
from data.tools import load_tools, load_categories, get_highlight_tool, tools_grouped_by_category
from routes.auth import is_private_mode, is_logged_in

bp = Blueprint("main", __name__)


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
