"""
Supabase-backed auth：多使用者 + 角色權限。

Roles:
    admin   — everything, including user management
    editor  — can add/edit/delete tools
    viewer  — read-only

States:
    approved=True  — 可登入
    approved=False — 等管理員核准，暫時無法登入

對外 API 與舊版 credentials.json 檔案版本完全相容。
"""
import hashlib
import secrets
from datetime import date

from data.supabase_client import get_client

ROLES = ("admin", "editor", "viewer")


# ------------------------------------------------------------------
# 內部工具
# ------------------------------------------------------------------

def _sb():
    return get_client()


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


# ------------------------------------------------------------------
# 讀取
# ------------------------------------------------------------------

def list_users() -> list[dict]:
    res = _sb().table("users").select("*").order("created_at").execute()
    return list(res.data or [])


def get_user(username: str) -> dict | None:
    if not username:
        return None
    res = _sb().table("users").select("*").eq("username", username).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def has_any_user() -> bool:
    res = _sb().table("users").select("username", count="exact").limit(1).execute()
    return (res.count or 0) > 0


def has_admin() -> bool:
    res = _sb().table("users").select("username").eq("role", "admin").eq("approved", True).limit(1).execute()
    return bool(res.data)


# ------------------------------------------------------------------
# 寫入
# ------------------------------------------------------------------

def create_user(username: str, password: str, role: str = "viewer",
                approved: bool = False) -> dict | None:
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return None
    if role not in ROLES:
        role = "viewer"

    sb = _sb()
    existing = sb.table("users").select("username").eq("username", username).execute().data or []
    if existing:
        return None  # duplicate

    salt = secrets.token_hex(16)
    user = {
        "username": username,
        "password_hash": _hash(password, salt),
        "salt": salt,
        "role": role,
        "approved": approved,
        "created_at": str(date.today()),
    }
    res = sb.table("users").insert(user).execute()
    return res.data[0] if res.data else user


def verify(username: str, password: str) -> dict | None:
    """通過驗證且 approved=True 才回傳使用者紀錄。"""
    u = get_user(username)
    if not u or not u.get("approved"):
        return None
    if _hash(password, u["salt"]) != u["password_hash"]:
        return None
    return u


def approve(username: str, role: str = "viewer") -> bool:
    if role not in ROLES:
        role = "viewer"
    res = _sb().table("users").update({"approved": True, "role": role}).eq("username", username).execute()
    return bool(res.data)


def set_role(username: str, role: str) -> bool:
    if role not in ROLES:
        return False
    res = _sb().table("users").update({"role": role}).eq("username", username).execute()
    return bool(res.data)


def delete_user(username: str) -> bool:
    res = _sb().table("users").delete().eq("username", username).execute()
    return bool(res.data)


# ------------------------------------------------------------------
# 向後相容 API
# ------------------------------------------------------------------

def has_credentials() -> bool:
    return has_any_user()


def create_credentials(username: str, password: str) -> None:
    """舊版 API — 建第一個 admin。"""
    create_user(username, password, role="admin", approved=True)
