@echo off
chcp 65001 >nul 2>&1
rem ============================================================================
rem  Update Fizgig AND re-apply the Chinese patch, in the right order.
rem
rem  Why: the patch edits three files under src/fizgig/web/static/. If Fizgig's
rem  own updater (git pull) also touches them, the pull aborts with "Your local
rem  changes would be overwritten" - which is exactly why Fizgig kept saying an
rem  update was available. This script restores English first, updates, then
rem  re-applies the patch (git branch / commit / tag are what the About box reads).
rem
rem  NOTE: ASCII-only on purpose - cmd.exe reads batch files in the console
rem  codepage, and Chinese text inside a .bat breaks the parser.
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
    echo Python not found. Run Fizgig's install_fizgig.bat first.
    pause
    exit /b 1
)

"%PY%" -u "update_zh.py"
echo.
pause
