@echo off
REM ===================================================================
REM  DSVV Grievance Management System - start the local web server
REM
REM  Double-click this file to run the project.
REM  It serves this folder on http://localhost:5500 and opens a browser.
REM
REM  The site cannot be opened by double-clicking index.html, because
REM  browsers block JavaScript modules loaded from a file:// path.
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
echo        http://localhost:5500
echo.
echo   Demo logins:
echo        student@dsvv.ac.in / student123
echo        officer@dsvv.ac.in / officer123
echo        admin@dsvv.ac.in   / admin123
echo.
echo   Press Ctrl+C in this window to stop the server.
echo  ================================================================
echo.

REM Give the server a moment to bind, then open the browser.
start "" http://localhost:5500

%PY% -m http.server 5500

echo.
echo   Server stopped.
pause
