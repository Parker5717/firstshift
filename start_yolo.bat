@echo off
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
set CASPER_YOLO=1
uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
