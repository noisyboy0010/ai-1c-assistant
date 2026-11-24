@echo off
chcp 65001 >nul
cd /d "%~dp0"
title RAG 1C - Telegram bot
python bot.py
pause
