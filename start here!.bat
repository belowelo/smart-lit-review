@echo off
title Lit Review Generator
cd /d "%~dp0"
python lit-review.py
echo.
echo ---
echo Done. Press any key to close.
pause >nul
