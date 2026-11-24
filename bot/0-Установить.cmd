@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 1C - setup
python -m pip install -r requirements.txt
echo.
echo OK
pause
