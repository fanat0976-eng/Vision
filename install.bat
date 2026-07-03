@echo off
chcp 65001 >nul 2>&1
title Vision AI Agent - Installer
echo ============================================
echo  Vision - Self-improving AI Agent Installer
echo  For clean Windows 10/11 machines
echo ============================================
echo.

REM Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Run as Administrator for full installation
    echo     Right-click install.bat - Run as administrator
    echo.
    pause
    exit /b 1
)

REM Run PowerShell installer
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Check errors above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installation complete!
echo ============================================
echo.
echo  Start Vision:
echo    CLI:     start_vision.bat
echo    Gateway: python run.py gateway
echo.
echo  Gateway URL: http://127.0.0.1:8080
echo.
pause
