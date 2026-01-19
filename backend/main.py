"""
ECTHR Translator - Main FastAPI Application.

A legal terminology translator using HUDOC, CURIA, and IATE databases.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from backend.config import settings
from backend.routers import terminology

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO" if not settings.debug else "DEBUG"
)

# Create FastAPI app
app = FastAPI(
    title="ECTHR Translator API",
    description="""
    Legal terminology translation API using multiple European legal databases:

    - **HUDOC**: European Court of Human Rights case law
    - **CURIA**: Court of Justice of the European Union case law (via EUR-Lex)
    - **IATE**: Interactive Terminology for Europe

    This API provides real integration with these databases for accurate legal terminology translation.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(terminology.router)


@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("=" * 80)
    logger.info(f"Starting {settings.app_name}")
    logger.info("=" * 80)
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"HUDOC enabled: {settings.hudoc_enabled} (mock: {settings.hudoc_use_mock})")
    logger.info(f"CURIA enabled: {settings.curia_enabled} (mock: {settings.curia_use_mock})")
    logger.info(f"IATE enabled: {settings.iate_enabled} (mock: {settings.iate_use_mock})")
    logger.info("=" * 80)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "Legal terminology translation API",
        "docs": "/docs",
        "health": "/api/terminology/health",
        "sources": "/api/terminology/sources"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
