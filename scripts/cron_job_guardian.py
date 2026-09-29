"""Re-enable the DinoDashboard cron-job.org keepalive after recovery.

The guardian intentionally checks the application first.  A disabled job is
only enabled when /ping-db is healthy, so a persistent database outage does
not turn into an endless retry loop.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


API_BASE = "https://api.cron-job.org"
DEFAULT_HEALTH_URL = "https://dinodashboard.onrender.com/ping-db"
DEFAULT_JOB_TITLE = "DinoDashboard Keepalive"


class GuardianError(RuntimeError):
    """Expected guardian failure with a user-readable message."""


def request_json(
    url: str,
    *,
    api_key: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Call cron-job.org without logging the bearer token."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DinoDashboard-Cron-Guardian/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise GuardianError(f"cron-job.org API 回傳 HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GuardianError(f"無法連線 cron-job.org API：{exc.reason}") from exc
    return json.loads(raw or "{}")


def health_is_ready(url: str, timeout: int = 90) -> bool:
    """Wake Render and verify that the database-backed endpoint is healthy."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DinoDashboard-Cron-Guardian/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(64).decode("utf-8", errors="replace").strip()
            return response.status == 200 and body.lower().startswith("ok")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False


def find_keepalive_job(jobs: list[dict], title: str, expected_url: str) -> dict:
    """Select exactly one job using both title and URL as safety guards."""
    matches = [
        job
        for job in jobs
        if job.get("title") == title and job.get("url") == expected_url
    ]
    if not matches:
        raise GuardianError(
            f"找不到標題為 {title!r} 且網址為 {expected_url!r} 的定時工作"
        )
    if len(matches) > 1:
        raise GuardianError("找到多個同名同網址工作，為避免誤改已停止操作")
    return matches[0]


def repair_if_needed(
    *,
    api_key: str,
    health_url: str,
    job_title: str,
    dry_run: bool = False,
) -> str:
    """Enable the exact keepalive job only after the target is healthy."""
    if not health_is_ready(health_url):
        raise GuardianError("/ping-db 尚未恢復；保留 cron 工作原狀")

    result = request_json(f"{API_BASE}/jobs", api_key=api_key)
    job = find_keepalive_job(result.get("jobs", []), job_title, health_url)
    if job.get("enabled") is True:
        return "端點正常，cron 工作已是啟用狀態"

    if dry_run:
        return f"dry-run：會重新啟用 cron 工作 jobId={job['jobId']}"

    request_json(
        f"{API_BASE}/jobs/{job['jobId']}",
        api_key=api_key,
        method="PATCH",
        payload={"job": {"enabled": True}},
    )
    return f"已重新啟用 cron 工作 jobId={job['jobId']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("CRON_JOB_ORG_API_KEY", "").strip()
    if not api_key:
        print("錯誤：缺少 CRON_JOB_ORG_API_KEY", file=sys.stderr)
        return 2

    health_url = os.environ.get("GUARDIAN_HEALTH_URL", DEFAULT_HEALTH_URL).strip()
    job_title = os.environ.get("GUARDIAN_JOB_TITLE", DEFAULT_JOB_TITLE).strip()

    try:
        print(
            repair_if_needed(
                api_key=api_key,
                health_url=health_url,
                job_title=job_title,
                dry_run=args.dry_run,
            )
        )
    except GuardianError as exc:
        print(f"守門員未修復：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
