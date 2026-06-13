# 2026 世界杯小组赛量化预测

基于 [openfootball/awesome-football](https://github.com/openfootball/awesome-football) 多源数据，对 2026 世界杯 **48 队 · 72 场小组赛** 进行概率化赛果预测。

**在线看板**：https://cyzhh.github.io/worldcup-prediction/

算法设计对齐项目内研究报告：`基于openfootball_awesome-football数据的2026世界杯小组赛概率预测算法研究报告.md`（稳定实力基准 + 非线性场景修正）。

---

## 快速开始

```powershell
cd D:\CYZ\project\worldcup

# 一键：同步数据 → 回测校准 → 预测 → 生成 HTML → 推送部署
.\update-and-push.ps1

# 仅本地构建
python build_all.py
# 浏览器打开 index.html
```

| 命令 | 说明 |
|------|------|
| `python build_all.py` | 完整流水线（含回测参数校准，约 1–2 分钟） |
| `python backtest.py --fast` | 仅回测，跳过网格搜索 |
| `python predictor.py` | 仅生成 `output/predictions.json` |
| `python generate_html.py` | 仅生成 `index.html` |

推送到 `main` 后，GitHub Actions 每 6 小时自动同步赛果并重建页面；也可手动 `git push` 触发部署。

---

## 预测算法

### 总览

```
外部数据源
    ↓
db_builder.py  →  worldcup_db.json（球队 / 赛程 / ELO / H2H / 球员）
    ↓
backtest.py    →  model_calibration.json（历史回测校准超参）
    ↓
predictor.py   →  七维因子 + ELO/泊松融合 → 胜平负概率 / 代表比分 / 大小球 / 亚盘
    ↓
generate_html.py → index.html（内嵌 JSON，GitHub Pages 发布）
```

每场比赛的核心计算在 `predictor.predict_match()`，分 **四步**：

1. **七维因子** → 综合实力差 `strength_diff`
2. **双模型概率** → ELO 胜平负 + 泊松比分矩阵
3. **历史校准** → 收缩至历届真实分布 + 冷门修正
4. **衍生输出** → 代表比分、大小球、亚盘、文字分析

---

### 第一步：七维因子模型

对主客队各维度打分（0–1），加权求差得到 `strength_diff`（正 = 主队更强）。

| 维度 | 默认权重 | 主要输入 |
|------|----------|----------|
| 基本面实力 | 35% | FIFA 排名、ELO、Opta 指数、阵容总身价、世界杯经验、预选赛胜率 |
| 近期状态 | 25% | 近 10 场胜平负、场均进球/失球、xG 差 |
| 战术风格 | 15% | 战术效率、风格克制（传控 vs 密集防守等）、历史 H2H edge |
| 阵容深度 | 10% | 球员数据聚合深度分、伤病风险（risingtransfers） |
| 比赛环境 | 10% | 东道主、海拔适应、距上场比赛旅行距离 |
| 小组赛战意 | 5% | 轮次（首轮偏保守）、实时积分榜（需抢分/可接受平局） |
| 临场风险 | 0–12% | 双方伤病风险（动态权重） |

**动态权重规则**（报告 3.1.2）：

- **首轮**：降低近期状态 / 战术权重，提高基本面 / 阵容深度（新赛制参考价值有限）
- **二轮**：提高近期状态、战术、战意权重
- **三轮**：进一步强调战意与当届表现，略降基本面
- 双方基本面接近（\|gap\| < 0.10）→ 战术权重 ≥25%，基本面 ≤30%
- 伤病风险越高 → 「临场风险」维度权重越大

**ELO 修正**：`strength_diff` 会转化为 ELO 调整量（±400 分），注入后续概率计算：

```
adj_elo_home = elo_home + strength_diff × 400
adj_elo_away = elo_away − strength_diff × 400
```

---

### 第二步：ELO + 泊松双模型融合

#### 2a. ELO 胜平负（含小组赛平局校准）

基于调整后 ELO 计算主队胜率，再分配平局概率：

- 2026 **联合东道主**（美/加/墨）额外 +35 ELO（`host_elo_bonus`）
- 平局基准 = `group_stage_draw_base`（默认 22%，回测校准）
- 首轮额外加成 `group_stage_round1_draw_boost`
- 实力接近 → 平局概率 ×1.15；差距 >200 → ×0.82
- 保留弱队爆冷区间（ELO 差 >180 时客队胜率 ≥5%）

#### 2b. 泊松比分矩阵（含 Dixon-Coles 低比分修正）

由 `strength_diff` 和双方攻防数据计算期望进球 λ_home、λ_away，生成 0–5 球的联合概率矩阵；对 **0-0 / 1-0 / 0-1 / 1-1** 应用 Dixon-Coles 修正项（`dixon_coles_rho ≈ -0.08`），缓解传统泊松低估低比分的偏差。汇总为泊松胜平负。

首轮 λ 乘以 0.95 / 0.92，体现小组赛首轮偏保守、低比分倾向。

#### 2c. 融合权重

| 场景 | ELO 权重 | 泊松权重 |
|------|----------|----------|
| \|strength_diff\| > 0.12（强弱分明） | 68%（回测可校准至 60%） | 32% |
| 势均力敌 | 52% | 48% |

---

### 第三步：历史校准层

参数存储于 `output/model_calibration.json`，由 `backtest.py` 对 **1998–2022 七届世界杯 336 场小组赛** walk-forward 回测后网格搜索得到；ELO/H2H 先验可回溯至 **1986** 及更早届次（openfootball 支持 1930 起，当前同步 1986–2026）。

| 机制 | 说明 |
|------|------|
| **历史先验收缩** | 按 ELO 差分桶，将模型输出向历届真实胜平负率收缩 |
| **平局质量校正** | `draw_mass_blend`：将过度偏高的平局概率向历史 ~22–25% 收缩 |
| **冷门修正** | ELO 差 >120 时，向弱队注入额外胜率（小组赛爆冷先验） |
| **球员阵容微调** | 融合后按双方 `depth_score` 差二次调整胜平负（约 ±5%，报告 3.4.2） |
| **参数网格搜索** | 平局基准、首轮加成、ELO 融合权重、收缩系数等，以胜平负准确率 + Brier 分数综合最优 |

**回测方法（无未来信息泄露）**：

- 预测 2018 世界杯时，仅使用 2006 / 2010 / 2014 赛果计算 ELO 和 H2H
- 当届比赛按**时间顺序**逐场预测；二、三轮注入**当届已踢场次**的 form 与积分榜战意
- 回测报告：`output/backtest_report.json`

**当前回测指标**（`model_calibration.json`，336 场 walk-forward）：

| 指标 | 数值 |
|------|------|
| 胜平负准确率 | **63.7%**（336 场 · 1998–2022；随机基准 33%；行业公开约 62–65%） |
| 精确比分准确率 | 12.5% |
| Brier 分数 | 0.610（越低越好） |
| 实际平局率 | 24.7% |

---

### 第四步：输出衍生指标

| 输出 | 方法 |
|------|------|
| **代表比分** | 从泊松矩阵中按平局/小胜/大胜规则选取（如高平局概率 → 1:1，明显优势 → 2:0） |
| **胜/平/负概率** | 融合 + 校准后的百分比 |
| **大小球** | 泊松矩阵 P(总进球 < 2.5)，与历史低比分倾向混合 |
| **亚盘** | 由 `strength_diff` 映射到 -1.5 ~ +1.0 盘口 |
| **文字分析** | 自动生成 6–8 条依据（排名、ELO、战绩、环境、战术、H2H、战意、旅行距离） |
| **Onside 基准** | 与 [Onside 开放模型](https://onsidearena.com/data) 概率并列展示 |

---

### 球员评分（独立模块）

`player_scores.py` 对 1363 名球员计算 **0–100 综合分**（页面「球员评分」标签页）：

```
综合分 = 身价分 × 42% + 赛季表现分 × 58%

身价分   = min(100, 市值 / 4000万欧 × 100)
表现分   = rating×9 + 进球/90×18 + 助攻/90×12 + 射门/90×1.2 + 关键传球/90×0.8
```

数据来源：[risingtransfers/world-cup-2026-data](https://github.com/risingtransfers/world-cup-2026-data) 身价 + per90 统计。  
球员分通过 `player_enrichment.py` 聚合为球队「阵容深度」；在胜平负融合后另有 **约 5% 阵容差微调**（`apply_player_calibration`）。

---

## 数据流水线

```
sync_openfootball.py   →  data/openfootball/     赛程、分组、历届 cup.txt
sync_all_sources.py    →  data/external/         球员 CSV、Onside 基准
build_teams_seed.py    →  data/teams_seed.json   48 队种子（FIFA 排名、档位）
db_builder.py          →  data/worldcup_db.json  统一数据库
backtest.py            →  output/model_calibration.json
predictor.py           →  output/predictions.json
generate_html.py       →  index.html
```

### 数据源

| 来源 | 用途 |
|------|------|
| [openfootball/worldcup](https://github.com/openfootball/worldcup) | 2026 赛程、分组、赛果 |
| [openfootball 历届 cup.txt](https://github.com/openfootball/worldcup) | 2006–2022 ELO、H2H、回测样本 |
| [risingtransfers/world-cup-2026-data](https://github.com/risingtransfers/world-cup-2026-data) | 1363 球员身价、per90 |
| [Onside 开放数据](https://onsidearena.com/data) | 外部模型基准对比 |
| `data/stadiums_2026.json` | 球场坐标 → 旅行距离、海拔 |

---

## 代码结构

| 文件 | 职责 |
|------|------|
| `predictor.py` | 七维因子 + ELO/泊松 + 校准，核心预测引擎 |
| `model_config.py` | 超参定义与 `model_calibration.json` 加载 |
| `db_builder.py` | 多源融合构建 `worldcup_db.json` |
| `elo_history.py` | 从历届赛果滚动计算 ELO |
| `player_enrichment.py` | 球员 CSV → 球队阵容因子 |
| `player_scores.py` | 球员 0–100 综合评分 |
| `standings.py` | 小组赛积分榜与战意上下文 |
| `openfootball_loader.py` | 赛程加载、H2H、动机注入 |
| `history_loader.py` | 解析历届 cup.txt 小组赛 |
| `historical_teams.py` | 回测用赛前球队快照重建 |
| `backtest.py` | Walk-forward 回测 + 参数网格校准 |
| `generate_html.py` | 模板 + 内嵌 JSON → `index.html` |
| `update-and-push.ps1` | 构建 + git push 一键部署 |

Cursor 改代码后部署流程见项目 skill：`.cursor/skills/worldcup-pages/SKILL.md`。

---

## 部署

**GitHub Pages**：https://cyzhh.github.io/worldcup-prediction/

```powershell
# 推荐：构建并推送（SSH 需已配置，见此前 ssh.github.com:443 方案）
.\update-and-push.ps1 -Message "更新说明"

# 若 HTTPS 被校园网阻断，确保 git remote 走 SSH：
# git remote set-url origin git@github-ssh:cyzhh/worldcup-prediction.git
```

仓库 **Settings → Pages → Build and deployment** 选择 **GitHub Actions**。

---

## 免责声明

公开数据与模型概率仅供研究参考，不构成投资建议或博彩建议。
