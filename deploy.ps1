#Requires -Version 5.1
<#
.SYNOPSIS
  创建 GitHub 仓库、推送代码、启用 GitHub Pages（GitHub Actions 部署）

.USAGE
  1. 先登录: gh auth login
  2. 运行:   .\deploy.ps1
  3. 分享链接给朋友（见脚本输出）
#>
param(
    [string]$RepoName = "worldcup",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 刷新 PATH（winget 安装 gh 后可能需要）
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 gh 命令。请安装 GitHub CLI: winget install GitHub.cli"
}

$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "请先登录 GitHub：" -ForegroundColor Yellow
    Write-Host "  gh auth login" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "登录完成后重新运行: .\deploy.ps1"
    exit 1
}

$user = (gh api user -q .login)
Write-Host "GitHub 用户: $user" -ForegroundColor Green

# 确保在 main 分支
git branch -M main 2>$null

# 本地构建最新页面（可选，CI 也会构建）
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "本地预构建 index.html ..." -ForegroundColor Gray
    python generate_html.py 2>$null
    if ($LASTEXITCODE -eq 0) {
        git add index.html output/predictions.json 2>$null
        git diff --cached --quiet 2>$null
        if ($LASTEXITCODE -ne 0) {
            git commit -m "Update predictions before deploy" 2>$null
        }
    }
}

# 创建远程仓库（若不存在）
$remoteUrl = "https://github.com/$user/$RepoName.git"
$repoExists = gh repo view "$user/$RepoName" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "创建仓库 $user/$RepoName ..." -ForegroundColor Cyan
    gh repo create $RepoName --$Visibility --source=. --remote=origin --description "2026 FIFA World Cup quantitative prediction dashboard"
} else {
    Write-Host "仓库已存在: $user/$RepoName" -ForegroundColor Gray
    git remote remove origin 2>$null
    git remote add origin $remoteUrl
}

Write-Host "推送到 GitHub ..." -ForegroundColor Cyan
git push -u origin main

# 启用 GitHub Pages（GitHub Actions 模式）
Write-Host "启用 GitHub Pages (Actions) ..." -ForegroundColor Cyan
gh api "repos/$user/$RepoName/pages" -X POST -f build_type=workflow 2>$null
if ($LASTEXITCODE -ne 0) {
    gh api "repos/$user/$RepoName/pages" -X PUT -f build_type=workflow 2>$null
}

# 触发首次部署
Write-Host "触发 Actions 部署 ..." -ForegroundColor Cyan
gh workflow run "deploy-pages.yml" 2>$null

$pagesUrl = "https://$user.github.io/$RepoName/"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  分享给朋友的链接：" -ForegroundColor White
Write-Host "  $pagesUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  首次部署约需 2-5 分钟，可在以下页面查看进度：" -ForegroundColor Gray
Write-Host "  https://github.com/$user/$RepoName/actions" -ForegroundColor Gray
Write-Host ""
Write-Host "  数据更新：推送代码或每 6 小时自动同步 openfootball 赛果" -ForegroundColor Gray
Write-Host ""
