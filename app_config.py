#!/usr/bin/env python3
"""加载 config.yaml（stdlib，无 PyYAML 依赖）。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if not s or s in ("null", "~"):
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    return s


def _load_yaml_simple(text: str) -> dict[str, Any]:
    """解析本项目用到的 YAML 子集（嵌套 dict、list、标量）。"""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]

    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        if content.startswith("- "):
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if not isinstance(parent, list):
                raise ValueError(f"列表项缺少父 list: {line}")
            parent.append(_parse_scalar(content[2:]))
            i += 1
            continue

        key, _, val = content.partition(":")
        key = key.strip()
        val = val.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if not isinstance(parent, dict):
            raise ValueError(f"键值对缺少父 dict: {line}")

        if val == "":
            child_indent = None
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                child_indent = len(nxt) - len(nxt.lstrip(" "))
            if i + 1 < len(lines) and child_indent is not None and child_indent > indent:
                nxt_content = lines[i + 1].strip()
                if nxt_content.startswith("- "):
                    new_list: list[Any] = []
                    parent[key] = new_list
                    stack.append((indent, new_list))
                else:
                    new_dict: dict[str, Any] = {}
                    parent[key] = new_dict
                    stack.append((indent, new_dict))
            else:
                parent[key] = None
        else:
            parent[key] = _parse_scalar(val)
        i += 1

    return root


@lru_cache(maxsize=1)
def load_app_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return _load_yaml_simple(CONFIG_PATH.read_text(encoding="utf-8"))


def get_section(name: str) -> dict[str, Any]:
    cfg = load_app_config()
    section = cfg.get(name, {})
    return section if isinstance(section, dict) else {}


def path_from_config(key: str, default: str) -> Path:
    rel = get_section("paths").get(key, default)
    return ROOT / str(rel)


def model_defaults() -> dict[str, Any]:
    return dict(get_section("model"))


def betting_config() -> dict[str, Any]:
    return get_section("betting")


def sync_config() -> dict[str, Any]:
    return get_section("sync")


def logging_config() -> dict[str, Any]:
    return get_section("logging")


def backtest_config() -> dict[str, Any]:
    return get_section("backtest")


def elo_config() -> dict[str, Any]:
    return get_section("elo")


def pipeline_config() -> dict[str, Any]:
    return get_section("pipeline")


def config_snapshot() -> str:
    """供 manifest / 调试用的 JSON 摘要。"""
    return json.dumps(load_app_config(), ensure_ascii=False, indent=2)
