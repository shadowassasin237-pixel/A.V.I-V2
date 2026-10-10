@echo off
title A.V.I. - Artificial Voice Intelligence
cd /d "%~dp0"
echo.
echo ================================================
echo A.V.I. - Natural Ashley Voice
echo ================================================
echo.
python app.py
if errorlevel 1 (
  echo.
  echo A.V.I. stopped with an error.
  pause
)
