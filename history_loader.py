#!/usr/bin/env python3
"""解析 openfootball cup.txt，提取历届世界杯小组赛赛程与赛果。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from team_registry import team_key

ROOT = Path(__file__).parent
OF_DIR = ROOT / "data" / "openfootball"

# 按时间顺序排列，用于 walk-forward 回测
TOURNAMENTS: list[dict[str, Any]] = [
    {"id": "2006--germany", "year": 2006, "hosts": {"GER"}, "label": "2006 德国世界杯"},
    {"id": "2010--south-africa", "year": 2010, "hosts": {"RSA"}, "label": "2010 南非世界杯"},
    {"id": "2014--brazil", "year": 2014, "hosts": {"BRA"}, "label": "2014 巴西世界杯"},
    {"id": "2018--russia", "year": 2018, "hosts": {"RUS"}, "label": "2018 俄罗斯世界杯"},
    {"id": "2022--qatar", "year": 2022, "hosts": {"QAT"}, "label": "2022 卡塔尔世界杯"},
]

GROUP_HEADER = re.compile(r"^Group\s+([A-H])\s*\|\s*(.+)$")
GROUP_SECTION = re.compile(r"^▪\s*Group\s+([A-H])\s*$", re.I)
KNOCKOUT_MARK = re.compile(
    r"^(Round of|Knockout|Quarter|Semi-?final|Final|▪\s*Round|Third place)",
    re.I,
)
MATCH_SCORE = re.compile(
    r"^\s*(?:\w{3}\s+\w{3}\s+\d{1,2}\s+)?"
    r"(?:\d{2}:\d{2}(?:\s+UTC[^\s@]+)?\s+)?"
    r"(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+(.+?)\s+@\s*(.+?)\s*$"
)
MATCH_SCORE_V = re.compile(
    r"^\s*(?:\d{2}:\d{2}\s+UTC[^\s@]+\s+)?"
    r"(.+?)\s+v\s+(.+?)\s+(\d+)-(\d+)\s*(?:\(\s*(\d+)-(\d+)\s*\))?\s+@\s*(.+?)\s*$"
)


@dataclass
class HistoricalMatch:
    tournament_id: str
    year: int
    group: str
    round_num: int
    seq_in_group: int
    home_name: str
    away_name: str
    home_key: str
    away_key: str
    score_home: int
    score_away: int
    venue: str
    line_no: int
    raw_home: str = ""
    raw_away: str = ""


@dataclass
class TournamentData:
    meta: dict[str, Any]
    groups: dict[str, list[str]]
    group_keys: dict[str, list[str]]
    matches: list[HistoricalMatch] = field(default_factory=list)


def parse_groups(cup_txt: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in cup_txt.splitlines():
        m = GROUP_HEADER.match(line.strip())
        if not m:
            continue
        names = re.split(r"\s{2,}|\t", m.group(2).strip())
        groups[m.group(1)] = [n.strip() for n in names if n.strip()]
    return groups


def _round_from_seq(seq: int, group_size: int) -> int:
    if group_size <= 4:
        if seq <= 2:
            return 1
        if seq <= 4:
            return 2
        return 3
    # 5+ 队扩军组：按每轮场数近似
    per_round = max(1, (group_size * (group_size - 1) // 2) // 3)
    return min(3, (seq - 1) // per_round + 1)


def parse_group_stage_matches(tournament: dict[str, Any], cup_path: Path) -> TournamentData:
    text = cup_path.read_text(encoding="utf-8")
    groups = parse_groups(text)
    group_keys = {g: [team_key(n) for n in names] for g, names in groups.items()}
    hosts = tournament["hosts"]

    matches: list[HistoricalMatch] = []
    current_group: str | None = None
    seq_in_group: dict[str, int] = {g: 0 for g in groups}

    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if KNOCKOUT_MARK.match(stripped):
            break

        sec = GROUP_SECTION.match(stripped)
        if sec:
            current_group = sec.group(1).upper()
            continue

        if not current_group:
            continue

        t1 = t2 = gh = ga = venue = None
        if " v " in line:
            mv = MATCH_SCORE_V.match(line.strip())
            if mv:
                t1, t2, gh, ga, _, _, venue = mv.groups()
        else:
            m = MATCH_SCORE.match(line)
            if m:
                t1, gh, ga, _, _, t2, venue = m.groups()

        if t1 is None or t2 is None:
            continue

        t1, t2 = t1.strip(), t2.strip()
        k1, k2 = team_key(t1), team_key(t2)
        if current_group not in group_keys:
            continue
        if k1 not in group_keys[current_group] or k2 not in group_keys[current_group]:
            continue

        seq_in_group[current_group] += 1
        seq = seq_in_group[current_group]
        gsize = len(group_keys[current_group])

        matches.append(
            HistoricalMatch(
                tournament_id=tournament["id"],
                year=tournament["year"],
                group=current_group,
                round_num=_round_from_seq(seq, gsize),
                seq_in_group=seq,
                home_name=t1,
                away_name=t2,
                home_key=k1,
                away_key=k2,
                score_home=int(gh),
                score_away=int(ga),
                venue=venue.strip(),
                line_no=i,
                raw_home=t1,
                raw_away=t2,
            )
        )

    return TournamentData(
        meta={
            "id": tournament["id"],
            "year": tournament["year"],
            "label": tournament["label"],
            "hosts": list(hosts),
            "groups_count": len(groups),
            "group_matches": len(matches),
        },
        groups=groups,
        group_keys=group_keys,
        matches=matches,
    )


def load_all_tournaments() -> list[TournamentData]:
    out: list[TournamentData] = []
    for t in TOURNAMENTS:
        path = OF_DIR / t["id"] / "cup.txt"
        if path.exists():
            out.append(parse_group_stage_matches(t, path))
    return out


def cup_files_before(tournament_id: str) -> list[Path]:
    files: list[Path] = []
    for t in TOURNAMENTS:
        if t["id"] == tournament_id:
            break
        p = OF_DIR / t["id"] / "cup.txt"
        if p.exists():
            files.append(p)
    return files


def to_predictor_match(hm: HistoricalMatch, match_id: int, motivation: dict | None = None) -> dict[str, Any]:
    return {
        "id": match_id,
        "title": f"{hm.home_name} vs {hm.away_name}",
        "subtitle": f"{hm.year} 小组赛 {hm.group}组 · 第{hm.round_num}轮",
        "round": hm.round_num,
        "group": hm.group,
        "venue": hm.venue,
        "home": hm.home_key,
        "away": hm.away_key,
        "home_name": hm.home_name,
        "away_name": hm.away_name,
        "played": True,
        "actual_score": {"home": hm.score_home, "away": hm.score_away},
        "venue_altitude_m": 0,
        "travel_km": {},
        "motivation": motivation or {},
        "openfootball": {
            "tournament": hm.tournament_id,
            "group": hm.group,
            "round_num": hm.round_num,
        },
    }
