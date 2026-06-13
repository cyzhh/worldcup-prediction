#!/usr/bin/env python3
"""从 openfootball/worldcup 同步 Football.TXT 与 worldcup.json 数据。"""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app_config import path_from_config, sync_config
from wc_logging import setup_logging

log = setup_logging("worldcup.sync")

ROOT = Path(__file__).parent
OUT = path_from_config("openfootball_dir", "data/openfootball")

_cfg = sync_config()
SOURCES: dict[str, str] = dict(_cfg.get("sources") or {})
LIVE_REFRESH: set[str] = set(_cfg.get("live_refresh") or [])
USER_AGENT = str(_cfg.get("user_agent", "worldcup-predictor/1.0"))
TIMEOUT = int(_cfg.get("timeout_sec", 60))
MAX_RETRIES = int(_cfg.get("retries", 3))
BACKOFF = float(_cfg.get("retry_backoff_sec", 2.0))


def fetch(url: str) -> bytes:
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            log.warning("下载失败 (%s/%s) %s: %s", attempt, MAX_RETRIES, url, e)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF * attempt)
    raise urllib.error.URLError(last_err or "unknown")


def sync(force: bool = False) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for rel, url in SOURCES.items():
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup = dest.with_suffix(dest.suffix + ".bak")

        if dest.exists() and not force and rel not in LIVE_REFRESH:
            status[rel] = "cached"
            continue

        if dest.exists() and rel in LIVE_REFRESH:
            shutil.copy2(dest, backup)

        try:
            dest.write_bytes(fetch(url))
            status[rel] = "downloaded"
            log.info("已同步 %s", rel)
        except urllib.error.URLError as e:
            if backup.exists() and rel in LIVE_REFRESH:
                shutil.copy2(backup, dest)
                status[rel] = f"fallback: {e}"
                log.warning("LIVE_REFRESH 回退上一版: %s", rel)
            elif dest.exists():
                status[rel] = f"error-kept-cache: {e}"
                log.warning("保留本地缓存: %s (%s)", rel, e)
            else:
                status[rel] = f"error: {e}"
                log.error("同步失败且无缓存: %s (%s)", rel, e)

    manifest = {
        "sources": SOURCES,
        "status": status,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = [k for k, v in status.items() if str(v).startswith("error:")]
    if errors:
        log.warning("同步完成但有 %d 项完全失败: %s", len(errors), errors)
    return status


def main() -> None:
    import sys

    status = sync(force="--force" in sys.argv)
    for k, v in status.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
