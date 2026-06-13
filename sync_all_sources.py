#!/usr/bin/env python3
"""同步 awesome-football 推荐的全部开源数据源。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "external"

# 来源索引：https://github.com/openfootball/awesome-football
SOURCES = {
    # openfootball 核心（已在 sync_openfootball 中，此处引用路径）
    "openfootball/worldcup": "see sync_openfootball.py",
    # risingtransfers 2026 球员数据 (CC BY 4.0)
    "risingtransfers/squads.csv": "https://raw.githubusercontent.com/risingtransfers/world-cup-2026-data/main/data/squads.csv",
    "risingtransfers/per90_stats.csv": "https://raw.githubusercontent.com/risingtransfers/world-cup-2026-data/main/data/per90_stats.csv",
    # Onside 2026 模型基准 (CC BY 4.0)
    "onside/predictions.csv": "https://onsidearena.com/data/predictions.csv",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "worldcup-db-builder/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def sync_external(force: bool = False) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for rel, url in SOURCES.items():
        if url.startswith("see "):
            status[rel] = "delegated"
            continue
        dest = OUT / rel.replace("/", "__")
        if dest.exists() and not force:
            status[rel] = "cached"
            continue
        try:
            dest.write_bytes(fetch(url))
            status[rel] = "downloaded"
        except urllib.error.URLError as e:
            status[rel] = f"error: {e}"
    (OUT / "manifest.json").write_text(json.dumps({"sources": SOURCES, "status": status}, indent=2), encoding="utf-8")
    return status


def sync_all(force: bool = False) -> None:
    from sync_openfootball import sync as sync_of

    print("=== openfootball/worldcup ===")
    for k, v in sync_of(force=force).items():
        print(f"  {k}: {v}")
    print("=== awesome-football 扩展源 ===")
    for k, v in sync_external(force=force).items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    import sys
    sync_all(force="--force" in sys.argv)
