@echo off
setlocal enabledelayedexpansion

title DevStat Stopper

rem ============================================================================
rem  DevStat Stopper — companion script to stop all DevStat services
rem
rem  Usage:
rem    stop_devstat.bat              stop backend + frontend on configured ports
rem    stop_devstat.bat --all        also kill any orphaned uvicorn/npm processes
rem ============================================================================

set "APP_NAME=DevStat"
set "BACKEND_PORT=8150"
set "FRONTEND_PORT=5173"
set "SCRIPT_DIR=%~dp0"

set "KILL_ALL=0"
if /I "%1"=="--all" set "KILL_ALL=1"

echo.
echo ========================================
echo   Stopping %APP_NAME% services...
echo ========================================
echo.

set "KILLED_COUNT=0"

rem ---- 1. Backend port ----
echo   Looking for backend on port %BACKEND_PORT%...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"127.0.0.1:%BACKEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" (
        >nul 2>&1 taskkill /F /PID %%P
        if !ERRORLEVEL! equ 0 (
            echo   [STOPPED] Backend PID %%P -- port %BACKEND_PORT%
            set /a KILLED_COUNT+=1
        )
    )
)

rem ---- 2. Frontend port ----
echo   Looking for frontend on port %FRONTEND_PORT%...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"127.0.0.1:%FRONTEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" (
        >nul 2>&1 taskkill /F /PID %%P
        if !ERRORLEVEL! equ 0 (
            echo   [STOPPED] Frontend PID %%P -- port %FRONTEND_PORT%
            set /a KILLED_COUNT+=1
        )
    )
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:"[::1]:%FRONTEND_PORT% " ^| findstr /C:"LISTENING"') do (
    if not "%%P"=="0" (
        >nul 2>&1 taskkill /F /PID %%P
        if !ERRORLEVEL! equ 0 (
            echo   [STOPPED] Frontend IPv6 PID %%P -- port %FRONTEND_PORT%
            set /a KILLED_COUNT+=1
        )
    )
)

rem ---- 3. Titled windows ----
echo   Looking for "%APP_NAME% Backend" and "%APP_NAME% Frontend" windows...
for /f "tokens=2 delims== " %%P in ('tasklist /V ^| findstr /C:"%APP_NAME% Backend" /C:"%APP_NAME% Frontend" 2^>nul') do (
    >nul 2>&1 taskkill /F /PID %%P
    if !ERRORLEVEL! equ 0 (
        echo   [STOPPED] Window PID %%P
        set /a KILLED_COUNT+=1
    )
)

rem ---- 4. (Optional) Kill all orphaned uvicorn / vite / npm ----
if %KILL_ALL% equ 1 (
    echo.
    echo   --all: Checking for orphaned DevStat processes...
    for /f "tokens=2 delims== " %%P in ('tasklist /V ^| findstr /C:"uvicorn" /C:"vite" /C:"%APP_NAME%" 2^>nul') do (
        >nul 2>&1 taskkill /F /PID %%P
        if !ERRORLEVEL! equ 0 (
            echo   [STOPPED] Orphaned PID %%P
            set /a KILLED_COUNT+=1
        )
    )
)

echo.
if %KILLED_COUNT% equ 0 (
    echo   No %APP_NAME% processes found. Nothing to stop.
) else (
    echo   Done. %KILLED_COUNT% process stopped.
    echo   Ports %BACKEND_PORT% and %FRONTEND_PORT% are now free.
)

echo.
echo ========================================
echo   %APP_NAME% stopped
echo ========================================
echo.

exit /b 0
