#!/usr/bin/env python3
"""生成带内嵌数据的 index.html。"""

import json
from pathlib import Path

from predictor import run_all

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "dashboard.html"
OUT = ROOT / "index.html"


def main() -> None:
    data = run_all()
    template = TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("/*__PREDICTIONS__*/", json.dumps(data, ensure_ascii=False, indent=2))
    OUT.write_text(html, encoding="utf-8")
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    main()
