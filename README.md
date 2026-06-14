# 2026 世界杯小组赛量化预测

基于 [openfootball/awesome-football](https://github.com/openfootball/awesome-football) 多源数据，对 2026 世界杯 **48 队 · 72 场小组赛** 进行概率化赛果预测，并提供 walk-forward 历史回测与虚拟投注验证。

**在线看板**：https://cyzhh.github.io/worldcup-prediction/

算法设计详见：`基于openfootball_awesome-football数据的2026世界杯小组赛概率预测算法研究报告.md`

> 指标来源：`output/backtest_report.json`（1998–2022 七届 · 336 场 walk-forward）与 `output/predictions.json`（2026 当届已赛）。虚拟投注使用 ELO 隐含欧赔 + 7% 抽水估算，**非真实博彩收益**。

---

## 核心成绩

### 预测胜率（胜平负）

| 维度 | 数值 | 说明 |
|------|------|------|
| **历史回测胜率** | **62.2%** | 336 场 · 1998–2022 七届世界杯小组赛 |
| 随机猜测基准 | 33.3% | 主/平/客三等概率 |
| 行业公开参考 | 62–65% | 主流统计模型区间 |
| 精确比分命中 | 11.0% | 代表比分 vs 实际比分 |
| 平局 F1 | 0.383 | 多因子平局模型（原接近 0） |
| Macro-F1 | 0.490 | 主/平/客均衡 F1 |
| Brier 分数 | 0.625 | 概率校准误差（越低越好） |
| **2026 当届已赛** | **50.0%** | 4 场 · 胜平负 2/4（实时更新） |

### 虚拟投注营收（策略：单场 1X2）

每场 **50 元**押模型最高概率赛果，每届本金 **2000 元**，共 48 场小组赛。

| 维度 | 数值 | 说明 |
|------|------|------|
| **七届合计营收** | **+3,192 元** | 1998–2022 虚拟盈亏合计 |
| **投资回报率 ROI** | **19.0%** | 总投入 16,800 元 |
| 虚拟注单命中率 | 49.4% | 166 中 / 336 注（赔率 edge 支撑盈利） |
| 七届盈利届数 | **6 / 7** | 仅 2022 届小幅亏损（-134 元） |
| **2026 当届已赛** | **+14.5 元** | 4 场 · 3 中 · 余额 2,014.5 元 |

<details>
<summary>历届虚拟投注明细（点击展开）</summary>

| 届次 | 命中率 | 盈亏 | ROI |
|------|--------|------|-----|
| 1998 法国 | 56.3%（27/48） | +1,278 元 | 53.3% |
| 2002 日韩 | 41.7%（20/48） | +222 元 | 9.3% |
| 2006 德国 | 58.3%（28/48） | +1,021 元 | 42.5% |
| 2010 南非 | 45.8%（22/48） | +306 元 | 12.7% |
| 2014 巴西 | 50.0%（24/48） | +361 元 | 15.0% |
| 2018 俄罗斯 | 47.9%（23/48） | +138 元 | 5.8% |
| 2022 卡塔尔 | 45.8%（22/48） | -134 元 | -5.6% |

</details>

---

## 算法优势

与「单模型 + 固定参数 + 样本内回测」的常见做法相比，本项目的差异化在于：

| 优势 | 具体做法 | 带来的效果 |
|------|----------|------------|
| **无泄露 walk-forward 回测** | 预测 2018 时仅用 2006–2014 赛果更新 ELO/H2H；当届逐场按时间顺序滚动 | 62.2% 胜率经严格样本外验证，非过拟合数字 |
| **七维因子 + 动态权重** | 基本面 / 状态 / 战术 / 阵容 / 环境 / 战意 / 伤病，按轮次与对阵态势自动调权 | 首轮保守、三轮抢分、势均力敌时强化战术与平局 |
| **ELO + 泊松双模型融合** | 强弱场五档动态权重（68%↔52%）；Dixon-Coles 低比分修正 | 同时捕捉实力差与进球分布，平局与小比分更稳 |
| **多因子平局模型** | ELO 差、轮次、近期状态、历史先验四路合成 `compute_draw_probability()` | 平局 F1 从 ≈0 提升至 **0.38**，不再系统性漏平 |
| **历史分布收缩** | 按 ELO 差分桶向 336 场真实胜平负率先验收缩 | 抑制模型过度自信，Brier 与 ROI 同步改善 |
| **ROI 导向两阶段校准** | 320 + 48 组网格；目标函数 **35% ROI + 20% 利润 + 30% 准确率** | 参数直接面向虚拟 1X2 盈利优化，而非单纯追准确率 |
| **1363 球员微观数据** | risingtransfers 身价 + per90 → 阵容深度 + Top5 微调 | 球队因子可解释，页面可下钻至球员评分 |
| **全开源可复现** | Python 标准库 + 一键 `update-and-push.ps1` | 数据、参数、回测报告均可审计 |

**一句话**：不是「猜比分的小工具」，而是带 **样本外验证、概率校准、虚拟 PnL 闭环** 的小组赛量化引擎。

---

## 快速开始

```powershell
cd D:\CYZ\project\worldcup

# 一键：同步 → 回测 → 预测 → 生成页面 → 推送 GitHub Pages
.\update-and-push.ps1

# 跳过 10 分钟网格校准，沿用已保存参数（日常更新推荐）
.\update-and-push.ps1 -EvalOnly

# 仅本地构建
python build_all.py
# 浏览器打开 index.html
```

| 命令 | 说明 |
|------|------|
| `python build_all.py` | 完整流水线 |
| `python backtest.py` | 两阶段网格校准（约 10 分钟） |
| `python backtest.py --eval-only` | 用已有 `model_calibration.json` 快速回测 |
| `python backtest.py --fast` | 默认参数快速回测（不覆盖校准文件） |
| `python predictor.py` | 生成 `output/predictions.json` |
| `python generate_html.py` | 生成 `index.html` |

推送到 `main` 后，GitHub Actions 每 6 小时自动同步赛果并重建页面。

---

## 预测算法

### 总览

```
外部数据源
    ↓
db_builder.py  →  worldcup_db.json（球队 / 赛程 / ELO / H2H / 球员）
    ↓
backtest.py    →  model_calibration.json（walk-forward + ROI 导向网格校准）
    ↓
predictor.py   →  七维因子 + ELO/泊松融合 + 平局多因子 → 胜平负 / 比分 / 大小球 / 亚盘
    ↓
betting_sim.py →  虚拟 1X2 回测与 2026 投注计划
    ↓
generate_html.py → index.html（内嵌 JSON，GitHub Pages）
```

每场比赛在 `predictor.predict_match()` 中分 **四步** 完成：

1. **七维因子** → 综合实力差 `strength_diff`
2. **双模型概率** → ELO 胜平负 + 泊松比分矩阵（Dixon-Coles）
3. **历史校准** → 收缩至历届分布 + 冷门修正 + 球员微调
4. **衍生输出** → 代表比分、大小球、亚盘、文字分析

---

### 第一步：七维因子模型

对主客队各维度打分（0–1），加权求差得到 `strength_diff`（正 = 主队更强）。

| 维度 | 默认权重 | 主要输入 |
|------|----------|----------|
| 基本面实力 | 35% | FIFA 排名、ELO、Opta 指数、阵容总身价、世界杯经验、预选赛胜率 |
| 近期状态 | 25% | 近 10 场胜平负、场均进球/失球、xG 差 |
| 战术风格 | 15% | 战术效率、风格克制、历史 H2H edge |
| 阵容深度 | 10% | 球员数据聚合、伤病风险 |
| 比赛环境 | 10% | 东道主、海拔、旅行距离 |
| 小组赛战意 | 5% | 轮次、实时积分榜（抢分 / 可接受平局） |
| 临场风险 | 0–12% | 双方伤病风险（动态权重） |

**动态权重**：首轮降状态/战术、提基本面；三轮提战意；势均力敌（\|gap\| < 0.10）时战术 ≥25%；伤病越高「临场风险」权重越大。

---

### 第二步：ELO + 泊松双模型融合

**ELO 胜平负**：联合东道主 +35 ELO；多因子平局基准（`compute_draw_probability`）；实力接近 ×1.15 平局；保留弱队爆冷区间。

**泊松比分矩阵**：λ 由攻防数据推导；Dixon-Coles 动态 ρ（势均力敌 -0.112 / 强弱分明 -0.048）；首轮 λ ×0.95 体现保守倾向。

**五档融合权重**（`get_blend_weights`）：

| 场景 | ELO 权重 | 泊松权重 |
|------|----------|----------|
| 强弱分明（\|diff\| > 0.12） | 68% | 32% |
| 势均力敌 | 52% | 48% |

---

### 第三步：历史校准层

参数存于 `output/model_calibration.json`，由 `backtest.py` 对 **1998–2022 七届 336 场** walk-forward 后两阶段网格搜索；ELO/H2H 先验可回溯至 **1986**。

| 机制 | 说明 |
|------|------|
| **历史先验收缩** | 按 ELO 差分桶向历届真实胜平负率收缩（`historical_shrinkage: 0.06`） |
| **平局质量校正** | `draw_mass_blend: 0.25`，向实际 ~25% 平局率校准 |
| **冷门修正** | ELO 差 >120 时向弱队注入额外胜率 |
| **球员 Top5 微调** | 融合后按阵容深度差二次调整（`player_top5_weight: 0.08`） |
| **ROI 导向校准** | 网格目标：1X2 虚拟 ROI / 利润 / 准确率 / Brier / 平局 F1 加权 |

**回测方法（无未来信息泄露）**：

- 预测当届时，仅使用此前届次赛果计算 ELO 和 H2H
- 当届按**时间顺序**逐场预测；二、三轮注入**当届已踢场次** form 与积分榜
- 完整报告：`output/backtest_report.json` · 页面「💰 虚拟投注」标签

---

### 第四步：输出与验证

| 输出 | 方法 |
|------|------|
| **胜/平/负概率** | 融合 + 校准后的百分比 |
| **代表比分** | 泊松矩阵按平局/小胜/大胜规则选取 |
| **大小球** | P(总进球 < 2.5) + 历史低比分倾向 |
| **亚盘** | `strength_diff` → -1.5 ~ +1.0 盘口 |
| **文字分析** | 6–8 条可解释依据 |
| **Onside 基准** | 与 [Onside 开放模型](https://onsidearena.com/data) 并列对比 |
| **虚拟 1X2** | 每场 50 元押最高概率赛果，历史 + 2026 实时结算 |

### 球员评分（独立模块）

`player_scores.py` 对 **1363 名球员** 计算 0–100 综合分（身价 42% + 赛季表现 58%），聚合为球队「阵容深度」因子。

---

## 数据流水线

```
sync_openfootball.py   →  data/openfootball/     赛程、分组、历届 cup.txt
sync_all_sources.py    →  data/external/         球员 CSV、Onside 基准
build_teams_seed.py    →  data/teams_seed.json   48 队种子
db_builder.py          →  data/worldcup_db.json  统一数据库
backtest.py            →  output/model_calibration.json
predictor.py           →  output/predictions.json
generate_html.py       →  index.html
```

| 来源 | 用途 |
|------|------|
| [openfootball/worldcup](https://github.com/openfootball/worldcup) | 2026 赛程、赛果、历届回测 |
| [risingtransfers/world-cup-2026-data](https://github.com/risingtransfers/world-cup-2026-data) | 1363 球员身价、per90 |
| [Onside 开放数据](https://onsidearena.com/data) | 外部模型基准 |
| `data/stadiums_2026.json` | 旅行距离、海拔 |

---

## 代码结构

| 文件 | 职责 |
|------|------|
| `predictor.py` | 七维因子 + ELO/泊松 + 平局多因子 + 校准 |
| `model_config.py` | 超参定义与 `model_calibration.json` 加载 |
| `backtest.py` | Walk-forward 回测 + ROI 导向两阶段网格校准 |
| `betting_sim.py` | 虚拟 1X2 回测与 2026 投注计划 |
| `db_builder.py` | 多源融合构建 `worldcup_db.json` |
| `elo_history.py` | 历届赛果滚动 ELO |
| `player_scores.py` / `player_enrichment.py` | 球员评分与阵容因子 |
| `generate_html.py` | 模板 + 内嵌 JSON → `index.html` |
| `update-and-push.ps1` | 构建 + git push 一键部署 |

更多工程说明见 `docs/ROADMAP.md`；Cursor 部署流程见 `.cursor/skills/worldcup-pages/SKILL.md`。

---

## 部署

**GitHub Pages**：https://cyzhh.github.io/worldcup-prediction/

```powershell
.\update-and-push.ps1 -EvalOnly -Message "更新说明"
```

仓库 **Settings → Pages → Build and deployment** 选择 **GitHub Actions**。

---

## 免责声明

公开数据与模型概率仅供研究参考；虚拟投注回测使用估算赔率，**不构成投资建议或博彩建议**。过往回测表现不保证未来结果。
