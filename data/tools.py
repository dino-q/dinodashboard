"""
Tools / categories / env_types / quick_inputs — Supabase-backed CRUD.

對外 API 跟原本的 YAML 版本一模一樣，讓 routes/api.py 完全不用改。
"""
import re
from datetime import date

from data.supabase_client import get_client

# Flask is always available in deploy, but this module is also imported by
# the standalone migrate script. has_request_context() guards the g access.
try:
    from flask import g, has_request_context
except ImportError:                                    # pragma: no cover
    g = None
    def has_request_context():
        return False


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _sb():
    return get_client()


# Per-request memoisation — dedupe repeated load_tools() / load_categories()
# calls inside a single handler (filter + total count + OOB re-renders all hit
# the same queries otherwise).
_CACHE_KEYS = ("_t_cache_tools", "_t_cache_categories")

def _cache_get(key):
    if g is None or not has_request_context():
        return None
    return getattr(g, key, None)

def _cache_set(key, value):
    if g is not None and has_request_context():
        setattr(g, key, value)
    return value

def _cache_clear_all():
    if g is None or not has_request_context():
        return
    for k in _CACHE_KEYS:
        if hasattr(g, k):
            delattr(g, k)


def _cat_row_to_dict(row: dict) -> dict:
    """DB 的 sort_order → API 的 order（對外相容）"""
    return {
        "id": row["id"],
        "name_zh": row.get("name_zh", ""),
        "icon": row.get("icon", "folder"),
        "order": row.get("sort_order", 99),
    }


# ------------------------------------------------------------------
# Screenshot normalization
# ------------------------------------------------------------------

# 每張截圖的樣式欄位與預設值；缺欄位會補上，確保模板永遠拿得到完整 dict。
_SCREENSHOT_STYLE_DEFAULTS = {
    "pos_x": 50,       # object-position x %（0 = 左，100 = 右）
    "pos_y": 50,       # object-position y %
    "scale": 100,      # transform: scale 百分比
    "opacity": 100,    # 0–100
    # brightness 100 = theme-default（在 CSS 裡會乘上 --theme-img-brightness：dark=0.85 / light=1）。
    # 使用者設 > 100 = 比該 theme 還亮；< 100 = 更暗。值跟 theme 是相對關係，跨 theme 一致。
    "brightness": 100,
    "blur": 0,         # px
}


def _normalize_one_screenshot(item: dict) -> dict:
    """補齊單張截圖的欄位，非 dict 輸入會被忽略（回傳 None）。"""
    if not isinstance(item, dict):
        return None
    url = (item.get("url") or "").strip()
    if not url:
        return None
    out = {
        "url": url,
        "object_key": (item.get("object_key") or "").strip(),
        "is_cover": bool(item.get("is_cover")),
    }
    for k, default in _SCREENSHOT_STYLE_DEFAULTS.items():
        v = item.get(k)
        try:
            out[k] = int(v) if v is not None else default
        except (TypeError, ValueError):
            out[k] = default
    return out


def _normalize_screenshots(tool: dict) -> dict:
    """把 tool['screenshots'] 正規化：
    - DB 回來若是 list，逐筆補欄位；壞資料剔除
    - DB 為空但有 legacy `screenshot` 欄位 → 合成單張封面
    - 確保最多一張 is_cover=True（第一張勝出；有就保留）
    直接 mutate 並回傳 tool。"""
    raw = tool.get("screenshots")
    items = []
    if isinstance(raw, list):
        for it in raw:
            norm = _normalize_one_screenshot(it)
            if norm:
                items.append(norm)

    if not items:
        legacy = (tool.get("screenshot") or "").strip()
        if legacy:
            items.append(_normalize_one_screenshot({
                "url": legacy,
                "object_key": "",
                "is_cover": True,
            }))

    # 保證最多一張 is_cover
    cover_seen = False
    for it in items:
        if it["is_cover"] and not cover_seen:
            cover_seen = True
        elif it["is_cover"]:
            it["is_cover"] = False

    tool["screenshots"] = items
    return tool


def get_cover(tool: dict) -> dict | None:
    """回傳封面那張的 dict，沒設就 None。"""
    for s in tool.get("screenshots") or []:
        if s.get("is_cover"):
            return s
    return None


# ------------------------------------------------------------------
# Categories
# ------------------------------------------------------------------

