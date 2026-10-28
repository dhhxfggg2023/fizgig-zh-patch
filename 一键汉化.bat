@echo off
chcp 65001 >nul 2>&1
rem ============================================================================
rem  Fizgig Chinese patch - one-click toggle (Chinese <-> English)
rem
rem  Double-click this file:
rem    - English UI  -> becomes Chinese
rem    - Chinese UI  -> becomes English
rem
rem  Restart Fizgig (or press Ctrl+F5 in the browser) to see the change.
rem  Your settings, models, LoRAs and training data are never touched.
rem
rem  NOTE: this .bat file is kept ASCII-only on purpose. cmd.exe reads batch
rem  files in the console codepage, and Chinese text inside a .bat breaks the
rem  parser on many machines. The Chinese messages come from the .py script.
rem ============================================================================
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PY="
if exist "%~dp0..\venv\Scripts\python.exe" set "PY=%~dp0..\venv\Scripts\python.exe"
if not defined PY if exist "%~dp0fizgig_root.txt" (
    for /f "usebackq delims=" %%p in ("%~dp0fizgig_root.txt") do (
        if exist "%%~dpvenv\Scripts\python.exe" set "PY=%%~dpvenv\Scripts\python.exe"
    )
)
if not defined PY (
    for %%p in (python.exe python3.exe) do (
        if not defined PY (
            for /f "delims=" %%q in ('where %%p 2^>nul') do if not defined PY set "PY=%%q"
        )
    )
)

if not defined PY (
    echo Python not found.
    echo.
    echo Run Fizgig's install_fizgig.bat first, or put this folder inside the
    echo Fizgig root so the script can find ..\venv\Scripts\python.exe.
    pause
    exit /b 1
)

"%PY%" -u "toggle_zh.py"
echo.
pause