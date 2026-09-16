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
    load_quick_inputs, save_quick_input_settings, build_local_map,
)
from data.auto_tag import auto_tag_all
from data.launcher import (
    build_server_rows, upsert_entry, get_manifest, TableMissing,
    add_manual_entry, delete_entry, validate_bat_path,
)
from routes.auth import login_required, editor_required, private_read_guard

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
                   has_github=False, has_gas=False, extra=None):
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
        # 同步刷新「本地」分頁(port → 工具對照)，免使用者 F5
        html += render_template("partials/_local_oob.html", local_map=build_local_map(load_tools()))
    resp = make_response(html)
    trigger = {}
    if toast_msg:
        trigger["showToast"] = toast_msg
    if extra:
        trigger.update(extra)
    if trigger:
        resp.headers["HX-Trigger"] = json.dumps(trigger)
    return resp


# ------------------------------------------------------------------
# Filter / search
# ------------------------------------------------------------------

@bp.route("/tools")
@private_read_guard
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
@private_read_guard
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
    before = get_tool(tool_id)
    tool = update_tool(tool_id, form)
    if not tool:
        return "Tool not found", 404
    # 封存狀態有變動 → 問要不要順便對它的 bat 做同一件事（兩邊刻意不自動連動）
    extra = None
    if before and before.get("status") != tool.get("status"):
        extra = _server_link_prompt(
            tool_id,
            tool.get("name_zh") or tool.get("name") or tool_id,
            tool.get("status") == "archived",
        )
    return _grid_response(toast_msg=f"已更新工具：{tool['name']}", extra=extra)


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


# 只有編輯表單的 ⚡ 面板會用（presets 含本機指令/路徑），比照寫入端掛 editor
@bp.route("/quick-inputs", methods=["GET"])
@editor_required
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


# 只有編輯表單的「智慧建議」鈕會用，匿名可打會被當免費翻譯 API 濫用
@bp.route("/tool/suggest", methods=["POST"])
@editor_required
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


# ====================================================================
# 伺服器分頁（Server_Launcher 伺服器總管）
# --------------------------------------------------------------------
# 清單是從 tools.commands 裡 env='bat' 的項目動態生成，這裡只負責存狀態。
# 每個 toggle 都回傳整塊重繪的 HTML，沿用專案既有的 HTMX 就地刷新模式，
# 不用整頁 F5。
# ====================================================================

def _server_response(toast_msg=None, extra=None):
    """重繪整個伺服器分頁（含封存區）。

    ♻️ 沿用 _grid_response 的 toast 模式：用 HX-Trigger 標頭觸發，不另外塞 partial。
    extra：要一起送出的其他 HX-Trigger 事件（例如「要不要順便封存卡片」的詢問）。
    """
    data = build_server_rows(load_tools())
    html = render_template("partials/_server_list.html", server=data)
    resp = make_response(html)
    trigger = {}
    if toast_msg:
        trigger["showToast"] = toast_msg
    if extra:
        trigger.update(extra)
    if trigger:
        resp.headers["HX-Trigger"] = json.dumps(trigger)
    return resp


def _find_row(data, bat_key):
    for r in data["active"] + data["archived"]:
        if r["bat_key"] == bat_key:
            return r
    return None


@bp.route("/server", methods=["GET"])
@private_read_guard
def server_list():
    return _server_response()


@bp.route("/server/<bat_key>/toggle", methods=["POST"])
@editor_required
def server_toggle(bat_key):
    """顯示／不顯示：要不要出現在本機總管的清單上。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    new_val = not row["visible"]
    try:
        upsert_entry(bat_key, bat_path=row["bat_path"], tool_id=row["tool_id"], sort_order=row["sort_order"],
                 visible=new_val, port=row["port"])
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    msg = f"已顯示：{row['label']}" if new_val else f"已隱藏：{row['label']}"
    return _server_response(toast_msg=msg)


@bp.route("/server/<bat_key>/default", methods=["POST"])
@editor_required
def server_default(bat_key):
    """預設打勾：總管一打開就先勾起來（＝開機會自動開）。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    new_val = not row["default_on"]
    try:
        upsert_entry(bat_key, bat_path=row["bat_path"], tool_id=row["tool_id"], sort_order=row["sort_order"],
                 default_on=new_val, port=row["port"])
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    msg = f"已設為預設啟動：{row['label']}" if new_val else f"已取消預設：{row['label']}"
    return _server_response(toast_msg=msg)


