"""FastAPI application factory.

Surface as of 2.3: /health and /config, plus a lifespan handler that runs the
streaming Runtime (source → feature streamer → [stub] engine/broadcaster/sessions)
as a background task. The real engine/broadcaster/sessions land in 2.4 / 2.5 / 2.6.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.db import UserDb
from .auth.dependencies import get_current_user
from .auth.routes import router as auth_router
from .config import ServiceConfig, get_service_config
from .demo import router as demo_router
from .features.streamer import FeatureStreamer
from .inference.engine import InferenceEngine
from .logging_setup import setup_logging
from .runtime import Runtime
from .sessions.manager import SessionManager
from .sources import build_source
from .ws.broadcaster import WebSocketBroadcaster
from .ws.control import router as control_router
from .ws.routes import router as ws_router

# Explicit dev-frontend origins (Vite default 5173, CRA 3000). Never "*".
_CORS_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg: ServiceConfig = app.state.config
    source = build_source(cfg)
    streamer = FeatureStreamer(cfg.window_s, cfg.stride_s, cfg.sampling_hz)
    engine = InferenceEngine(
        cfg.inference.model_path,
        smoothing_method=cfg.inference.smoothing.method,
        smoothing_window=cfg.inference.smoothing.window,
        ema_alpha=cfg.inference.smoothing.ema_alpha,
        model_type=cfg.inference.model_type,
        fallback_model_path=cfg.inference.fallback_model_path,
    )
    broadcaster = WebSocketBroadcaster()
    session_mgr = SessionManager(cfg.session.db_path, cfg.session.export_dir)
    await session_mgr.initialize()

    # Users live in the same SQLite file as sessions (single-deployment auth).
    user_db = UserDb(cfg.session.db_path)
    await user_db.initialize()
    app.state.user_db = user_db

    runtime = Runtime(cfg, source, streamer, engine, broadcaster, session_mgr)
    app.state.runtime = runtime

    task = asyncio.create_task(runtime.run())
    logger.info("Lifespan: runtime task started")
    try:
        yield
    finally:
        await runtime.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Lifespan: runtime task stopped")


def create_app(cfg: ServiceConfig | None = None) -> FastAPI:
    """Build and return the FastAPI app."""
    cfg = cfg or get_service_config()
    setup_logging(cfg.service.log_level)
    logger.info("Creating app (input.source=%s)", cfg.input.source)

    app = FastAPI(title="Stress Detection Service", version="0.1.0", lifespan=lifespan)
    app.state.config = cfg

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(demo_router)
    app.include_router(ws_router)
    app.include_router(control_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # /config is auth-protected (per Phase 3 brief). _user is unused but the
    # dependency enforces a valid token before the handler runs.
    @app.get("/config")
    def show_config(_user=Depends(get_current_user)) -> dict:
        return app.state.config.to_dict()

    return app
