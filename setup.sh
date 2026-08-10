#!/usr/bin/env bash
# Setup script for Gmail Reminder on Unix/macOS systems

echo "==================================================="
echo "  Gmail Reminder - Open Source Project Setup"
echo "==================================================="
echo

# 1. Check prerequisites
echo "Checking Prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed. Please install Python 3.12+"
    exit 1
else
    echo "[OK] Python 3 is installed."
fi

if ! command -v node &> /dev/null; then
    echo "[WARNING] Node.js is not installed. You will need it to run the WhatsApp bridge locally without Docker."
else
    echo "[OK] Node.js is installed."
fi

if ! command -v docker &> /dev/null; then
    echo "[INFO] Docker is not installed or running. You can still run the services manually."
else
    echo "[OK] Docker is installed."
fi
echo

# 2. Create local directories
echo "Creating folders..."
mkdir -p tokens
echo "[OK] Created 'tokens' directory. This is where Google OAuth credentials will be stored."

mkdir -p logs
echo "[OK] Created 'logs' directory."

mkdir -p whatsapp-bridge/session
echo "[OK] Created 'whatsapp-bridge/session' directory."
echo

# 3. Configure .env file
echo "Configuring environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created '.env' from template."
    echo "[ACTION] Please open '.env' and fill in your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
else
    echo "[INFO] '.env' file already exists."
fi
echo

echo "==================================================="
echo "  Setup Complete!"
echo "==================================================="
echo "To run using Docker:"
echo "  docker-compose up --build"
echo
echo "To run manually:"
echo "  1. Start MongoDB (default expected at localhost:27017)"
echo "  2. Run Backend:"
echo "     cd backend"
echo "     python3 -m venv .venv"
echo "     source .venv/bin/activate"
echo "     pip install -r requirements.txt"
echo "     python3 -m uvicorn app.main:app --reload --port 8000"
echo "  3. Run WhatsApp Bridge:"
echo "     cd whatsapp-bridge"
echo "     npm install"
echo "     npm run dev"
echo "==================================================="
chmod +x "$0" 2>/dev/null || true
