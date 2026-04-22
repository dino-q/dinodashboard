"""
API routes — CRUD + filter + screenshot upload + AI suggest (HTMX endpoints).
"""
import json
import os
import random
import re
import urllib.request
import urllib.parse
import uuid

from flask import Blueprint, request, render_template, make_response, jsonify

from data.supabase_client import get_client
from data.tools import (
    load_tools, load_categories, get_tool, get_highlight_tool,
    tools_grouped_by_category, add_tool, update_tool, delete_tool,
    update_screenshot, toggle_starred, reorder_tool, load_env_types,
    load_quick_inputs, save_quick_input_settings,
)
from data.auto_tag import auto_tag_all
from routes.auth import login_required, editor_required

bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# Curated accent palette for new tools — picked randomly on new form load
ACCENT_PALETTE = [
    "#6366F1",  # indigo
    "#818CF8",  # indigo-light
    "#8B5CF6",  # violet
    "#A78BFA",  # purple
    "#EC4899",  # pink
    "#EF4444",  # red
    "#F97316",  # orange
    "#F59E0B",  # amber
    "#22C55E",  # green
    "#10B981",  # emerald
    "#14B8A6",  # teal
    "#0EA5E9",  # sky
    "#3B82F6",  # blue
    "#64748B",  # slate
]


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _grid_response(category=None, q=None, toast_msg=None, include_oob=True, status=None,
                   has_external=False, has_local_url=False, has_notion=False,
                   has_github=False, has_gas=False):
    """Return re-rendered grid partial with optional toast + OOB featured swap."""
    hero = get_highlight_tool()
    groups = tools_grouped_by_category(category, q, status, has_external, has_local_url,
                                       has_notion, has_github, has_gas)
    categories = load_categories()
    total = len(load_tools())
    html = render_template(
        "partials/_tool_grid.html",
        hero=hero,
        groups=groups,
        categories=categories,
        total=total,
        active_category=category,
        active_status=status,
    )
    if include_oob:
        html += render_template("partials/_featured_oob.html", hero=hero)
        html += render_template("partials/_toc_oob.html", groups=groups)
    resp = make_response(html)
    if toast_msg:
        resp.headers["HX-Trigger"] = json.dumps({"showToast": toast_msg})
    return resp


# ------------------------------------------------------------------
# Filter / search
# ------------------------------------------------------------------

@bp.route("/tools")
def list_tools():
    category = request.args.get("category", "").strip() or None
    q = request.args.get("q", "").strip() or None
    status = request.args.get("status", "").strip() or None
    has_external = request.args.get("has_external") == "1"
    has_local_url = request.args.get("has_local_url") == "1"
    has_notion = request.args.get("has_notion") == "1"
    has_github = request.args.get("has_github") == "1"
    has_gas = request.args.get("has_gas") == "1"
    return _grid_response(category, q, include_oob=False, status=status,
                          has_external=has_external, has_local_url=has_local_url,
                          has_notion=has_notion, has_github=has_github, has_gas=has_gas)


# ------------------------------------------------------------------
# Detail view
# ------------------------------------------------------------------

