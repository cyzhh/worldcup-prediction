#!/usr/bin/env python3
"""2026 世界杯小组赛量化预测引擎 — 七维因子融合 + 概率化输出。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_config import ModelConfig, elo_gap_bucket, load_config

# 七大维度基准权重（文档 3.1–3.7）
DIM_WEIGHTS = {
    "fundamental": 0.35,
    "form": 0.25,
    "tactical": 0.15,
    "squad": 0.10,
    "environment": 0.10,
    "motivation": 0.05,
    "risk": 0.0,  # 浮动，运行时按数据赋值
}

# 小组赛历史统计校准（默认值，可被 model_calibration.json 覆盖）
GROUP_STAGE_DRAW_BASE = 0.22
GROUP_STAGE_ROUND1_DRAW_BOOST = 0.04
UNDER_25_BASE = 0.55


def _cfg(config: ModelConfig | None = None) -> ModelConfig:
    return config or load_config()


@dataclass
class TeamSnapshot:
    key: str
    code: str
    name: str
    raw: dict[str, Any]


@dataclass
class DimensionScore:
    name: str
    home: float
    away: float
    weight: float
    detail: str = ""


@dataclass
class PredictionResult:
    match_id: int
    title: str
    subtitle: str
    home: TeamSnapshot
    away: TeamSnapshot
    score_home: int
    score_away: int
    prob_home: float
    prob_draw: float
    prob_away: float
    prob_under_25: float
    asian_handicap: str
    played: bool = False
    actual_score: dict[str, int] | None = None
    group: str = ""
    openfootball: dict[str, Any] = field(default_factory=dict)
    benchmark: dict[str, Any] = field(default_factory=dict)
    travel_km: dict[str, float] = field(default_factory=dict)
    dimensions: list[DimensionScore] = field(default_factory=list)
    analysis: list[str] = field(default_factory=list)
    score_probs: list[dict[str, Any]] = field(default_factory=list)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _normalize_rank(rank: int, max_rank: int = 210) -> float:
    """FIFA 排名越小越强，映射到 0–1。"""
    return _clamp(1.0 - (rank - 1) / max_rank)


def _normalize_elo(elo: float, min_elo: float = 1200, max_elo: float = 2200) -> float:
    return _clamp((elo - min_elo) / (max_elo - min_elo))


def _form_score(form: dict[str, Any]) -> float:
    total = form["wins"] + form["draws"] + form["losses"]
    if total == 0:
        return 0.5
    win_pts = form["wins"] * 3 + form["draws"]
    base = win_pts / (total * 3)
    xg = form.get("xg_diff", 0)
    xg_adj = _clamp(0.5 + xg * 0.15)
    return _clamp(base * 0.6 + xg_adj * 0.4)


def score_fundamental(team: dict[str, Any]) -> float:
    rank_s = _normalize_rank(team["fifa_rank"])
    elo_s = _normalize_elo(team["elo"])
    opta_s = team["opta_index"] / 100.0
    value_s = _clamp(team["squad_value_m"] / 300.0)
    wc_exp = _clamp(team["wc_appearances"] / 20.0)
    qual = team["qualifier_win_rate"]
    return rank_s * 0.22 + elo_s * 0.28 + opta_s * 0.22 + value_s * 0.12 + wc_exp * 0.08 + qual * 0.08


def score_form(team: dict[str, Any]) -> float:
    return _form_score(team["form"])


def score_tactical(home: dict[str, Any], away: dict[str, Any], h2h: dict[str, Any] | None) -> tuple[float, float]:
    """战术对抗：效率差 + 风格克制（传控 vs 密集防守等）。"""
    h_eff = home["tactics"]["efficiency"]
    a_eff = away["tactics"]["efficiency"]
    h_style = home["tactics"]["style"]
    a_style = away["tactics"]["style"]

    h_bonus, a_bonus = 0.0, 0.0
    if "密集防守" in a_style and ("传控" in h_style or "渗透" in h_style):
        h_bonus += 0.08
    if "密集防守" in h_style and ("快速" in a_style or "反击" in a_style):
        a_bonus += 0.06
    if "高位" in h_style and "密集防守" in a_style:
        h_bonus += 0.04

    if h2h:
        h_bonus += h2h.get("home_edge", 0)

    h = _clamp(0.5 + (h_eff - a_eff) * 0.5 + h_bonus)
    a = _clamp(0.5 + (a_eff - h_eff) * 0.5 + a_bonus)
    return h, a


def score_squad(team: dict[str, Any]) -> float:
    sq = team["squad"]
    injury_penalty = sq["injury_risk"] * 0.25
    return _clamp(sq["depth_score"] - injury_penalty)


def score_environment(
    team: dict[str, Any],
    is_home: bool,
    venue_altitude: int = 0,
    travel_km: float = 0.0,
) -> float:
    base = team["environment"]["climate_adapt"]
    if is_home and team["environment"].get("is_host"):
        base += 0.18
    elif is_home:
        base += 0.08
    if venue_altitude >= 2000 and team["environment"].get("altitude_m", 0) >= 1500:
        base += 0.06
    if travel_km > 2000:
        base -= 0.08
    elif travel_km > 1000:
        base -= 0.04
    return _clamp(base)


def score_motivation(
    round_num: int,
    is_home: bool,
    strength_gap: float,
    ctx: dict[str, Any] | None = None,
) -> float:
    """小组赛战意：首轮偏保守；二三轮结合积分榜形势。"""
    base = 0.5
    if round_num == 1:
        base += 0.05 if is_home and strength_gap > 0.12 else 0.0
        base -= 0.03 if not is_home and strength_gap < -0.05 else 0.0
    if ctx:
        if ctx.get("need_win"):
            base += 0.12
        if ctx.get("need_draw"):
            base -= 0.06
        if ctx.get("need_gd"):
            base += 0.04
        if ctx.get("qualification_zone") == "direct" and ctx.get("pts", 0) >= 6:
            base -= 0.08
    return _clamp(base)


def score_risk(team: dict[str, Any]) -> float:
    return _clamp(1.0 - team["squad"]["injury_risk"] * 0.6)


def dixon_coles_tau(i: int, j: int, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles 低比分修正因子（0-0 / 1-0 / 0-1 / 1-1）。"""
    if i == 0 and j == 0:
        return 1.0 - lam_h * lam_a * rho
    if i == 0 and j == 1:
        return 1.0 + lam_a * rho
    if i == 1 and j == 0:
        return 1.0 + lam_h * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def apply_player_calibration(
    p_h: float,
    p_d: float,
    p_a: float,
    home: dict[str, Any],
    away: dict[str, Any],
    config: ModelConfig,
) -> tuple[float, float, float]:
    """球员阵容深度差 → 胜平负二次微调（报告 3.4.2）。"""
    sq_h = home["squad"].get("depth_score", 0.5)
    sq_a = away["squad"].get("depth_score", 0.5)
    delta = (sq_h - sq_a) * config.player_prob_weight
    if abs(delta) < 0.005:
        return p_h, p_d, p_a
    p_h = p_h + delta * 0.65
    p_a = p_a - delta * 0.65
    p_d = p_d - abs(delta) * 0.08
    t = p_h + p_d + p_a
    return p_h / t, p_d / t, p_a / t