def load_categories() -> list[dict]:
    cached = _cache_get("_t_cache_categories")
    if cached is not None:
        return cached
    res = _sb().table("categories").select("*").order("sort_order").execute()
    return _cache_set("_t_cache_categories", [_cat_row_to_dict(r) for r in (res.data or [])])


# ------------------------------------------------------------------
# Tools
# ------------------------------------------------------------------

def load_tools() -> list[dict]:
    cached = _cache_get("_t_cache_tools")
    if cached is not None:
        return cached
    res = (_sb().table("tools").select("*").order("sort_order").execute())
    rows = [_normalize_screenshots(r) for r in (res.data or [])]
    return _cache_set("_t_cache_tools", rows)


def get_tool(tool_id: str) -> dict | None:
    if not tool_id:
        return None
    res = _sb().table("tools").select("*").eq("id", tool_id).limit(1).execute()
    rows = res.data or []
    return _normalize_screenshots(rows[0]) if rows else None


def get_highlight_tool() -> dict | None:
    res = _sb().table("tools").select("*").eq("highlight", True).limit(1).execute()
    rows = res.data or []
    return _normalize_screenshots(rows[0]) if rows else None


def filter_tools(category: str | None = None, q: str | None = None,
                 status: str | None = None,
                 has_external: bool = False, has_local_url: bool = False,
                 has_notion: bool = False, has_github: bool = False,
                 has_gas: bool = False) -> list[dict]:
    # 用 SQL-side 過濾簡單條件，複雜條件（tag 搜尋、commands env 過濾）用 Python 端
    query = _sb().table("tools").select("*").order("sort_order")
    if status:
        query = query.eq("status", status)
    if category:
        query = query.eq("category", category)
    tools = [_normalize_screenshots(r) for r in (query.execute().data or [])]

    # has_* filters (OR logic)
    has_any = any([has_external, has_local_url, has_notion, has_github, has_gas])
    if has_any:
        def _has_env(tool, env_name):
            return any((c.get("env") or "").lower() == env_name for c in tool.get("commands", []))

        def matches(t):
            if has_external and (t.get("external_url") or "").strip():
                return True
            if has_local_url and (t.get("url") or "").strip():
                return True
            if has_notion and _has_env(t, "notion"):
                return True
            if has_github and _has_env(t, "github"):
                return True
            if has_gas and _has_env(t, "google apps script"):
                return True
            return False
        tools = [t for t in tools if matches(t)]

    if q:
        q_lower = q.lower()
        tools = [
            t for t in tools
            if q_lower in (t.get("name") or "").lower()
            or q_lower in (t.get("name_zh") or "").lower()
            or q_lower in (t.get("description") or "").lower()
            or any(q_lower in str(tag).lower() for tag in (t.get("tags") or []))
        ]
    return tools


def tools_grouped_by_category(category: str | None = None, q: str | None = None,
                              status: str | None = None,
                              has_external: bool = False, has_local_url: bool = False,
                              has_notion: bool = False, has_github: bool = False,
                              has_gas: bool = False) -> list[dict]:
    tools = filter_tools(category, q, status, has_external, has_local_url,
                         has_notion, has_github, has_gas)
    categories = load_categories()
    if category:
        categories = [c for c in categories if c["id"] == category]

    groups = []
    if not category:
        starred = [t for t in tools if t.get("starred") and not t.get("highlight")]
        if starred:
            groups.append({
                "category": {"id": "_starred", "name_zh": "常用工具", "icon": "star", "order": -1},
                "tools": starred,
            })

    for cat in categories:
        cat_tools = [t for t in tools if t.get("category") == cat["id"] and not t.get("highlight")]
        if cat_tools:
            groups.append({"category": cat, "tools": cat_tools})

    known_ids = {c["id"] for c in categories}
    uncategorized = [t for t in tools if t.get("category") not in known_ids and not t.get("highlight")]
    if uncategorized:
        groups.append({
            "category": {"id": "_other", "name_zh": "其他", "icon": "folder", "order": 99},
            "tools": uncategorized,
        })
    return groups


# ------------------------------------------------------------------
# env_types
# ------------------------------------------------------------------

DEFAULT_ENV_TYPES = ["local", "docker", "bat", "github", "Google Apps Script"]

