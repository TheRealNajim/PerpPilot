@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.11+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .env copy .env.example .env
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo Starting PerpPilot on http://127.0.0.1:8317 ...
start "" http://127.0.0.1:8317
python -m uvicorn app.main:app --port 8317