def _round_dimension_weights(round_num: int, w: dict[str, float]) -> dict[str, float]:
    """按小组赛轮次动态调整七维权重（报告 3.1.2）。"""
    out = dict(w)
    if round_num == 1:
        out["form"] *= 0.85
        out["tactical"] *= 0.90
        out["fundamental"] *= 1.08
        out["squad"] *= 1.10
    elif round_num == 2:
        out["form"] *= 1.12
        out["tactical"] *= 1.08
        out["motivation"] *= 1.15
    elif round_num >= 3:
        out["form"] *= 1.15
        out["tactical"] *= 1.12
        out["motivation"] *= 1.25
        out["fundamental"] *= 0.92
    return out


def _renormalize_weights(w: dict[str, float]) -> dict[str, float]:
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def elo_win_prob(
    elo_home: float,
    elo_away: float,
    draw_factor: float = 0.0,
    config: ModelConfig | None = None,
) -> tuple[float, float, float]:
    """ELO 胜平负概率（含小组赛平局校准）。"""
    cfg = _cfg(config)
    diff = elo_home - elo_away
    p_home_raw = 1.0 / (1.0 + 10 ** (-diff / 400))
    p_away_raw = 1.0 - p_home_raw

    draw_base = cfg.group_stage_draw_base + cfg.group_stage_round1_draw_boost
    draw_base += draw_factor
    draw_base = _clamp(draw_base, 0.12, 0.32)

    gap = abs(diff)
    if gap > 200:
        draw_base *= 0.82
    elif gap < 80:
        draw_base *= 1.15

    if gap > cfg.upset_elo_threshold:
        draw_base -= cfg.favorite_draw_penalty

    remain = 1.0 - draw_base
    p_home = remain * p_home_raw
    p_away = remain * p_away_raw

    # 极端强弱对话保留弱队爆冷区间（约 5–10%）
    if diff > 250:
        p_away = max(p_away, 0.07)
        p_home = 1.0 - draw_base - p_away
    elif diff > 180:
        p_away = max(p_away, 0.05)

    total = p_home + draw_base + p_away
    return p_home / total, draw_base / total, p_away / total