# One-shot migration: old raw key → new human-readable name. Kept here so
# load_env_types() can run it lazily on first call per process.
_ENV_MIGRATIONS = {"gas": "Google Apps Script"}
_MIGRATIONS_DONE = False


def _migrate_env_names():
    """Rename legacy env keys in env_types / quick_inputs / tools.commands.
    Idempotent — once the old key is gone everywhere, later calls no-op."""
    global _MIGRATIONS_DONE
    if _MIGRATIONS_DONE:
        return
    sb = _sb()
    for old, new in _ENV_MIGRATIONS.items():
        # Skip if no legacy rows exist (already migrated)
        stale = sb.table("env_types").select("name").eq("name", old).execute().data or []
        if not stale:
            continue

        # env_types: if new name already exists, drop the old row; else rename.
        conflict = sb.table("env_types").select("name").eq("name", new).execute().data or []
        if conflict:
            sb.table("env_types").delete().eq("name", old).execute()
        else:
            sb.table("env_types").update({"name": new}).eq("name", old).execute()

        # quick_inputs: rename the env field
        sb.table("quick_inputs").update({"env": new}).eq("env", old).execute()

        # tools.commands (jsonb): fetch, mutate, write back per-tool
        tools_rows = sb.table("tools").select("id, commands").execute().data or []
        for t in tools_rows:
            cmds = t.get("commands") or []
            changed = False
            for c in cmds:
                if (c.get("env") or "") == old:
                    c["env"] = new
                    changed = True
            if changed:
                sb.table("tools").update({"commands": cmds}).eq("id", t["id"]).execute()
    _MIGRATIONS_DONE = True


def load_env_types() -> list[str]:
    """讀 env_types 表。
    - 首次啟動（table 完全空）才種入預設值
    - 已經有資料之後，使用者刪除的類型「不會」自動補回；但仍會把工具 commands 實際在用、
      卻不在 env_types 的 env 名稱補上，避免指令顯示成 orphan
    """
    _migrate_env_names()  # idempotent — runs once per process
    sb = _sb()
    res = sb.table("env_types").select("*").order("sort_order").execute()
    names = [r["name"] for r in (res.data or [])]

    # 只在完全空白時種入預設值（視為首次啟動）
    if not names:
        rows = [{"name": n, "sort_order": i} for i, n in enumerate(DEFAULT_ENV_TYPES)]
        sb.table("env_types").insert(rows).execute()
        names = list(DEFAULT_ENV_TYPES)

    # 把工具 commands 實際在用、但沒登記的 env 補上（防止 orphan）。
    # 只抓 commands 欄，避免為了 orphan 檢查把整個 tools 表拉回來。
    used = set()
    orphan_res = sb.table("tools").select("commands").execute()
    for row in (orphan_res.data or []):
        for c in row.get("commands") or []:
            e = c.get("env")
            if e:
                used.add(e)
    missing = used - set(names)
    if missing:
        next_order = len(names)
        rows = [{"name": n, "sort_order": next_order + i} for i, n in enumerate(sorted(missing))]
        sb.table("env_types").insert(rows).execute()
        names.extend(sorted(missing))

    return names


