@echo off
cd /d "%~dp0"
py -3 main.py
if errorlevel 1 (
  echo.
  echo Python could not start. Run: py -3 -m pip install -r requirements.txt
  pause
)
