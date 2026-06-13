#!/usr/bin/env python3
"""从 openfootball Football.TXT 赛果文件计算 ELO 评分。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app_config import elo_config
from football_txt_parser import parse_all_results
from team_registry import NAME_TO_KEY, team_key

_elo = elo_config()
K_FACTOR = int(_elo.get("k_factor", 32))
HOME_ADV = int(_elo.get("home_adv", 65))


def parse_cup_txt_results(text: str) -> list[dict[str, Any]]:
    """解析 cup.txt 中带比分的行（兼容多种 Football.TXT 格式）。"""
    return parse_all_results(text)


def _expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))


def _update(elo: dict[str, float], team: str, delta: float) -> None:
    elo[team] = elo.get(team, 1500.0) + delta


def build_elo_ratings(
    cup_files: list[Path],
    seed_teams: dict[str, Any],
) -> dict[str, float]:
    """按时间顺序处理多届世界杯，返回 team_key → ELO。"""
    by_name: dict[str, float] = {}
    for key, t in seed_teams.items():
        by_name[key] = float(t.get("elo", 1500))

    def resolve(name: str) -> str:
        if name in NAME_TO_KEY:
            return NAME_TO_KEY[name]
        return team_key(name)

    all_results: list[dict[str, Any]] = []
    for path in cup_files:
        if path.exists():
            all_results.extend(parse_cup_txt_results(path.read_text(encoding="utf-8")))

    elo_by_key = dict(by_name)
    for r in all_results:
        k1 = resolve(r["team1"])
        k2 = resolve(r["team2"])
        e1 = elo_by_key.get(k1, 1500.0) + HOME_ADV
        e2 = elo_by_key.get(k2, 1500.0)
        exp1 = _expected(e1, e2)
        gh, ga = r["score_home"], r["score_away"]
        if gh > ga:
            s1, s2 = 1.0, 0.0
        elif gh < ga:
            s1, s2 = 0.0, 1.0
        else:
            s1 = s2 = 0.5
        _update(elo_by_key, k1, K_FACTOR * (s1 - exp1))
        _update(elo_by_key, k2, K_FACTOR * (s2 - (1 - exp1)))

    return {k: round(v, 1) for k, v in elo_by_key.items()}
