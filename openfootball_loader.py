#!/usr/bin/env python3
"""解析 openfootball 2026 世界杯 JSON/TXT，构建预测引擎输入。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from elo_history import build_elo_ratings, parse_cup_txt_results
from team_registry import team_key

ROOT = Path(__file__).parent
OF_DIR = ROOT / "data" / "openfootball"
SEED_PATH = ROOT / "data" / "teams_seed.json"
DB_PATH = ROOT / "data" / "worldcup_db.json"

# 球场 → 海拔（米），用于环境因子
GROUND_ALTITUDE: dict[str, int] = {
    "Mexico City": 2240,
    "Guadalajara (Zapopan)": 1560,
    "Monterrey (Guadalupe)": 540,
}

GROUP_STAGE_ROUNDS = {
    "Matchday 1",
    "Matchday 2",
    "Matchday 3",
    "Matchday 4",
    "Matchday 5",
    "Matchday 6",
    "Matchday 7",
    "Matchday 8",
    "Matchday 9",
    "Matchday 10",
    "Matchday 11",
    "Matchday 12",
    "Matchday 13",
    "Matchday 14",
    "Matchday 15",
    "Matchday 16",
    "Matchday 17",
}



def load_worldcup_json(path: Path | None = None) -> dict[str, Any]:
    p = path or OF_DIR / "2026" / "worldcup.json"
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def load_seed_teams() -> dict[str, Any]:
    with SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def merge_elo_into_teams(teams: dict[str, Any], elo_map: dict[str, float]) -> dict[str, Any]:
    out = {}
    for key, t in teams.items():
        t = dict(t)
        if key in elo_map:
            t["elo"] = round(elo_map[key])
            t["elo_source"] = "openfootball_history"
        out[key] = t
    return out


def parse_groups_from_txt(cup_txt: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in cup_txt.splitlines():
        m = re.match(r"^Group\s+([A-L])\s*\|\s*(.+)$", line.strip())
        if m:
            names = re.split(r"\s{2,}|\t", m.group(2).strip())
            groups[m.group(1)] = [n.strip() for n in names if n.strip()]
    return groups


def build_h2h_from_history(cup_files: list[Path]) -> dict[str, dict[str, Any]]:
    """从历史世界杯赛果构建交锋 edge。"""
    h2h: dict[str, dict[str, Any]] = {}
    for path in cup_files:
        if not path.exists():
            continue
        for r in parse_cup_txt_results(path.read_text(encoding="utf-8")):
            k1, k2 = team_key(r["team1"]), team_key(r["team2"])
            key = f"{k1}_{k2}"
            entry = h2h.setdefault(key, {"home_wins": 0, "away_wins": 0, "draws": 0, "matches": []})
            gh, ga = r["score_home"], r["score_away"]
            if gh > ga:
                entry["home_wins"] += 1
            elif gh < ga:
                entry["away_wins"] += 1
            else:
                entry["draws"] += 1
            entry["matches"].append(f"{r['team1']} {gh}-{ga} {r['team2']}")
    # 转为 home_edge（下次主队在 home 一侧时的优势）
    result: dict[str, dict[str, Any]] = {}
    for key, e in h2h.items():
        total = e["home_wins"] + e["away_wins"] + e["draws"]
        if total == 0:
            continue
        hw_rate = e["home_wins"] / total
        result[key] = {
            "home_edge": round((hw_rate - 0.33) * 0.3, 3),
            "history": e["matches"][-3:],
            "record": f"{e['home_wins']}W{e['draws']}D{e['away_wins']}L",
        }
    return result


def matchday_to_round(matchday: str) -> int:
    m = re.search(r"(\d+)", matchday or "")
    if not m:
        return 1
    md = int(m.group(1))
    if md <= 7:
        return 1
    if md <= 13:
        return 2
    return 3


def format_subtitle(m: dict[str, Any]) -> str:
    parts = []
    if m.get("date"):
        try:
            dt = datetime.strptime(m["date"], "%Y-%m-%d")
            parts.append(f"{dt.month}月{dt.day}日")
        except ValueError:
            parts.append(m["date"])
    if m.get("round"):
        parts.append(m["round"])
    if m.get("group"):
        parts.append(m["group"])
    return " · ".join(parts)


def json_match_to_internal(m: dict[str, Any], idx: int) -> dict[str, Any] | None:
    rnd = m.get("round", "")
    if rnd not in GROUP_STAGE_ROUNDS:
        return None
    t1, t2 = m["team1"], m["team2"]
    k1, k2 = team_key(t1), team_key(t2)
    score = m.get("score", {})
    ft = score.get("ft") if score else None
    played = ft is not None
    venue = m.get("ground", "")
    return {
        "id": idx,
        "openfootball": {
            "group": m.get("group"),
            "round": rnd,
            "date": m.get("date"),
            "time": m.get("time"),
            "ground": venue,
        },
        "title": f"{t1} vs {t2}",
        "subtitle": format_subtitle(m),
        "round": matchday_to_round(rnd),
        "group": (m.get("group") or "").replace("Group ", ""),
        "datetime": f"{m.get('date', '')}T{m.get('time', '')}",
        "venue": venue,
        "home": k1,
        "away": k2,
        "home_name": t1,
        "away_name": t2,
        "played": played,
        "actual_score": {"home": ft[0], "away": ft[1]} if played else None,
        "actual_ht": score.get("ht") if played else None,
        "venue_altitude_m": GROUND_ALTITUDE.get(venue, 0),
    }


def load_schedule(
    *,
    group: str | None = None,
    matchday: str | None = None,
    only_unplayed: bool = False,
    only_played: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """返回 (meta, teams, bundle)。优先读取 db_builder 产出的 worldcup_db.json。"""
    if DB_PATH.exists():
        return _load_from_db(group, matchday, only_unplayed, only_played)

    wc = load_worldcup_json()
    seed = load_seed_teams()
    history_files = [
        OF_DIR / "2010--south-africa" / "cup.txt",
        OF_DIR / "2018--russia" / "cup.txt",
        OF_DIR / "2022--qatar" / "cup.txt",
    ]
    elo_map = build_elo_ratings(history_files, seed)
    teams = merge_elo_into_teams(seed, elo_map)
    cup_2026 = OF_DIR / "2026--usa" / "cup.txt"
    groups = parse_groups_from_txt(cup_2026.read_text(encoding="utf-8")) if cup_2026.exists() else {}
    matches: list[dict[str, Any]] = []
    for i, m in enumerate(wc.get("matches", []), start=1):
        internal = json_match_to_internal(m, i)
        if internal is None:
            continue
        if group and internal["group"] != group.upper().replace("GROUP ", ""):
            continue
        if matchday and internal["openfootball"]["round"] != matchday:
            continue
        if only_unplayed and internal["played"]:
            continue
        if only_played and not internal["played"]:
            continue
        matches.append(internal)
    h2h = build_h2h_from_history(history_files)
    meta = {
        "tournament": wc.get("name", "World Cup 2026"),
        "stage": "小组赛",
        "date_range": "2026.06.11 - 06.27",
        "subtitle": "基于 openfootball 赛程 + ELO/FIFA 因子量化分析",
        "data_source": "https://github.com/openfootball/worldcup",
        "json_source": "https://github.com/openfootball/worldcup.json",
        "groups": groups,
        "total_group_matches": len(matches),
    }
    return meta, teams, {"matches": matches, "h2h": h2h, "standings": {}, "benchmarks": {}}


def _load_from_db(
    group: str | None,
    matchday: str | None,
    only_unplayed: bool,
    only_played: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    with DB_PATH.open(encoding="utf-8") as f:
        db = json.load(f)

    from standings import motivation_context

    matches = []
    for m in db["matches"]:
        if group and m.get("group") != group.upper().replace("GROUP ", ""):
            continue
        if matchday and m.get("openfootball", {}).get("round") != matchday:
            continue
        if only_unplayed and m.get("played"):
            continue
        if only_played and not m.get("played"):
            continue
        mc = m.copy()
        g = mc.get("group", "")
        rnd = mc.get("round", 1)
        mc["motivation"] = {
            mc["home"]: motivation_context(mc["home"], g, db.get("standings", {}), rnd),
            mc["away"]: motivation_context(mc["away"], g, db.get("standings", {}), rnd),
        }
        if mc.get("venue_meta"):
            mc["venue_altitude_m"] = mc["venue_meta"].get("altitude_m", mc.get("venue_altitude_m", 0))
        matches.append(mc)

    meta = {
        "tournament": db["meta"].get("tournament", "World Cup 2026"),
        "stage": "小组赛",
        "date_range": "2026.06.11 - 06.27",
        "subtitle": "awesome-football 多源融合 · 赛程/球员/球场/ELO/H2H/积分榜",
        "data_source": "https://github.com/openfootball/awesome-football",
        "db_built_at": db["meta"].get("built_at"),
        "sources": db["meta"].get("sources", []),
        "groups": db.get("groups", {}),
        "total_group_matches": len(matches),
        "teams_count": db["meta"].get("teams_count"),
        "squads_players": db["meta"].get("squads_players"),
    }
    return meta, db["teams"], {
        "matches": matches,
        "h2h": db.get("h2h", {}),
        "standings": db.get("standings", {}),
        "benchmarks": db.get("benchmarks", {}),
        "stadiums": db.get("stadiums", {}),
        "players_by_team": db.get("players_by_team", {}),
    }
