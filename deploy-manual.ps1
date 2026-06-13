#Requires -Version 5.1
<#
.SYNOPSIS
  不依赖 gh auth 浏览器流程，纯 git + Token 推送到 GitHub Pages

.USAGE
  1. 浏览器打开 https://github.com/new 创建空仓库 worldcup（不要勾选 README）
  2. 浏览器打开 https://github.com/settings/tokens 生成 classic token，勾选 repo
  3. 运行: .\deploy-manual.ps1 -UserName 你的GitHub用户名 -Token ghp_xxxx
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$UserName,
    [Parameter(Mandatory = $true)]
    [string]$Token,
    [string]$RepoName = "worldcup"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "测试 GitHub 连通性 ..." -ForegroundColor Gray
try {
    $tcp = Test-NetConnection github.com -Port 443 -WarningAction SilentlyContinue
    if (-not $tcp.TcpTestSucceeded) {
        Write-Host "警告: 无法直连 github.com:443" -ForegroundColor Yellow
        Write-Host "若 push 失败，请在 PowerShell 先设置代理，例如:" -ForegroundColor Yellow
        Write-Host '  $env:HTTPS_PROXY = "http://127.0.0.1:7890"' -ForegroundColor Cyan
        Write-Host '  $env:HTTP_PROXY  = "http://127.0.0.1:7890"' -ForegroundColor Cyan
        Write-Host ""
    }
} catch { }

git branch -M main 2>$null

if (Get-Command python -ErrorAction SilentlyContinue) {
    python generate_html.py 2>$null
    git add index.html 2>$null
    git diff --cached --quiet 2>$null
    if ($LASTEXITCODE -ne 0) { git commit -m "Update index.html" 2>$null }
}

$remoteUrl = "https://${UserName}:${Token}@github.com/${UserName}/${RepoName}.git"
git remote remove origin 2>$null
git remote add origin $remoteUrl

Write-Host "推送到 github.com/$UserName/$RepoName ..." -ForegroundColor Cyan
git push -u origin main

# 移除 remote 中的 token（避免明文留在 .git/config）
git remote set-url origin "https://github.com/${UserName}/${RepoName}.git"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 代码已推送！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  请在浏览器完成 Pages 设置（只需一次）：" -ForegroundColor White
Write-Host "  1. 打开 https://github.com/$UserName/$RepoName/settings/pages" -ForegroundColor Cyan
Write-Host "  2. Build and deployment → Source 选 GitHub Actions" -ForegroundColor Cyan
Write-Host "  3. 打开 https://github.com/$UserName/$RepoName/actions" -ForegroundColor Cyan
Write-Host "  4. 运行 workflow「构建并部署 GitHub Pages」" -ForegroundColor Cyan
Write-Host ""
Write-Host "  部署成功后分享链接：" -ForegroundColor White
Write-Host "  https://${UserName}.github.io/${RepoName}/" -ForegroundColor Green
Write-Host ""
Write-Host "  注意: Token 已用于 push，请勿在聊天中泄露。用完后可在 GitHub 删除该 Token。" -ForegroundColor Gray
Write-Host ""
