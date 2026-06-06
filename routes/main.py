"""
Main route — GET / renders the dashboard.
"""
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for

from data.tools import load_tools, load_categories, get_highlight_tool, tools_grouped_by_category
from routes.auth import is_private_mode, is_logged_in

bp = Blueprint("main", __name__)


def _local_url_info(url: str):
    """把工具的本地網址解析成 (port, host)。
    支援 `http://localhost:5050`、`localhost:5050`、`127.0.0.1:8000/path` 等寫法。
    無 port 回傳 (None, host)；解析失敗回傳 (None, "")。"""
    u = (url or "").strip()
    if not u:
        return None, ""
    if "://" not in u:
        u = "http://" + u
    try:
        parsed = urlparse(u)
        return parsed.port, (parsed.hostname or "").lower()
    except ValueError:
        return None, ""


def build_local_map(tools):
    """產生「本地」分頁用的 port → 工具 對照清單，依 port 由小到大排序（無 port 排最後）。"""
    rows = []
    for t in tools:
        url = (t.get("url") or "").strip()
        if not url:
            continue
        port, host = _local_url_info(url)
        rows.append({
            "id": t.get("id"),
            "name": t.get("name") or t.get("id"),
            "name_zh": t.get("name_zh") or t.get("name") or t.get("id"),
            "url": url,
            "port": port,
            "host": host,
            "color": t.get("color") or "#6366F1",
            "icon": t.get("icon") or "box",
            "category": t.get("category"),
            "status": t.get("status"),
        })
    rows.sort(key=lambda r: (r["port"] is None, r["port"] or 0, r["name_zh"]))
    return rows


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
        local_map=build_local_map(tools),
        active_category=None,
        active_status=None,
    )