def wdl_from_score_matrix(scores: list[tuple[int, int, float]]) -> tuple[float, float, float]:
    h = d = a = 0.0
    for i, j, p in scores:
        if i > j:
            h += p
        elif i == j:
            d += p
        else:
            a += p
    t = h + d + a or 1.0
    return h / t, d / t, a / t


def blend_wdl(
    elo_wdl: tuple[float, float, float],
    poisson_wdl: tuple[float, float, float],
    elo_weight: float = 0.62,
    config: ModelConfig | None = None,
    elo_diff: float = 0.0,
) -> tuple[float, float, float]:
    cfg = _cfg(config)
    w = elo_weight
    h = elo_wdl[0] * w + poisson_wdl[0] * (1 - w)
    d = elo_wdl[1] * w + poisson_wdl[1] * (1 - w)
    a = elo_wdl[2] * w + poisson_wdl[2] * (1 - w)
    t = h + d + a
    h, d, a = h / t, d / t, a / t

    if cfg.wdl_priors_by_elo_gap and cfg.historical_shrinkage > 0:
        h, d, a = apply_historical_shrinkage(h, d, a, elo_diff, cfg)

    return h, d, a


def apply_historical_shrinkage(
    p_h: float,
    p_d: float,
    p_a: float,
    elo_diff: float,
    config: ModelConfig,
) -> tuple[float, float, float]:
    """将模型输出向历史 ELO 分桶胜平负先验收缩，降低系统性偏差。"""
    bucket = elo_gap_bucket(elo_diff)
    prior = config.wdl_priors_by_elo_gap.get(bucket)
    if not prior:
        return p_h, p_d, p_a

    sh = config.historical_shrinkage
    h = p_h * (1 - sh) + prior["home"] * sh
    d = p_d * (1 - sh) + prior["draw"] * sh
    a = p_a * (1 - sh) + prior["away"] * sh
    t = h + d + a
    return h / t, d / t, a / t


def apply_upset_adjustment(
    p_h: float,
    p_d: float,
    p_a: float,
    elo_home: float,
    elo_away: float,
    config: ModelConfig,
) -> tuple[float, float, float]:
    """强队 ELO 显著领先时，向弱队注入小组赛冷门先验。"""
    diff = elo_home - elo_away
    if diff <= config.upset_elo_threshold:
        return p_h, p_d, p_a
    boost = config.upset_prob_boost * min(1.0, (diff - config.upset_elo_threshold) / 150)
    p_a = min(p_a + boost, 0.35)
    p_h = max(p_h - boost * 0.65, 0.25)
    p_d = max(p_d - boost * 0.35, 0.12)
    t = p_h + p_d + p_a
    return p_h / t, p_d / t, p_a / t


def pick_display_score(
    p_h: float,
    p_d: float,
    p_a: float,
    scores: list[tuple[int, int, float]],
    strength_diff: float,
) -> tuple[int, int]:
    """从比分矩阵中选取最符合小组赛场景的代表比分。"""
    # 势均力敌 / 高平局概率 → 优先 1:1
    if p_d >= 0.28 and abs(p_h - p_a) < 0.35:
        for s in scores:
            if s[0] == 1 and s[1] == 1:
                return 1, 1

    # 主队明显优势 → 优先 2:0 / 2:1 类净胜球比分
    if p_h >= 0.55 and strength_diff > 0.12:
        for s in scores:
            if s[0] == 2 and s[1] == 0 and s[2] >= 0.12:
                return 2, 0
        for s in scores:
            if s[0] > s[1]:
                return s[0], s[1]

    # 主队小幅领先
    if p_h >= 0.42 and p_h > p_a:
        for s in scores:
            if s[0] == 1 and s[1] == 0:
                return 1, 0

    best = scores[0]
    return best[0], best[1]


