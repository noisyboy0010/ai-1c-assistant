@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 1C - chat
python rag.py chat
pause
