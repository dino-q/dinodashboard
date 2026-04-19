# DinoDashboard — Tool Portfolio & Showcase

## Overview

個人工具成果展示頁。展示所有自建工具的截圖/預覽，提供一鍵複製啟動指令。

## Tech Stack

- **Backend**: Flask + Jinja2
- **Frontend**: HTMX + Lucide Icons + Inter/JetBrains Mono (CDN)
- **Data**: `tools.yaml` (single source of truth)
- **Screenshots**: `static/screenshots/` (uploaded via web UI)

## Quick Start

```bash
cd DinoDashboard
pip install -r requirements.txt
python app.py
# http://localhost:5050
```

## File Structure

```
app.py              — Flask entry point (port 5050)
config.py           — Path constants
tools.yaml          — Tool registry (YAML CRUD)
data/tools.py       — YAML read/write/filter helpers
routes/main.py      — GET / → dashboard
routes/api.py       — CRUD + filter + screenshot upload (HTMX)
templates/          — Jinja2 templates (base, dashboard, partials)
static/css/         — Design tokens (dark/light) + component styles
static/js/          — Copy-cmd, modal, toast, theme toggle
static/screenshots/ — Tool preview images
```

## Data Layer

- `tools.yaml` 是唯一資料來源
- CRUD 操作都在 `data/tools.py`
- 每個工具有 `highlight: true/false`，highlight 的工具置頂顯示在 hero section
- 截圖上傳後存為 `static/screenshots/{tool-id}.{ext}`

## Design System

- Dark mode first (Slate-900 + Indigo accent)
- Light mode via `data-theme="light"` toggle
- CSS custom properties for all tokens
- 8px spacing grid
- Lucide SVG icons (no emoji)
