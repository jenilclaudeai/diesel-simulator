@echo off
rem Build a custom engine's drivable grid on this computer (P13), for Windows:
rem sets up its own Python environment (numpy, certifi) and runs
rem tools\build_my_grid.py. Then load the file in the app: /drive or /enjoy ->
rem Import grid.
rem
rem   buildgrid\build.bat my-engine.json              the full grid (~1 h on a laptop)
rem   buildgrid\build.bat my-engine.json --no-weather cells only (~1/4 of the time)
rem   buildgrid\build.bat my-engine.json --workers 10
rem
rem my-engine.json is what the app exports: Dyno -> Custom -> Export.
setlocal
if "%~1"=="" (
  echo usage: buildgrid\build.bat my-engine.json [--no-weather] [--workers N] [--out PATH]
  echo ^(export the engine from the app first: Dyno -^> Custom -^> Export^)
  exit /b 1
)
rem the engine's full path, before changing directory
set "ENGINE=%~f1"
shift
set "REST="
:collect
if "%~1"=="" goto collected
set "REST=%REST% %1"
shift
goto collect
:collected
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
set "VENV=buildgrid\.venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo creating %VENV% ...
  %PY% -m venv "%VENV%" || exit /b 1
)
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --quiet "numpy>=1.24" certifi || exit /b 1

"%VENV%\Scripts\python.exe" tools\build_my_grid.py "%ENGINE%" %REST%
exit /b %errorlevel%
