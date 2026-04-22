"""
Scan the `screenshots` Storage bucket for files that aren't referenced by any
tool's `screenshots` JSONB. Deletes them on --apply.

This cleans up two kinds of orphans:
  1. Uploads from abandoned "new tool" sessions (user uploaded then cancelled).
  2. Files left behind when a tool was deleted before Phase 6 cascade was wired.

Usage (from DinoDashboard/ root, in Flask venv):
    python scripts/cleanup_orphan_screenshots.py            # dry-run, list only
    python scripts/cleanup_orphan_screenshots.py --apply    # actually delete
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.supabase_client import get_client  # noqa: E402
from data.tools import load_tools  # noqa: E402


def _list_all_storage_keys(bucket) -> list[str]:
    """Recursively list every object under the screenshots bucket.
    Supabase Storage's list() is single-level — we walk tool_id folders."""
    out: list[str] = []
    top = bucket.list() or []
    for entry in top:
        name = entry.get("name")
        if not name:
            continue
        # Files at bucket root (legacy) show up with an `id` key; folders don't.
        if entry.get("id"):
            out.append(name)
            continue
        # Treat as folder: list inside
        children = bucket.list(name) or []
        for c in children:
            cname = c.get("name")
            if cname:
                out.append(f"{name}/{cname}")
    return out


def _referenced_keys() -> set[str]:
    """Union of every `object_key` across all tools' screenshots JSONB."""
    refs = set()
    for t in load_tools():
        for s in t.get("screenshots") or []:
            k = (s.get("object_key") or "").strip()
            if k:
                refs.add(k)
    return refs


def main(apply: bool) -> int:
    bucket = get_client().storage.from_("screenshots")
    all_keys = _list_all_storage_keys(bucket)
    referenced = _referenced_keys()

    orphans = [k for k in all_keys if k not in referenced]
    print(f"Storage objects: {len(all_keys)}  |  referenced: {len(referenced)}  |  orphans: {len(orphans)}")

    if not orphans:
        print("✓ nothing to clean")
        return 0

    for k in orphans:
        print(f"  {'DELETE' if apply else 'ORPHAN'}  {k}")

    if apply:
        bucket.remove(orphans)
        print(f"✓ removed {len(orphans)} orphans")
    else:
        print("(dry-run — pass --apply to actually delete)")
    return 0


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    sys.exit(main(apply))
