@echo off
title CASPER Setup

cd /d "C:\Users\demas\PycharmProjects\Tehnostrelka"

echo.
echo ========================================
echo  CASPER AR Assistant - Setup ^& Run
echo ========================================
echo.

:: --- 1. Check Python 3.13 ---
echo [1/5] Checking Python 3.13...
py -3.13 --version >nul 2>&1
if %errorlevel% == 0 (
    echo       OK - Python 3.13 found.
    goto :venv
)

python --version 2>&1 | findstr /C:"Python 3.13" >nul
if %errorlevel% == 0 (
    echo       OK - Python 3.13 found via python command.
    goto :venv
)

:: --- 2. Install Python 3.13 via winget ---
echo [2/5] Python 3.13 not found. Installing via winget...
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] winget not found. Downloading Python 3.13 manually...
    goto :download_python
)

winget install --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 (
    echo  [!] winget failed. Trying manual download...
    goto :download_python
)
echo       Python 3.13 installed via winget.
goto :venv

:download_python
echo  Downloading Python 3.13.3 from python.org...
set PY_INSTALLER=%TEMP%\python-3.13.3-amd64.exe
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe' -OutFile '%PY_INSTALLER%'"
if not exist "%PY_INSTALLER%" (
    echo.
    echo  [ERROR] Download failed.
    echo  Please install Python 3.13 manually from https://www.python.org/downloads/
    echo  Then run this script again.
    pause
    exit /b 1
)
echo  Running Python 3.13 installer...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%PY_INSTALLER%"
echo  Python 3.13 installed.

:venv
:: --- 3. Create virtual environment ---
echo.
echo [3/5] Setting up virtual environment...
if exist "backend\.venv\Scripts\uvicorn.exe" (
    echo       .venv already exists, skipping.
    goto :run
)
if exist "backend\.venv\" (
    echo       .venv exists but incomplete, recreating...
    rmdir /s /q backend\.venv
)

py -3.13 -m venv backend\.venv 2>nul
if %errorlevel% neq 0 (
    python -m venv backend\.venv
)
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to create .venv!
    pause
    exit /b 1
)
echo       .venv created.

:: --- 4. Install dependencies ---
echo.
echo [4/5] Installing dependencies...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip -q
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo       Dependencies installed.

:run
:: --- 5. Start server ---
echo.
echo [5/5] Starting CASPER server...
echo.
echo  Server running at: http://localhost:8000
echo  Press Ctrl+C to stop.
echo.

cd backend
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload

pause
