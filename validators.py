#!/usr/bin/env python3
"""预测与数据库基础校验。"""

from __future__ import annotations

from typing import Any

from wc_logging import setup_logging

log = setup_logging("worldcup.validators")


def validate_probabilities(prob_home: float, prob_draw: float, prob_away: float, *, tol: float = 0.02) -> list[str]:
    issues: list[str] = []
    total = prob_home + prob_draw + prob_away
    if abs(total - 100.0) > tol * 100:
        issues.append(f"概率和偏离 100%: {total:.2f}")
    for name, v in (("home", prob_home), ("draw", prob_draw), ("away", prob_away)):
        if v < -0.01 or v > 100.01:
            issues.append(f"{name} 概率越界: {v}")
    return issues


def validate_elo(elo: float, team: str = "") -> list[str]:
    issues: list[str] = []
    if elo < 1200 or elo > 2300:
        issues.append(f"ELO 异常{(' ' + team) if team else ''}: {elo}")
    return issues


def validate_prediction(pred: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    issues.extend(
        validate_probabilities(
            float(pred.get("prob_home", 0)),
            float(pred.get("prob_draw", 0)),
            float(pred.get("prob_away", 0)),
        )
    )
    home = pred.get("home") or {}
    away = pred.get("away") or {}
    if "elo" in home:
        issues.extend(validate_elo(float(home["elo"]), str(home.get("name", "home"))))
    if "elo" in away:
        issues.extend(validate_elo(float(away["elo"]), str(away.get("name", "away"))))
    ah, aa = pred.get("actual_home"), pred.get("actual_away")
    if ah is not None and int(ah) < 0:
        issues.append("actual_home 为负")
    if aa is not None and int(aa) < 0:
        issues.append("actual_away 为负")
    return issues


def validate_predictions_batch(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    all_issues: list[dict[str, Any]] = []
    for i, pred in enumerate(predictions):
        issues = validate_prediction(pred)
        if issues:
            all_issues.append({"index": i, "title": pred.get("title", ""), "issues": issues})
    if all_issues:
        log.warning("预测校验发现 %d 条异常", len(all_issues))
    return {"checked": len(predictions), "anomalies": len(all_issues), "samples": all_issues[:10]}
