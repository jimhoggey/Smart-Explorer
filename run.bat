@echo off
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv)
.venv\Scripts\pip install -q -r requirements.txt
.venv\Scripts\python desktop.py
