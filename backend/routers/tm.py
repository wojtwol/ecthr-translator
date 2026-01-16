"""Router dla zarządzania Translation Memory (TMX)."""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil

from config import settings
from services.tm_manager import TMManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tm", tags=["translation-memory"])


@router.post("/upload")
async def upload_tmx(file: UploadFile = File(...)):
    """
    Upload pliku TMX do pamięci tłumaczeniowej.

    Args:
        file: Plik TMX

    Returns:
        Informacje o uploadzie i statystyki załadowanych wpisów
    """
    try:
        if not file.filename.endswith('.tmx'):
            raise HTTPException(
                status_code=400,
                detail="Only TMX files are allowed"
            )

        # Zapisz plik
        tm_path = settings.tm_path
        tm_path.mkdir(parents=True, exist_ok=True)

        file_path = tm_path / file.filename

        with open(file_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"TMX file uploaded: {file_path}")

        # Załaduj i zwróć statystyki
        tm_manager = TMManager()
        count = tm_manager.load(file.filename)

        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path),
            "entries_loaded": count,
            "tm_stats": tm_manager.get_stats()
        }

    except Exception as e:
        logger.error(f"Error uploading TMX: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_tmx(filename: str):
    """
    Download pliku TMX z pamięci tłumaczeniowej.

    Args:
        filename: Nazwa pliku TMX

    Returns:
        Plik TMX do pobrania
    """
    try:
        file_path = settings.tm_path / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"TMX file not found: {filename}"
            )

        if not file_path.suffix == '.tmx':
            raise HTTPException(
                status_code=400,
                detail="Only TMX files can be downloaded"
            )

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/xml"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading TMX: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_tmx():
    """
    Lista dostępnych plików TMX.

    Returns:
        Lista plików TMX z informacjami
    """
    try:
        tm_path = settings.tm_path

        if not tm_path.exists():
            return {"files": []}

        files = []
        for tmx_file in tm_path.glob("*.tmx"):
            files.append({
                "filename": tmx_file.name,
                "size": tmx_file.stat().st_size,
                "modified": tmx_file.stat().st_mtime,
            })

        return {"files": files}

    except Exception as e:
        logger.error(f"Error listing TMX files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_tm_stats():
    """
    Statystyki aktualnej pamięci tłumaczeniowej.

    Returns:
        Statystyki TM
    """
    try:
        tm_manager = TMManager()
        tm_manager.load()

        return {
            "stats": tm_manager.get_stats(),
            "loaded_files": len(list(settings.tm_path.glob("*.tmx")))
        }

    except Exception as e:
        logger.error(f"Error getting TM stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_tm():
    """
    Przeładuj pamięć tłumaczeniową z dysku.

    Returns:
        Liczba załadowanych wpisów
    """
    try:
        tm_manager = TMManager()
        count = tm_manager.load()

        return {
            "status": "success",
            "entries_loaded": count,
            "stats": tm_manager.get_stats()
        }

    except Exception as e:
        logger.error(f"Error reloading TM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
