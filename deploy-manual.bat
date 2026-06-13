@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~2"=="" (
  echo 用法: deploy-manual.bat 你的GitHub用户名 ghp_你的Token
  echo 示例: deploy-manual.bat cyzhh ghp_xxxx
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-manual.ps1" -UserName "%~1" -Token "%~2"
exit /b %ERRORLEVEL%
