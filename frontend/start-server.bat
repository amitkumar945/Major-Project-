@echo off
REM ===================================================================
REM  DSVV Grievance Management System - start the full local app
REM
REM  Double-click this file to run Flask, which serves both the frontend
REM  and API on http://127.0.0.1:5000.
REM
REM  MongoDB must be running before starting the backend.
REM ===================================================================

title DSVV Grievance Management System - Server
cd /d "%~dp0"

echo.
echo  ================================================================
echo   DSVV Grievance Management System
echo  ================================================================
echo.
echo   Starting the server...
echo.

REM Find a working Python command.
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" (where py >nul 2>nul && set PY=py)
if "%PY%"=="" (where python3 >nul 2>nul && set PY=python3)

if "%PY%"=="" (
  echo   [ERROR] Python was not found on this computer.
  echo.
  echo   Install Python from https://www.python.org/downloads/
  echo   and tick "Add Python to PATH" during installation.
  echo.
  pause
  exit /b 1
)

echo   Open this address in your browser:
echo.
echo        http://127.0.0.1:5000
echo.
echo   Demo logins:
echo        student@dsvv.ac.in / student123
echo        officer@dsvv.ac.in / officer123
echo        admin@dsvv.ac.in   / admin123
echo.
echo   Press Ctrl+C in this window to stop the server.
echo  ================================================================
echo.

REM Prefer the project virtual environment when it exists.
set PROJECT_PY=%~dp0..\.venv\Scripts\python.exe
if exist "%PROJECT_PY%" set PY="%PROJECT_PY%"

REM Flask serves the frontend and /api from this single process.
cd /d "%~dp0..\backend"
start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5000'"
%PY% app.py

echo.
echo   Server stopped.
pause
