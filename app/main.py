from fastapi import FastAPI
import socketio
import asyncio
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

# ── Structured Logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger("atlas-agent")

from app.api import router
from app.database.sqlite_live import init_live_db
from app.database.duckdb_olap import init_olap_db
app = FastAPI(title="Atlas Agent Backend")

# REST Routing
app.include_router(router)

# ── Health Check (Immediate) ──
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "atlas-agent"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Must be False if origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Async Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Backend starting up...")
    # Initialize Databases
    try:
        init_live_db()
        init_olap_db()
        logger.info("✅ Databases initialized.")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
    
    # Start the core engine loop in the background
    from app.engine import start_engine
    asyncio.create_task(start_engine(sio))
    logger.info("--- BACKEND READY AND LISTENING ON PORT 8000 ---")

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    # Force an immediate sync_state on connect
    from app.database.sqlite_live import get_live_state
    from app.database.duckdb_olap import get_all_carriers
    state = get_live_state()
    state["carriers"] = get_all_carriers()
    await sio.emit('sync_state', state, to=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

# We serve the socket_app, not just the fastapi app
