"""
Auto-tag tools by scanning their local project paths.

Detects programming languages, frameworks, runtimes based on marker files
(package.json, requirements.txt, Dockerfile, *.py, *.ts, etc.) and merges
the detected tags with existing tags on each tool.

Exposes:
    scan_all_tools()  → list of { id, name_zh, added_tags, current_tags }
    auto_tag_all(apply=True)  → scans + writes back to tools.yaml if apply
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from data.tools import load_raw, save_raw

# Automation root on Linux host (mapped from Windows: C:\Users\AG_Di\Desktop\automation\Claude_code\automatic_evolution)
AUTOMATION_ROOT = Path("/app")
WIN_PREFIX = r"C:\Users\AG_Di\Desktop\automation\Claude_code\automatic_evolution"


def to_local_path(path_str: str) -> Path | None:
    """Resolve a tool's stored path to a real filesystem path.
    Tries the path natively first (for Windows-hosted Flask), then falls back
    to Linux/WSL mapping (for container-hosted Flask like /app)."""
    if not path_str:
        return None
    p = path_str.strip()

    # 1. Try the path as-is (works when Flask runs on Windows with C:\... paths native)
    try:
        native = Path(p)
        if native.exists():
            return native
    except (OSError, ValueError):
        pass

    # 2. Windows prefix → map onto AUTOMATION_ROOT (Linux/WSL case)
    if p.startswith(WIN_PREFIX):
        rel = p[len(WIN_PREFIX):].lstrip("\\/")
        mapped = AUTOMATION_ROOT / rel.replace("\\", "/")
        if mapped.exists():
            return mapped

    # 3. Any other Windows drive letter — give up
    if re.match(r"^[A-Za-z]:[\\/]", p):
        return None

    # 4. Dot / relative → resolve against AUTOMATION_ROOT
    if p in (".", "./"):
        return AUTOMATION_ROOT if AUTOMATION_ROOT.exists() else None

    mapped = AUTOMATION_ROOT / p.replace("\\", "/")
    if mapped.exists():
        return mapped

    return None


def _walk_shallow(root: Path, max_depth: int = 2) -> list[Path]:
    out: list[Path] = []
    try:
        for e in root.iterdir():
            if e.name.startswith(".") or e.name in (
                "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "output"
            ):
                continue
            if e.is_file():
                out.append(e)
            elif e.is_dir() and max_depth > 0:
                out.extend(_walk_shallow(e, max_depth - 1))
    except (PermissionError, OSError):
        pass
    return out


def scan_tool(path: Path) -> set[str]:
    """Return detected tech tags for the given local directory."""
    tags: set[str] = set()
    if not path.exists() or not path.is_dir():
        return tags

    # Marker files at root of the tool directory
    root_markers: dict[str, list[str]] = {
        "package.json": ["node"],
        "Dockerfile": ["docker"],
        "docker-compose.yml": ["docker"],
        "docker-compose.yaml": ["docker"],
        "requirements.txt": ["python"],
        "pyproject.toml": ["python"],
        "Pipfile": ["python"],
        "tsconfig.json": ["typescript"],
        ".nvmrc": ["node"],
        "appsscript.json": ["google-apps-script"],
        "vite.config.js": ["vite"],
        "vite.config.ts": ["vite", "typescript"],
        "tailwind.config.js": ["tailwind"],
        "tailwind.config.ts": ["tailwind", "typescript"],
        "next.config.js": ["next"],
        "next.config.mjs": ["next"],
        "svelte.config.js": ["svelte"],
        "astro.config.mjs": ["astro"],
    }
    try:
        for entry in path.iterdir():
            if entry.name in root_markers:
                tags.update(root_markers[entry.name])
    except (PermissionError, OSError):
        return tags

    # File extension counts (2 levels deep)
    files = _walk_shallow(path, max_depth=2)
    ext_has: dict[str, bool] = {}
    for f in files:
        ext_has[f.suffix.lower()] = True

    if ext_has.get(".py"):
        tags.add("python")
    if ext_has.get(".ts") or ext_has.get(".tsx"):
        tags.add("typescript")
    if ext_has.get(".js") or ext_has.get(".jsx"):
        tags.add("javascript")
    if ext_has.get(".gs"):
        tags.add("google-apps-script")
    if ext_has.get(".bat"):
        tags.add("bat")
    if ext_has.get(".ps1"):
        tags.add("powershell")
    if ext_has.get(".sh"):
        tags.add("bash")
    if ext_has.get(".html"):
        tags.add("html")

    # package.json deps → specific framework tags
    pkg_json = path / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            names = set(deps.keys())
            dep_map = {
                "react": "react", "vue": "vue", "svelte": "svelte",
                "next": "next", "nuxt": "nuxt", "vite": "vite",
                "tailwindcss": "tailwind", "express": "express",
                "peerjs": "peerjs",
            }
            for dep, tag in dep_map.items():
                if dep in names:
                    tags.add(tag)
            if any("puppeteer" in d for d in names):
                tags.add("puppeteer")
            if any("playwright" in d for d in names):
                tags.add("playwright")
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass

    # requirements.txt → python library tags
    req = path / "requirements.txt"
    if req.exists():
        try:
            txt = req.read_text(encoding="utf-8", errors="ignore").lower()
            py_libs = {
                "flask": "flask", "django": "django", "fastapi": "fastapi",
                "htmx": "htmx", "pyautogui": "pyautogui", "playwright": "playwright",
                "pandas": "pandas", "numpy": "numpy",
                "beautifulsoup4": "beautifulsoup", "scrapy": "scrapy",
                "openai": "openai", "anthropic": "anthropic",
                "langchain": "langchain", "chromadb": "chromadb",
                "sentence-transformers": "sentence-transformers",
                "sqlalchemy": "sqlalchemy",
                "line-bot-sdk": "line-api",
            }
            for lib, tag in py_libs.items():
                if lib in txt:
                    tags.add(tag)
        except OSError:
            pass

    # Shallow scan of *.py files for common imports
    for f in files[:50]:  # cap for performance
        if f.suffix == ".py":
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")[:5000]
                if re.search(r"from flask\b|import flask\b", content):
                    tags.add("flask")
                if re.search(r"from fastapi\b|import fastapi\b", content):
                    tags.add("fastapi")
                if re.search(r"import pyautogui", content):
                    tags.add("pyautogui")
                if re.search(r"from playwright\b|playwright\.sync_api|playwright\.async_api", content):
                    tags.add("playwright")
                if re.search(r"import openai\b|from openai\b", content):
                    tags.add("openai")
                if re.search(r"import anthropic\b|from anthropic\b", content):
                    tags.add("anthropic")
            except (OSError, UnicodeDecodeError):
                pass

    # HTML files for htmx
    for f in files[:30]:
        if f.suffix == ".html":
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")[:3000]
                if "htmx" in content.lower():
                    tags.add("htmx")
                    break
            except (OSError, UnicodeDecodeError):
                pass

    return tags


def scan_all_tools() -> list[dict[str, Any]]:
    """Dry-run scan: returns diff per tool without writing."""
    data = load_raw()
    results: list[dict[str, Any]] = []
    for tool in data.get("tools", []):
        local = to_local_path(tool.get("path", ""))
        if local is None or not local.exists():
            results.append({
                "id": tool["id"],
                "name_zh": tool.get("name_zh", ""),
                "status": "skipped",
                "reason": "path unreachable",
                "existing_tags": tool.get("tags", []),
                "added_tags": [],
            })
            continue
        detected = scan_tool(local)
        existing = set(tool.get("tags", []))
        added = sorted(detected - existing)
        results.append({
            "id": tool["id"],
            "name_zh": tool.get("name_zh", ""),
            "status": "ok",
            "existing_tags": tool.get("tags", []),
            "added_tags": added,
        })
    return results


def auto_tag_all(apply: bool = False) -> dict[str, Any]:
    """Scan every tool's path + merge detected tech tags into tags array.
    Returns summary dict with tool-level results.  If apply=True, saves to YAML.
    """
    data = load_raw()
    tools_changed = 0
    tag_additions_total = 0
    per_tool: list[dict[str, Any]] = []

    for tool in data.get("tools", []):
        local = to_local_path(tool.get("path", ""))
        if local is None or not local.exists():
            per_tool.append({
                "id": tool["id"], "status": "skipped",
                "added": [], "existing": tool.get("tags", []),
            })
            continue

        detected = scan_tool(local)
        existing = list(tool.get("tags", []))
        existing_lower = {t.lower() for t in existing}
        added: list[str] = []
        for t in sorted(detected):
            if t.lower() not in existing_lower:
                existing.append(t)
                existing_lower.add(t.lower())
                added.append(t)

        if added:
            tool["tags"] = existing
            tools_changed += 1
            tag_additions_total += len(added)

        per_tool.append({
            "id": tool["id"], "status": "ok",
            "added": added, "existing": existing,
        })

    skipped = sum(1 for r in per_tool if r["status"] == "skipped")
    scanned = len(per_tool) - skipped
    summary = {
        "tools_changed": tools_changed,
        "tag_additions_total": tag_additions_total,
        "tools_skipped": skipped,
        "tools_scanned": scanned,
        "per_tool": per_tool,
    }
    if apply and tools_changed > 0:
        save_raw(data)
        summary["written"] = True
    return summary
