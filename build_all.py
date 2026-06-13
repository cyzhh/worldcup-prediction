#!/usr/bin/env python3
"""一键：同步数据源 → 构建数据库 → 运行预测 → 生成 HTML。"""

from sync_all_sources import sync_all
from db_builder import main as build_db
from predictor import main as run_predict
from generate_html import main as gen_html


def main() -> None:
    print(">>> 1/4 同步 awesome-football 数据源")
    sync_all()
    print(">>> 2/4 构建 worldcup_db.json")
    build_db()
    print(">>> 3/4 运行量化预测")
    run_predict()
    print(">>> 4/4 生成 index.html")
    gen_html()
    print("完成。")


if __name__ == "__main__":
    main()
