#!/usr/bin/env python3
"""从 openfootball/worldcup 同步 Football.TXT 与 worldcup.json 数据。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "openfootball"

# 数据源：https://github.com/openfootball/worldcup
# JSON 镜像：https://github.com/openfootball/worldcup.json
SOURCES = {
    "2026--usa/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt",
    "2026/worldcup.json": "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
    "2022--qatar/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2022--qatar/cup.txt",
    "2018--russia/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2018--russia/cup.txt",
    "2014--brazil/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2014--brazil/cup.txt",
    "2010--south-africa/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2010--south-africa/cup.txt",
    "2006--germany/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2006--germany/cup.txt",
    "2002--south-korea-n-japan/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/2002--south-korea-n-japan/cup.txt",
    "1998--france/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/1998--france/cup.txt",
    "1994--usa/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/1994--usa/cup.txt",
    "1990--italy/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/1990--italy/cup.txt",
    "1986--mexico/cup.txt": "https://raw.githubusercontent.com/openfootball/worldcup/master/1986--mexico/cup.txt",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "worldcup-predictor/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def sync(force: bool = False) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for rel, url in SOURCES.items():
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            status[rel] = "cached"
            continue
        try:
            dest.write_bytes(fetch(url))
            status[rel] = "downloaded"
        except urllib.error.URLError as e:
            status[rel] = f"error: {e}"
    manifest = {"sources": SOURCES, "status": status}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def main() -> None:
    status = sync(force="--force" in __import__("sys").argv)
    for k, v in status.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