@bp.route("/tool/<tool_id>/detail")
def detail(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return "Tool not found", 404
    return render_template("partials/_tool_detail.html", tool=tool)


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------

@bp.route("/tool", methods=["POST"])
@editor_required
def create_tool():
    form = request.form.to_dict()
    tool = add_tool(form)
    return _grid_response(toast_msg=f"已新增工具：{tool['name']}")


@bp.route("/tool/<tool_id>/edit")
@editor_required
def edit_form(tool_id):
    tool = get_tool(tool_id)
    if not tool:
        return "Tool not found", 404
    categories = load_categories()
    env_types = load_env_types()
    quick_inputs = load_quick_inputs()
    return render_template("partials/_tool_form.html", tool=tool, categories=categories,
                           mode="edit", palette=ACCENT_PALETTE, env_types=env_types,
                           quick_inputs=quick_inputs)


@bp.route("/tool/new")
@editor_required
def new_form():
    categories = load_categories()
    default_color = random.choice(ACCENT_PALETTE)
    env_types = load_env_types()
    quick_inputs = load_quick_inputs()
    # Pre-assign UUID so screenshot upload URL `/api/tool/<id>/screenshots` has
    # a stable target before the tool is persisted. add_tool honors form.id.
    pending_id = uuid.uuid4().hex
    return render_template("partials/_tool_form.html", tool=None, categories=categories,
                           mode="new", palette=ACCENT_PALETTE, default_color=default_color,
                           env_types=env_types, quick_inputs=quick_inputs,
                           pending_id=pending_id)


@bp.route("/tool/<tool_id>", methods=["POST"])
@editor_required
def update(tool_id):
    form = request.form.to_dict()
    tool = update_tool(tool_id, form)
    if not tool:
        return "Tool not found", 404
    return _grid_response(toast_msg=f"已更新工具：{tool['name']}")


@bp.route("/auto-tag", methods=["POST"])
@editor_required
def auto_tag():
    """Scan each tool's local path and auto-add detected tech tags. No external API / no Claude token."""
    summary = auto_tag_all(apply=True)
    n = summary["tools_changed"]
    t = summary["tag_additions_total"]
    skipped = summary["tools_skipped"]
    scanned = summary["tools_scanned"]

    # Cloud / no-local-access environment → swap a how-to modal into #modal-content
    if scanned == 0:
        html = render_template("partials/_auto_tag_cloud_info.html")
        resp = make_response(html)
        resp.headers["HX-Retarget"] = "#modal-content"
        resp.headers["HX-Reswap"] = "innerHTML"
        resp.headers["HX-Trigger"] = json.dumps({"openAutoTagModal": True})
        return resp

    if n == 0:
        msg = f"✓ 掃描 {scanned} 個工具，所有技術標籤已是最新"
    else:
        suffix = f"，{skipped} 個路徑無法存取" if skipped else ""
        msg = f"🔍 更新 {n}/{scanned} 個工具，新增 {t} 個標籤{suffix}"
    return _grid_response(toast_msg=msg)


@bp.route("/tool/<tool_id>/reorder", methods=["POST"])
@editor_required
def reorder(tool_id):
    category = request.form.get("category", "").strip() or None
    before_id = request.form.get("before", "").strip() or None
    tool = reorder_tool(tool_id, before_id, category)
    if not tool:
        return "Tool not found", 404
    return _grid_response()


@bp.route("/tool/<tool_id>/star", methods=["POST"])
@editor_required
def star(tool_id):
    tool = toggle_starred(tool_id)
    if not tool:
        return "Tool not found", 404
    msg = f"⭐ 已加入常用：{tool['name']}" if tool.get("starred") else f"已從常用移除：{tool['name']}"
    return _grid_response(toast_msg=msg)


@bp.route("/tool/<tool_id>", methods=["DELETE"])
@editor_required
def delete(tool_id):
    tool = get_tool(tool_id)
    name = tool["name"] if tool else tool_id
    ok = delete_tool(tool_id)
    if not ok:
        return "Tool not found", 404
    return _grid_response(toast_msg=f"已刪除工具：{name}")


# ------------------------------------------------------------------
# Screenshot upload
# ------------------------------------------------------------------

_MIME_BY_EXT = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif",
}


def _upload_one(bucket, tool_id: str, file_storage) -> dict | None:
    """把單一檔案丟進 Storage `{tool_id}/{uuid}.{ext}`，回傳 {url, object_key}。失敗回 None。"""
    if not file_storage or not file_storage.filename or not _allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    object_key = f"{tool_id}/{uuid.uuid4().hex}.{ext}"
    content = file_storage.read()
    bucket.upload(
        path=object_key,
        file=content,
        file_options={
            "content-type": _MIME_BY_EXT.get(ext, "application/octet-stream"),
            "upsert": "false",
        },
    )
    return {"url": bucket.get_public_url(object_key), "object_key": object_key}


# ---- Stateless screenshot upload ----
# 只把檔案塞進 Storage，不動 DB。表單送出時 add_tool/update_tool 會把 screenshots_json 寫進 JSONB。
# 這允許 new-tool 模式在工具還沒存進 DB 前就能上傳圖片（用 client 生的 UUID 作 tool_id）。

@bp.route("/tool/<tool_id>/screenshots", methods=["POST"])
@editor_required
def upload_screenshots(tool_id):
    files = request.files.getlist("files") or ([request.files["file"]] if "file" in request.files else [])
    if not files:
        return jsonify({"error": "No files"}), 400

    bucket = get_client().storage.from_("screenshots")
    added = []
    failed = []
    for f in files:
        up = _upload_one(bucket, tool_id, f)
        if up:
            added.append(up)
        else:
            failed.append(f.filename or "")

    if not added:
        return jsonify({"error": "All uploads failed", "failed": failed}), 400

    return jsonify({"ok": True, "added": added, "failed": failed})


@bp.route("/storage/screenshots/delete", methods=["POST"])
@editor_required
def delete_storage_screenshots():
    """Remove one-or-many objects from the screenshots bucket. No DB touched.
    Used by the form's cancel path to drop this-session uploads the user didn't keep.
    Idempotent — missing objects don't fail."""
    body = request.get_json(silent=True) or {}
    keys = body.get("keys") or []
    if not isinstance(keys, list):
        return jsonify({"error": "invalid keys"}), 400
    keys = [str(k) for k in keys if k]
    if not keys:
        return jsonify({"ok": True, "removed": 0})
    try:
        get_client().storage.from_("screenshots").remove(keys)
    except Exception:
        pass  # best-effort
    return jsonify({"ok": True, "removed": len(keys)})


