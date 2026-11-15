@echo off
title Terra Twin
cd /d "%~dp0web"
echo Terra Twin is running at http://localhost:8000  (close this window to stop)
start "" http://localhost:8000
python -m http.server 8000 || py -m http.server 8000
