@echo off
chcp 65001 >nul 2>&1
rem ============================================================================
rem  Restore the English UI (you can also just double-click the toggle .bat)
rem
rem  Your settings, models, LoRAs and training data are never touched.
rem  Restart Fizgig, or press Ctrl+F5 in the browser, afterwards.
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
    echo Python not found.
    pause
    exit /b 1
)

"%PY%" -u "install.py" uninstall
echo.
pause