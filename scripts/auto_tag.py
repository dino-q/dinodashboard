"""
CLI wrapper for the auto-tag feature.

Usage (from DinoDashboard/ root, in Flask venv):
    python scripts/auto_tag.py            # dry-run
    python scripts/auto_tag.py --apply    # write back to tools.yaml

Same logic as the UI button "掃描本機技術標籤" — pure local file scan, no API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure we can import data.auto_tag from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.auto_tag import auto_tag_all  # noqa: E402


def main(apply: bool) -> int:
    summary = auto_tag_all(apply=apply)
    for row in summary["per_tool"]:
        if row["status"] == "skipped":
            print(f"—  {row['id']:30s}  path unreachable")
        elif row["added"]:
            print(f"✎  {row['id']:30s}  + {', '.join(row['added'])}")
        else:
            print(f"○  {row['id']:30s}  no change")

    n = summary["tools_changed"]
    t = summary["tag_additions_total"]
    if n == 0:
        print("\n✓ 所有工具標籤已是最新")
    else:
        suffix = " (written to tools.yaml)" if summary.get("written") else " (dry-run; run with --apply)"
        print(f"\n✎ {n} tools updated, {t} tags added{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
