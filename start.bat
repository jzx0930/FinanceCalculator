@echo off
title Stock Dip-Buy Calculator
cd /d "%~dp0"

echo ==============================================
echo   Small dip - small buy / Big dip - big buy
echo   Local dashboard launcher
echo ==============================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
    echo [X] Python not found.
    echo     Please install Python 3 from https://www.python.org/downloads/
    echo     and tick "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found: %PY%
echo Starting server... a browser tab will open automatically.
echo Close this window (or press Ctrl+C) to stop the server.
echo.
%PY% "%~dp0server.py"
if errorlevel 1 (
    echo.
    echo [X] Server exited with an error.
    pause
)
