# 2026 世界杯小组赛量化预测

基于 [openfootball/awesome-football](https://github.com/openfootball/awesome-football) 多源数据与七维因子引擎的 A 股式概率化赛果预测看板。

## 在线访问（GitHub Pages）

### 第一次部署（三步）

```powershell
cd D:\CYZ\project\worldcup

# 1. 登录 GitHub（浏览器授权，只需一次）
gh auth login

# 2. 一键创建仓库 + 推送 + 开启 Pages
.\deploy.ps1

# 3. 等待 2~5 分钟，打开脚本输出的链接
#    例如 https://你的用户名.github.io/worldcup/
```

### 分享给朋友

把 Pages 链接发给朋友即可，**无需安装任何软件**。页面内嵌最新预测数据，打开即看。

### 保持「实时」更新

| 方式 | 说明 |
|------|------|
| **自动** | GitHub Actions 每 **6 小时**拉取 [openfootball](https://github.com/openfootball/worldcup) 最新赛果并重建页面 |
| **手动** | 本地运行 `python build_all.py` 后 `git push`，或到 Actions 页点击 **Run workflow** |

仓库 **Settings → Pages → Build and deployment** 应选择 **GitHub Actions**。

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
