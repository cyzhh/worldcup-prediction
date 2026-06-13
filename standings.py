#!/usr/bin/env python3
"""根据 openfootball 赛果计算小组积分榜与晋级形势。"""

from __future__ import annotations

from typing import Any


def _empty(team: str) -> dict[str, Any]:
    return {"team": team, "played": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0, "pts": 0}


def compute_standings(matches: list[dict[str, Any]], groups: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    """groups: { 'A': ['MEX', 'RSA', ...], ... } keys 为内部 team key。"""
    tables: dict[str, dict[str, dict]] = {}
    for g, teams in groups.items():
        tables[g] = {t: _empty(t) for t in teams}

    for m in matches:
        if not m.get("played"):
            continue
        g = m.get("group")
        if not g or g not in tables:
            continue
        h, a = m["home"], m["away"]
        if h not in tables[g] or a not in tables[g]:
            continue
        gh = m["actual_score"]["home"]
        ga = m["actual_score"]["away"]
        for side, gf, gc, win, draw, loss in (
            (h, gh, ga, gh > ga, gh == ga, gh < ga),
            (a, ga, gh, ga > gh, ga == gh, ga < gh),
        ):
            row = tables[g][side]
            row["played"] += 1
            row["gf"] += gf
            row["ga"] += gc
            row["gd"] = row["gf"] - row["ga"]
            if win:
                row["w"] += 1
                row["pts"] += 3
            elif draw:
                row["d"] += 1
                row["pts"] += 1
            else:
                row["l"] += 1

    out: dict[str, list[dict[str, Any]]] = {}
    for g, team_rows in tables.items():
        ranked = sorted(
            team_rows.values(),
            key=lambda r: (r["pts"], r["gd"], r["gf"]),
            reverse=True,
        )
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
            r["qualification_zone"] = "direct" if i <= 2 else ("best_third" if i == 3 else "out")
        out[g] = ranked
    return out


def motivation_context(team: str, group: str, standings: dict[str, list[dict]], round_num: int) -> dict[str, Any]:
    """小组赛战意上下文（维度六）。"""
    rows = standings.get(group, [])
    row = next((r for r in rows if r["team"] == team), None)
    if not row or round_num == 1:
        return {"need_win": False, "need_draw": False, "need_gd": False, "pts": 0, "rank": 0}
    pts, rank, gd = row["pts"], row["rank"], row["gd"]
    remaining = 3 - row["played"]
    return {
        "pts": pts,
        "rank": rank,
        "gd": gd,
        "remaining": remaining,
        "need_win": rank >= 3 and remaining <= 1 and pts < 4,
        "need_draw": rank <= 2 and pts >= 4 and remaining >= 1,
        "need_gd": rank == 3 and gd < 0,
        "qualification_zone": row.get("qualification_zone", "out"),
    }
