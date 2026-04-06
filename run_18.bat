@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -X utf8 main.py 18 >> logs\scheduler.log 2>&1