def composite_strength(
    home: dict[str, Any],
    away: dict[str, Any],
    round_num: int,
    h2h: dict[str, Any] | None,
    venue_altitude: int,
    travel: dict[str, float] | None = None,
    motivation: dict[str, dict[str, Any]] | None = None,
    home_key: str = "",
    away_key: str = "",
) -> tuple[float, list[DimensionScore]]:
    """七维融合 → 综合实力差（home - away）。"""
    travel = travel or {}
    motivation = motivation or {}
    fund_h, fund_a = score_fundamental(home), score_fundamental(away)
    form_h, form_a = score_form(home), score_form(away)
    tac_h, tac_a = score_tactical(home, away, h2h)
    sq_h, sq_a = score_squad(home), score_squad(away)
    env_h = score_environment(home, True, venue_altitude, travel.get(home_key, 0.0))
    env_a = score_environment(away, False, venue_altitude, travel.get(away_key, 0.0))
    gap = fund_h - fund_a
    mot_h = score_motivation(round_num, True, gap, motivation.get(home_key))
    mot_a = score_motivation(round_num, False, -gap, motivation.get(away_key))
    risk_h, risk_a = score_risk(home), score_risk(away)

    strength_gap_pct = abs(gap)
    w = dict(DIM_WEIGHTS)
    w = _round_dimension_weights(round_num, w)
    if strength_gap_pct < 0.10:
        w["tactical"] = max(w["tactical"], 0.25)
        w["fundamental"] = min(w["fundamental"], 0.30)

    risk_w = 0.05 + (home["squad"]["injury_risk"] + away["squad"]["injury_risk"]) * 0.08
    w["risk"] = min(risk_w, 0.12)
    scale = 1.0 - w["risk"]
    for k in ("fundamental", "form", "tactical", "squad", "environment", "motivation"):
        w[k] *= scale
    w = _renormalize_weights(w)

    dims = [
        DimensionScore("基本面实力", fund_h, fund_a, w["fundamental"]),
        DimensionScore("近期状态", form_h, form_a, w["form"]),
        DimensionScore("战术风格", tac_h, tac_a, w["tactical"]),
        DimensionScore("阵容深度", sq_h, sq_a, w["squad"]),
        DimensionScore("比赛环境", env_h, env_a, w["environment"]),
        DimensionScore("小组赛战意", mot_h, mot_a, w["motivation"]),
        DimensionScore("临场风险", risk_h, risk_a, w["risk"]),
    ]

    home_total = sum(d.home * d.weight for d in dims)
    away_total = sum(d.away * d.weight for d in dims)
    return home_total - away_total, dims


def expected_goals(strength_diff: float, home: dict[str, Any], away: dict[str, Any], round_num: int) -> tuple[float, float]:
    """泊松模型期望进球。"""
    base_total = 2.45 if round_num == 1 else 2.6
    base_total -= GROUP_STAGE_ROUND1_DRAW_BOOST * 0.5  # 首轮略低

    h_attack = home["form"]["goals_for"] * 0.4 + _normalize_elo(home["elo"]) * 1.8
    a_attack = away["form"]["goals_for"] * 0.4 + _normalize_elo(away["elo"]) * 1.8
    h_def = home["form"]["goals_against"]
    a_def = away["form"]["goals_against"]

    lam_home = _clamp(h_attack * 0.35 + (2.0 - a_def) * 0.25 + strength_diff * 2.5, 0.3, 3.2)
    lam_away = _clamp(a_attack * 0.35 + (2.0 - h_def) * 0.25 - strength_diff * 2.5, 0.2, 2.5)

    if round_num == 1:
        lam_home *= 0.95
        lam_away *= 0.92

    return lam_home, lam_away


