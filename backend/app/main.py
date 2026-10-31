import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import health
from app.api.v1 import api_v1_router
from app.config import settings
from app.database.db import close_db, init_db
from app.services.scheduler import start_scheduler, stop_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend_static"

_wa_process: subprocess.Popen | None = None
_wa_thread: threading.Thread | None = None


def start_whatsapp_bridge():
    global _wa_process, _wa_thread
    if settings.dry_run or settings.whatsapp_provider == "dry_run":
        logger.info("WhatsApp bridge subprocess skipped: DRY_RUN mode enabled")
        return
    if settings.whatsapp_provider != "webjs":
        logger.info("WhatsApp bridge subprocess skipped: provider is %s", settings.whatsapp_provider)
        return

    bridge_dir = Path(__file__).resolve().parents[2] / "whatsapp-bridge"
    script_path = bridge_dir / "src" / "index.js"
    if not script_path.exists():
        script_path = bridge_dir / "index.js"

    # 1. Quick check: Is Node installed?
    try:
        subprocess.run(["node", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception:
        logger.warning("Node.js not found on system path; WhatsApp bridge will not auto-start.")
        return

    # 2. Check if bridge is already running
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{settings.whatsapp_service_url}/health")
            if resp.status_code == 200:
                logger.info("WhatsApp bridge is already active on %s", settings.whatsapp_service_url)
                return
    except Exception:
        pass

    logger.info("Launching WhatsApp bridge subprocess...")
    is_windows = sys.platform.startswith("win")

    try:
        _wa_process = subprocess.Popen(
            ["node", str(script_path)],
            cwd=str(bridge_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=is_windows,
        )
    except Exception as exc:
        logger.error("Failed to start WhatsApp bridge process: %s", exc)
        return

    def log_output():
        try:
            if _wa_process and _wa_process.stdout:
                for line in _wa_process.stdout:
                    cleaned_line = line.strip()
                    if cleaned_line:
                        logger.info("[WhatsApp Bridge] %s", cleaned_line)
        except Exception:
            pass

    _wa_thread = threading.Thread(target=log_output, daemon=True)
    _wa_thread.start()
    logger.info("WhatsApp bridge subprocess started successfully")


def stop_whatsapp_bridge():
    global _wa_process, _wa_thread
    if _wa_process:
        logger.info("Stopping WhatsApp bridge subprocess...")
        try:
            if sys.platform.startswith("win"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(_wa_process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
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
    import asyncio
    from app.websocket import set_main_event_loop
    try:
        set_main_event_loop(asyncio.get_running_loop())
    except Exception:
        pass
    logger.info("Starting up Gmail Reminder System")
    settings.validate_security_settings()
    init_db()
    start_whatsapp_bridge()
    start_scheduler()
    yield
    logger.info("Shutting down Gmail Reminder System")
    stop_scheduler()
    stop_whatsapp_bridge()
    close_db()


app = FastAPI(
    title="Gmail → WhatsApp & Telegram Notification System",
    description="Monitors Gmail mailboxes, classifies emails, and delivers notifications and reminders via WhatsApp and Telegram.",
    version="2.0.0",
    docs_url=None if settings.environment.lower() == "production" else "/docs",
    redoc_url=None if settings.environment.lower() == "production" else "/redoc",
    openapi_url=None if settings.environment.lower() == "production" else "/openapi.json",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend and authenticated requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Health and Readiness probes
app.include_router(health.router)

# Mount only the authenticated, versioned API. Legacy Mongo-backed management
# routers are intentionally not mounted.
app.include_router(api_v1_router)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.environment.lower() == "production":
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'")
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    return response


# Serve static dashboard assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    """Redirect root to dashboard."""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard():
    """Serve administrative dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Dashboard UI not found", "api_docs": "/docs"}


# The WhatsApp bridge is an internal service and is never exposed through
# a public reverse-proxy route. Backend services call it over the private network.
