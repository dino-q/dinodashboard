-- =====================================================================
-- DinoDashboard — Supabase Postgres Schema
-- ---------------------------------------------------------------------
-- 從 tools.yaml + credentials.json 遷移過來的資料結構。
--
-- 執行方式：
--   1. 在 Supabase Dashboard 打開 SQL Editor
--   2. 整份複製 → 貼上 → 按 Run
--   3. 應該看到 "Success. No rows returned"
--
-- 可重複執行 — 有 DROP ... IF EXISTS，不會爆。
-- =====================================================================

-- 先清乾淨，避免重跑出錯
DROP TABLE IF EXISTS quick_inputs CASCADE;
DROP TABLE IF EXISTS env_types CASCADE;
DROP TABLE IF EXISTS tools CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- =====================================================================
-- categories — 工具分類
-- =====================================================================
CREATE TABLE categories (
  id          TEXT PRIMARY KEY,                 -- e.g. 'web-app', 'scraper'
  name_zh     TEXT NOT NULL,                    -- 顯示名稱，例如「網頁應用」
  icon        TEXT NOT NULL DEFAULT 'folder',   -- Lucide icon name
  sort_order  INTEGER NOT NULL DEFAULT 99       -- 排序（原 YAML 的 order 欄位）
);

-- =====================================================================
-- tools — 主工具表
-- =====================================================================
CREATE TABLE tools (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL DEFAULT '',
  name_zh           TEXT NOT NULL DEFAULT '',
  description       TEXT NOT NULL DEFAULT '',
  category          TEXT REFERENCES categories(id) ON DELETE SET NULL,
  tags              JSONB NOT NULL DEFAULT '[]'::jsonb,   -- 字串陣列
  icon              TEXT NOT NULL DEFAULT 'box',
  color             TEXT NOT NULL DEFAULT '#6366F1',
  status            TEXT NOT NULL DEFAULT 'active',
  highlight         BOOLEAN NOT NULL DEFAULT false,
  starred           BOOLEAN NOT NULL DEFAULT false,
  screenshot        TEXT NOT NULL DEFAULT '',             -- 存 Storage 裡的檔名（legacy，保留做向後相容）
  screenshots       JSONB NOT NULL DEFAULT '[]'::jsonb,   -- 多張截圖 + 樣式：[{url, object_key, is_cover, pos_x, pos_y, scale, opacity, brightness, blur}]
  path              TEXT NOT NULL DEFAULT '',
  commands          JSONB NOT NULL DEFAULT '[]'::jsonb,   -- 物件陣列：{label,cmd,env,pinned}
  url               TEXT NOT NULL DEFAULT '',
  external_url      TEXT NOT NULL DEFAULT '',
  pin_path          BOOLEAN NOT NULL DEFAULT false,
  pin_url           BOOLEAN NOT NULL DEFAULT false,
  pin_external_url  BOOLEAN NOT NULL DEFAULT false,
  sort_order        INTEGER NOT NULL DEFAULT 0,           -- 拖曳排序用
  created_at        DATE NOT NULL DEFAULT CURRENT_DATE,
  updated_at        DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX idx_tools_category ON tools(category);
CREATE INDEX idx_tools_status   ON tools(status);
CREATE INDEX idx_tools_sort     ON tools(sort_order);
CREATE INDEX idx_tools_starred  ON tools(starred) WHERE starred = true;
CREATE INDEX idx_tools_highlight ON tools(highlight) WHERE highlight = true;

-- =====================================================================
-- env_types — 啟動指令的環境類型（local / docker / bat / ...）
-- =====================================================================
CREATE TABLE env_types (
  name        TEXT PRIMARY KEY,
  sort_order  INTEGER NOT NULL DEFAULT 99
);

-- =====================================================================
-- quick_inputs — 啟動指令的 preset（新增工具時快速填入）
-- =====================================================================
CREATE TABLE quick_inputs (
  id          SERIAL PRIMARY KEY,
  env         TEXT NOT NULL DEFAULT 'local',
  label       TEXT NOT NULL DEFAULT '',
  cmd         TEXT NOT NULL DEFAULT '',
  sort_order  INTEGER NOT NULL DEFAULT 0
);

-- =====================================================================
-- users — 登入帳號（多使用者 + 角色權限）
-- =====================================================================
CREATE TABLE users (
  username       TEXT PRIMARY KEY,
  password_hash  TEXT NOT NULL,
  salt           TEXT NOT NULL,
  role           TEXT NOT NULL DEFAULT 'viewer'
                 CHECK (role IN ('admin', 'editor', 'viewer')),
  approved       BOOLEAN NOT NULL DEFAULT false,
  created_at     DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX idx_users_approved ON users(approved);
CREATE INDEX idx_users_role     ON users(role);

-- =====================================================================
-- 完成！執行後應該看到：
--   Success. No rows returned
-- =====================================================================
