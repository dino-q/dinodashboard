-- ====================================================================
-- DinoDashboard — 「伺服器」分頁用的資料表（Server_Launcher 伺服器總管）
-- ====================================================================
--
-- 怎麼用：
--   1. 在 Supabase Dashboard 打開 SQL Editor
--   2. 整份複製 → 貼上 → 按 Run
--   3. 應該看到 "Success. No rows returned"
--
-- 這份只新增一張表，**完全不動既有的 tools / categories / users**。
-- 重複執行沒關係（都有 IF NOT EXISTS）。
--
-- 設計說明：
--   伺服器清單本身不存在這裡，而是每次從 tools.commands 裡 env='bat' 的
--   項目動態生成。這張表只存「Dino 對每一支 bat 做過的決定」：
--   要不要顯示、要不要預設打勾、有沒有被封存、顯示名稱改成什麼。
--   好處是在任何卡片新增一筆 bat 指令，伺服器分頁就會自動多一列，
--   不需要兩邊手動同步。
-- ====================================================================

CREATE TABLE IF NOT EXISTS launcher_entries (
  bat_key     TEXT PRIMARY KEY,                -- 正規化路徑的 sha1 前 16 碼（當網址用，穩定且安全）
  tool_id     TEXT,                            -- 來源卡片 id（顯示與追溯用）
  bat_path    TEXT NOT NULL DEFAULT '',        -- 原始大小寫的完整 Windows 路徑
  label       TEXT NOT NULL DEFAULT '',        -- 顯示名稱；空字串＝用卡片名自動帶
  visible     BOOLEAN NOT NULL DEFAULT true,   -- 要不要出現在本機總管的清單上
  default_on  BOOLEAN NOT NULL DEFAULT false,  -- 總管打開時預設打勾（＝開機會自動開）
  archived    BOOLEAN NOT NULL DEFAULT false,  -- 封存：收進封存區，可查看、可解除
  port        INTEGER,                         -- 偵測「是否已在跑」用；NULL＝偵測不到
  sort_order  INTEGER NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_launcher_visible ON launcher_entries(visible, archived);
CREATE INDEX IF NOT EXISTS idx_launcher_sort    ON launcher_entries(sort_order);
CREATE INDEX IF NOT EXISTS idx_launcher_tool    ON launcher_entries(tool_id);

COMMENT ON TABLE launcher_entries IS
  'Server_Launcher 伺服器總管：每支 bat 的顯示/預設/封存狀態。清單來源是 tools.commands 中 env=bat 的項目。';
