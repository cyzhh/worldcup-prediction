#!/usr/bin/env python3
"""分类指标：F1、平局精准率、冷门捕捉率。"""

from __future__ import annotations

from typing import Any

LABELS = ("home", "draw", "away")


def _pred_outcome(p_h: float, p_d: float, p_a: float) -> str:
    probs = {"home": p_h, "draw": p_d, "away": p_a}
    return max(probs, key=probs.get)


def per_class_prf(
    y_true: list[str],
    y_pred: list[str],
    labels: tuple[str, ...] = LABELS,
) -> dict[str, dict[str, float | int]]:
    stats: dict[str, dict[str, float | int]] = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        stats[label] = {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }
    return stats


def macro_f1(per_class: dict[str, dict[str, float | int]]) -> float:
    f1s = [float(v["f1"]) for v in per_class.values()]
    return round(sum(f1s) / len(f1s), 4) if f1s else 0.0


def upset_capture_rate(
    preds: list[dict[str, Any]],
    *,
    threshold: float = 120.0,
) -> dict[str, Any]:
    """冷门 = ELO 差距≥阈值且弱队获胜；捕捉 = 模型最高概率项命中该冷门。"""
    upsets = captured = 0
    for p in preds:
        elo_h = float(p["home"]["elo"])
        elo_a = float(p["away"]["elo"])
        diff = elo_h - elo_a
        if abs(diff) < threshold:
            continue
        underdog = "away" if diff > 0 else "home"
        ah, aa = p["actual_home"], p["actual_away"]
        if ah > aa:
            actual = "home"
        elif ah < aa:
            actual = "away"
        else:
            actual = "draw"
        if actual != underdog:
            continue
        upsets += 1
        ph = p["prob_home"] / 100.0
        pd = p["prob_draw"] / 100.0
        pa = p["prob_away"] / 100.0
        if _pred_outcome(ph, pd, pa) == underdog:
            captured += 1
    rate = captured / upsets if upsets else None
    return {
        "upset_matches": upsets,
        "upset_captured": captured,
        "upset_capture_rate": round(rate, 4) if rate is not None else None,
        "threshold_elo": threshold,
    }


def classification_summary(
    preds: list[dict[str, Any]],
    *,
    upset_threshold: float = 120.0,
) -> dict[str, Any]:
    y_true: list[str] = []
    y_pred: list[str] = []
    for p in preds:
        ah, aa = p["actual_home"], p["actual_away"]
        if ah > aa:
            y_true.append("home")
        elif ah < aa:
            y_true.append("away")
        else:
            y_true.append("draw")
        ph = p["prob_home"] / 100.0
        pd = p["prob_draw"] / 100.0
        pa = p["prob_away"] / 100.0
        y_pred.append(_pred_outcome(ph, pd, pa))

    per_class = per_class_prf(y_true, y_pred)
    draw = per_class["draw"]
    upset = upset_capture_rate(preds, threshold=upset_threshold)
    return {
        "macro_f1": macro_f1(per_class),
        "per_class": per_class,
        "draw_precision": draw["precision"],
        "draw_recall": draw["recall"],
        "draw_f1": draw["f1"],
        **upset,
    }
