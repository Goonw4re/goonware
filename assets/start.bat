@echo off
chcp 65001 >nul
title GOONWARE
mode con: cols=90 lines=30
color 0D 
setlocal enabledelayedexpansion

:: Set script directory and navigate to project root
set "ASSETS_DIR=%~dp0"
set "PROJECT_ROOT=%ASSETS_DIR%\.."
cd /d "%PROJECT_ROOT%"

:: Function to print a fancy header
echo ==================================================
echo                    [ GOONWARE ]
echo ==================================================
echo.
echo [*] Working directory: %CD%

:: Create necessary directories
for %%D in (assets assets\logs assets\resources assets\resources\img assets\resources\vid models) do (
    if not exist "%%D" mkdir "%%D"
)

:: Check if first run flag exists
if not exist "assets\first_run.flag" (
    echo [*] First time setup detected...
    
    :: Check Python installation
    python --version >nul 2>&1
    if errorlevel 1 (
        color 0C
        echo [!] Python is not installed! Please install Python 3.8 or later.
        pause
        exit /b 1
    )
    color 0D 

    :: Create virtual environment in the root directory
    echo [+] Creating virtual environment in: %CD%
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo [!] Failed to create virtual environment!
        pause
        exit /b 1
    )
    color 0D 

    :: Activate and install dependencies
    call venv\Scripts\activate.bat
    echo [+] Installing dependencies...
    pip install -r assets/requirements.txt
    if errorlevel 1 (
        color 0C
        echo [!] Failed to install dependencies!
        pause
        exit /b 1
    )
    color 0D 

    :: Create first run flag
    echo. > assets\first_run.flag
) else (
    echo [+] Virtual environment detected. Activating...
    call venv\Scripts\activate.bat
)
color 0D 

:: Force recreate file registry entries with icon (added as requested)
echo [+] Refreshing file associations...
pythonw -c "import sys; sys.path.append('./src'); import main; main.register_file_associations()"
echo [✓] File associations refreshed.

:: Check if another instance is running
pythonw src/main.py --check-instance
if errorlevel 1 (
    color 0D 
    echo [+] No running instance detected. Starting GOONWARE...
    start /B pythonw src/main.py
    echo [✓] Showing GOONWARE UI.
) else (
    color 0D 
    echo [+] Existing instance found
    echo [✓] Open GOONWARE UI from system tray.
)

timeout /t 2 /nobreak >nul
exit /b 0 