#!/usr/bin/env python3
"""历届世界杯小组赛 walk-forward 回测与模型参数校准。"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_config import backtest_config, path_from_config
from history_loader import TOURNAMENTS, cup_files_before, load_all_tournaments, to_predictor_match
from historical_teams import build_team_profiles, refresh_teams_form
from metrics import classification_summary
from model_config import ModelConfig, elo_gap_bucket, save_config
from openfootball_loader import build_h2h_from_history
from elo_history import parse_cup_txt_results
from predictor import predict_match, result_to_dict
from betting_sim import simulate_betting_report

simulate_by_tournament = simulate_betting_report
from standings import compute_standings, motivation_context
from wc_logging import setup_logging

log = setup_logging("worldcup.backtest")

ROOT = Path(__file__).parent
REPORT_PATH = path_from_config("backtest_report", "output/backtest_report.json")


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
        **classification_summary(
            all_preds,
            upset_threshold=float(backtest_config().get("upset_elo_threshold", 120.0)),
        ),
    }


def _walk_forward_cfg(cfg: ModelConfig) -> ModelConfig:
    """回测/校准用：禁用 shrinkage 与全样本先验，避免泄露。"""
    return ModelConfig.from_dict({**cfg.to_dict(), "historical_shrinkage": 0.0, "wdl_priors_by_elo_gap": {}})


def _score_for_calibration(
    metrics: dict[str, Any],
    preds: list[dict[str, Any]] | None = None,
    cfg: ModelConfig | None = None,
) -> float:
    """校准目标：优先单场 1X2 虚拟 ROI/利润。"""
    draw_f1 = float(metrics.get("draw_f1") or 0.0)
    acc = float(metrics["outcome_accuracy"])
    brier = float(metrics["brier_score"])
    roi_score = profit_score = 0.0
    if preds is not None and cfg is not None:
        flat = simulate_betting_report(preds, config=cfg)["flat_1x2"]
        flat_roi = float(flat.get("overall_roi") or 0.0)
        flat_profit = float(flat.get("overall_profit_all_tournaments") or 0.0)
        roi_score = max(0.0, min(1.0, (flat_roi + 0.05) / 0.20))
        profit_score = max(0.0, min(1.0, (flat_profit + 500.0) / 3000.0))
    return roi_score * 0.35 + profit_score * 0.20 + acc * 0.30 + (1.0 - brier / 2.0) * 0.10 + draw_f1 * 0.05


def _evaluate_config(cfg: ModelConfig, tournaments, meta_by_id) -> tuple[float, dict[str, Any], list[dict[str, Any]]]:
    eval_cfg = _walk_forward_cfg(cfg)
    preds: list[dict[str, Any]] = []
    for td in tournaments:
        tmeta = meta_by_id[td.meta["id"]]
        preds.extend(run_tournament_backtest(td, tmeta, eval_cfg))
    metrics = aggregate_metrics(preds)
    flat = simulate_betting_report(preds, config=eval_cfg)["flat_1x2"]
    metrics["flat_betting_roi"] = flat.get("overall_roi")
    metrics["flat_betting_profit"] = flat.get("overall_profit_all_tournaments")
    return _score_for_calibration(metrics, preds, eval_cfg), metrics, preds


def calibrate_params(fast: bool = False) -> ModelConfig:
    tournaments = load_all_tournaments()
    meta_by_id = {t["id"]: t for t in TOURNAMENTS}

    if fast:
        cfg = ModelConfig()
        _, metrics, _ = _evaluate_config(cfg, tournaments, meta_by_id)
        cfg.wdl_priors_by_elo_gap = metrics.get("wdl_priors_by_elo_gap", {})
        cfg.calibrated_at = datetime.now(timezone.utc).isoformat()
        cfg.backtest_summary = {
            "composite_score": round(_score_for_calibration(metrics), 4),
            **{k: v for k, v in metrics.items() if k != "wdl_priors_by_elo_gap"},
            "calibration_mode": "fast_defaults",
            "calibration_objective": "flat_1x2_roi_weighted",
        }
        return cfg

    best_cfg = ModelConfig()
    best_score = -1.0
    best_metrics: dict[str, Any] = {}
    total_phase1 = 5 * 4 * 4 * 4
    done = 0
    draw_bases = [0.19, 0.21, 0.23, 0.25, 0.27]
    round1_boosts = [0.03, 0.05, 0.07, 0.09]
    shrinkages = [0.06, 0.10, 0.14, 0.18]
    draw_blends = [0.25, 0.35, 0.45, 0.55]

    print(f"    阶段1/2：核心参数 ({total_phase1} 组，目标=1X2 ROI)...")
    for db in draw_bases:
        for rb in round1_boosts:
            for sh in shrinkages:
                for dbl in draw_blends:
                    done += 1
                    cfg = ModelConfig(
                        group_stage_draw_base=db,
                        group_stage_round1_draw_boost=rb,
                        historical_shrinkage=sh,
                        draw_mass_blend=dbl,
                    )
                    score, metrics, _ = _evaluate_config(cfg, tournaments, meta_by_id)
                    if score > best_score:
                        best_score = score
                        best_cfg = cfg
                        best_metrics = metrics
                        print(
                            f"      [{done}/{total_phase1}] score={score:.4f} · "
                            f"准确率 {metrics['outcome_accuracy']:.1%} · "
                            f"1X2 ROI {metrics.get('flat_betting_roi', 0):.1%} · "
                            f"利润 {metrics.get('flat_betting_profit', 0):+.0f}"
                        )

    dixon_rhos = [-0.06, -0.08, -0.10, -0.12]
    player_weights = [0.04, 0.06, 0.08, 0.10]
    upset_boosts = [0.025, 0.035, 0.045]
    phase2_cfg, phase2_score, phase2_metrics = best_cfg, best_score, best_metrics
    print("    阶段2/2：Dixon/球员/冷门 (48 组)...")
    for dr in dixon_rhos:
        for pw in player_weights:
            for ub in upset_boosts:
                cfg = ModelConfig.from_dict(
                    {
                        **phase2_cfg.to_dict(),
                        "dixon_coles_rho": dr,
                        "dixon_rho_close": dr * 1.4,
                        "dixon_rho_strong": dr * 0.6,
                        "player_top5_weight": pw,
                        "player_prob_weight": pw,
                        "upset_prob_boost": ub,
                    }
                )
                score, metrics, _ = _evaluate_config(cfg, tournaments, meta_by_id)
                if score > phase2_score:
                    phase2_score = score
                    phase2_cfg = cfg
                    phase2_metrics = metrics
                    print(
                        f"      新最优 score={score:.4f} · ROI {metrics.get('flat_betting_roi', 0):.1%} · "
                        f"利润 {metrics.get('flat_betting_profit', 0):+.0f}"
                    )

    best_cfg = phase2_cfg
    best_metrics = phase2_metrics
    best_cfg.wdl_priors_by_elo_gap = best_metrics.get("wdl_priors_by_elo_gap", {})
    if best_cfg.historical_shrinkage == 0.0 and best_cfg.wdl_priors_by_elo_gap:
        best_cfg.historical_shrinkage = 0.08
    best_cfg.calibrated_at = datetime.now(timezone.utc).isoformat()
    best_cfg.backtest_summary = {
        "composite_score": round(phase2_score, 4),
        **{k: v for k, v in best_metrics.items() if k != "wdl_priors_by_elo_gap"},
        "calibration_mode": "two_phase_grid",
        "calibration_objective": "flat_1x2_roi_weighted",
    }
    return best_cfg


def run_full_backtest(calibrate: bool = True, *, fast: bool = False) -> dict[str, Any]:
    tournaments = load_all_tournaments()
    meta_by_id = {t["id"]: t for t in TOURNAMENTS}

    if calibrate:
        log.info("历史回测参数校准（1998–2022 walk-forward）")
        print(">>> 历史回测参数校准（1998–2022 七届 walk-forward，ELO 先验自 1986 起）...")
        cfg = calibrate_params(fast=fast)
        save_config(cfg)
        print(f"    最优平局基准: {cfg.group_stage_draw_base}, shrinkage: {cfg.historical_shrinkage}")
        bs = cfg.backtest_summary or {}
        if bs.get("flat_betting_roi") is not None:
            print(
                f"    校准目标(1X2): ROI {bs['flat_betting_roi']:.1%} · "
                f"利润 {bs.get('flat_betting_profit', 0):+.0f} 元"
            )
    else:
        from model_config import load_config

        cfg = load_config(force_reload=True)
        print(">>> 使用已保存 model_calibration.json（跳过网格搜索）")

    by_tournament: dict[str, Any] = {}
    all_preds: list[dict[str, Any]] = []
    eval_cfg = _walk_forward_cfg(cfg)

    for td in tournaments:
        tmeta = meta_by_id[td.meta["id"]]
        preds = run_tournament_backtest(td, tmeta, eval_cfg)
        metrics = aggregate_metrics(preds)
        by_tournament[tmeta["label"]] = metrics
        all_preds.extend(preds)
        print(
            f"  {tmeta['label']}: {metrics['matches']} 场 · "
            f"胜平负 {metrics['outcome_accuracy']:.1%} · "
            f"F1 {metrics.get('macro_f1', 0):.3f} · "
            f"精确比分 {metrics['exact_score_accuracy']:.1%} · "
            f"Brier {metrics['brier_score']:.3f}"
        )

    overall = aggregate_metrics(all_preds)
    betting = simulate_betting_report(all_preds, config=eval_cfg)
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
        f"Macro-F1 {overall.get('macro_f1', 0):.3f} · "
        f"平局 F1 {overall.get('draw_f1', 0):.3f} · "
        f"Brier {overall['brier_score']:.3f} · 实际平局率 {overall['draw_rate_actual']:.1%}"
    )
    flat = betting.get("flat_1x2") or {}
    tiered = betting.get("tiered_curated") or {}
    print(
        f"虚拟投注 A（单场1X2）: 七届合计 {flat.get('overall_profit_all_tournaments', 0):+.0f} 元 · "
        f"ROI {flat.get('overall_roi', 0):.1%}"
    )
    print(
        f"虚拟投注 B（三档精选）: 七届合计 {tiered.get('overall_profit_all_tournaments', 0):+.0f} 元 · "
        f"ROI {tiered.get('overall_roi', 0):.1%}"
    )
    return report


def main() -> None:
    import sys

    if "--eval-only" in sys.argv:
        run_full_backtest(calibrate=False)
    elif "--fast" in sys.argv:
        run_full_backtest(calibrate=True, fast=True)
    else:
        run_full_backtest(calibrate=True, fast=False)


if __name__ == "__main__":
    main()
