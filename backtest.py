#!/usr/bin/env python3
"""历届世界杯小组赛 walk-forward 回测与模型参数校准。"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from history_loader import TOURNAMENTS, cup_files_before, load_all_tournaments, to_predictor_match
from historical_teams import build_team_profiles, refresh_teams_form
from model_config import ModelConfig, elo_gap_bucket, save_config
from openfootball_loader import build_h2h_from_history
from elo_history import parse_cup_txt_results
from predictor import predict_match, result_to_dict
from betting_sim import simulate_by_tournament
from standings import compute_standings, motivation_context

ROOT = Path(__file__).parent
REPORT_PATH = ROOT / "output" / "backtest_report.json"


def _actual_outcome(h: int, a: int) -> str:
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def _pred_outcome(p_h: float, p_d: float, p_a: float) -> str:
    probs = {"home": p_h, "draw": p_d, "away": p_a}
    return max(probs, key=probs.get)


def _brier(probs: tuple[float, float, float], outcome: str) -> float:
    idx = {"home": 0, "draw": 1, "away": 2}[outcome]
    return sum((p - (1 if i == idx else 0)) ** 2 for i, p in enumerate(probs))


def _log_loss(probs: tuple[float, float, float], outcome: str) -> float:
    idx = {"home": 0, "draw": 1, "away": 2}[outcome]
    p = max(probs[idx], 1e-6)
    return -math.log(p)


def _build_standings_from_played(
    played: list[dict[str, Any]], groups: dict[str, list[str]]
) -> dict[str, list[dict[str, Any]]]:
    group_keys = {g: [k for k in keys] for g, keys in groups.items()}
    return compute_standings(played, group_keys)


def run_tournament_backtest(
    td,
    tournament_meta: dict[str, Any],
    cfg: ModelConfig | None = None,
) -> list[dict[str, Any]]:
    """单届 walk-forward：每场比赛仅使用赛前 ELO/H2H/当届已踢场次积分。"""
    prior_files = cup_files_before(tournament_meta["id"])
    teams = build_team_profiles(
        tournament_meta,
        td.group_keys,
        prior_files,
        group_names=td.groups,
    )
    h2h = build_h2h_from_history(prior_files)
    prior_results: list[dict[str, Any]] = []
    for path in prior_files:
        if path.exists():
            for r in parse_cup_txt_results(path.read_text(encoding="utf-8")):
                prior_results.append(r)

    played_internal: list[dict[str, Any]] = []
    current_results: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for i, hm in enumerate(td.matches, start=1):
        refresh_teams_form(teams, prior_results, current_results)
        standings = _build_standings_from_played(played_internal, td.group_keys)
        motivation = {
            hm.home_key: motivation_context(hm.home_key, hm.group, standings, hm.round_num),
            hm.away_key: motivation_context(hm.away_key, hm.group, standings, hm.round_num),
        }
        match = to_predictor_match(hm, i, motivation)
        pred = predict_match(match, teams, h2h, benchmarks={}, config=cfg)
        d = result_to_dict(pred)
        d["tournament"] = tournament_meta["label"]
        d["year"] = hm.year
        results.append(d)

        played_internal.append(
            {
                "id": i,
                "group": hm.group,
                "round": hm.round_num,
                "home": hm.home_key,
                "away": hm.away_key,
                "played": True,
                "actual_score": {"home": hm.score_home, "away": hm.score_away},
            }
        )
        current_results.append(
            {
                "team1": hm.raw_home or hm.home_name,
                "team2": hm.raw_away or hm.away_name,
                "score_home": hm.score_home,
                "score_away": hm.score_away,
            }
        )

    return results


def aggregate_metrics(all_preds: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(all_preds)
    if n == 0:
        return {}

    outcome_hits = exact_hits = 0
    brier_sum = logloss_sum = 0.0
    draw_actual = draw_pred = 0
    bucket_stats: dict[str, dict[str, float]] = {}

    for p in all_preds:
        ah, aa = p["actual_home"], p["actual_away"]
        actual = _actual_outcome(ah, aa)
        ph, pd, pa = p["prob_home"] / 100, p["prob_draw"] / 100, p["prob_away"] / 100
        pred_o = _pred_outcome(ph, pd, pa)

        if p.get("outcome_hit"):
            outcome_hits += 1
        if p.get("result_hit"):
            exact_hits += 1
        brier_sum += _brier((ph, pd, pa), actual)
        logloss_sum += _log_loss((ph, pd, pa), actual)

        if actual == "draw":
            draw_actual += 1
        if pred_o == "draw":
            draw_pred += 1

        elo_h = p["home"]["elo"]
        elo_a = p["away"]["elo"]
        bucket = elo_gap_bucket(elo_h - elo_a)
        bs = bucket_stats.setdefault(bucket, {"home": 0, "draw": 0, "away": 0, "n": 0})
        bs[actual] += 1
        bs["n"] += 1

    wdl_priors: dict[str, dict[str, float]] = {}
    for bucket, bs in bucket_stats.items():
        total = bs["n"]
        wdl_priors[bucket] = {
            "home": round(bs["home"] / total, 4),
            "draw": round(bs["draw"] / total, 4),
            "away": round(bs["away"] / total, 4),
            "samples": int(total),
        }

    return {
        "matches": n,
        "outcome_accuracy": round(outcome_hits / n, 4),
        "exact_score_accuracy": round(exact_hits / n, 4),
        "brier_score": round(brier_sum / n, 4),
        "log_loss": round(logloss_sum / n, 4),
        "draw_rate_actual": round(draw_actual / n, 4),
        "draw_rate_predicted": round(draw_pred / n, 4),
        "wdl_priors_by_elo_gap": wdl_priors,
    }


def _score_for_calibration(metrics: dict[str, Any]) -> float:
    """综合评分：胜平负准确率为主，Brier 为辅。"""
    return metrics["outcome_accuracy"] * 0.65 + (1.0 - metrics["brier_score"] / 2.0) * 0.35


def calibrate_params() -> ModelConfig:
    """网格搜索关键超参，以五届世界杯合并回测表现最优为准。"""
    tournaments = load_all_tournaments()
    meta_by_id = {t["id"]: t for t in TOURNAMENTS}

    best_cfg = ModelConfig()
    best_score = -1.0
    best_metrics: dict[str, Any] = {}

    draw_bases = [0.18, 0.20, 0.22, 0.24, 0.26]
    round1_boosts = [0.02, 0.04, 0.06]
    shrinkages = [0.0, 0.08, 0.12, 0.16]
    elo_strongs = [0.60, 0.65, 0.68, 0.72]
    draw_blends = [0.35, 0.45, 0.55]

    for db in draw_bases:
        for rb in round1_boosts:
            for sh in shrinkages:
                for es in elo_strongs:
                    for dbl in draw_blends:
                        cfg = ModelConfig(
                            group_stage_draw_base=db,
                            group_stage_round1_draw_boost=rb,
                            historical_shrinkage=sh,
                            elo_blend_strong=es,
                            draw_mass_blend=dbl,
                        )
                        preds: list[dict[str, Any]] = []
                        for td in tournaments:
                            tmeta = meta_by_id[td.meta["id"]]
                            preds.extend(run_tournament_backtest(td, tmeta, cfg))
                        metrics = aggregate_metrics(preds)
                        score = _score_for_calibration(metrics)
                        if score > best_score:
                            best_score = score
                            best_cfg = cfg
                            best_metrics = metrics

    best_cfg.wdl_priors_by_elo_gap = best_metrics.get("wdl_priors_by_elo_gap", {})
    if best_cfg.historical_shrinkage == 0.0 and best_cfg.wdl_priors_by_elo_gap:
        best_cfg.historical_shrinkage = 0.08  # 仅用于 2026 前瞻预测，不参与回测评分
    best_cfg.calibrated_at = datetime.now(timezone.utc).isoformat()
    best_cfg.backtest_summary = {
        "composite_score": round(best_score, 4),
        **{k: v for k, v in best_metrics.items() if k != "wdl_priors_by_elo_gap"},
    }
    return best_cfg


def run_full_backtest(calibrate: bool = True) -> dict[str, Any]:
    tournaments = load_all_tournaments()
    meta_by_id = {t["id"]: t for t in TOURNAMENTS}

    if calibrate:
        print(">>> 历史回测参数校准（1998–2022 七届 walk-forward，ELO 先验自 1986 起）...")
        cfg = calibrate_params()
        save_config(cfg)
        print(f"    最优平局基准: {cfg.group_stage_draw_base}, shrinkage: {cfg.historical_shrinkage}")
    else:
        from model_config import load_config

        cfg = load_config(force_reload=True)

    by_tournament: dict[str, Any] = {}
    all_preds: list[dict[str, Any]] = []

    for td in tournaments:
        tmeta = meta_by_id[td.meta["id"]]
        eval_cfg = ModelConfig.from_dict({**cfg.to_dict(), "historical_shrinkage": 0.0, "wdl_priors_by_elo_gap": {}})
        preds = run_tournament_backtest(td, tmeta, eval_cfg)
        metrics = aggregate_metrics(preds)
        by_tournament[tmeta["label"]] = metrics
        all_preds.extend(preds)
        print(
            f"  {tmeta['label']}: {metrics['matches']} 场 · "
            f"胜平负 {metrics['outcome_accuracy']:.1%} · "
            f"精确比分 {metrics['exact_score_accuracy']:.1%} · "
            f"Brier {metrics['brier_score']:.3f}"
        )

    overall = aggregate_metrics(all_preds)
    betting = simulate_by_tournament(all_preds, config=cfg)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "walk-forward group stage backtest (1998-2022, ELO priors from 1986+)",
        "calibration": cfg.to_dict(),
        "overall": overall,
        "by_tournament": by_tournament,
        "betting": betting,
        "sample_predictions": all_preds[:8],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {REPORT_PATH}")
    print(
        f"合并回测: 胜平负准确率 {overall['outcome_accuracy']:.1%} · "
        f"Brier {overall['brier_score']:.3f} · 实际平局率 {overall['draw_rate_actual']:.1%}"
    )
    print(
        f"虚拟投注(每届2000元/场50元): 七届合计盈亏 {betting['overall_profit_all_tournaments']:+.0f} 元 · "
        f"ROI {betting['overall_roi']:.1%}"
    )
    return report


def main() -> None:
    import sys

    fast = "--fast" in sys.argv
    run_full_backtest(calibrate=not fast)


if __name__ == "__main__":
    main()
