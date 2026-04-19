"""
tools.yaml CRUD operations.
"""
import os
import re
from datetime import date

import yaml

from config import TOOLS_YAML

# ------------------------------------------------------------------
# Raw YAML read / write
# ------------------------------------------------------------------

def load_raw() -> dict:
    with open(TOOLS_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"tools": [], "categories": []}


def save_raw(data: dict) -> None:
    with open(TOOLS_YAML, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ------------------------------------------------------------------
# Read helpers
# ------------------------------------------------------------------

def load_tools() -> list[dict]:
    return load_raw().get("tools", [])


def load_categories() -> list[dict]:
    data = load_raw()
    cats = data.get("categories", [])
    return sorted(cats, key=lambda c: c.get("order", 99))


def get_tool(tool_id: str) -> dict | None:
    for t in load_tools():
        if t["id"] == tool_id:
            return t
    return None


DEFAULT_ENV_TYPES = ["local", "docker", "bat", "github"]


def load_env_types() -> list[str]:
    """Global list of launch-command env types. Seeded with defaults, augmented by custom types."""
    data = load_raw()
    types = data.get("env_types")
    if types is None:
        types = list(DEFAULT_ENV_TYPES)
        data["env_types"] = types
        save_raw(data)
    # Ensure all defaults present (in case user removed one)
    for d in DEFAULT_ENV_TYPES:
        if d not in types:
            types.append(d)
    # Also merge any env currently in use that isn't in the list (for older yaml)
    used = set()
    for t in data.get("tools", []):
        for c in t.get("commands", []):
            e = c.get("env")
            if e:
                used.add(e)
    added = False
    for e in used:
        if e not in types:
            types.append(e)
            added = True
    if added:
        data["env_types"] = types
        save_raw(data)
    return types


def add_env_type(name: str) -> bool:
    if not name:
        return False
    data = load_raw()
    types = data.setdefault("env_types", list(DEFAULT_ENV_TYPES))
    if name in types:
        return False
    types.append(name)
    save_raw(data)
    return True


def remove_env_type(name: str) -> bool:
    if name in DEFAULT_ENV_TYPES:
        return False
    data = load_raw()
    types = data.get("env_types", [])
    if name not in types:
        return False
    types.remove(name)
    save_raw(data)
    return True


# Seed presets — used when tools.yaml has no `quick_inputs` key yet. Matches the
# previously-hardcoded ENV_DEFAULT_LABELS in dashboard.js so "change env → auto-fill
# label" behavior is preserved.
_QUICK_INPUT_SEED = [
    {"env": "local",   "label": "啟動 Dev Server", "cmd": ""},
    {"env": "bat",     "label": "啟動 Bat",        "cmd": ""},
    {"env": "github",  "label": "Github_Repo",     "cmd": ""},
    {"env": "Notion",  "label": "Notion",          "cmd": ""},
    {"env": "Netlify", "label": "Netlify",         "cmd": ""},
    {"env": "gas",     "label": "GAS",             "cmd": ""},
    {"env": "Google",  "label": "啟動 sheet",      "cmd": ""},
]


def load_quick_inputs() -> list[dict]:
    """Presets used to quickly populate the Launch Commands editor.
    Returns seed defaults the first time (no `quick_inputs` key in yaml yet)."""
    data = load_raw()
    raw = data.get("quick_inputs")
    if raw is None:
        return [dict(x) for x in _QUICK_INPUT_SEED]
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        out.append({
            "env": (it.get("env") or "local").strip(),
            "label": (it.get("label") or "").strip(),
            "cmd": (it.get("cmd") or "").strip(),
        })
    return out


def save_quick_input_settings(env_types: list[str], quick_inputs: list[dict]) -> None:
    """Overwrite env_types + quick_inputs in tools.yaml in one pass."""
    data = load_raw()

    # Normalize env types — keep defaults, preserve order, drop blanks/dups
    cleaned_env = []
    seen = set()
    for name in env_types or []:
        n = (name or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        cleaned_env.append(n)
    for d in DEFAULT_ENV_TYPES:
        if d not in seen:
            cleaned_env.append(d)
            seen.add(d)

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

    data["env_types"] = cleaned_env
    data["quick_inputs"] = cleaned_qi
    save_raw(data)


def get_highlight_tool() -> dict | None:
    for t in load_tools():
        if t.get("highlight"):
            return t
    return None


def filter_tools(category: str | None = None, q: str | None = None,
                 status: str | None = None,
                 has_external: bool = False, has_local_url: bool = False,
                 has_notion: bool = False, has_github: bool = False,
                 has_gas: bool = False) -> list[dict]:
    tools = load_tools()
    if status:
        tools = [t for t in tools if t.get("status") == status]
    if category:
        tools = [t for t in tools if t.get("category") == category]
    # "has_*" filters — OR logic: show tools matching ANY enabled criterion
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
            if has_gas and _has_env(t, "gas"):
                return True
            return False

        tools = [t for t in tools if matches(t)]
    if q:
        q_lower = q.lower()
        tools = [
            t for t in tools
            if q_lower in t.get("name", "").lower()
            or q_lower in t.get("name_zh", "").lower()
            or q_lower in t.get("description", "").lower()
            or any(q_lower in tag.lower() for tag in t.get("tags", []))
        ]
    return tools


def tools_grouped_by_category(category: str | None = None, q: str | None = None,
                              status: str | None = None,
                              has_external: bool = False, has_local_url: bool = False,
                              has_notion: bool = False, has_github: bool = False,
                              has_gas: bool = False) -> list[dict]:
    """Return categories with their tools, for display grouping."""
    tools = filter_tools(category, q, status, has_external, has_local_url,
                         has_notion, has_github, has_gas)
    categories = load_categories()
    if category:
        categories = [c for c in categories if c["id"] == category]

    groups = []

    # Prepend 常用工具 (starred) — only when not filtering by category
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

    # Uncategorized
    known_ids = {c["id"] for c in categories}
    uncategorized = [t for t in tools if t.get("category") not in known_ids and not t.get("highlight")]
    if uncategorized:
        groups.append({
            "category": {"id": "_other", "name_zh": "其他", "icon": "folder", "order": 99},
            "tools": uncategorized,
        })
    return groups


# ------------------------------------------------------------------
# Write helpers
# ------------------------------------------------------------------

def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")[:60]


def _ensure_category(data: dict, form: dict) -> str:
    """If form has new category fields, create it and return its id."""
    cat_id = form.get("category", "utility")
    if cat_id != "__new__":
        return cat_id
    new_id = form.get("new_cat_id", "").strip()
    new_name = form.get("new_cat_name", "").strip()
    new_icon = form.get("new_cat_icon", "").strip() or "folder"
    if not new_id or not new_name:
        return "utility"
    cats = data.setdefault("categories", [])
    if not any(c["id"] == new_id for c in cats):
        max_order = max((c.get("order", 0) for c in cats), default=0)
        cats.append({"id": new_id, "name_zh": new_name, "icon": new_icon, "order": max_order + 1})
    return new_id


def add_tool(form: dict) -> dict:
    data = load_raw()
    tool_id = form.get("id") or _slugify(form.get("name", "tool"))

    # Ensure unique id
    existing_ids = {t["id"] for t in data.get("tools", [])}
    base_id = tool_id
    counter = 2
    while tool_id in existing_ids:
        tool_id = f"{base_id}-{counter}"
        counter += 1

    category = _ensure_category(data, form)
    today = str(date.today())
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
        "screenshot": form.get("screenshot", ""),
        "path": form.get("path", ""),
        "commands": _parse_commands(form),
        "url": form.get("url", ""),
        "external_url": form.get("external_url", ""),
        "pin_path": form.get("pin_path") == "on",
        "pin_url": form.get("pin_url") == "on",
        "pin_external_url": form.get("pin_external_url") == "on",
        "created_at": today,
        "updated_at": today,
    }
    # Sync any new env types into the global list
    env_types = data.setdefault("env_types", list(DEFAULT_ENV_TYPES))
    for cmd in tool["commands"]:
        if cmd.get("env") and cmd["env"] not in env_types:
            env_types.append(cmd["env"])
    data.setdefault("tools", []).append(tool)
    save_raw(data)
    return tool


def update_tool(tool_id: str, form: dict) -> dict | None:
    data = load_raw()
    category = _ensure_category(data, form)
    for i, t in enumerate(data.get("tools", [])):
        if t["id"] == tool_id:
            t["name"] = form.get("name", t["name"])
            t["name_zh"] = form.get("name_zh", t.get("name_zh", ""))
            t["description"] = form.get("description", t["description"])
            t["category"] = category
            t["tags"] = _parse_tags(form.get("tags", ",".join(t.get("tags", []))))
            t["icon"] = form.get("icon", t.get("icon", "box"))
            t["color"] = form.get("color", t.get("color", "#6366F1"))
            t["status"] = form.get("status", t.get("status", "active"))
            if "highlight" in form:
                t["highlight"] = form.get("highlight") == "on"
            t["screenshot"] = form.get("screenshot", t.get("screenshot", ""))
            t["path"] = form.get("path", t.get("path", ""))
            t["commands"] = _parse_commands(form)
            t["url"] = form.get("url", t.get("url", ""))
            t["external_url"] = form.get("external_url", t.get("external_url", ""))
            t["pin_path"] = form.get("pin_path") == "on"
            t["pin_url"] = form.get("pin_url") == "on"
            t["pin_external_url"] = form.get("pin_external_url") == "on"
            t["updated_at"] = str(date.today())
            data["tools"][i] = t
            # Sync any new env types into the global list
            env_types = data.setdefault("env_types", list(DEFAULT_ENV_TYPES))
            for cmd in t["commands"]:
                if cmd.get("env") and cmd["env"] not in env_types:
                    env_types.append(cmd["env"])
            save_raw(data)
            return t
    return None


def delete_tool(tool_id: str) -> bool:
    data = load_raw()
    before = len(data.get("tools", []))
    data["tools"] = [t for t in data.get("tools", []) if t["id"] != tool_id]
    if len(data["tools"]) < before:
        save_raw(data)
        return True
    return False


def reorder_tool(tool_id: str, before_id: str | None, category: str | None) -> dict | None:
    """Move tool to appear before before_id (or append to end if None).
    If category is a real category (not starting with _), also change the tool's category."""
    data = load_raw()
    tools = data.get("tools", [])

    tool = None
    for i, t in enumerate(tools):
        if t["id"] == tool_id:
            tool = tools.pop(i)
            break
    if not tool:
        return None

    if category and not category.startswith("_"):
        tool["category"] = category

    inserted = False
    if before_id:
        for i, t in enumerate(tools):
            if t["id"] == before_id:
                tools.insert(i, tool)
                inserted = True
                break
    if not inserted:
        tools.append(tool)

    tool["updated_at"] = str(date.today())
    data["tools"] = tools
    save_raw(data)
    return tool


def toggle_starred(tool_id: str) -> dict | None:
    data = load_raw()
    for t in data.get("tools", []):
        if t["id"] == tool_id:
            t["starred"] = not t.get("starred", False)
            t["updated_at"] = str(date.today())
            save_raw(data)
            return t
    return None


def update_screenshot(tool_id: str, filename: str) -> bool:
    data = load_raw()
    for t in data.get("tools", []):
        if t["id"] == tool_id:
            t["screenshot"] = f"screenshots/{filename}"
            t["updated_at"] = str(date.today())
            save_raw(data)
            return True
    return False


# ------------------------------------------------------------------
# Internal parse helpers
# ------------------------------------------------------------------

def _parse_tags(tags_str: str) -> list[str]:
    if isinstance(tags_str, list):
        return tags_str
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def _parse_commands(form: dict) -> list[dict]:
    """Parse dynamic command fields from form: cmd_label_0, cmd_cmd_0, cmd_env_0, ..."""
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
