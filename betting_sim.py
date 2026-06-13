#!/usr/bin/env python3
"""虚拟分级投注：三档信号 + 精选 15 场 / 2000 元预算。"""

from __future__ import annotations

import re
from typing import Any

from app_config import betting_config
from model_config import ModelConfig, load_config
from predictor import elo_win_prob

_bet = betting_config()
STAKE = float(_bet.get("stake_per_bet", 50.0))
BANKROLL_START = float(_bet.get("bankroll_per_tournament", 2000.0))
BOOK_MARGIN = float(_bet.get("book_margin", 0.07))
RESERVE = float(_bet.get("reserve", 200.0))
_TIERED = dict(_bet.get("tiered") or {})
_TYPICAL = dict(_bet.get("typical_odds") or {})


def _tier_cfg() -> dict[str, Any]:
    return {
        "strong_strength": float(_TIERED.get("strong_strength", 0.12)),
        "medium_strength": float(_TIERED.get("medium_strength", 0.06)),
        "ou_min_strong": float(_TIERED.get("ou_min_strong", 0.60)),
        "ou_min_medium": float(_TIERED.get("ou_min_medium", 0.55)),
        "draw_override": float(_TIERED.get("draw_override", 0.30)),
        "max_strong_matches": int(_TIERED.get("max_strong_matches", 10)),
        "max_medium_matches": int(_TIERED.get("max_medium_matches", 5)),
        "skip_weak_1x2": bool(_TIERED.get("skip_weak_1x2", True)),
    }


def _actual_outcome(h: int, a: int) -> str:
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def _pred_outcome(p_h: float, p_d: float, p_a: float) -> str:
    probs = {"home": p_h, "draw": p_d, "away": p_a}
    return max(probs, key=probs.get)


def _strength_diff(pred: dict[str, Any]) -> float:
    if pred.get("strength_diff") is not None:
        return float(pred["strength_diff"])
    elo_h = float(pred["home"]["elo"])
    elo_a = float(pred["away"]["elo"])
    return max(-0.35, min(0.35, (elo_h - elo_a) / 400.0))


def _asian_line(pred: dict[str, Any]) -> float:
    if pred.get("asian_line_home") is not None:
        return float(pred["asian_line_home"])
    text = pred.get("asian_handicap") or ""
    if "平手" in text:
        return 0.0
    m = re.search(r"([-+]?[\d.]+)\s*$", text)
    return float(m.group(1)) if m else 0.0


def _confidence(pred: dict[str, Any]) -> float:
    return max(float(pred["prob_home"]), float(pred["prob_draw"]), float(pred["prob_away"])) / 100.0


def classify_tier(pred: dict[str, Any], cfg: dict[str, Any] | None = None) -> str:
    tc = cfg or _tier_cfg()
    ad = abs(_strength_diff(pred))
    if ad > tc["strong_strength"]:
        return "strong"
    if ad >= tc["medium_strength"]:
        return "medium"
    return "weak"


def market_odds_from_elo(
    elo_home: float,
    elo_away: float,
    config: ModelConfig | None = None,
) -> dict[str, float]:
    cfg = config or load_config()
    p_h, p_d, p_a = elo_win_prob(elo_home, elo_away, draw_factor=0.0, config=cfg)
    odds: dict[str, float] = {}
    for key, p in (("home", p_h), ("draw", p_d), ("away", p_a)):
        p = max(p, 0.02)
        odds[key] = round((1.0 / p) * (1.0 - BOOK_MARGIN), 2)
    return odds


def market_odds_from_probs(prob_home: float, prob_draw: float, prob_away: float) -> dict[str, float]:
    odds: dict[str, float] = {}
    for key, pct in (("home", prob_home), ("draw", prob_draw), ("away", prob_away)):
        p = max(float(pct) / 100.0, 0.02)
        odds[key] = round((1.0 / p) * (1.0 - BOOK_MARGIN), 2)
    return odds


def _pick_odds_for_prediction(pred: dict[str, Any], config: ModelConfig | None = None) -> dict[str, float]:
    bench = pred.get("benchmark_onside") or {}
    if bench.get("prob_home") is not None:
        return market_odds_from_probs(bench["prob_home"], bench["prob_draw"], bench["prob_away"])
    return market_odds_from_elo(pred["home"]["elo"], pred["away"]["elo"], config)


