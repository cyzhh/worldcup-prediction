#!/usr/bin/env python3
"""模型超参与历史回测校准参数。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_config import model_defaults, path_from_config

ROOT = Path(__file__).parent
CALIBRATION_PATH = path_from_config("model_calibration", "output/model_calibration.json")

# 默认参数（config.yaml → 回测校准覆盖）
_DEFAULTS_FALLBACK = {
    "group_stage_draw_base": 0.22,
    "group_stage_round1_draw_boost": 0.04,
    "under_25_base": 0.55,
    "elo_blend_strong": 0.68,
    "elo_blend_close": 0.52,
    "historical_shrinkage": 0.12,
    "upset_elo_threshold": 120.0,
    "upset_prob_boost": 0.035,
    "favorite_draw_penalty": 0.015,
    # Dixon-Coles 低比分修正（报告 3.2.2）
    "dixon_coles_rho": -0.08,
    # 球员阵容差对胜平负的二次微调（报告 3.4.2，约 5%）
    "player_prob_weight": 0.05,
    # 2026 联合东道主 ELO 加成（报告 3.2.1）
    "host_elo_bonus": 35.0,
    # 将平局概率质量向历史频率收缩（缓解模型过度预测平局）
    "draw_mass_blend": 0.40,
}

DEFAULTS = {**_DEFAULTS_FALLBACK, **model_defaults()}


@dataclass
class ModelConfig:
    group_stage_draw_base: float = 0.22
    group_stage_round1_draw_boost: float = 0.04
    under_25_base: float = 0.55
    elo_blend_strong: float = 0.68
    elo_blend_close: float = 0.52
    historical_shrinkage: float = 0.12
    upset_elo_threshold: float = 120.0
    upset_prob_boost: float = 0.035
    favorite_draw_penalty: float = 0.015
    dixon_coles_rho: float = -0.08
    player_prob_weight: float = 0.05
    host_elo_bonus: float = 35.0
    draw_mass_blend: float = 0.40
    # 由回测填充：ELO 差分桶 → 历史胜/平/负率
    wdl_priors_by_elo_gap: dict[str, dict[str, float]] = field(default_factory=dict)
    calibrated_at: str | None = None
    backtest_summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelConfig:
        kw = {k: d[k] for k in DEFAULTS if k in d}
        cfg = cls(**kw)
        cfg.wdl_priors_by_elo_gap = d.get("wdl_priors_by_elo_gap", {})
        cfg.calibrated_at = d.get("calibrated_at")
        cfg.backtest_summary = d.get("backtest_summary", {})
        return cfg

    def to_dict(self) -> dict[str, Any]:
        out = {k: getattr(self, k) for k in DEFAULTS}
        out["wdl_priors_by_elo_gap"] = self.wdl_priors_by_elo_gap
        out["calibrated_at"] = self.calibrated_at
        out["backtest_summary"] = self.backtest_summary
        return out


_active: ModelConfig | None = None


def load_config(force_reload: bool = False) -> ModelConfig:
    global _active
    if _active is not None and not force_reload:
        return _active
    if CALIBRATION_PATH.exists():
        with CALIBRATION_PATH.open(encoding="utf-8") as f:
            _active = ModelConfig.from_dict(json.load(f))
    else:
        _active = ModelConfig(**DEFAULTS)
    return _active


def save_config(cfg: ModelConfig) -> None:
    global _active
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    _active = cfg


def elo_gap_bucket(elo_diff: float) -> str:
    """按主队 ELO 优势分桶（用于历史先验）。"""
    d = abs(elo_diff)
    if d < 40:
        return "even"
    if d < 100:
        return "slight"
    if d < 180:
        return "moderate"
    if d < 260:
        return "large"
    return "extreme"
