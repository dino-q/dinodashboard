"""
File-based auth with multiple users + role-based permissions.

Roles:
    admin   — everything, including user management
    editor  — can add/edit/delete tools
    viewer  — read-only

States:
    approved=True  — can log in
    approved=False — pending, blocked from login

Credentials file layout (gitignored):
    {
      "users": [
        {"username", "password_hash", "salt", "role", "approved", "created_at"},
        ...
      ]
    }
"""
import hashlib
import json
import secrets
from datetime import date

from config import BASE_DIR

CREDENTIALS_FILE = BASE_DIR / "credentials.json"

ROLES = ("admin", "editor", "viewer")


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def _load() -> dict:
    if not CREDENTIALS_FILE.exists():
        return {"users": []}
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"users": []}
    # Legacy single-user format → migrate to multi-user, promote to admin
    if "username" in data and "users" not in data:
        migrated = {
            "users": [{
                "username": data["username"],
                "password_hash": data["password_hash"],
                "salt": data["salt"],
                "role": "admin",
                "approved": True,
                "created_at": str(date.today()),
            }]
        }
        _save(migrated)
        return migrated
    data.setdefault("users", [])
    return data


def _save(data: dict) -> None:
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_users() -> list[dict]:
    return _load().get("users", [])


def get_user(username: str) -> dict | None:
    if not username:
        return None
    for u in list_users():
        if u["username"] == username:
            return u
    return None


def has_any_user() -> bool:
    return len(list_users()) > 0


def has_admin() -> bool:
    return any(u.get("role") == "admin" and u.get("approved") for u in list_users())


def create_user(username: str, password: str, role: str = "viewer",
                approved: bool = False) -> dict | None:
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return None
    data = _load()
    if any(u["username"] == username for u in data["users"]):
        return None  # duplicate
    if role not in ROLES:
        role = "viewer"
    salt = secrets.token_hex(16)
    user = {
        "username": username,
        "password_hash": _hash(password, salt),
        "salt": salt,
        "role": role,
        "approved": approved,
        "created_at": str(date.today()),
    }
    data["users"].append(user)
    _save(data)
    return user


def verify(username: str, password: str) -> dict | None:
    """Return the user record iff credentials are valid AND approved."""
    u = get_user(username)
    if not u or not u.get("approved"):
        return None
    if _hash(password, u["salt"]) != u["password_hash"]:
        return None
    return u


def approve(username: str, role: str = "viewer") -> bool:
    if role not in ROLES:
        role = "viewer"
    data = _load()
    for u in data["users"]:
        if u["username"] == username:
            u["approved"] = True
            u["role"] = role
            _save(data)
            return True
    return False


def set_role(username: str, role: str) -> bool:
    if role not in ROLES:
        return False
    data = _load()
    for u in data["users"]:
        if u["username"] == username:
            u["role"] = role
            _save(data)
            return True
    return False


def delete_user(username: str) -> bool:
    data = _load()
    before = len(data["users"])
    data["users"] = [u for u in data["users"] if u["username"] != username]
    if len(data["users"]) < before:
        _save(data)
        return True
    return False


# Backwards-compat shim for existing code
def has_credentials() -> bool:
    return has_any_user()


def create_credentials(username: str, password: str) -> None:
    """Legacy setup API — now creates the first admin."""
    create_user(username, password, role="admin", approved=True)
