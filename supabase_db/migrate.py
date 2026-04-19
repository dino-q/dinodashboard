"""
DinoDashboard — 一次性資料搬家腳本

把 tools.yaml + credentials.json 的資料匯入 Supabase。
可重複執行（每次會先清空再重灌），所以跑幾次都 OK。

用法：
    # Linux / WSL:
    export SUPABASE_URL=https://xxx.supabase.co
    export SUPABASE_SECRET_KEY=sb_secret_xxx
    python supabase_db/migrate.py

    # Windows PowerShell:
    $env:SUPABASE_URL="https://xxx.supabase.co"
    $env:SUPABASE_SECRET_KEY="sb_secret_xxx"
    python supabase_db\migrate.py
"""
import json
import os
import sys
from pathlib import Path

import yaml
from supabase import create_client

# 從 .env 讀 SUPABASE_URL / SUPABASE_SECRET_KEY（若 dotenv 沒裝就跳過）
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# --------------------------------------------------------------------
# 讀設定
# --------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("❌ 缺少環境變數 SUPABASE_URL 或 SUPABASE_SECRET_KEY")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
TOOLS_YAML = BASE_DIR / "tools.yaml"
CREDENTIALS_JSON = BASE_DIR / "credentials.json"

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


# --------------------------------------------------------------------
# 1. 讀 tools.yaml
# --------------------------------------------------------------------
def load_yaml() -> dict:
    if not TOOLS_YAML.exists():
        print(f"⚠️  找不到 {TOOLS_YAML}，跳過工具資料")
        return {}
    with open(TOOLS_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_users() -> list[dict]:
    if not CREDENTIALS_JSON.exists():
        print(f"⚠️  找不到 {CREDENTIALS_JSON}，跳過使用者資料")
        return []
    with open(CREDENTIALS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("users", [])


# --------------------------------------------------------------------
# 2. 清空現有資料（按 FK 順序）
# --------------------------------------------------------------------
def clear_all():
    print("🧹 清空舊資料...")
    for table in ["tools", "categories", "env_types", "quick_inputs", "users"]:
        # 用 neq 技巧刪除全部（Supabase 不允許無條件 delete）
        # tools/categories/env_types/users 用 id/name；quick_inputs 用 id
        if table == "quick_inputs":
            sb.table(table).delete().gte("id", 0).execute()
        elif table == "env_types":
            sb.table(table).delete().neq("name", "__sentinel_never_exists__").execute()
        elif table == "users":
            sb.table(table).delete().neq("username", "__sentinel_never_exists__").execute()
        else:
            sb.table(table).delete().neq("id", "__sentinel_never_exists__").execute()
        print(f"   ✓ {table} 清空")


# --------------------------------------------------------------------
# 3. 匯入：categories
# --------------------------------------------------------------------
def import_categories(yaml_data: dict) -> int:
    cats = yaml_data.get("categories", [])
    defined_ids = {c.get("id") for c in cats if c.get("id")}

    # 自動補：掃所有工具的 category，如果 YAML 漏了就自己補一筆
    used_ids = {t.get("category") for t in yaml_data.get("tools", []) if t.get("category")}
    missing = used_ids - defined_ids
    # 從預設清單猜顯示名稱
    default_names = {
        "web-app": ("網頁應用", "globe"),
        "scraper": ("爬蟲", "search"),
        "game": ("遊戲", "gamepad-2"),
        "automation": ("自動化", "zap"),
        "utility": ("工具", "wrench"),
        "gas": ("Google Apps Script", "cloud"),
        "devtool": ("開發工具", "terminal"),
        "system": ("系統", "cpu"),
    }
    next_order = max((c.get("order", 0) for c in cats), default=0) + 1
    for mid in sorted(missing):
        name, icon = default_names.get(mid, (mid.replace("-", " ").title(), "folder"))
        cats.append({"id": mid, "name_zh": name, "icon": icon, "order": next_order})
        next_order += 1
        print(f"   ⚠ 自動補分類：{mid}（YAML 沒定義但工具有用到）")

    rows = [{
        "id": c.get("id"),
        "name_zh": c.get("name_zh", ""),
        "icon": c.get("icon", "folder"),
        "sort_order": c.get("order", 99),
    } for c in cats if c.get("id")]
    if rows:
        sb.table("categories").insert(rows).execute()
    return len(rows)


# --------------------------------------------------------------------
# 4. 匯入：tools
# --------------------------------------------------------------------
def import_tools(yaml_data: dict) -> int:
    tools = yaml_data.get("tools", [])
    if not tools:
        return 0

    rows = []
    for i, t in enumerate(tools):
        if not t.get("id"):
            continue
        rows.append({
            "id": t["id"],
            "name": t.get("name", ""),
            "name_zh": t.get("name_zh", ""),
            "description": t.get("description", ""),
            "category": t.get("category") or None,
            "tags": t.get("tags", []) or [],
            "icon": t.get("icon", "box"),
            "color": t.get("color", "#6366F1"),
            "status": t.get("status", "active"),
            "highlight": bool(t.get("highlight", False)),
            "starred": bool(t.get("starred", False)),
            "screenshot": t.get("screenshot", "") or "",
            "path": t.get("path", "") or "",
            "commands": t.get("commands", []) or [],
            "url": t.get("url", "") or "",
            "external_url": t.get("external_url", "") or "",
            "pin_path": bool(t.get("pin_path", False)),
            "pin_url": bool(t.get("pin_url", False)),
            "pin_external_url": bool(t.get("pin_external_url", False)),
            "sort_order": i,  # 保留 YAML 的原始順序
            "created_at": str(t.get("created_at", "")) or None,
            "updated_at": str(t.get("updated_at", "")) or None,
        })
    # 分批匯入，避免 request body 太大
    batch = 20
    for i in range(0, len(rows), batch):
        sb.table("tools").insert(rows[i:i + batch]).execute()
    return len(rows)


# --------------------------------------------------------------------
# 5. 匯入：env_types
# --------------------------------------------------------------------
def import_env_types(yaml_data: dict) -> int:
    types = yaml_data.get("env_types", [])
    if not types:
        return 0
    rows = [{"name": name, "sort_order": i} for i, name in enumerate(types) if name]
    if rows:
        sb.table("env_types").insert(rows).execute()
    return len(rows)


# --------------------------------------------------------------------
# 6. 匯入：quick_inputs
# --------------------------------------------------------------------
def import_quick_inputs(yaml_data: dict) -> int:
    qi = yaml_data.get("quick_inputs", [])
    if not qi:
        return 0
    rows = [{
        "env": (q.get("env") or "local").strip(),
        "label": (q.get("label") or "").strip(),
        "cmd": (q.get("cmd") or "").strip(),
        "sort_order": i,
    } for i, q in enumerate(qi) if isinstance(q, dict)]
    if rows:
        sb.table("quick_inputs").insert(rows).execute()
    return len(rows)


# --------------------------------------------------------------------
# 7. 匯入：users
# --------------------------------------------------------------------
def import_users(users: list[dict]) -> int:
    if not users:
        return 0
    rows = [{
        "username": u["username"],
        "password_hash": u["password_hash"],
        "salt": u["salt"],
        "role": u.get("role", "viewer"),
        "approved": bool(u.get("approved", False)),
        "created_at": str(u.get("created_at", "")) or None,
    } for u in users if u.get("username")]
    if rows:
        sb.table("users").insert(rows).execute()
    return len(rows)


# --------------------------------------------------------------------
# main
# --------------------------------------------------------------------
def main():
    print(f"🔗 連線：{SUPABASE_URL}")
    yaml_data = load_yaml()
    users = load_users()

    clear_all()

    n_cat = import_categories(yaml_data)
    print(f"📁 分類：匯入 {n_cat} 筆")

    n_tool = import_tools(yaml_data)
    print(f"🔧 工具：匯入 {n_tool} 筆")

    n_env = import_env_types(yaml_data)
    print(f"🌿 Env types：匯入 {n_env} 筆")

    n_qi = import_quick_inputs(yaml_data)
    print(f"⚡ Quick inputs：匯入 {n_qi} 筆")

    n_u = import_users(users)
    print(f"👤 使用者：匯入 {n_u} 筆")

    print()
    print("✅ 全部匯入完成！可以去 Supabase Dashboard → Table Editor 檢查。")


if __name__ == "__main__":
    main()
