"""FastAPI application entry point.

Configures the app, mounts static files, registers API routes,
and serves Jinja2 frontend templates.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.documents import router as documents_router
from app.core.config import settings
from app.core.database import init_db, get_db
from app.core.logging import setup_logging
from app.repositories.document_repository import DocumentRepository

logger = setup_logging()

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATE_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"


# ── Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    logger.info("Starting Document Intelligence Platform v%s", settings.APP_VERSION)
    init_db()
    yield
    logger.info("Shutting down")


# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="AI-powered document extraction, validation & API platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS – allow all for the case study
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# API routes
app.include_router(documents_router, prefix="/api/v1")


# ── Frontend routes ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    """Render the main dashboard page."""
    db = next(get_db())
    try:
        documents = DocumentRepository.list_all(db)
    finally:
        db.close()
    return templates.TemplateResponse(
        request, "dashboard.html", context={"documents": documents}
    )


@app.get("/document/{document_name:path}", response_class=HTMLResponse, include_in_schema=False)
async def document_result_page(request: Request, document_name: str):
    """Render a single document result page."""
    db = next(get_db())
    try:
        result = DocumentRepository.get_by_name(db, document_name)
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "document_result.html",
        context={
            "document_name": document_name,
            "result": result,
            "result_json": json.dumps(result, indent=2, default=str) if result else "null",
        },
    )
