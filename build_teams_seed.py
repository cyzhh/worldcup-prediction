#!/usr/bin/env python3
"""生成 48 支球队的 seed 数据（FIFA 排名 / 档位 / 东道主标记）。"""

from __future__ import annotations

import json
from pathlib import Path

# (key, 中文名, display_code, fifa_rank, elo, opta, tier, host, wc_apps)
TEAMS_META = [
    ("MEX", "墨西哥", "MX", 14, 1845, 82, 2, True, 18),
    ("RSA", "南非", "ZA", 56, 1420, 68, 4, False, 4),
    ("KOR", "韩国", "KR", 23, 1725, 76, 3, False, 12),
    ("CZE", "捷克", "CZ", 38, 1610, 72, 3, False, 2),
    ("CAN", "加拿大", "CA", 27, 1680, 74, 3, True, 3),
    ("BIH", "波黑", "BA", 75, 1380, 65, 4, False, 2),
    ("QAT", "卡塔尔", "QA", 35, 1630, 70, 3, False, 2),
    ("SUI", "瑞士", "CH", 19, 1780, 78, 2, False, 12),
    ("BRA", "巴西", "BR", 5, 2050, 92, 1, False, 22),
    ("MAR", "摩洛哥", "MA", 13, 1860, 81, 2, False, 6),
    ("HAI", "海地", "HT", 87, 1320, 62, 5, False, 1),
    ("SCO", "苏格兰", "SX", 36, 1620, 71, 3, False, 8),
    ("USA", "美国", "US", 11, 1880, 84, 2, True, 12),
    ("PAR", "巴拉圭", "PY", 52, 1450, 66, 4, False, 9),
    ("AUS", "澳大利亚", "AU", 24, 1710, 75, 3, False, 6),
    ("TUR", "土耳其", "TR", 42, 1580, 70, 3, False, 2),
    ("GER", "德国", "DE", 8, 1920, 86, 1, False, 20),
    ("CUW", "库拉索", "CW", 90, 1280, 60, 5, False, 1),
    ("CIV", "科特迪瓦", "CI", 37, 1615, 72, 3, False, 4),
    ("ECU", "厄瓜多尔", "EC", 31, 1660, 73, 3, False, 4),
    ("NED", "荷兰", "NL", 7, 1940, 87, 1, False, 11),
    ("JPN", "日本", "JP", 18, 1790, 79, 2, False, 8),
    ("SWE", "瑞典", "SE", 32, 1650, 73, 3, False, 12),
    ("TUN", "突尼斯", "TN", 41, 1590, 70, 3, False, 6),
    ("BEL", "比利时", "BE", 15, 1830, 83, 2, False, 14),
    ("EGY", "埃及", "EG", 33, 1645, 72, 3, False, 3),
    ("IRN", "伊朗", "IR", 20, 1770, 77, 2, False, 6),
    ("NZL", "新西兰", "NZ", 103, 1250, 58, 5, False, 3),
    ("ESP", "西班牙", "ES", 3, 2080, 90, 1, False, 16),
    ("CPV", "佛得角", "CV", 65, 1400, 66, 4, False, 1),
    ("KSA", "沙特", "SA", 58, 1410, 67, 4, False, 6),
    ("URU", "乌拉圭", "UY", 9, 1900, 85, 1, False, 14),
    ("FRA", "法国", "FR", 2, 2100, 91, 1, False, 16),
    ("SEN", "塞内加尔", "SN", 17, 1800, 80, 2, False, 3),
    ("IRQ", "伊拉克", "IQ", 59, 1405, 67, 4, False, 1),
    ("NOR", "挪威", "NO", 45, 1550, 69, 3, False, 3),
    ("ARG", "阿根廷", "AR", 1, 2120, 93, 1, False, 18),
    ("ALG", "阿尔及利亚", "DZ", 43, 1565, 69, 3, False, 4),
    ("AUT", "奥地利", "AT", 22, 1735, 76, 2, False, 3),
    ("JOR", "约旦", "JO", 70, 1370, 64, 4, False, 1),
    ("POR", "葡萄牙", "PT", 6, 1960, 88, 1, False, 8),
    ("COD", "刚果（金）", "CD", 62, 1415, 66, 4, False, 1),
    ("UZB", "乌兹别克斯坦", "UZ", 66, 1395, 65, 4, False, 1),
    ("COL", "哥伦比亚", "CO", 12, 1870, 82, 2, False, 6),
    ("ENG", "英格兰", "GB", 4, 2060, 89, 1, False, 16),
    ("CRO", "克罗地亚", "HR", 10, 1890, 84, 1, False, 6),
    ("GHA", "加纳", "GH", 68, 1385, 65, 4, False, 4),
    ("PAN", "巴拿马", "PA", 41, 1590, 70, 3, False, 2),
]


def _form_for_tier(tier: int) -> dict:
    base = {
        1: (6, 2, 2, 2.0, 0.9, 1.0),
        2: (5, 3, 2, 1.7, 1.1, 0.5),
        3: (4, 3, 3, 1.4, 1.2, 0.2),
        4: (3, 3, 4, 1.1, 1.4, -0.2),
        5: (2, 3, 5, 0.9, 1.6, -0.5),
    }[tier]
    w, d, l, gf, ga, xg = base
    return {
        "wins": w, "draws": d, "losses": l,
        "goals_for": gf, "goals_against": ga, "xg_diff": xg,
        "ppda": 10.0 + tier, "home_win_rate": 0.85 - tier * 0.05,
    }


def _tactics_for_tier(tier: int) -> dict:
    styles = {
        1: ("4-3-3", "高位压迫 + 控球组织", 0.82),
        2: ("4-2-3-1", "快速转换 + 边路进攻", 0.75),
        3: ("4-4-2", "中场绞杀 + 定位球", 0.68),
        4: ("5-4-1", "密集防守 + 反击", 0.62),
        5: ("5-3-2", "低位防守 + 长传", 0.55),
    }
    f, s, e = styles[tier]
    return {"formation": f, "style": s, "efficiency": e}


def build_seed() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, name, code, rank, elo, opta, tier, host, wc in TEAMS_META:
        out[key] = {
            "code": code,
            "name": name,
            "fifa_rank": rank,
            "elo": elo,
            "opta_index": opta,
            "tier": tier,
            "squad_value_m": max(20, 320 - rank * 3),
            "wc_appearances": wc,
            "wc_group_avg_pts": round(1.8 - tier * 0.25, 1),
            "qualifier_win_rate": round(0.78 - tier * 0.08, 2),
            "qualifier_gd": max(0, 22 - rank // 3),
            "form": _form_for_tier(tier),
            "tactics": _tactics_for_tier(tier),
            "squad": {
                "depth_score": round(0.9 - tier * 0.08, 2),
                "key_players": [],
                "injury_risk": 0.08 + tier * 0.02,
            },
            "environment": {
                "is_host": host,
                "altitude_m": 0,
                "climate_adapt": 0.92 if host else 0.8 - tier * 0.02,
            },
        }
    return out


def main() -> None:
    path = Path(__file__).parent / "data" / "teams_seed.json"
    data = build_seed()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {path}，共 {len(data)} 支球队")


if __name__ == "__main__":
    main()
