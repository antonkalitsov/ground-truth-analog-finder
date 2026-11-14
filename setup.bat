@echo off
rem One-command setup for Windows.
rem   setup.bat            start the app with the data pack that ships in the repo
rem   setup.bat rebuild    install Python packages, download all raw data (about 6 GB), rebuild the data pack, then start
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause & exit /b 1
)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))" || (
  echo Python 3.10 or newer is required. & %PY% --version & pause & exit /b 1
)
if /i "%~1"=="rebuild" (
  if not exist .venv\Scripts\python.exe %PY% -m venv .venv || goto :fail
  .venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
  .venv\Scripts\python.exe -m pip install -r analog-finder\requirements.txt || goto :fail
  .venv\Scripts\python.exe analog-finder\pipeline\rebuild.py || goto :fail
)
call analog-finder\start.bat
exit /b 0
:fail
echo Setup stopped because of the error above. Fix it and run setup.bat rebuild again; finished steps are kept.
pause & exit /b 1
