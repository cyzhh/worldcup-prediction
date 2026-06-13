#Requires -Version 5.1
param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ">>> 1/2 build..." -ForegroundColor Cyan
python db_builder.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python backtest.py --fast
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python predictor.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python generate_html.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">>> 2/2 git push..." -ForegroundColor Cyan
git add -A
$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "No changes to push." -ForegroundColor Yellow
    exit 0
}

if (-not $Message) {
    $Message = "Update site $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git commit -m $Message
git push origin main

Write-Host "Done. Pages: https://cyzhh.github.io/worldcup-prediction/" -ForegroundColor Green
