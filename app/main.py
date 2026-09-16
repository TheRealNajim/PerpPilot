import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import ACCESS_TOKEN, DEMO_MODE, NANSEN_API_KEY
from .engine import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


class TokenGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if ACCESS_TOKEN and request.url.path.startswith("/api/") and request.url.path != "/api/health":
            if request.headers.get("X-PerpPilot-Token") != ACCESS_TOKEN:
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await engine.start()
    yield
    await engine.client.close()


app = FastAPI(title="PerpPilot", lifespan=lifespan)
app.add_middleware(TokenGate)


class WatchRequest(BaseModel):
    address: str
    label: str | None = None


class PauseRequest(BaseModel):
    paused: bool


class SettingsRequest(BaseModel):
    webhook_url: str | None = None
    telegram_chat_id: str | None = None


@app.post("/api/pause")
async def pause(req: PauseRequest):
    engine.set_paused(req.paused)
    return {"ok": True, "paused": engine.paused}


@app.get("/api/settings")
async def get_settings():
    return {
        "webhook_url": engine.settings.get("webhook_url", ""),
        "telegram_chat_id": engine.settings.get("telegram_chat_id", ""),
    }


@app.post("/api/settings")
async def set_settings(req: SettingsRequest):
    engine.set_settings(req.webhook_url, req.telegram_chat_id)
    return {"ok": True}


@app.get("/api/basket")
async def basket():
    return engine.basket()


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "api_key_set": bool(NANSEN_API_KEY),
        **engine.stats(),
    }


@app.get("/api/stats")
async def stats():
    return engine.stats()


@app.get("/api/leaderboard")
async def leaderboard():
    return {"updated_at": engine.leaderboard_updated, "data": engine.leaderboard}


@app.get("/api/watchlist")
async def watchlist():
    return {"data": [engine.trader_summary(a) for a in engine.watchlist]}


@app.post("/api/watchlist")
async def add_watch(req: WatchRequest):
    addr = req.address.strip().lower()
    if not addr.startswith("0x") or len(addr) != 42:
        raise HTTPException(400, "Invalid Hyperliquid address (expected 0x + 40 hex chars)")
    engine.add_to_watchlist(addr, req.label)
    return {"ok": True, "trader": engine.trader_summary(addr)}


@app.delete("/api/watchlist/{address}")
async def remove_watch(address: str):
    engine.remove_from_watchlist(address.lower())
    return {"ok": True}


@app.get("/api/traders/{address}")
async def trader_detail(address: str):
    addr = address.lower()
    if addr not in engine.watchlist:
        raise HTTPException(404, "Trader not in watchlist")
    return engine.trader_detail(addr)


@app.get("/api/alerts")
async def alerts(limit: int = 100):
    return {"data": list(engine.alerts)[: max(1, min(limit, 400))]}


@app.get("/api/smart-trades")
async def smart_trades(limit: int = 100):
    return {"data": list(engine.smart_trades)[: max(1, min(limit, 400))]}


@app.get("/api/consensus")
async def consensus():
    return {"data": engine.consensus()}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
