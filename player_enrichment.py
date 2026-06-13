#!/usr/bin/env python3
"""从 risingtransfers 球员数据聚合球队维度因子。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from team_registry import NAME_TO_KEY, team_key

ROOT = Path(__file__).parent
EXT = ROOT / "data" / "external"


def _resolve_country(country: str, code: str) -> str:
    if country in NAME_TO_KEY:
        return NAME_TO_KEY[country]
    # ISO3 三字码映射
    iso3 = {
        "MEX": "MEX", "RSA": "RSA", "KOR": "KOR", "CZE": "CZE", "CAN": "CAN",
        "BIH": "BIH", "QAT": "QAT", "SUI": "SUI", "BRA": "BRA", "MAR": "MAR",
        "HAI": "HAI", "SCO": "SCO", "USA": "USA", "PAR": "PAR", "AUS": "AUS",
        "TUR": "TUR", "GER": "GER", "CUW": "CUW", "CIV": "CIV", "ECU": "ECU",
        "NED": "NED", "JPN": "JPN", "SWE": "SWE", "TUN": "TUN", "BEL": "BEL",
        "EGY": "EGY", "IRN": "IRN", "NZL": "NZL", "ESP": "ESP", "CPV": "CPV",
        "KSA": "KSA", "URU": "URU", "FRA": "FRA", "SEN": "SEN", "IRQ": "IRQ",
        "NOR": "NOR", "ARG": "ARG", "ALG": "ALG", "AUT": "AUT", "JOR": "JOR",
        "POR": "POR", "COD": "COD", "UZB": "UZB", "COL": "COL", "ENG": "ENG",
        "CRO": "CRO", "GHA": "GHA", "PAN": "PAN",
    }
    if code in iso3:
        return iso3[code]
    return team_key(country)


def load_squads(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or EXT / "risingtransfers__squads.csv"
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_per90(path: Path | None = None) -> dict[str, dict[str, float]]:
    p = path or EXT / "risingtransfers__per90_stats.csv"
    if not p.exists():
        return {}
    out: dict[str, dict[str, float]] = {}
    with p.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("player_id") or row.get("slug", "")
            stats: dict[str, float] = {}
            for k, v in row.items():
                if k in ("player_id", "player_name", "slug", "country", "country_code", "position", "club"):
                    continue
                try:
                    stats[k] = float(v)
                except (TypeError, ValueError):
                    pass
            if pid:
                out[str(pid)] = stats
    return out


def aggregate_by_team(squads: list[dict[str, Any]], per90: dict[str, dict[str, float]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict]] = {}
    for row in squads:
        key = _resolve_country(row.get("country", ""), row.get("country_code", ""))
        buckets.setdefault(key, []).append(row)

    result: dict[str, dict[str, Any]] = {}
    for key, players in buckets.items():
        values = []
        ages = []
        top: list[tuple[str, float]] = []
        pos_count: dict[str, int] = {}
        for p in players:
            try:
                val = float(p.get("rt_value_estimate_eur") or 0)
            except ValueError:
                val = 0.0
            values.append(val)
            try:
                ages.append(float(p.get("age") or 0))
            except ValueError:
                pass
            top.append((p.get("player_name", ""), val))
            pos = p.get("position", "MF")
            pos_count[pos] = pos_count.get(pos, 0) + 1

        top.sort(key=lambda x: x[1], reverse=True)
        squad_value_m = sum(values) / 1_000_000
        avg_age = sum(ages) / len(ages) if ages else 27.0

        # per90 聚合（进球+助攻近似进攻产出）
        goals_p90 = assists_p90 = 0.0
        n_stats = 0
        for p in players:
            pid = str(p.get("player_id", ""))
            st = per90.get(pid, {})
            if st:
                goals_p90 += st.get("goals_p90", st.get("goals_per90", 0))
                assists_p90 += st.get("assists_p90", st.get("assists_per90", 0))
                n_stats += 1
        avg_goals = goals_p90 / max(n_stats, 1)
        avg_assists = assists_p90 / max(n_stats, 1)

        depth = min(1.0, len(players) / 26) * 0.4 + min(1.0, squad_value_m / 200) * 0.6

        result[key] = {
            "squad_size": len(players),
            "squad_value_m": round(squad_value_m, 1),
            "avg_age": round(avg_age, 1),
            "key_players": [n for n, _ in top[:5] if n],
            "position_balance": pos_count,
            "squad": {
                "depth_score": round(depth, 3),
                "key_players": [n for n, _ in top[:5] if n],
                "injury_risk": round(max(0.05, 0.08 + (avg_age - 27) * 0.01), 3),
            },
            "form": {
                "goals_for": round(0.8 + avg_goals * 8, 2),
                "xg_diff": round((avg_goals + avg_assists) * 0.15 - 0.1, 2),
            },
            "data_source": "risingtransfers/world-cup-2026-data",
        }
    return result
