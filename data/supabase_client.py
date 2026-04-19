"""
Supabase client singleton.

從環境變數 SUPABASE_URL + SUPABASE_SECRET_KEY 建立連線。
本機測試：建 .env 檔；Render：在 Dashboard 設環境變數。
"""
import os

from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    """Lazy-init Supabase client. 呼叫第一次時才建連線。"""
    global _client
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY environment variables.\n"
            "Set them in your .env file (local) or Render dashboard (deployed)."
        )

    _client = create_client(url, key)
    return _client
