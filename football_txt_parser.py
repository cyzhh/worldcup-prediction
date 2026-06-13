#!/usr/bin/env python3
"""openfootball Football.TXT 赛果行解析（多届格式兼容）。"""

from __future__ import annotations

import re
from typing import Any

GROUP_HEADER = re.compile(r"^Group\s+([A-L])\s*\|\s*(.+)$", re.I)
GROUP_SECTION = re.compile(r"^▪\s*Group\s+([A-L])\s*$", re.I)
KNOCKOUT_MARK = re.compile(
    r"^(Round of|Knockout|Quarter|Semi-?final|Final|▪\s*Round|Third place)",
    re.I,
)
DATE_ONLY = re.compile(
    r"^\s*(?:\d{1,2}\s+)?"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"(?:\s+\d{1,2})?\s*$",
    re.I,
)

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
DATE_PREFIX = (
    r"(?:(?:\w{3}\s+" + MONTH + r"\s+\d{1,2}|\d{1,2}\s+" + MONTH + r")\s+)"
)

SCORE_LINE = re.compile(
    r"^\s*(?:" + DATE_PREFIX + r")?"
    r"(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+(.+?)\s+@\s*(.+?)\s*$"
)
SCORE_LINE_V = re.compile(
    r"^\s*(?:" + DATE_PREFIX + r")?"
    r"(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+@\s*(.+?)\s*$"
)


def normalize_score_line(line: str) -> str:
    """剥离开场时间、日期前缀，保留 球队 比分 球队 @ 场馆。"""
    s = line.strip()
    s = re.sub(
        rf"^\w{{3}}\s+{MONTH}\s+\d{{1,2}}(?:\s+\d{{2}}:\d{{2}})?\s+",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(rf"^\d{{1,2}}\s+{MONTH}\s+", "", s, flags=re.I)
    for _ in range(2):
        s = re.sub(r"^\d{2}:\d{2}(?:\s+UTC[-+]?\d+)?\s+", "", s)
    return s.strip()


def parse_score_line(line: str) -> dict[str, Any] | None:
    """解析单行赛果，失败返回 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("="):
        return None
    if DATE_ONLY.match(stripped):
        return None
    if stripped.startswith("(") or " og)" in stripped:
        return None

    normalized = normalize_score_line(stripped)
    if not normalized or "@" not in normalized:
        return None

    if " v " in normalized:
        mv = re.match(
            r"^(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+@\s*(.+?)\s*$",
            normalized,
        )
        if mv:
            t1, t2, gh, ga, _, _, venue = mv.groups()
            return {
                "team1": t1.strip(),
                "team2": t2.strip(),
                "score_home": int(gh),
                "score_away": int(ga),
                "venue": venue.strip(),
            }

    m = re.match(
        r"^(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+(.+?)\s+@\s*(.+?)\s*$",
        normalized,
    )
    if m:
        t1, gh, ga, _, _, t2, venue = m.groups()
        return {
            "team1": t1.strip(),
            "team2": t2.strip(),
            "score_home": int(gh),
            "score_away": int(ga),
            "venue": venue.strip(),
        }
    return None


def parse_all_results(text: str) -> list[dict[str, Any]]:
    """从 cup.txt 提取全部带 @ venue 的赛果行。"""
    results: list[dict[str, Any]] = []
    for line in text.splitlines():
        row = parse_score_line(line)
        if row:
            results.append(row)
    return results
