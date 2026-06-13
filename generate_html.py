#!/usr/bin/env python3
"""生成带内嵌数据的 index.html。"""

import json
from pathlib import Path

from predictor import run_all

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "dashboard.html"
OUT = ROOT / "index.html"
BACKTEST_PATH = ROOT / "output" / "backtest_report.json"


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
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()
