@echo off
rem Drivable-grid benchmark for Windows: sets up its own Python environment
rem (numpy only) and runs tools\bench_grid.py.
rem
rem   bench\run_bench.bat            quick estimate (~3-6 min)
rem   bench\run_bench.bat --full     build a whole grid and time it (~15-25 min)
rem   bench\run_bench.bat --workers 4
rem
rem Results are printed and saved to out\bench\<host>-<mode>-<date>.json.
setlocal
cd /d "%~dp0\.."

rem a Python 3.10 or newer: the py launcher first, then python on PATH
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3.10 or newer is needed: install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
  exit /b 1
)
%PY% --version

rem its own environment, so nothing on the machine is changed
set "VENV=bench\.venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo creating %VENV% ...
  %PY% -m venv "%VENV%" || exit /b 1
)
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --quiet "numpy>=1.24" || exit /b 1

"%VENV%\Scripts\python.exe" tools\bench_grid.py %*
exit /b %errorlevel%
