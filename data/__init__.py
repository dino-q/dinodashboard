"""
Data layer initialization.
"""
from config import TOOLS_YAML, SCREENSHOTS_DIR


_DEFAULT_YAML = """\
tools: []

categories:
  - id: web-app
    name_zh: "\\u7DB2\\u9801\\u61C9\\u7528"
    icon: globe
    order: 1
  - id: scraper
    name_zh: "\\u722C\\u87F2"
    icon: search
    order: 2
  - id: game
    name_zh: "\\u904A\\u6232"
    icon: gamepad-2
    order: 3
  - id: automation
    name_zh: "\\u81EA\\u52D5\\u5316"
    icon: zap
    order: 4
  - id: utility
    name_zh: "\\u5DE5\\u5177"
    icon: wrench
    order: 5
  - id: gas
    name_zh: Google Apps Script
    icon: cloud
    order: 6
  - id: devtool
    name_zh: "\\u958B\\u767C\\u5DE5\\u5177"
    icon: terminal
    order: 7
"""


def init_data_files():
    """Ensure tools.yaml and screenshots dir exist on startup."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if not TOOLS_YAML.exists():
        TOOLS_YAML.write_text(_DEFAULT_YAML, encoding="utf-8")
