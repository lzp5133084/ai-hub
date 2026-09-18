@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=D:\ai-tools\Python311\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" scripts\run_daily.py >> logs\task_out.log 2>&1
