@echo off
:: EyeDE - Debug Console Launcher (Shows logs & real-time output)
title EyeDE - Look-To-Code (Debug Mode)
cd /d "%~dp0"
echo ========================================================
echo   EyeDE - Launching with Console Logging
echo ========================================================
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)
