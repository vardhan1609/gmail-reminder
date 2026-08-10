import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import accounts, calendar, destinations, reminder
from app.config import settings
from app.database.db import close_db, init_db
from app.services.scheduler import start_scheduler, stop_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend"

_wa_process: subprocess.Popen | None = None
_wa_thread: threading.Thread | None = None


def start_whatsapp_bridge():
    global _wa_process, _wa_thread
    bridge_dir = Path(__file__).resolve().parents[2] / "whatsapp-bridge"

    # 1. Quick check: Is Node installed?
    try:
        subprocess.run(["node", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception:
        logger.error("Node.js is not found on the system path. Cannot start WhatsApp bridge automatically.")
        return

    # 2. Check if bridge is already running
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{settings.whatsapp_service_url}/health")
            if resp.status_code == 200:
                logger.info("WhatsApp bridge is already running on %s", settings.whatsapp_service_url)
                return
    except Exception:
        pass

    logger.info("Starting WhatsApp bridge subprocess...")
    is_windows = sys.platform.startswith("win")

    try:
        _wa_process = subprocess.Popen(
            ["node", "index.js"],
            cwd=str(bridge_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=is_windows
        )
    except Exception as exc:
        logger.error("Failed to start WhatsApp bridge process: %s", exc)
        return

    def log_output():
        try:
            for line in _wa_process.stdout:
                cleaned_line = line.strip()
                if cleaned_line:
                    logger.info("[WhatsApp Bridge] %s", cleaned_line)
        except Exception:
            pass

    _wa_thread = threading.Thread(target=log_output, daemon=True)
    _wa_thread.start()
    logger.info("WhatsApp bridge subprocess launched successfully")


def stop_whatsapp_bridge():
    global _wa_process, _wa_thread
    if _wa_process:
        logger.info("Stopping WhatsApp bridge subprocess...")
        try:
            if sys.platform.startswith("win"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(_wa_process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                _wa_process.terminate()
                _wa_process.wait(timeout=5)
        except Exception as exc:
            logger.warning("Failed to cleanly stop WhatsApp bridge: %s", exc)
        _wa_process = None
        _wa_thread = None
        logger.info("WhatsApp bridge subprocess stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: initializing MongoDB, WhatsApp bridge and scheduler")
    init_db()
    start_whatsapp_bridge()
    start_scheduler()
    yield
    logger.info("Shutting down: stopping scheduler, WhatsApp bridge and closing DB")
    stop_scheduler()
    stop_whatsapp_bridge()
    close_db()


app = FastAPI(
    title="Gmail → WhatsApp Group Reminder System",
    description="Monitors Gmail inboxes and posts deadline reminders to WhatsApp/Telegram groups.",
    version="2.0.0",
    lifespan=lifespan,
)

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(accounts.router)
app.include_router(destinations.router)
app.include_router(calendar.router)
app.include_router(reminder.router)


@app.get("/")
def root():
    """Redirect root to the dashboard UI."""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard():
    """Serve the unified admin dashboard (Gmail + WhatsApp)."""
    return FileResponse(STATIC_DIR / "index.html")


# ══════════════════════════════════════════════
#  WhatsApp Bridge Reverse Proxy
#  Forwards /whatsapp-api/* → Node bridge on port 3000
# ══════════════════════════════════════════════

WA_BRIDGE_URL = settings.whatsapp_service_url.rstrip("/")

# Proxy all methods (GET, POST, PUT, PATCH, DELETE) to the Node bridge
@app.api_route("/whatsapp-api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def whatsapp_proxy(path: str, request: Request):
    """Reverse proxy requests to the WhatsApp Node bridge."""
    target_url = f"{WA_BRIDGE_URL}/{path}"

    # Forward query string
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Read request body
    body = await request.body()

    # Forward headers (skip host)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
            )

        # Forward response back
        excluded_headers = {"content-encoding", "transfer-encoding", "content-length"}
        response_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in excluded_headers
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        return Response(
            content='{"error":"WhatsApp bridge is not running (port 3000)"}',
            status_code=502,
            media_type="application/json",
        )
    except httpx.TimeoutException:
        return Response(
            content='{"error":"WhatsApp bridge timed out"}',
            status_code=504,
            media_type="application/json",
        )
