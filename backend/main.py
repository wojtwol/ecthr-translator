"""ECTHR Translator FastAPI Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from routers import documents, translation, glossary, websocket, tm_management
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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://ecthr-translator-n99j3xpxx-wojteks-projects-a85f52e4.vercel.app",
        "https://ecthr-translator-7j8pomy95-wojteks-projects-a85f52e4.vercel.app",
    ],
    allow_origin_regex=r"https://ecthr-translator-[a-z0-9]+-wojteks-projects-[a-z0-9]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api")
app.include_router(translation.router, prefix="/api")
app.include_router(glossary.router, prefix="/api")
app.include_router(tm_management.router, prefix="/api")
app.include_router(websocket.router)


@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("Starting ECTHR Translator API")

    # Ensure data directories exist (critical for Render /tmp storage)
    import os
    import shutil
    from pathlib import Path

    os.makedirs("/tmp/data", exist_ok=True)
    os.makedirs(settings.tm_path, exist_ok=True)
    os.makedirs(settings.upload_path, exist_ok=True)
    os.makedirs(settings.output_path, exist_ok=True)
    logger.info("Data directories created")

    # Copy bundled TM files to runtime TM directory
    # This ensures default terminology is always available
    repo_tm_dir = Path(__file__).parent.parent / "tm"
    if repo_tm_dir.exists():
        tmx_files = list(repo_tm_dir.glob("*.tmx"))
        if tmx_files:
            logger.info(f"Copying {len(tmx_files)} bundled TM files to {settings.tm_path}")
            for tmx_file in tmx_files:
                dest = settings.tm_path / tmx_file.name
                # Only copy if doesn't exist or is older than source
                if not dest.exists() or tmx_file.stat().st_mtime > dest.stat().st_mtime:
                    shutil.copy2(tmx_file, dest)
                    logger.info(f"  ✓ Copied {tmx_file.name}")
                else:
                    logger.info(f"  → {tmx_file.name} (already up-to-date)")
        else:
            logger.warning(f"No TMX files found in {repo_tm_dir}")
    else:
        logger.warning(f"Bundled TM directory not found: {repo_tm_dir}")

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