def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def score_distribution(
    lam_h: float,
    lam_a: float,
    max_goals: int = 5,
    rho: float = -0.08,
) -> list[tuple[int, int, float]]:
    raw: list[tuple[int, int, float]] = []
    total = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a) * dixon_coles_tau(i, j, lam_h, lam_a, rho)
            raw.append((i, j, p))
            total += p
    if total <= 0:
        raw = []
        total = 0.0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a)
                raw.append((i, j, p))
                total += p
        scores = [(i, j, p / total) for i, j, p in raw]
        scores.sort(key=lambda x: x[2], reverse=True)
        return scores
    scores = [(i, j, p / total) for i, j, p in raw]
    scores.sort(key=lambda x: x[2], reverse=True)
    return scores


def prob_under_25(lam_h: float, lam_a: float, strength_diff: float = 0.0, config: ModelConfig | None = None) -> float:
    cfg = _cfg(config)
    under = 0.0
    for i in range(6):
        for j in range(6):
            if i + j < 2.5:
                under += poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a)
    blend = cfg.under_25_base * 0.18 + under * 0.82
    if abs(strength_diff) < 0.08:
        blend += 0.03
    if strength_diff > 0.15:
        blend -= 0.04
    return _clamp(blend, 0.48, 0.72)


def asian_handicap_line(strength_diff: float, home_name: str) -> str:
    if strength_diff > 0.18:
        line = -1.5
    elif strength_diff > 0.10:
        line = -1.0
    elif strength_diff > 0.04:
        line = -0.5
    elif strength_diff > -0.04:
        line = 0.0
    elif strength_diff > -0.10:
        line = 0.5
    else:
        line = 1.0
    if line == 0.0:
        return "亚盘: 平手"
    sign = "-" if line < 0 else "+"
    return f"亚盘: {home_name}{sign}{abs(line)}"


def build_analysis(
    home: dict[str, Any],
    away: dict[str, Any],
    strength_diff: float,
    dims: list[DimensionScore],
    round_num: int,
    venue: str,
    h2h: dict[str, Any] | None = None,
) -> list[str]:
    rank_gap = away["fifa_rank"] - home["fifa_rank"]
    elo_gap = home["elo"] - away["elo"]
    h_form = home["form"]
    a_form = away["form"]
    h_record = f"{h_form['wins']}胜{h_form['draws']}平{h_form['losses']}负"
    a_record = f"{a_form['wins']}胜{a_form['draws']}平{a_form['losses']}负"

    lines = [
        f"FIFA排名差距 {abs(rank_gap)} 位（{home['name']} #{home['fifa_rank']} vs {away['name']} #{away['fifa_rank']}），"
        f"纸面实力{'主队显著占优' if rank_gap > 25 else '接近' if abs(rank_gap) < 15 else '主队略优'}。",
        f"ELO 分差 {elo_gap} 分，对应历史胜率约 {int(_clamp(50 + elo_gap / 8, 35, 85))}%。",
        f"世界杯参赛经验：{home['name']} {home['wc_appearances']} 次 vs {away['name']} {away['wc_appearances']} 次。",
        f"近10场战绩 {home['name']} {h_record}，{away['name']} {a_record}；xG差 {h_form.get('xg_diff', 0):+.1f} vs {a_form.get('xg_diff', 0):+.1f}。",
    ]

    if home["environment"].get("is_host"):
        lines.append(f"主场优势：{home['name']} 联合东道主，{venue} 作战，高原/主场效应显著。")
    else:
        lines.append(f"比赛环境：{venue}，气候适应度 {home['name']} {home['environment']['climate_adapt']:.0%} vs {away['name']} {away['environment']['climate_adapt']:.0%}。")

    keys_h = "、".join(home["squad"]["key_players"][:3]) or "整体阵容"
    lines.append(f"阵容深度：{home['name']} {keys_h}；伤病风险 {home['squad']['injury_risk']:.0%} vs {away['squad']['injury_risk']:.0%}。")

    tac = next(d for d in dims if d.name == "战术风格")
    lines.append(
        f"战术对抗：{home['name']}（{home['tactics']['style']}）vs {away['name']}（{away['tactics']['style']}），"
        f"战术维度主队得分 {tac.home:.2f}、客队 {tac.away:.2f}。"
    )

    if h2h and h2h.get("history"):
        lines.append(f"历史交锋（openfootball）：{'；'.join(h2h['history'])}。")

    if round_num == 1:
        lines.append("小组赛首轮：各队战术偏保守，平局概率高于赛季均值；强队倾向控分而非大胜。")

    return lines