def add_env_type(name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    sb = _sb()
    existing = sb.table("env_types").select("name").eq("name", name).execute().data or []
    if existing:
        return False
    # 找最後一個 sort_order
    res = sb.table("env_types").select("sort_order").order("sort_order", desc=True).limit(1).execute()
    next_order = (res.data[0]["sort_order"] + 1) if res.data else 0
    sb.table("env_types").insert({"name": name, "sort_order": next_order}).execute()
    return True


def remove_env_type(name: str) -> bool:
    if name in DEFAULT_ENV_TYPES:
        return False
    sb = _sb()
    res = sb.table("env_types").delete().eq("name", name).execute()
    return bool(res.data)


# ------------------------------------------------------------------
# quick_inputs
# ------------------------------------------------------------------

_QUICK_INPUT_SEED = [
    {"env": "local",   "label": "啟動 Dev Server", "cmd": ""},
    {"env": "bat",     "label": "啟動 Bat",        "cmd": ""},
    {"env": "github",  "label": "Github_Repo",     "cmd": ""},
    {"env": "Notion",  "label": "Notion",          "cmd": ""},
    {"env": "Netlify", "label": "Netlify",         "cmd": ""},
    {"env": "Google Apps Script", "label": "GAS",   "cmd": ""},
    {"env": "Google",  "label": "啟動 sheet",      "cmd": ""},
]


def load_quick_inputs() -> list[dict]:
    sb = _sb()
    res = sb.table("quick_inputs").select("*").order("sort_order").execute()
    rows = res.data or []
    if not rows:
        # 第一次跑時回傳 seed，不寫回 DB（讓使用者手動存才寫）
        return [dict(x) for x in _QUICK_INPUT_SEED]
    return [{
        "env": (r.get("env") or "local").strip(),
        "label": (r.get("label") or "").strip(),
        "cmd": (r.get("cmd") or "").strip(),
    } for r in rows]


def save_quick_input_settings(env_types: list[str], quick_inputs: list[dict]) -> None:
    """一次覆寫 env_types + quick_inputs。"""
    sb = _sb()

    # 清理 env_types — 依使用者送來的順序寫入，不強制補回預設值（讓刪除生效）
    cleaned_env = []
    seen = set()
    for name in env_types or []:
        n = (name or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        cleaned_env.append(n)

    # 清空 env_types 再灌入
    sb.table("env_types").delete().neq("name", "__sentinel__").execute()
    if cleaned_env:
        rows = [{"name": n, "sort_order": i} for i, n in enumerate(cleaned_env)]
        sb.table("env_types").insert(rows).execute()

    # quick_inputs
    cleaned_qi = []
    for it in quick_inputs or []:
        if not isinstance(it, dict):
            continue
        env = (it.get("env") or "").strip() or "local"
        label = (it.get("label") or "").strip()
        cmd = (it.get("cmd") or "").strip()
        if not label and not cmd:
            continue
        cleaned_qi.append({"env": env, "label": label, "cmd": cmd})

    sb.table("quick_inputs").delete().gte("id", 0).execute()
    if cleaned_qi:
        rows = [{**it, "sort_order": i} for i, it in enumerate(cleaned_qi)]
        sb.table("quick_inputs").insert(rows).execute()


# ------------------------------------------------------------------
# CRUD: tools
# ------------------------------------------------------------------

def _ensure_category(form: dict) -> str:
    """若 form 填了新分類欄位，幫他建一筆分類並回傳 id。"""
    cat_id = form.get("category", "utility")
    if cat_id != "__new__":
        return cat_id
    new_id = form.get("new_cat_id", "").strip()
    new_name = form.get("new_cat_name", "").strip()
    new_icon = form.get("new_cat_icon", "").strip() or "folder"
    if not new_id or not new_name:
        return "utility"

    sb = _sb()
    existing = sb.table("categories").select("id").eq("id", new_id).execute().data or []
    if not existing:
        # 拿目前最大 sort_order
        res = sb.table("categories").select("sort_order").order("sort_order", desc=True).limit(1).execute()
        next_order = (res.data[0]["sort_order"] + 1) if res.data else 1
        sb.table("categories").insert({
            "id": new_id, "name_zh": new_name, "icon": new_icon, "sort_order": next_order
        }).execute()
    return new_id


def add_tool(form: dict) -> dict:
    _cache_clear_all()
    sb = _sb()
    tool_id = form.get("id") or _slugify(form.get("name", "tool"))

    # 確保 id 唯一
    existing_ids = {r["id"] for r in (sb.table("tools").select("id").execute().data or [])}
    base_id = tool_id
    counter = 2
    while tool_id in existing_ids:
        tool_id = f"{base_id}-{counter}"
        counter += 1

    category = _ensure_category(form)
    today = str(date.today())

    # 新增到最後一個 sort_order
    res = sb.table("tools").select("sort_order").order("sort_order", desc=True).limit(1).execute()
    next_order = (res.data[0]["sort_order"] + 1) if res.data else 0

    commands = _parse_commands(form)
    screenshots = _parse_screenshots_json(form) or []
    cover_url = next((s["url"] for s in screenshots if s.get("is_cover")), "")
    tool = {
        "id": tool_id,
        "name": form.get("name", ""),
        "name_zh": form.get("name_zh", ""),
        "description": form.get("description", ""),
        "category": category,
        "tags": _parse_tags(form.get("tags", "")),
        "icon": form.get("icon", "box"),
        "color": form.get("color", "#6366F1"),
        "status": form.get("status", "active"),
        "highlight": form.get("highlight") == "on",
        "screenshot": cover_url or form.get("screenshot", ""),
        "screenshots": screenshots,
        "path": form.get("path", ""),
        "commands": commands,
        "url": form.get("url", ""),
        "external_url": form.get("external_url", ""),
        "pin_path": form.get("pin_path") == "on",
        "pin_url": form.get("pin_url") == "on",
        "pin_external_url": form.get("pin_external_url") == "on",
        "sort_order": next_order,
        "created_at": today,
        "updated_at": today,
    }
    res = sb.table("tools").insert(tool).execute()
    _sync_env_types_from_commands(commands)
    return res.data[0] if res.data else tool


def update_tool(tool_id: str, form: dict) -> dict | None:
    _cache_clear_all()
    sb = _sb()
    existing = get_tool(tool_id)
    if not existing:
        return None

    category = _ensure_category(form)
    commands = _parse_commands(form)

    patch = {
        "name": form.get("name", existing["name"]),
        "name_zh": form.get("name_zh", existing.get("name_zh", "")),
        "description": form.get("description", existing["description"]),
        "category": category,
        "tags": _parse_tags(form.get("tags", ",".join(existing.get("tags") or []))),
        "icon": form.get("icon", existing.get("icon", "box")),
        "color": form.get("color", existing.get("color", "#6366F1")),
        "status": form.get("status", existing.get("status", "active")),
        "path": form.get("path", existing.get("path", "")),
        "commands": commands,
        "url": form.get("url", existing.get("url", "")),
        "external_url": form.get("external_url", existing.get("external_url", "")),
        "pin_path": form.get("pin_path") == "on",
        "pin_url": form.get("pin_url") == "on",
        "pin_external_url": form.get("pin_external_url") == "on",
        "updated_at": str(date.today()),
    }
    if "highlight" in form:
        patch["highlight"] = form.get("highlight") == "on"

    # screenshots: 只在表單明確帶了 screenshots_json 才動
    new_screenshots = _parse_screenshots_json(form)
    orphan_keys: list[str] = []
    if new_screenshots is not None:
        old_keys = {s.get("object_key") for s in (existing.get("screenshots") or []) if s.get("object_key")}
        new_keys = {s.get("object_key") for s in new_screenshots if s.get("object_key")}
        orphan_keys = list(old_keys - new_keys)
        cover_url = next((s["url"] for s in new_screenshots if s.get("is_cover")), "")
        patch["screenshots"] = new_screenshots
        patch["screenshot"] = cover_url  # 同步 legacy 欄位
    else:
        # 沒帶 screenshots_json 就維持舊 screenshot legacy 欄位（若表單有帶）
        if "screenshot" in form:
            patch["screenshot"] = form["screenshot"]

    res = sb.table("tools").update(patch).eq("id", tool_id).execute()
    _sync_env_types_from_commands(commands)
    # Storage 清理：砍掉被使用者移除的舊截圖
    if orphan_keys:
        _delete_storage_objects(orphan_keys)
    return res.data[0] if res.data else None


def delete_tool(tool_id: str) -> bool:
    _cache_clear_all()
    # 先把該工具 Storage 底下的所有截圖檔一併清掉
    try:
        bucket = _sb().storage.from_("screenshots")
        objs = bucket.list(tool_id) or []
        keys = [f"{tool_id}/{o['name']}" for o in objs if o.get("name")]
        if keys:
            bucket.remove(keys)
    except Exception:
        pass  # Storage 失敗不阻擋 DB 刪除
    res = _sb().table("tools").delete().eq("id", tool_id).execute()
    return bool(res.data)


def reorder_tool(tool_id: str, before_id: str | None, category: str | None) -> dict | None:
    """把 tool_id 搬到 before_id 前面（None 則放到最後）。同時可換分類。"""
    _cache_clear_all()
    sb = _sb()
    tools = load_tools()
    tool = next((t for t in tools if t["id"] == tool_id), None)
    if not tool:
        return None

    # 移除後重新插入
    tools = [t for t in tools if t["id"] != tool_id]
    inserted = False
    if before_id:
        for i, t in enumerate(tools):
            if t["id"] == before_id:
                tools.insert(i, tool)
                inserted = True
                break
    if not inserted:
        tools.append(tool)

    # 如有換分類，更新 category
    patch_cat = None
    if category and not category.startswith("_") and tool.get("category") != category:
        patch_cat = category
        tool["category"] = category

    # 一次性 UPDATE 所有 sort_order 變動；只改有變動的 row
    today = str(date.today())
    for i, t in enumerate(tools):
        new_order = i
        if t.get("sort_order") != new_order:
            sb.table("tools").update({"sort_order": new_order, "updated_at": today}).eq("id", t["id"]).execute()

    if patch_cat is not None:
        sb.table("tools").update({"category": patch_cat, "updated_at": today}).eq("id", tool_id).execute()

    return get_tool(tool_id)


def toggle_starred(tool_id: str) -> dict | None:
    _cache_clear_all()
    sb = _sb()
    t = get_tool(tool_id)
    if not t:
        return None
    patch = {"starred": not bool(t.get("starred")), "updated_at": str(date.today())}
    res = sb.table("tools").update(patch).eq("id", tool_id).execute()
    return res.data[0] if res.data else None


def update_screenshot(tool_id: str, url_or_path: str) -> bool:
    """Legacy：存舊的單張 screenshot 欄位。新路徑請用 screenshots helpers。"""
    _cache_clear_all()
    patch = {
        "screenshot": url_or_path,
        "updated_at": str(date.today()),
    }
    res = _sb().table("tools").update(patch).eq("id", tool_id).execute()
    return bool(res.data)


# ------------------------------------------------------------------
# Screenshots — form field parsing + Storage cleanup
# ------------------------------------------------------------------

def _parse_screenshots_json(form: dict) -> list[dict] | None:
    """解析 form["screenshots_json"]，回傳正規化過的 list。
    - 回 None = 表單沒帶這個欄位（不動 DB 現有的 screenshots）
    - 回 [] = 表單明確清空
    - 回 [...] = 表單明確覆寫"""
    import json as _json
    raw = form.get("screenshots_json")
    if raw is None:
        return None
    try:
        parsed = _json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    out = []
    cover_seen = False
    for it in parsed:
        n = _normalize_one_screenshot(it)
        if not n:
            continue
        # 保證最多一張封面
        if n["is_cover"] and not cover_seen:
            cover_seen = True
        elif n["is_cover"]:
            n["is_cover"] = False
        out.append(n)
    return out


def _delete_storage_objects(object_keys: list[str]) -> None:
    """砍 Supabase Storage 的 screenshots bucket 裡的物件。失敗不 raise（容忍離線 / 已不存在）。"""
    keys = [k for k in object_keys if k]
    if not keys:
        return
    try:
        _sb().storage.from_("screenshots").remove(keys)
    except Exception:
        pass


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")[:60]


def _parse_tags(tags_str) -> list[str]:
    if isinstance(tags_str, list):
        return tags_str
    return [t.strip() for t in str(tags_str or "").split(",") if t.strip()]


def _parse_commands(form: dict) -> list[dict]:
    commands = []
    i = 0
    while True:
        label = form.get(f"cmd_label_{i}")
        cmd = form.get(f"cmd_cmd_{i}")
        if label is None and cmd is None:
            break
        if cmd and cmd.strip():
            commands.append({
                "label": (label or "").strip() or f"Command {i+1}",
                "cmd": cmd.strip(),
                "env": form.get(f"cmd_env_{i}", "local"),
                "pinned": form.get(f"cmd_pinned_{i}") == "on",
            })
        i += 1
    return commands


def _sync_env_types_from_commands(commands: list[dict]) -> None:
    """新工具/修改工具後，把 commands 裡用到的 env 同步進 env_types 表。"""
    if not commands:
        return
    sb = _sb()
    envs = {c.get("env") for c in commands if c.get("env")}
    if not envs:
        return
    existing = {r["name"] for r in (sb.table("env_types").select("name").execute().data or [])}
    to_add = envs - existing
    if not to_add:
        return
    res = sb.table("env_types").select("sort_order").order("sort_order", desc=True).limit(1).execute()
    next_order = (res.data[0]["sort_order"] + 1) if res.data else 0
    rows = [{"name": n, "sort_order": next_order + i} for i, n in enumerate(sorted(to_add))]
    sb.table("env_types").insert(rows).execute()