# ------------------------------------------------------------------
# Smart suggest: translate name + extract tags
# ------------------------------------------------------------------

# Tech keyword dictionary — Chinese/English terms → tag
_TECH_KEYWORDS = {
    # Languages
    "python": "python", "javascript": "javascript", "typescript": "typescript",
    "js": "javascript", "ts": "typescript", "golang": "go", "rust": "rust",
    "java": "java", "c#": "csharp", "php": "php", "ruby": "ruby",
    "shell": "shell", "bash": "bash", "powershell": "powershell",
    # Frameworks
    "flask": "flask", "django": "django", "fastapi": "fastapi",
    "express": "express", "react": "react", "vue": "vue", "svelte": "svelte",
    "next": "nextjs", "nextjs": "nextjs", "nuxt": "nuxt",
    "vite": "vite", "tailwind": "tailwind",
    # Tools
    "docker": "docker", "git": "git", "npm": "npm",
    "puppeteer": "puppeteer", "playwright": "playwright", "selenium": "selenium",
    "peerjs": "peerjs", "htmx": "htmx",
    # Data
    "sqlite": "sqlite", "postgres": "postgresql", "mysql": "mysql",
    "redis": "redis", "mongodb": "mongodb", "yaml": "yaml", "json": "json",
    # AI
    "claude": "claude", "openai": "openai", "gpt": "gpt",
    "ai": "ai", "llm": "llm", "機器學習": "ml", "人工智慧": "ai",
    # Platforms
    "line": "line-api", "telegram": "telegram", "discord": "discord",
    "notion": "notion", "obsidian": "obsidian",
    "google apps script": "google-apps-script", "gas": "google-apps-script",
    "google sheets": "google-sheets",
    # Concepts (Chinese)
    "爬蟲": "scraper", "爬取": "scraper", "網頁應用": "web-app",
    "自動化": "automation", "機器人": "bot", "遊戲": "game",
    "計算機": "calculator", "計算器": "calculator",
    "截圖": "screenshot", "剪貼簿": "clipboard",
    "桌面": "desktop", "排程": "scheduler",
    "pdf": "pdf", "圖表": "chart", "儀表板": "dashboard",
    # Libraries
    "pyautogui": "pyautogui", "beautifulsoup": "beautifulsoup",
    "canvas": "canvas", "websocket": "websocket",
    "chromadb": "chromadb", "sentence-transformers": "sentence-transformers",
}


def _extract_tags(text: str) -> list[str]:
    """Extract tech tags from Chinese/English text using keyword dictionary."""
    text_lower = text.lower()
    found = set()
    for keyword, tag in _TECH_KEYWORDS.items():
        if keyword in text_lower:
            found.add(tag)
    return sorted(found)


def _translate_zh_to_en(text: str) -> str:
    """Translate Chinese to English via MyMemory free API."""
    try:
        encoded = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=zh-TW|en"
        req = urllib.request.Request(url, headers={"User-Agent": "DinoDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and "MYMEMORY" not in translated.upper():
                return translated
    except Exception:
        pass
    return ""


@bp.route("/quick-inputs", methods=["GET"])
def quick_inputs_get():
    return jsonify({
        "env_types": load_env_types(),
        "quick_inputs": load_quick_inputs(),
    })


@bp.route("/quick-inputs", methods=["POST"])
@editor_required
def quick_inputs_save():
    body = request.get_json(silent=True) or {}
    env_types = body.get("env_types") or []
    quick_inputs = body.get("quick_inputs") or []
    if not isinstance(env_types, list) or not isinstance(quick_inputs, list):
        return jsonify({"error": "invalid payload"}), 400
    save_quick_input_settings(env_types, quick_inputs)
    return jsonify({
        "ok": True,
        "env_types": load_env_types(),
        "quick_inputs": load_quick_inputs(),
    })


@bp.route("/tool/suggest", methods=["POST"])
def suggest():
    name_zh = request.form.get("name_zh", "").strip()
    description = request.form.get("description", "").strip()
    combined = f"{name_zh} {description}"

    # Translate name
    name_en = ""
    if name_zh:
        name_en = _translate_zh_to_en(name_zh)
        # Title case
        if name_en:
            name_en = name_en.title()

    # Extract tags
    tags = _extract_tags(combined)

    return jsonify({"name_en": name_en, "tags": tags})
