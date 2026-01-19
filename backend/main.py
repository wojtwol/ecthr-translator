"""ECTHR Translator FastAPI Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from routers import documents, translation, glossary, websocket, tm
from db.database import init_db

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ECTHR Translator API",
    description="Translation system for European Court of Human Rights judgments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api")
app.include_router(translation.router, prefix="/api")
app.include_router(glossary.router, prefix="/api")
app.include_router(tm.router, prefix="/api")
app.include_router(websocket.router)


@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("Starting ECTHR Translator API")

    # Ensure data directories exist (critical for Render /tmp storage)
    import os
    os.makedirs("/tmp/data", exist_ok=True)
    os.makedirs(settings.tm_path, exist_ok=True)
    os.makedirs(settings.upload_path, exist_ok=True)
    os.makedirs(settings.output_path, exist_ok=True)
    logger.info("Data directories created")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    logger.info(f"Upload path: {settings.upload_path}")
    logger.info(f"Output path: {settings.output_path}")
    logger.info(f"TM path: {settings.tm_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info("Shutting down ECTHR Translator API")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ECTHR Translator API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "hudoc": settings.hudoc_enabled,
            "curia": settings.curia_enabled,
            "iate": not settings.iate_use_mock,
        },
        "features": {
            "case_law_research": settings.hudoc_enabled or settings.curia_enabled or not settings.iate_use_mock,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
