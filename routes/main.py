"""
Main route — GET / renders the dashboard.
"""
from flask import Blueprint, render_template, redirect, url_for

from data.tools import (
    load_tools, load_categories, get_highlight_tool, tools_grouped_by_category,
    build_local_map,
)
from routes.auth import is_private_mode, is_logged_in

bp = Blueprint("main", __name__)


# UptimeRobot 每 5 分鐘打一次，讓 Render 免費方案不會進入 sleep。
# 故意不查 DB、不渲染 template——回傳純文字最省資源也最快。
@bp.route("/ping")
def ping():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}


# 保活（含 DB）：跟 /ping 一樣防 Render sleep，但會「真的查一次 Supabase」。
# 免費版 Supabase 連續 7 天「資料庫零活動」就會自動暫停（2026-06 踩過：keep-alive
# 只打 /ping 不碰 DB → Render 醒著但 Supabase 看不到活動 → 被暫停 → 全站 500）。
# 把 cron-job.org 的排程改打這條，就能讓 Supabase 每次都看到一筆查詢、不再閒置暫停。
# 查詢極輕量（select 1 筆 id）；失敗回 503 讓 cron 寄失敗通知，當作 DB 不可用的早期警報。
@bp.route("/ping-db")
def ping_db():
    from data.supabase_client import get_client
    try:
        get_client().table("tools").select("id").limit(1).execute()
    except Exception as e:
        return f"db-unreachable: {type(e).__name__}", 503, \
            {"Content-Type": "text/plain; charset=utf-8"}
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