def build_analysis_extended(
    home: dict[str, Any],
    away: dict[str, Any],
    strength_diff: float,
    dims: list[DimensionScore],
    round_num: int,
    venue: str,
    h2h: dict[str, Any] | None = None,
    travel: dict[str, float] | None = None,
    motivation: dict[str, dict] | None = None,
    home_key: str = "",
    away_key: str = "",
) -> list[str]:
    lines = build_analysis(home, away, strength_diff, dims, round_num, venue, h2h)
    if travel:
        th, ta = travel.get(home_key, 0), travel.get(away_key, 0)
        if th or ta:
            lines.append(f"旅行成本：{home['name']} 距上场 {th:.0f} km，{away['name']} {ta:.0f} km（openfootball 赛程 + 球场坐标）。")
    if motivation and round_num > 1:
        mh, ma = motivation.get(home_key, {}), motivation.get(away_key, {})
        if mh.get("pts") is not None:
            lines.append(
                f"积分榜战意：{home['name']} {mh.get('pts',0)}分第{mh.get('rank',0)}名"
                f"{'，需抢分' if mh.get('need_win') else '，可接受平局' if mh.get('need_draw') else ''}；"
                f"{away['name']} {ma.get('pts',0)}分第{ma.get('rank',0)}名。"
            )
    return lines


def predict_match(
    match: dict[str, Any],
    teams: dict[str, Any],
    h2h_map: dict[str, dict[str, Any]] | None = None,
    benchmarks: dict[str, dict[str, Any]] | None = None,
    config: ModelConfig | None = None,
) -> PredictionResult:
    cfg = _cfg(config)
    home = teams[match["home"]]
    away = teams[match["away"]]
    h2h = (h2h_map or {}).get(f"{match['home']}_{match['away']}")
    if not h2h:
        rev = (h2h_map or {}).get(f"{match['away']}_{match['home']}")
        if rev:
            h2h = {**rev, "home_edge": -rev.get("home_edge", 0), "reversed": True}

    venue_altitude = match.get("venue_altitude_m", 0)
    if venue_altitude == 0 and "Mexico City" in match.get("venue", ""):
        venue_altitude = 2240
    strength_diff, dims = composite_strength(
        home,
        away,
        match["round"],
        h2h,
        venue_altitude,
        travel=match.get("travel_km"),
        motivation=match.get("motivation"),
        home_key=match["home"],
        away_key=match["away"],
    )

    adj_elo_h = home["elo"] + strength_diff * 400
    adj_elo_a = away["elo"] - strength_diff * 400
    if home["environment"].get("is_host"):
        adj_elo_h += cfg.host_elo_bonus
    draw_factor = 0.02 if abs(strength_diff) < 0.08 else -0.01 if abs(strength_diff) > 0.15 else 0.0
    if match["round"] == 1:
        draw_factor += cfg.group_stage_round1_draw_boost * 0.5
    elo_wdl = elo_win_prob(adj_elo_h, adj_elo_a, draw_factor, config=cfg)

    lam_h, lam_a = expected_goals(strength_diff, home, away, match["round"])
    scores = score_distribution(lam_h, lam_a, rho=cfg.dixon_coles_rho)
    poisson_wdl = wdl_from_score_matrix(scores)
    elo_w = cfg.elo_blend_strong if abs(strength_diff) > 0.12 else cfg.elo_blend_close
    p_h, p_d, p_a = blend_wdl(elo_wdl, poisson_wdl, elo_weight=elo_w, config=cfg, elo_diff=adj_elo_h - adj_elo_a)
    p_h, p_d, p_a = apply_upset_adjustment(p_h, p_d, p_a, adj_elo_h, adj_elo_a, cfg)
    p_h, p_d, p_a = apply_player_calibration(p_h, p_d, p_a, home, away, cfg)

    score_h, score_a = pick_display_score(p_h, p_d, p_a, scores, strength_diff)
    under25 = prob_under_25(lam_h, lam_a, strength_diff, config=cfg)
    handicap = asian_handicap_line(strength_diff, home["name"])
    analysis = build_analysis_extended(
        home, away, strength_diff, dims, match["round"], match.get("venue", ""), h2h,
        travel=match.get("travel_km"), motivation=match.get("motivation"),
        home_key=match["home"], away_key=match["away"],
    )

    top_scores = [
        {"home": s[0], "away": s[1], "prob": round(s[2] * 100, 1)}
        for s in scores[:5]
    ]

    bench_key = f"{match['home']}_{match['away']}"
    onside = (benchmarks or {}).get("onside", {}).get(bench_key, {})

    return PredictionResult(
        match_id=match["id"],
        title=match.get("title", f"{home['name']} vs {away['name']}"),
        subtitle=match.get("subtitle", ""),
        home=TeamSnapshot(match["home"], home["code"], home["name"], home),
        away=TeamSnapshot(match["away"], away["code"], away["name"], away),
        score_home=score_h,
        score_away=score_a,
        prob_home=round(p_h * 100, 1),
        prob_draw=round(p_d * 100, 1),
        prob_away=round(p_a * 100, 1),
        prob_under_25=round(under25 * 100, 1),
        asian_handicap=handicap,
        played=bool(match.get("played")),
        actual_score=match.get("actual_score"),
        group=match.get("group", ""),
        openfootball=match.get("openfootball", {}),
        benchmark=onside,
        travel_km=match.get("travel_km") or {},
        dimensions=dims,
        analysis=analysis,
        score_probs=top_scores,
    )


