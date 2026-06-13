#!/usr/bin/env python3
"""基于历史赛果构建回测用球队快照（仅使用赛前可得信息）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from build_teams_seed import _form_for_tier, _tactics_for_tier
from elo_history import build_elo_ratings, parse_cup_txt_results
from team_registry import team_key

ROOT = Path(__file__).parent
OF_DIR = ROOT / "data" / "openfootball"


def _elo_to_tier(elo: float) -> int:
    if elo >= 1900:
        return 1
    if elo >= 1750:
        return 2
    if elo >= 1600:
        return 3
    if elo >= 1450:
        return 4
    return 5


def _collect_prior_results(cup_files: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(cup_files):
        for r in parse_cup_txt_results(path.read_text(encoding="utf-8")):
            rows.append({**r, "file_idx": idx})
    return rows


def _form_from_history(team_key_str: str, prior_results: list[dict[str, Any]], window: int = 10) -> dict[str, Any]:
    """从赛前历史赛果估算近态（指数衰减加权，越近权重越高）。"""
    decay = 0.88
    wins = draws = losses = 0.0
    gf = ga = 0.0
    weight_sum = 0.0
    count = 0

    for r in reversed(prior_results):
        k1, k2 = team_key(r["team1"]), team_key(r["team2"])
        if k1 != team_key_str and k2 != team_key_str:
            continue
        gh, ga_sc = r["score_home"], r["score_away"]
        w = decay ** count
        if k1 == team_key_str:
            tg, og = gh, ga_sc
            if gh > ga_sc:
                wins += w
            elif gh < ga_sc:
                losses += w
            else:
                draws += w
        else:
            tg, og = ga_sc, gh
            if ga_sc > gh:
                wins += w
            elif ga_sc < gh:
                losses += w
            else:
                draws += w
        gf += tg * w
        ga += og * w
        weight_sum += w
        count += 1
        if count >= window:
            break

    if weight_sum <= 0:
        return _form_for_tier(3)

    wdl = wins + draws + losses
    return {
        "wins": int(round(wins)),
        "draws": int(round(draws)),
        "losses": int(round(losses)),
        "goals_for": round(gf / weight_sum, 2),
        "goals_against": round(ga / weight_sum, 2),
        "xg_diff": round((gf - ga) / weight_sum * 0.85, 2),
        "ppda": 10.5,
        "home_win_rate": 0.55,
    }


def refresh_teams_form(
    teams: dict[str, dict[str, Any]],
    prior_results: list[dict[str, Any]],
    current_results: list[dict[str, Any]],
    window: int = 10,
) -> None:
    """将当届已赛结果并入 form（二、三轮预测用当届真实状态）。"""
    combined = prior_results + current_results
    for key in teams:
        teams[key]["form"] = _form_from_history(key, combined, window=window)


def build_elo_as_of(prior_cup_files: list[Path], team_keys: set[str]) -> dict[str, float]:
    seed = {k: {"elo": 1500.0} for k in team_keys}
    if not prior_cup_files:
        return {k: 1500.0 for k in team_keys}
    elo_map = build_elo_ratings(prior_cup_files, seed)
    return {k: elo_map.get(k, 1500.0) for k in team_keys}


def build_team_profiles(
    tournament: dict[str, Any],
    group_keys: dict[str, list[str]],
    prior_cup_files: list[Path],
    group_names: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """为当届参赛队构建 predictor 兼容的球队字典。"""
    all_keys: set[str] = set()
    for keys in group_keys.values():
        all_keys.update(keys)

    elo_map = build_elo_as_of(prior_cup_files, all_keys)
    prior_results = _collect_prior_results(prior_cup_files)
    hosts = tournament.get("hosts", set())

    ranked = sorted(all_keys, key=lambda k: elo_map[k], reverse=True)
    rank_of = {k: i + 1 for i, k in enumerate(ranked)}

    name_by_key: dict[str, str] = {}
    for names in (group_names or {}).values():
        for nm in names:
            name_by_key[team_key(nm)] = nm

    teams: dict[str, dict[str, Any]] = {}
    for key in all_keys:
        elo = elo_map[key]
        tier = _elo_to_tier(elo)
        rank = rank_of[key]
        display_name = name_by_key.get(key, key)
        is_host = key in hosts
        opta = int(_clamp_elo_norm(elo) * 100)
        teams[key] = {
            "code": key[:3],
            "name": display_name,
            "fifa_rank": rank,
            "elo": round(elo, 1),
            "opta_index": opta,
            "tier": tier,
            "squad_value_m": max(15, int(300 - rank * 4 + (elo - 1500) * 0.05)),
            "wc_appearances": min(22, 2 + len(prior_cup_files)),
            "wc_group_avg_pts": round(1.9 - tier * 0.22, 1),
            "qualifier_win_rate": round(0.75 - tier * 0.07 + _clamp_elo_norm(elo) * 0.1, 2),
            "qualifier_gd": max(0, 18 - rank // 2),
            "form": _form_from_history(key, prior_results),
            "tactics": _tactics_for_tier(tier),
            "squad": {
                "depth_score": round(0.88 - tier * 0.07 + _clamp_elo_norm(elo) * 0.08, 2),
                "key_players": [],
                "injury_risk": 0.07 + tier * 0.018,
            },
            "environment": {
                "is_host": is_host,
                "altitude_m": 0,
                "climate_adapt": 0.90 if is_host else 0.78 - tier * 0.015,
            },
            "data_source": "historical_backtest",
        }
    return teams


def _clamp_elo_norm(elo: float) -> float:
    return max(0.0, min(1.0, (elo - 1200) / 1000))
