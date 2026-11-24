@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 1C - eval
python rag.py index
echo.
python eval.py
pause