def result_to_dict(r: PredictionResult) -> dict[str, Any]:
    d = {
        "match_id": r.match_id,
        "title": r.title,
        "subtitle": r.subtitle,
        "group": r.group,
        "played": r.played,
        "openfootball": r.openfootball,
        "home": {
            "key": r.home.key,
            "code": r.home.code,
            "name": r.home.name,
            "fifa_rank": r.home.raw["fifa_rank"],
            "elo": r.home.raw["elo"],
        },
        "away": {
            "key": r.away.key,
            "code": r.away.code,
            "name": r.away.name,
            "fifa_rank": r.away.raw["fifa_rank"],
            "elo": r.away.raw["elo"],
        },
        "predicted_score": f"{r.score_home} : {r.score_away}",
        "score_home": r.score_home,
        "score_away": r.score_away,
        "prob_home": r.prob_home,
        "prob_draw": r.prob_draw,
        "prob_away": r.prob_away,
        "prob_under_25": r.prob_under_25,
        "asian_handicap": r.asian_handicap,
        "analysis": r.analysis,
        "score_probs": r.score_probs,
        "dimensions": [
            {"name": dim.name, "home": round(dim.home, 3), "away": round(dim.away, 3), "weight": dim.weight}
            for dim in r.dimensions
        ],
    }
    if r.travel_km:
        d["travel_km"] = r.travel_km
    if r.benchmark:
        d["benchmark_onside"] = r.benchmark
    if r.actual_score:
        d["actual_score"] = f"{r.actual_score['home']} : {r.actual_score['away']}"
        d["actual_home"] = r.actual_score["home"]
        d["actual_away"] = r.actual_score["away"]
        pred = (r.score_home, r.score_away)
        act = (r.actual_score["home"], r.actual_score["away"])
        d["result_hit"] = pred == act
        d["outcome_hit"] = (
            (pred[0] > pred[1]) == (act[0] > act[1])
            or (pred[0] == pred[1] == act[0] == act[1])
        )
    return d


def run_all(
    data_dir: Path | None = None,
    *,
    group: str | None = None,
    matchday: str | None = None,
    only_unplayed: bool = False,
) -> dict[str, Any]:
    """从 openfootball 数据加载赛程并运行预测。"""
    from openfootball_loader import load_schedule

    meta, teams, bundle = load_schedule(
        group=group,
        matchday=matchday,
        only_unplayed=only_unplayed,
    )
    h2h = bundle["h2h"]
    benchmarks = bundle.get("benchmarks", {})

    predictions = []
    for m in bundle["matches"]:
        if m["home"] not in teams or m["away"] not in teams:
            continue
        pred = predict_match(m, teams, h2h, benchmarks)
        predictions.append(result_to_dict(pred))

    return {
        "meta": meta,
        "generated_by": "worldcup/predictor.py + awesome-football 多源数据库",
        "standings": bundle.get("standings", {}),
        "players_by_team": bundle.get("players_by_team", {}),
        "predictions": predictions,
    }


def main() -> None:
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    result = run_all()
    out_path = out_dir / "predictions.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"已生成 {out_path}，共 {len(result['predictions'])} 场比赛预测。")


if __name__ == "__main__":
    main()
