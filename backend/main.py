"""ECTHR Translator FastAPI Application."""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import logging

from config import settings
from routers import documents, translation, glossary, websocket, tm_management, tm, auth
from routers.auth import require_auth
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

# Configure CORS - Allow all Vercel deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router (no auth required for auth endpoints)
app.include_router(auth.router, prefix="/api")

# Include protected routers (require authentication)
app.include_router(documents.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(translation.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(glossary.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(tm_management.router, prefix="/api", dependencies=[Depends(require_auth)])
app.include_router(tm.router, prefix="/api", dependencies=[Depends(require_auth)])
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


@app.get("/docs/project-description")
async def download_project_description():
    """Download project description document."""
    docs_path = Path(__file__).parent.parent / "data" / "docs" / "PROJECT_DESCRIPTION.docx"
    if not docs_path.exists():
        # Fallback to repo docs
        docs_path = Path(__file__).parent.parent / "docs" / "PROJECT_DESCRIPTION.docx"

    if not docs_path.exists():
        return {"error": "Document not found"}

    return FileResponse(
        path=docs_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="PROJECT_DESCRIPTION.docx",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
