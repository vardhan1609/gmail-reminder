@echo off
:: Setup script for Gmail Reminder on Windows
SETLOCAL EnableDelayedExpansion

echo ===================================================
echo   Gmail Reminder - Open Source Project Setup (Windows)
echo ===================================================
echo.

:: 1. Check prerequisites
echo Checking Prerequisites...

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.12+
    goto :error
) else (
    echo [OK] Python is installed.
)

:: Check Node.js
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Node.js is not installed. You will need it to run the WhatsApp bridge locally without Docker.
) else (
    echo [OK] Node.js is installed.
)

:: Check Docker (optional)
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Docker is not installed or running. You can still run the services manually.
) else (
    echo [OK] Docker is installed.
)
echo.

:: 2. Create local directories
echo Creating folders...
if not exist "tokens" (
    mkdir tokens
    echo [OK] Created "tokens" directory. This is where Google OAuth credentials will be stored.
) else (
    echo [INFO] "tokens" folder already exists.
)

if not exist "logs" (
    mkdir logs
    echo [OK] Created "logs" directory.
) else (
    echo [INFO] "logs" folder already exists.
)

if not exist "whatsapp-bridge\session" (
    mkdir whatsapp-bridge\session
    echo [OK] Created "whatsapp-bridge\session" directory.
) else (
    echo [INFO] "whatsapp-bridge\session" folder already exists.
)
echo.

:: 3. Configure .env file
echo Configuring environment file...
if not exist ".env" (
    copy .env.example .env >nul
    echo [OK] Created ".env" from template.
    echo [ACTION] Please open ".env" and fill in your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.
) else (
    echo [INFO] ".env" file already exists.
)
echo.

echo ===================================================
echo   Setup Complete!
echo ===================================================
echo To run using Docker:
echo   docker-compose up --build
echo.
echo To run manually:
echo   1. Start MongoDB (default expected at localhost:27017)
echo   2. Run Backend:
echo      cd backend
echo      python -m venv .venv
echo      .venv\Scripts\activate
echo      pip install -r requirements.txt
echo      python -m uvicorn app.main:app --reload --port 8000
echo   3. Run WhatsApp Bridge:
echo      cd whatsapp-bridge
echo      npm install
echo      npm run dev
echo ===================================================
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed. Please fix prerequisites and try again.
pause
exit /b 1
