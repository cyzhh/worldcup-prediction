#!/usr/bin/env python3
"""虚拟 1X2 投注回测：按模型预测方向、市场赔率（ELO 隐含 + 抽水）计算盈亏。"""

from __future__ import annotations

from typing import Any

from model_config import ModelConfig, load_config
from predictor import elo_win_prob

STAKE = 50.0
BANKROLL_START = 2000.0
BOOK_MARGIN = 0.07  # 胜平负市场约 7% 抽水


def _actual_outcome(h: int, a: int) -> str:
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def _pred_outcome(p_h: float, p_d: float, p_a: float) -> str:
    probs = {"home": p_h, "draw": p_d, "away": p_a}
    return max(probs, key=probs.get)


def market_odds_from_elo(
    elo_home: float,
    elo_away: float,
    config: ModelConfig | None = None,
) -> dict[str, float]:
    """ELO 胜平负 → 欧赔（含抽水），作为历史/缺赔率时的市场基准。"""
    cfg = config or load_config()
    p_h, p_d, p_a = elo_win_prob(elo_home, elo_away, draw_factor=0.0, config=cfg)
    odds: dict[str, float] = {}
    for key, p in (("home", p_h), ("draw", p_d), ("away", p_a)):
        p = max(p, 0.02)
        odds[key] = round((1.0 / p) * (1.0 - BOOK_MARGIN), 2)
    return odds


def market_odds_from_probs(prob_home: float, prob_draw: float, prob_away: float) -> dict[str, float]:
    """百分比概率 → 欧赔（含抽水）。"""
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


def simulate_flat_bets(
    predictions: list[dict[str, Any]],
    *,
    stake: float = STAKE,
    bankroll_start: float = BANKROLL_START,
    label: str = "",
    config: ModelConfig | None = None,
    only_played: bool = False,
) -> dict[str, Any]:
    """按时间顺序 flat bet，模型最高概率项为投注方向。"""
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
            # 未赛：仅展示若押中可赢多少
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
        "label": label,
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


def simulate_by_tournament(
    all_predictions: list[dict[str, Any]],
    config: ModelConfig | None = None,
) -> dict[str, Any]:
    """每届世界杯独立 2000 本金、每场 50。"""
    by_label: dict[str, list[dict[str, Any]]] = {}
    for p in all_predictions:
        label = p.get("tournament") or str(p.get("year", "unknown"))
        by_label.setdefault(label, []).append(p)

    tournaments: dict[str, Any] = {}
    total_profit = 0.0
    for label in sorted(by_label.keys(), key=lambda x: by_label[x][0].get("year", 0)):
        sim = simulate_flat_bets(by_label[label], label=label, config=config, only_played=True)
        tournaments[label] = {k: v for k, v in sim.items() if k != "details"}
        total_profit += sim["profit"]

    overall_staked = sum(t["staked"] for t in tournaments.values())
    return {
        "config": {
            "stake_per_bet": STAKE,
            "bankroll_per_tournament": BANKROLL_START,
            "book_margin": BOOK_MARGIN,
            "bet_rule": "每场押模型最高概率赛果（1X2）",
            "odds_source": "ELO 隐含欧赔 + 7% 抽水（历史届次无公开赔率时的市场基准）",
        },
        "disclaimer": "虚拟投注回测，非真实博彩建议；历史赔率未接入时使用 ELO 市场线近似。",
        "overall_profit_all_tournaments": round(total_profit, 2),
        "overall_roi": round(total_profit / overall_staked, 4) if overall_staked else 0.0,
        "by_tournament": tournaments,
    }


def simulate_2026(predictions: list[dict[str, Any]], config: ModelConfig | None = None) -> dict[str, Any]:
    """2026 当届：已赛结算 + 未赛展示潜在收益。"""
    played = [p for p in predictions if p.get("played")]
    upcoming = [p for p in predictions if not p.get("played")]
    settled = simulate_flat_bets(played, label="2026 世界杯", config=config, only_played=True) if played else None
    next_bets = simulate_flat_bets(upcoming[:5], label="未赛示例", config=config, only_played=False) if upcoming else None
    return {
        "settled": settled,
        "next_potential": next_bets,
    }
