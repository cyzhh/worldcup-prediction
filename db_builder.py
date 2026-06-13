#!/usr/bin/env python3
"""构建统一世界杯数据库 worldcup_db.json（awesome-football 多源融合）。"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_teams_seed import build_seed
from elo_history import build_elo_ratings
from openfootball_loader import (
    OF_DIR,
    build_h2h_from_history,
    json_match_to_internal,
    load_worldcup_json,
    parse_groups_from_txt,
    team_key,
)
from player_enrichment import aggregate_by_team, load_per90, load_squads
from player_scores import build_players_by_team
from standings import compute_standings

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "worldcup_db.json"
STADIUMS_PATH = ROOT / "data" / "stadiums_2026.json"
EXT = ROOT / "data" / "external"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_stadiums() -> dict[str, Any]:
    with STADIUMS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def history_cup_files() -> list[Path]:
    files = [
        OF_DIR / "2010--south-africa" / "cup.txt",
        OF_DIR / "2014--brazil" / "cup.txt",
        OF_DIR / "2006--germany" / "cup.txt",
        OF_DIR / "2018--russia" / "cup.txt",
        OF_DIR / "2022--qatar" / "cup.txt",
    ]
    return [p for p in files if p.exists()]


def parse_groups_internal(cup_txt: str) -> dict[str, list[str]]:
    raw = parse_groups_from_txt(cup_txt)
    return {g: [team_key(n) for n in names] for g, names in raw.items()}


def merge_team(base: dict[str, Any], enrich: dict[str, Any], elo: float) -> dict[str, Any]:
    t = dict(base)
    t["elo"] = round(elo, 1)
    t["elo_source"] = "openfootball_history_multi_wc"
    if enrich:
        t["squad_value_m"] = enrich.get("squad_value_m", t.get("squad_value_m"))
        t["squad_size"] = enrich.get("squad_size")
        t["avg_age"] = enrich.get("avg_age")
        t["data_sources"] = list({t.get("data_source", "seed"), enrich.get("data_source", "")} - {""})
        if enrich.get("squad"):
            t["squad"] = {**t.get("squad", {}), **enrich["squad"]}
        if enrich.get("form"):
            f = t.get("form", {})
            f["goals_for"] = enrich["form"].get("goals_for", f.get("goals_for"))
            f["xg_diff"] = enrich["form"].get("xg_diff", f.get("xg_diff"))
            t["form"] = f
    return t


def attach_travel(matches: list[dict[str, Any]], stadiums: dict[str, Any]) -> None:
    """为每场比赛计算球队旅行距离（距上一场 venue）。"""
    last_venue: dict[str, str] = {}
    for m in sorted(matches, key=lambda x: (x.get("openfootball", {}).get("date", ""), x["id"])):
        ground = m.get("venue", "")
        st = stadiums.get(ground, {})
        travel: dict[str, float] = {}
        for side in ("home", "away"):
            tk = m[side]
            prev = last_venue.get(tk)
            if prev and prev in stadiums and ground in stadiums:
                p, c = stadiums[prev], stadiums[ground]
                travel[tk] = round(
                    haversine_km(p["lat"], p["lon"], c["lat"], c["lon"]), 0
                )
            else:
                travel[tk] = 0.0
            last_venue[tk] = ground
        m["travel_km"] = travel
        m["venue_meta"] = st


def load_onside_benchmark() -> dict[str, dict[str, float]]:
    path = EXT / "onside__predictions.csv"
    if not path.exists():
        return {}
    code_map = {
        "mex": "MEX", "rsa": "RSA", "kor": "KOR", "cze": "CZE", "can": "CAN", "bih": "BIH",
        "qat": "QAT", "sui": "SUI", "bra": "BRA", "mar": "MAR", "hai": "HAI", "sco": "SCO",
        "usa": "USA", "par": "PAR", "aus": "AUS", "tur": "TUR", "ger": "GER", "cuw": "CUW",
        "civ": "CIV", "ecu": "ECU", "ned": "NED", "jpn": "JPN", "swe": "SWE", "tun": "TUN",
        "bel": "BEL", "egy": "EGY", "irn": "IRN", "nzl": "NZL", "esp": "ESP", "cpv": "CPV",
        "ksa": "KSA", "uru": "URU", "fra": "FRA", "sen": "SEN", "irq": "IRQ", "nor": "NOR",
        "arg": "ARG", "alg": "ALG", "aut": "AUT", "jor": "JOR", "por": "POR", "cod": "COD",
        "uzb": "UZB", "col": "COL", "eng": "ENG", "cro": "CRO", "gha": "GHA", "pan": "PAN",
    }
    out: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            hc = (row.get("home_code") or "").lower()
            ac = (row.get("away_code") or "").lower()
            hk, ak = code_map.get(hc), code_map.get(ac)
            if not hk or not ak:
                hk = team_key(row.get("home_name", ""))
                ak = team_key(row.get("away_name", ""))
            key = f"{hk}_{ak}"
            try:
                out[key] = {
                    "prob_home": float(row.get("model_home_pct") or 0),
                    "prob_draw": float(row.get("model_draw_pct") or 0),
                    "prob_away": float(row.get("model_away_pct") or 0),
                    "verdict": row.get("verdict", ""),
                    "source": "onsidearena.com",
                }
            except (TypeError, ValueError):
                continue
    return out


def build_db() -> dict[str, Any]:
    wc = load_worldcup_json()
    cup_2026 = OF_DIR / "2026--usa" / "cup.txt"
    groups_raw = parse_groups_internal(cup_2026.read_text(encoding="utf-8")) if cup_2026.exists() else {}
    stadiums = load_stadiums()

    seed = build_seed()
    hist = history_cup_files()
    elo_map = build_elo_ratings(hist, seed)
    h2h = build_h2h_from_history(hist)

    squads = load_squads()
    per90 = load_per90()
    player_agg = aggregate_by_team(squads, per90) if squads else {}
    players_by_team = build_players_by_team(squads, per90) if squads else {}

    teams: dict[str, Any] = {}
    for key, base in seed.items():
        teams[key] = merge_team(base, player_agg.get(key, {}), elo_map.get(key, base["elo"]))

    matches: list[dict[str, Any]] = []
    for i, m in enumerate(wc.get("matches", []), start=1):
        internal = json_match_to_internal(m, i)
        if internal:
            matches.append(internal)
    attach_travel(matches, stadiums)
    standings = compute_standings(matches, groups_raw)
    onside = load_onside_benchmark()

    return {
        "meta": {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "tournament": "World Cup 2026",
            "sources": [
                "https://github.com/openfootball/worldcup",
                "https://github.com/openfootball/worldcup.json",
                "https://github.com/openfootball/awesome-football",
                "https://github.com/risingtransfers/world-cup-2026-data",
                "https://onsidearena.com/data",
                "local/stadiums_2026.json",
            ],
            "teams_count": len(teams),
            "matches_count": len(matches),
            "squads_players": len(squads),
            "h2h_pairs": len(h2h),
            "onside_benchmarks": len(onside),
            "history_tournaments": [p.parent.name for p in hist],
        },
        "groups": groups_raw,
        "stadiums": stadiums,
        "teams": teams,
        "matches": matches,
        "standings": standings,
        "h2h": h2h,
        "elo_ratings": elo_map,
        "benchmarks": {"onside": onside},
        "players_by_team": players_by_team,
    }


def main() -> None:
    db = build_db()
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    m = db["meta"]
    print(f"已构建 {DB_PATH}")
    print(f"  球队 {m['teams_count']} · 比赛 {m['matches_count']} · 球员 {m['squads_players']} · H2H {m['h2h_pairs']}")


if __name__ == "__main__":
    main()
