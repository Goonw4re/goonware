@echo off
echo ===================================
echo Goonware Installer Build Script
echo ===================================
echo.

:: Get version number (default or provided)
set "VERSION=1.0.0"
if not "%~1"=="" (
    set "VERSION=%~1"
)

:: Prompt for version if not provided as parameter
if "%~1"=="" (
    set /p VERSION_INPUT="Enter version number [%VERSION%]: "
    if not "%VERSION_INPUT%"=="" (
        set "VERSION=%VERSION_INPUT%"
    )
)

echo [INFO] Building installer for version %VERSION%

:: Check if Inno Setup is installed
set "INNOSETUP_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%INNOSETUP_PATH%" (
    set "INNOSETUP_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
    if not exist "%INNOSETUP_PATH%" (
        echo [ERROR] Inno Setup not found.
        echo Please download and install Inno Setup from https://jrsoftware.org/isinfo.php
        echo Then run this script again.
        pause
        exit /b 1
    )
)

echo [INFO] Inno Setup found at: %INNOSETUP_PATH%

:: Create a temporary copy of the .iss file
copy "goonware_installer.iss" "goonware_installer_temp.iss" > nul

:: Update the version in the temporary file
powershell -Command "(Get-Content goonware_installer_temp.iss) -replace '#define MyAppVersion \"1.0.0\"', '#define MyAppVersion \"%VERSION%\"' | Set-Content goonware_installer_temp.iss"

echo [INFO] Building installer...

:: Compile the setup script using the temporary file
"%INNOSETUP_PATH%" "goonware_installer_temp.iss"

:: Delete the temporary file
del "goonware_installer_temp.iss" > nul

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to build installer.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Installer (v%VERSION%) created successfully!
echo You can find GoonwareSetup.exe in the builds folder.
echo.
echo Usage: build_installer.bat [version]
echo Example: build_installer.bat 1.2.3
echo.
pause 