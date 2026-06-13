#!/usr/bin/env python3
"""生成带内嵌数据的 index.html。"""

import json
from pathlib import Path

from app_config import path_from_config
from predictor import run_all
from wc_logging import setup_logging

log = setup_logging("worldcup.generate_html")

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "dashboard.html"
OUT = ROOT / "index.html"
BACKTEST_PATH = path_from_config("backtest_report", "output/backtest_report.json")


def load_backtest_summary() -> dict:
    if not BACKTEST_PATH.exists():
        return {}
    report = json.loads(BACKTEST_PATH.read_text(encoding="utf-8"))
    overall = report.get("overall") or {}
    return {
        "method": report.get("method", ""),
        "generated_at": report.get("generated_at", ""),
        "overall": {
            "matches": overall.get("matches"),
            "outcome_accuracy": overall.get("outcome_accuracy"),
            "exact_score_accuracy": overall.get("exact_score_accuracy"),
            "brier_score": overall.get("brier_score"),
            "macro_f1": overall.get("macro_f1"),
            "draw_f1": overall.get("draw_f1"),
            "draw_precision": overall.get("draw_precision"),
            "upset_capture_rate": overall.get("upset_capture_rate"),
        },
        "betting": report.get("betting", {}),
    }


def main() -> None:
    data = run_all()
    bt = load_backtest_summary()
    data["backtest"] = bt
    from betting_sim import simulate_2026

    data["betting_2026"] = simulate_2026(data.get("predictions") or [])
    template = TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("/*__PREDICTIONS__*/", json.dumps(data, ensure_ascii=False, indent=2))
    OUT.write_text(html, encoding="utf-8")
    log.info("已生成 %s", OUT)
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()
