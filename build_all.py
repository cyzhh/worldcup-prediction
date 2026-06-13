#!/usr/bin/env python3
"""一键：同步数据源 → 构建数据库 → 运行预测 → 生成 HTML。"""

from sync_all_sources import sync_all
from db_builder import main as build_db
from backtest import run_full_backtest
from predictor import main as run_predict
from generate_html import main as gen_html


def main() -> None:
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
    print("完成。")


if __name__ == "__main__":
    main()