def _typical_odds(kind: str, tier: str) -> float:
    if kind == "1x2":
        return float(_TYPICAL.get("wdl_strong" if tier == "strong" else "wdl_medium", 1.65))
    if kind == "asian":
        return float(_TYPICAL.get("asian", 1.9))
    return float(_TYPICAL.get("over_under", 1.85))


def settle_asian(home_goals: int, away_goals: int, line_home: float) -> str:
    """主队受让 line_home，返回 win / lose / push。"""
    v = home_goals + line_home - away_goals
    if line_home == int(line_home):
        if v > 0:
            return "win"
        if v == 0:
            return "push"
        return "lose"
    if v > 0:
        return "win"
    return "lose"


def settle_over_under(home_goals: int, away_goals: int, pick: str) -> bool:
    total = home_goals + away_goals
    if pick == "under":
        return total < 2.5
    return total > 2.5


def _wdl_pick(pred: dict[str, Any], tier: str, tc: dict[str, Any]) -> str:
    ph = float(pred["prob_home"]) / 100.0
    pd = float(pred["prob_draw"]) / 100.0
    pa = float(pred["prob_away"]) / 100.0
    if tier == "medium" and pd >= tc["draw_override"]:
        return "draw"
    return _pred_outcome(ph, pd, pa)


def _ou_pick(pred: dict[str, Any]) -> tuple[str, float]:
    under = float(pred.get("prob_under_25", 50)) / 100.0
    over = 1.0 - under
    if over >= under:
        return "over", over
    return "under", under


