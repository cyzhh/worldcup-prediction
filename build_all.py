#!/usr/bin/env python3
"""一键：同步数据源 → 构建数据库 → 运行预测 → 生成 HTML。"""

from __future__ import annotations

import json
import sys

from app_config import path_from_config, pipeline_config
from sync_all_sources import sync_all
from db_builder import main as build_db
from backtest import run_full_backtest
from predictor import main as run_predict
from generate_html import main as gen_html
from validators import validate_predictions_batch
from wc_logging import setup_logging

log = setup_logging("worldcup.build")


def _pipeline_checks() -> None:
    expected = int(pipeline_config().get("expected_group_matches", 72))
    pred_path = path_from_config("predictions", "output/predictions.json")
    if not pred_path.exists():
        raise FileNotFoundError(f"缺少 {pred_path}")
    data = json.loads(pred_path.read_text(encoding="utf-8"))
    preds = data.get("predictions") or []
    if len(preds) != expected:
        raise ValueError(f"预测场次 {len(preds)} != 预期 {expected}")
    quality = validate_predictions_batch(preds)
    quality_path = path_from_config("output_dir", "output") / "data_quality.json"
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    if quality["anomalies"] > len(preds) * 0.05:
        log.warning("超过 5%% 预测存在校验异常 (%s/%s)", quality["anomalies"], quality["checked"])
    log.info("流水线校验通过：%s 场预测", len(preds))


def main() -> None:
    try:
        print(">>> 1/5 同步 awesome-football 数据源")
        sync_all()
        print(">>> 2/5 构建 worldcup_db.json")
        build_db()
        print(">>> 3/5 历史回测与参数校准")
        run_full_backtest(calibrate=True)
        print(">>> 4/5 运行量化预测")
        run_predict()
        print(">>> 5/5 生成 index.html")
        gen_html()
        _pipeline_checks()
        print("完成。")
    except Exception:
        log.exception("build_all 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
