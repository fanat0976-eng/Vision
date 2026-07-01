@echo off
echo ===================================
echo  Vision Agent - Installer
echo ===================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python 3.11+
    pause
    exit /b 1
)

echo Installing Vision...
pip install -e .

echo.
echo Creating config...
if not exist config.json (
    echo {"llm": {"provider": "ollama", "model": "qwen2.5:14b"}, "voice": {"enabled": false}, "gestures": {"enabled": false}} > config.json
)

echo.
echo Creating data directory...
if not exist data mkdir data

echo.
echo ===================================
echo  Installation complete!
echo ===================================
echo.
echo To start Vision:
echo   CLI:  vision
echo   Gateway: python run.py gateway
echo.
echo Configure Telegram bot token in config.json
echo.
pause