def build_match_legs(pred: dict[str, Any], tier: str, tc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """按三档规则生成单场注单列表。"""
    tc = tc or _tier_cfg()
    legs: list[dict[str, Any]] = []
    stake = STAKE

    if tier == "strong":
        pick = _wdl_pick(pred, tier, tc)
        legs.append({"type": "1x2", "pick": pick, "stake": stake, "odds": _typical_odds("1x2", tier)})
        line = _asian_line(pred)
        legs.append(
            {
                "type": "asian",
                "side": "home",
                "line": line,
                "label": pred.get("asian_handicap", f"主{line:+.1f}"),
                "stake": stake,
                "odds": _typical_odds("asian", tier),
            }
        )
        ou_pick, ou_conf = _ou_pick(pred)
        if ou_conf >= tc["ou_min_strong"]:
            legs.append(
                {
                    "type": "ou",
                    "pick": ou_pick,
                    "stake": stake,
                    "odds": _typical_odds("ou", tier),
                    "confidence": round(ou_conf, 3),
                }
            )
    elif tier == "medium":
        pick = _wdl_pick(pred, tier, tc)
        legs.append({"type": "1x2", "pick": pick, "stake": stake, "odds": _typical_odds("1x2", tier)})
        ou_pick, ou_conf = _ou_pick(pred)
        if ou_conf >= tc["ou_min_medium"]:
            legs.append(
                {
                    "type": "ou",
                    "pick": ou_pick,
                    "stake": stake,
                    "odds": _typical_odds("ou", tier),
                    "confidence": round(ou_conf, 3),
                }
            )
    else:
        ou_pick, ou_conf = _ou_pick(pred)
        if ou_conf >= tc["ou_min_medium"]:
            legs.append(
                {
                    "type": "ou",
                    "pick": ou_pick,
                    "stake": stake,
                    "odds": _typical_odds("ou", tier),
                    "confidence": round(ou_conf, 3),
                }
            )
    return legs


def select_curated_matches(
    predictions: list[dict[str, Any]],
    tc: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """精选：强信号前 N + 中信号前 M（按置信度排序）。"""
    tc = tc or _tier_cfg()
    strong = [p for p in predictions if classify_tier(p, tc) == "strong"]
    medium = [p for p in predictions if classify_tier(p, tc) == "medium"]
    strong.sort(key=_confidence, reverse=True)
    medium.sort(key=_confidence, reverse=True)
    picked = strong[: tc["max_strong_matches"]] + medium[: tc["max_medium_matches"]]
    return picked


def _settle_leg(leg: dict[str, Any], pred: dict[str, Any]) -> tuple[bool | None, float]:
    """返回 (是否命中, pnl)。push 时 pnl=0, won=None 不计入命中率。"""
    stake = float(leg["stake"])
    odds = float(leg.get("odds") or 1.85)
    ah, aa = int(pred["actual_home"]), int(pred["actual_away"])

    if leg["type"] == "1x2":
        actual = _actual_outcome(ah, aa)
        won = leg["pick"] == actual
        return won, stake * (odds - 1.0) if won else -stake

    if leg["type"] == "asian":
        result = settle_asian(ah, aa, float(leg["line"]))
        if result == "push":
            return None, 0.0
        won = result == "win"
        return won, stake * (odds - 1.0) if won else -stake

    if leg["type"] == "ou":
        won = settle_over_under(ah, aa, leg["pick"])
        return won, stake * (odds - 1.0) if won else -stake

    return False, -stake


def simulate_tiered_bets(
    predictions: list[dict[str, Any]],
    *,
    bankroll_start: float = BANKROLL_START,
    label: str = "",
    config: ModelConfig | None = None,
    only_played: bool = False,
    curated: bool = True,
) -> dict[str, Any]:
    """三档分级投注模拟。"""
    _ = config or load_config()
    tc = _tier_cfg()
    budget_cap = bankroll_start - RESERVE if RESERVE else bankroll_start

    pool = [p for p in predictions if not only_played or p.get("played")]
    if curated:
        selected = select_curated_matches(pool, tc)
    else:
        selected = pool

    selected_ids = {id(p) for p in selected}
    ordered = [p for p in pool if id(p) in selected_ids]
    ordered.sort(key=lambda p: (p.get("openfootball") or {}).get("date", ""))

    bankroll = bankroll_start
    staked = profit = 0.0
    legs_total = wins = counted = 0
    tier_stats: dict[str, dict[str, Any]] = {}
    details: list[dict[str, Any]] = []

    for pred in ordered:
        tier = classify_tier(pred, tc)
        legs = build_match_legs(pred, tier, tc)
        match_stake = sum(l["stake"] for l in legs)
        if staked + match_stake > budget_cap:
            continue
        if bankroll < match_stake:
            break

        match_pnl = 0.0
        leg_results: list[dict[str, Any]] = []
        for leg in legs:
            if only_played and pred.get("played"):
                won, pnl = _settle_leg(leg, pred)
                match_pnl += pnl
                staked += leg["stake"]
                legs_total += 1
                if won is not None:
                    counted += 1
                    if won:
                        wins += 1
                leg_results.append({**leg, "won": won, "pnl": round(pnl, 2)})
            else:
                leg_results.append({**leg, "potential_win": round(leg["stake"] * (leg["odds"] - 1), 2)})

        if only_played and pred.get("played"):
            bankroll += match_pnl
            profit += match_pnl

        ts = tier_stats.setdefault(tier, {"matches": 0, "staked": 0.0, "profit": 0.0, "legs": 0})
        ts["matches"] += 1
        ts["staked"] += match_stake if (only_played and pred.get("played")) else 0
        ts["profit"] += match_pnl if (only_played and pred.get("played")) else 0
        ts["legs"] += len(legs)

        details.append(
            {
                "title": pred.get("title", ""),
                "tier": tier,
                "confidence": round(_confidence(pred) * 100, 1),
                "strength_diff": round(_strength_diff(pred), 3),
                "match_stake": match_stake,
                "match_pnl": round(match_pnl, 2) if (only_played and pred.get("played")) else None,
                "legs": leg_results,
            }
        )

    roi = (profit / staked) if staked else 0.0
    return {
        "label": label,
        "strategy": "tiered_curated" if curated else "tiered_all",
        "bankroll_start": bankroll_start,
        "budget_cap": budget_cap,
        "reserve": RESERVE,
        "stake_per_leg": STAKE,
        "selected_matches": len(ordered),
        "legs": legs_total,
        "legs_counted": counted,
        "wins": wins,
        "hit_rate": round(wins / counted, 4) if counted else None,
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "ending_bankroll": round(bankroll, 2),
        "roi": round(roi, 4),
        "by_tier": tier_stats,
        "details": details[:25],
    }


def simulate_flat_bets(
    predictions: list[dict[str, Any]],
    *,
    stake: float = STAKE,
    bankroll_start: float = BANKROLL_START,
    label: str = "",
    config: ModelConfig | None = None,
    only_played: bool = False,
) -> dict[str, Any]:
    """兼容旧版：每场单注 1X2。"""
    cfg = config or load_config()
    bankroll = bankroll_start
    bets = wins = 0
    staked = 0.0
    profit = 0.0
    details: list[dict[str, Any]] = []

    for pred in predictions:
        if only_played and not pred.get("played"):
            continue
        if bankroll < stake:
            break

        ph = pred["prob_home"] / 100.0
        pd = pred["prob_draw"] / 100.0
        pa = pred["prob_away"] / 100.0
        pick = _pred_outcome(ph, pd, pa)
        odds_map = _pick_odds_for_prediction(pred, cfg)
        dec = odds_map[pick]

        if only_played:
            ah, aa = pred["actual_home"], pred["actual_away"]
            actual = _actual_outcome(ah, aa)
            won = pick == actual
        else:
            won = None

        pnl = stake * (dec - 1.0) if won else (-stake if won is False else None)
        if won is not None:
            bankroll += pnl or 0.0
            profit += pnl or 0.0
            staked += stake
            bets += 1
            if won:
                wins += 1
            details.append(
                {
                    "title": pred.get("title", ""),
                    "pick": pick,
                    "odds": dec,
                    "stake": stake,
                    "won": won,
                    "pnl": round(pnl or 0.0, 2),
                    "bankroll_after": round(bankroll, 2),
                }
            )
        else:
            details.append(
                {
                    "title": pred.get("title", ""),
                    "pick": pick,
                    "odds": dec,
                    "stake": stake,
                    "potential_win": round(stake * (dec - 1.0), 2),
                }
            )

    roi = (profit / staked) if staked else 0.0
    return {
        "strategy": "flat_1x2",
        "bankroll_start": bankroll_start,
        "stake_per_bet": stake,
        "bets": bets,
        "wins": wins,
        "hit_rate": round(wins / bets, 4) if bets else None,
        "staked": round(staked, 2),
        "profit": round(profit, 2),
        "ending_bankroll": round(bankroll, 2),
        "roi": round(roi, 4),
        "details": details[:20] if len(details) > 20 else details,
    }


def _group_by_tournament(all_predictions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_label: dict[str, list[dict[str, Any]]] = {}
    for p in all_predictions:
        label = p.get("tournament") or str(p.get("year", "unknown"))
        by_label.setdefault(label, []).append(p)
    return by_label


def _run_per_tournament(by_label, sim_fn):
    tournaments: dict[str, Any] = {}
    total_profit = 0.0
    total_staked = 0.0
    merged_leg_types: dict[str, dict[str, Any]] = {}
    for label in sorted(by_label.keys(), key=lambda x: by_label[x][0].get("year", 0)):
        sim = sim_fn(by_label[label], label=label)
        tournaments[label] = {k: v for k, v in sim.items() if k != "details"}
        total_profit += sim["profit"]
        total_staked += sim["staked"]
        for leg_type, stats in (sim.get("by_leg_type") or {}).items():
            m = merged_leg_types.setdefault(
                leg_type, {"legs": 0, "wins": 0, "counted": 0, "staked": 0.0, "profit": 0.0}
            )
            for key in m:
                if key in stats:
                    m[key] += stats[key]
    leg_breakdown = {
        k: {
            **v,
            "staked": round(v["staked"], 2),
            "profit": round(v["profit"], 2),
            "hit_rate": round(v["wins"] / v["counted"], 4) if v["counted"] else None,
        }
        for k, v in merged_leg_types.items()
    }
    return tournaments, total_profit, total_staked, leg_breakdown


def simulate_betting_report(
    all_predictions: list[dict[str, Any]],
    config: ModelConfig | None = None,
) -> dict[str, Any]:
    """同时回测：单场 1X2 vs 三档精选。"""
    tc = _tier_cfg()
    by_label = _group_by_tournament(all_predictions)

    flat_t, flat_profit, flat_staked, _ = _run_per_tournament(
        by_label,
        lambda preds, label: simulate_flat_bets(preds, label=label, config=config, only_played=True),
    )
    tiered_t, tiered_profit, tiered_staked, leg_breakdown = _run_per_tournament(
        by_label,
        lambda preds, label: simulate_tiered_bets(
            preds, label=label, config=config, only_played=True, curated=True
        ),
    )

    return {
        "disclaimer": "虚拟投注回测，非真实博彩建议；历史赔率未接入时使用 ELO/典型市场线估算。",
        "flat_1x2": {
            "strategy": "flat_1x2",
            "config": {
                "stake_per_bet": STAKE,
                "bankroll_per_tournament": BANKROLL_START,
                "book_margin": BOOK_MARGIN,
                "bet_rule": "每场 50 元押模型最高概率赛果（1X2），共 48 场",
                "odds_source": "ELO 隐含欧赔 + 7% 抽水",
            },
            "overall_profit_all_tournaments": round(flat_profit, 2),
            "overall_roi": round(flat_profit / flat_staked, 4) if flat_staked else 0.0,
            "overall_staked": round(flat_staked, 2),
            "by_tournament": flat_t,
        },
        "tiered_curated": {
            "strategy": "tiered_curated",
            "config": {
                "stake_per_leg": STAKE,
                "bankroll_per_tournament": BANKROLL_START,
                "reserve": RESERVE,
                "budget_cap": BANKROLL_START - RESERVE,
                "bet_rule": "三档精选：强10×3注 + 中5×2注",
                "tier_thresholds": {
                    "strong": f"|strength_diff| > {tc['strong_strength']}",
                    "medium": f"{tc['medium_strength']}–{tc['strong_strength']}",
                    "weak": f"< {tc['medium_strength']}（跳过）",
                },
                "odds_source": "典型欧赔（1X2 1.6 / 亚盘 1.9 / 大小 1.85）",
            },
            "overall_profit_all_tournaments": round(tiered_profit, 2),
            "overall_roi": round(tiered_profit / tiered_staked, 4) if tiered_staked else 0.0,
            "overall_staked": round(tiered_staked, 2),
            "leg_breakdown": leg_breakdown,
            "by_tournament": tiered_t,
        },
        "comparison": {
            "flat_profit": round(flat_profit, 2),
            "tiered_profit": round(tiered_profit, 2),
            "delta": round(tiered_profit - flat_profit, 2),
            "why_tiered_underperforms": [
                "1X2 模型有 walk-forward edge，亚盘/大小球未单独校准",
                "强信号场追加亚盘要求净胜球，1 球小胜常赢 1X2 却输亚盘",
                "三档使用固定典型赔率，未接入真实历史赔率",
            ],
        },
    }


def simulate_by_tournament(
    all_predictions: list[dict[str, Any]],
    config: ModelConfig | None = None,
) -> dict[str, Any]:
    return simulate_betting_report(all_predictions, config=config)


def plan_2026_bets(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """2026 精选 15 场投注计划（含未赛）。"""
    tc = _tier_cfg()
    upcoming = [p for p in predictions if not p.get("played")]
    selected = select_curated_matches(upcoming, tc)
    selected.sort(key=_confidence, reverse=True)

    plans: list[dict[str, Any]] = []
    total_stake = 0.0
    for pred in selected:
        tier = classify_tier(pred, tc)
        legs = build_match_legs(pred, tier, tc)
        ms = sum(l["stake"] for l in legs)
        total_stake += ms
        plans.append(
            {
                "title": pred.get("title", ""),
                "group": pred.get("group", ""),
                "date": (pred.get("openfootball") or {}).get("date", ""),
                "tier": tier,
                "confidence": round(_confidence(pred) * 100, 1),
                "strength_diff": round(_strength_diff(pred), 3),
                "match_stake": ms,
                "legs": legs,
            }
        )

    return {
        "selected_count": len(plans),
        "total_stake": total_stake,
        "budget_cap": BANKROLL_START - RESERVE,
        "plans": plans,
    }


def simulate_2026(predictions: list[dict[str, Any]], config: ModelConfig | None = None) -> dict[str, Any]:
    played = [p for p in predictions if p.get("played")]
    flat_settled = (
        simulate_flat_bets(played, label="2026 世界杯", config=config, only_played=True) if played else None
    )
    tiered_settled = (
        simulate_tiered_bets(played, label="2026 世界杯", config=config, only_played=True, curated=True)
        if played
        else None
    )
    return {"flat_1x2": flat_settled, "tiered_curated": tiered_settled, "plan": plan_2026_bets(predictions)}