@bp.route("/server/<bat_key>/archive", methods=["POST"])
@editor_required
def server_archive(bat_key):
    """封存／解除封存。封存＝收進摺疊區，總管完全看不到它。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    new_val = not row["archived"]
    try:
        upsert_entry(bat_key, bat_path=row["bat_path"], tool_id=row["tool_id"], sort_order=row["sort_order"],
                 archived=new_val, port=row["port"])
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    msg = f"已封存：{row['label']}" if new_val else f"已解除封存：{row['label']}"
    return _server_response(toast_msg=msg, extra=_card_link_prompt(row, new_val))


@bp.route("/server/<bat_key>/label", methods=["POST"])
@editor_required
def server_label(bat_key):
    """改顯示名稱（＝總管的分頁名稱）。清空＝恢復自動帶的名字。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    label = (request.form.get("label") or "").strip()
    try:
        upsert_entry(bat_key, bat_path=row["bat_path"], tool_id=row["tool_id"], sort_order=row["sort_order"],
                 label=label, port=row["port"])
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    return _server_response(toast_msg=f"已改名：{label or row['auto_label']}")


@bp.route("/server/<bat_key>/port", methods=["POST"])
@editor_required
def server_port(bat_key):
    """手動補 port。卡片的網址沒寫 port 時，填了才有「執行中／重開」的偵測。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    raw = (request.form.get("port") or "").strip()
    try:
        port = int(raw) if raw else 0
    except ValueError:
        port = 0
    if port and not (1 <= port <= 65535):
        port = 0
    try:
        upsert_entry(bat_key, bat_path=row["bat_path"], tool_id=row["tool_id"], sort_order=row["sort_order"], port=port)
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    return _server_response(toast_msg=f"已更新 port：{row['label']} → {port or '（無）'}")


@bp.route("/server/manifest", methods=["GET"])
@private_read_guard
def server_manifest():
    """給本機伺服器總管讀的 JSON 清單。

    只回「要顯示且沒封存」的項目，另附被封存的 key，
    讓總管可以把本機掃到、但已在這裡封存的項目一併藏掉。
    """
    tools = load_tools()
    data = build_server_rows(tools)
    return jsonify({
        "items": get_manifest(tools),
        "archived_paths": [r["bat_path"] for r in data["archived"]],
        "hidden_paths": [r["bat_path"] for r in data["active"] if not r["visible"]],
    })


@bp.route("/server/add", methods=["POST"])
@editor_required
def server_add():
    r"""手動新增一支沒有登記在任何卡片上的 bat（例：n8n\start-n8n.bat）。"""
    raw = request.form.get("bat_path") or ""
    label = (request.form.get("label") or "").strip()
    raw_port = (request.form.get("port") or "").strip()

    path, err = validate_bat_path(raw)
    if err:
        return _server_response(toast_msg=f"新增失敗：{err}")

    try:
        port = int(raw_port) if raw_port else None
    except ValueError:
        port = None
    if port is not None and not (1 <= port <= 65535):
        port = None

    try:
        add_manual_entry(path, label, port)
    except TableMissing:
        return _server_response(
            toast_msg='還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行')
    return _server_response(toast_msg=f"已新增：{label or path.rsplit(chr(92), 1)[-1]}")


@bp.route("/server/<bat_key>/delete", methods=["POST"])
@editor_required
def server_delete(bat_key):
    """刪掉手動新增的項目。卡片來的不給刪（刪了下次還是會從卡片長回來）。"""
    data = build_server_rows(load_tools())
    row = _find_row(data, bat_key)
    if not row:
        return "Entry not found", 404
    if not row.get("manual"):
        return _server_response(toast_msg="這是從卡片來的，不能刪；請改用「封存」")
    try:
        delete_entry(bat_key)
    except TableMissing:
        return _server_response(toast_msg="還沒建資料表")
    return _server_response(toast_msg=f"已刪除：{row['label']}")


# =====================================================================
# 批次調整 ＋ 封存連動（Dino 2026-09-15）
# ---------------------------------------------------------------------
# 「伺服器封存」和「卡片封存」是兩套獨立狀態，刻意不自動連動：
#   伺服器：launcher_entries.archived  → 這支 bat 要不要進 CLI 總管
#   卡片　：tools.status == 'archived' → 這張卡片要不要出現在卡片牆
# 一支 bat 不想開機自動開，不代表整個專案要從儀表板消失，所以不硬綁。
# 改其中一邊時回一個「要不要順便改另一邊」的詢問事件，由使用者決定。
# =====================================================================

_BATCH_ACTIONS = {
    "show":        ("visible",    True,  "已顯示"),
    "hide":        ("visible",    False, "已隱藏"),
    "default_on":  ("default_on", True,  "已設為預設啟動"),
    "default_off": ("default_on", False, "已取消預設"),
    "archive":     ("archived",   True,  "已封存"),
    "unarchive":   ("archived",   False, "已解除封存"),
}


def _card_link_prompt(row, archived_now):
    """伺服器那邊封存／解封存之後，問要不要順便對卡片做同一件事。

    只有「狀態真的不一致」才問，避免每次都跳提示。
    """
    tool_id = row.get("tool_id")
    if not tool_id:
        return None
    tool = get_tool(tool_id)
    if not tool:
        return None
    card_archived = (tool.get("status") == "archived")
    if card_archived == archived_now:
        return None
    return {"askArchiveCard": {
        "tool_id": tool_id,
        "tool_name": tool.get("name_zh") or tool.get("name") or tool_id,
        "bat_label": row.get("label") or "",
        "archive": archived_now,
    }}


@bp.route("/server/batch", methods=["POST"])
@editor_required
def server_batch():
    """一次調整多支 bat：顯示／隱藏／預設／取消預設／封存／解除封存。

    前端把勾選到的 bat_key 全部放在 bat_keys 送過來。
    ♻️ 沿用 upsert_entry，不另外寫一套寫入邏輯。
    """
    action = (request.form.get("action") or "").strip()
    if action not in _BATCH_ACTIONS:
        return "Unknown action", 400
    keys = [k for k in request.form.getlist("bat_keys") if k]
    if not keys:
        return _server_response(toast_msg="一個都沒選")

    field, value, verb = _BATCH_ACTIONS[action]
    data = build_server_rows(load_tools())
    done, skipped = 0, 0
    try:
        for key in keys:
            row = _find_row(data, key)
            if not row:
                skipped += 1
                continue
            if bool(row.get(field)) == value:   # 本來就是這個狀態，不用白寫一次
                skipped += 1
                continue
            upsert_entry(key, bat_path=row["bat_path"], tool_id=row["tool_id"],
                         sort_order=row["sort_order"], port=row["port"],
                         **{field: value})
            done += 1
    except TableMissing:
        return _server_response(
            toast_msg="還沒建資料表，請先把 supabase_db/launcher_entries.sql 貼到 Supabase SQL Editor 執行")

    msg = f"{verb} {done} 項"
    if skipped:
        msg += f"（{skipped} 項本來就是這樣，略過）"
    return _server_response(toast_msg=msg)


@bp.route("/server/archive-card/<tool_id>", methods=["POST"])
@editor_required
def server_archive_card(tool_id):
    """把伺服器那邊的封存決定，套到對應的卡片上（使用者按了「一起封存」才會走這裡）。"""
    tool = get_tool(tool_id)
    if not tool:
        return "Tool not found", 404
    archive = (request.form.get("archive") or "").lower() in ("1", "true", "on", "yes")
    update_tool(tool_id, {"status": "archived" if archive else "active"})
    name = tool.get("name_zh") or tool.get("name") or tool_id
    verb = "已一併封存卡片" if archive else "已一併解除卡片封存"
    return _server_response(toast_msg=f"{verb}：{name}")


@bp.route("/tool/<tool_id>/archive-servers", methods=["POST"])
@editor_required
def tool_archive_servers(tool_id):
    """把卡片的封存決定，套到它底下所有 bat 上（使用者按了「一起封存」才會走這裡）。"""
    archive = (request.form.get("archive") or "").lower() in ("1", "true", "on", "yes")
    data = build_server_rows(load_tools())
    rows = [r for r in (data["active"] + data["archived"]) if r.get("tool_id") == tool_id]
    if not rows:
        return _grid_response(toast_msg="這張卡片沒有對應的 bat")
    try:
        n = 0
        for r in rows:
            if bool(r.get("archived")) == archive:
                continue
            upsert_entry(r["bat_key"], bat_path=r["bat_path"], tool_id=tool_id,
                         sort_order=r["sort_order"], port=r["port"], archived=archive)
            n += 1
    except TableMissing:
        return _grid_response(toast_msg="還沒建資料表")
    verb = "已一併封存" if archive else "已一併解除封存"
    return _grid_response(toast_msg=f"{verb} {n} 支 bat")


def _server_link_prompt(tool_id, tool_name, archived_now):
    """卡片那邊改了封存狀態之後，問要不要順便對它的 bat 做同一件事。"""
    try:
        data = build_server_rows(load_tools())
    except Exception:
        return None
    rows = [r for r in (data["active"] + data["archived"]) if r.get("tool_id") == tool_id]
    mismatched = [r for r in rows if bool(r.get("archived")) != archived_now]
    if not mismatched:
        return None
    return {"askArchiveServers": {
        "tool_id": tool_id,
        "tool_name": tool_name,
        "count": len(mismatched),
        "archive": archived_now,
    }}
