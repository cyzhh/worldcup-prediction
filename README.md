# 2026 世界杯小组赛量化预测

基于 [openfootball/awesome-football](https://github.com/openfootball/awesome-football) 多源数据与七维因子引擎的 A 股式概率化赛果预测看板。

## 在线访问（GitHub Pages）

### 若 `gh auth login` 网络超时（校园网常见）

终端报 `dial tcp ... github.com:443 ... failed` 时，说明 **CLI 直连 GitHub 被拦**，可改用 **浏览器 + Token**：

```powershell
# 可选：若你有本地代理（Clash 等），先让终端走代理
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
$env:HTTP_PROXY  = "http://127.0.0.1:7890"

# 1. 浏览器创建空仓库: https://github.com/new  名称 worldcup
# 2. 浏览器生成 Token: https://github.com/settings/tokens  勾选 repo
# 3. 推送（把 USER 和 ghp_xxx 换成你的）
.\deploy-manual.ps1 -UserName USER -Token ghp_xxxx
```

然后在浏览器打开仓库 **Settings → Pages → Source 选 GitHub Actions**，到 **Actions** 页运行 workflow。

### 第一次部署（有 gh 且网络正常时）

```powershell
cd D:\CYZ\project\worldcup

# 1. 登录 GitHub（浏览器授权，只需一次）
#    若提示找不到 gh，先执行下面一行，或关闭终端重新打开：
#    $env:Path = "C:\Program Files\GitHub CLI;" + $env:Path
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
