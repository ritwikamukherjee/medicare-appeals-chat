"""FastAPI entry point — serves the API and the React SPA."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes.chat import router as chat_router
from server.routes.summary import router as summary_router

app = FastAPI(title="Claims Ops Platform")

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(chat_router, prefix="/api")
app.include_router(summary_router, prefix="/api")

# ── Static files (React build) ───────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """Serve index.html for all non-API routes (SPA fallback)."""
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
