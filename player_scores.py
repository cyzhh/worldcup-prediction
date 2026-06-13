#!/usr/bin/env python3
"""球员综合评分（身价 + per90 产出 + 评分）。"""

from __future__ import annotations

from typing import Any

from player_enrichment import load_per90, load_squads, _resolve_country


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute_player_score(row: dict[str, Any], per90: dict[str, dict[str, float]]) -> dict[str, Any]:
    """单球员 0–100 综合分。"""
    val = _f(row.get("rt_value_estimate_eur"))
    val_score = min(100.0, (val / 40_000_000) * 100)

    pid = str(row.get("player_id", ""))
    st = per90.get(pid, {})
    rating = _f(st.get("rating"))
    goals = _f(st.get("goals_per90", st.get("goals_p90")))
    assists = _f(st.get("assists_per90", st.get("assists_p90")))
    shots = _f(st.get("shots_per90"))
    key_passes = _f(st.get("key_passes_per90"))

    form_score = min(
        100.0,
        rating * 9.0 + goals * 18.0 + assists * 12.0 + shots * 1.2 + key_passes * 0.8,
    )
    overall = val_score * 0.42 + form_score * 0.58

    return {
        "player_id": pid,
        "name": row.get("player_name", ""),
        "position": row.get("position", ""),
        "club": row.get("club", ""),
        "age": int(_f(row.get("age"), 0)) or None,
        "value_m": round(val / 1_000_000, 2),
        "rating": round(rating, 2) if rating else None,
        "goals_p90": round(goals, 3),
        "assists_p90": round(assists, 3),
        "score": round(overall, 1),
    }


def build_players_by_team(
    squads: list[dict[str, Any]] | None = None,
    per90: dict[str, dict[str, float]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    squads = squads if squads is not None else load_squads()
    per90 = per90 if per90 is not None else load_per90()
    buckets: dict[str, list[dict[str, Any]]] = {}

    for row in squads:
        key = _resolve_country(row.get("country", ""), row.get("country_code", ""))
        scored = compute_player_score(row, per90)
        if scored["name"]:
            buckets.setdefault(key, []).append(scored)

    for key in buckets:
        buckets[key].sort(key=lambda x: x["score"], reverse=True)
    return buckets
