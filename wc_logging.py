#!/usr/bin/env python3
"""统一 logging 配置。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app_config import logging_config, path_from_config

_CONFIGURED = False


def setup_logging(name: str | None = None) -> logging.Logger:
    """初始化根 logger（幂等），返回具名 logger。"""
    global _CONFIGURED
    cfg = logging_config()
    level_name = str(cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    if not _CONFIGURED:
        root = logging.getLogger("worldcup")
        root.setLevel(level)
        root.handlers.clear()
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        if cfg.get("console", True):
            ch = logging.StreamHandler(sys.stderr)
            ch.setFormatter(fmt)
            ch.setLevel(level)
            root.addHandler(ch)
        log_file = cfg.get("file")
        if log_file:
            log_path = path_from_config("logs_dir", "logs") if log_file.startswith("logs") else Path(log_file)
            if not log_path.is_absolute():
                from app_config import ROOT

                log_path = ROOT / log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            fh.setLevel(level)
            root.addHandler(fh)
        _CONFIGURED = True

    return logging.getLogger(name or "worldcup")
