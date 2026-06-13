# 2026 世界杯小组赛量化预测

基于 [openfootball/awesome-football](https://github.com/openfootball/awesome-football) 多源数据与七维因子引擎的 A 股式概率化赛果预测看板。

## 在线访问

部署 GitHub Pages 后，分享链接：

`https://<你的用户名>.github.io/worldcup/`

## 本地运行

```bash
python build_all.py
# 浏览器打开 index.html
```

## 数据源

| 来源 | 用途 |
|------|------|
| [openfootball/worldcup](https://github.com/openfootball/worldcup) | 赛程、分组、赛果 |
| [risingtransfers/world-cup-2026-data](https://github.com/risingtransfers/world-cup-2026-data) | 1363 名球员、身价、per90 |
| [Onside 开放数据](https://onsidearena.com/data) | 外部模型基准 |
| 五届世界杯历史 | ELO、H2H |

## 自动更新

推送到 `main` 分支，或每 6 小时 GitHub Actions 会自动：同步数据 → 重建 `worldcup_db.json` → 更新预测 → 发布 Pages。

手动触发：仓库 **Actions** → **构建并部署 GitHub Pages** → **Run workflow**。

## 免责声明

公开数据与模型概率仅供研究参考，不构成投资建议或博彩建议。
