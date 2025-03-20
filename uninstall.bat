@echo off
chcp 65001 >nul
color 0D 
title Goonware Uninstaller

:: Set script directory and navigate to project root
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo              [ GOONWARE UNINSTALLER ]
echo ==================================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    color 0C
    echo [!] Administrator privileges required.
    echo [!] Please right-click on this batch file and select "Run as administrator".
    pause
    exit /b 1
)

:: Define absolute paths
set "SRC_DIR=%ROOT_DIR%src"
set "UNINSTALL_SCRIPT=%SRC_DIR%\uninstall.py"

:: Check if src directory and uninstall script exist using absolute paths
if not exist "%SRC_DIR%" (
    color 0C
    echo [!] ERROR: src directory not found at: %SRC_DIR%
    echo [!] This batch file must be run from the Goonware installation directory.
    pause
    exit /b 1
)

if not exist "%UNINSTALL_SCRIPT%" (
    color 0C
    echo [!] ERROR: uninstall.py script not found at: %UNINSTALL_SCRIPT%
    echo [!] The uninstaller may be corrupted or incomplete.
    pause
    exit /b 1
)

:: Run the uninstaller directly with system Python using absolute paths
echo [+] Running Goonware uninstaller...
python "%UNINSTALL_SCRIPT%"

:: Check for Python errors
if %errorlevel% neq 0 (
    color 0C
    echo [!] ERROR: Failed to run the uninstall script.
    echo [!] Please ensure Python is installed correctly.
    pause
    exit /b 1
)

echo [+] Uninstallation completed.
echo [+] You can now delete this uninstaller batch file manually.

:: Clean exit
timeout /t 3 /nobreak >nul 