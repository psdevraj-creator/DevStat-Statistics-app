@echo off
setlocal enabledelayedexpansion

title DevStat Launcher

set "APP_NAME=DevStat"
set "BACKEND_PORT=8150"
set "FRONTEND_PORT=5173"
set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"

echo Engine: Python

set "PYTHON_CMD=py -3.14"
%PYTHON_CMD% --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo WARNING: Python 3.14 not found via 'py -3.14'. Trying 'python'...
    set "PYTHON_CMD=python"
)

set "NPM_CMD=npm"
call npm --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    where npm.cmd >nul 2>&1
    if !ERRORLEVEL! equ 0 set "NPM_CMD=npm.cmd"
)

echo ========================================
echo   %APP_NAME% Launcher
echo ========================================
echo.

rem ---- Kill previous processes ----
echo [1/5] Stopping previous %APP_NAME% processes...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"127.0.0.1:%BACKEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"127.0.0.1:%FRONTEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" taskkill /F /PID %%P >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"[::1]:%FRONTEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" taskkill /F /PID %%P >nul 2>&1
)
echo   Ports cleared.
echo.

rem ---- Start backend via wrapper batch ----
echo [2/5] Starting backend on port %BACKEND_PORT%...
(
    echo @echo off
    echo rem Python engine only
    echo cd /d %BACKEND_DIR%
    echo %PYTHON_CMD% -m uvicorn app.main:create_app --host 127.0.0.1 --port %BACKEND_PORT% --factory
    echo pause
) > "%TEMP%\devstat_backend.bat"
start "" /B "%TEMP%\devstat_backend.bat"
echo   Backend starting...
echo.

rem ---- Wait for backend ----
echo [3/5] Waiting for backend...
set "WAITED=0"
:WAIT_BE
    timeout /t 2 /nobreak >nul
    set /a WAITED+=2
    netstat -ano | findstr /C:"127.0.0.1:%BACKEND_PORT% " | findstr /C:"LISTENING" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo   Backend ready after !WAITED!s
        goto :BE_DONE
    )
    if !WAITED! geq 60 (
        echo   ERROR: Backend not ready after 60s. Check the backend window.
        pause
        exit /b 1
    )
    goto WAIT_BE
:BE_DONE
echo.

rem ---- Open browser ----
echo [4/4] Opening browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:%BACKEND_PORT%"

echo.
echo ========================================
echo   %APP_NAME% is running!
echo   App:  http://localhost:%BACKEND_PORT%
echo ========================================
echo.
pause
