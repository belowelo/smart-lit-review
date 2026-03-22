@echo off
title Lit Review Generator
cd /d "%~dp0"

:: Find Python — try python, then py
set PYTHON=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=py
    )
)

:: No Python found — try winget
if "%PYTHON%"=="" (
    echo Python not found. Installing via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo Automatic install failed. Please install Python 3.8+ manually:
        echo https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b
    )
    echo.
    echo Python installed! Please close and reopen this window.
    pause
    exit /b
)

:: Install dependencies if missing
%PYTHON% -m pip show pyyaml >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    %PYTHON% -m pip install requests pyyaml
    echo.
)

%PYTHON% lit-review.py
echo.
echo ---
echo Done. Press any key to close.
pause >nul
