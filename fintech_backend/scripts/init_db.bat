@echo off
REM Database initialization script wrapper for Windows
REM This script provides convenient shortcuts for common database operations

setlocal enabledelayedexpansion

echo HoardRun Fintech Backend - Database Initialization
echo ==================================================

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

REM Function to show usage
if "%1"=="" goto :show_usage
if "%1"=="-h" goto :show_usage
if "%1"=="--help" goto :show_usage

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    exit /b 1
)

REM Change to project directory
cd /d "%PROJECT_DIR%"

REM Parse command line arguments
set "COMMAND=%1"
set "VERBOSE="

:parse_args
shift
if "%1"=="" goto :execute_command
if "%1"=="--verbose" (
    set "VERBOSE=--verbose"
    goto :parse_args
)
echo [ERROR] Unknown option: %1
goto :show_usage

:execute_command
REM Execute the appropriate command
if "%COMMAND%"=="check" goto :check
if "%COMMAND%"=="init" goto :init
if "%COMMAND%"=="reset" goto :reset
if "%COMMAND%"=="sample" goto :sample
if "%COMMAND%"=="migrate" goto :migrate

echo [ERROR] Unknown command: %COMMAND%
goto :show_usage

:check
echo [INFO] Checking database connection...
python scripts\init_database.py --check-only %VERBOSE%
goto :success

:init
echo [INFO] Initializing database...
python scripts\init_database.py %VERBOSE%
goto :success

:reset
echo [WARNING] This will reset the database and delete all data!
python scripts\init_database.py --force-reset %VERBOSE%
goto :success

:sample
echo [INFO] Initializing database with sample data...
python scripts\init_database.py --create-sample-data %VERBOSE%
goto :success

:migrate
echo [INFO] Running database migrations...
alembic upgrade head
goto :success

:success
echo [INFO] Operation completed successfully!
exit /b 0

:show_usage
echo Usage: %0 [COMMAND] [OPTIONS]
echo.
echo Commands:
echo   check       - Check database connection only
echo   init        - Initialize database with migrations
echo   reset       - Reset database (DANGEROUS - development only)
echo   sample      - Initialize database and create sample data
echo   migrate     - Run migrations only
echo.
echo Options:
echo   --verbose   - Enable verbose output
echo.
echo Examples:
echo   %0 check                    # Check database connection
echo   %0 init                     # Initialize database
echo   %0 sample --verbose         # Initialize with sample data and verbose output
echo   %0 reset                    # Reset database (development only)
exit /b 1
