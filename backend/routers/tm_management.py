"""Translation Memory Management API."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
import uuid

from services.multi_tm_manager import MultiTMManager
from config import settings

router = APIRouter(prefix="/tm", tags=["translation-memory"])

# Global TM Manager instance (shared across requests)
_tm_manager: Optional[MultiTMManager] = None


def get_tm_manager() -> MultiTMManager:
    """Get or create TM Manager instance."""
    global _tm_manager
    if _tm_manager is None:
        _tm_manager = MultiTMManager()
        _tm_manager.load_all_from_directory()
    return _tm_manager


class TMInfo(BaseModel):
    """TM information model."""
    name: str
    priority: int
    enabled: bool
    entries_count: int
    file_path: str


class TMCreateRequest(BaseModel):
    """Request to create/add new TM."""
    name: str
    priority: int = 4
    enabled: bool = True


class TMUpdateRequest(BaseModel):
    """Request to update TM settings."""
    priority: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/list", response_model=List[TMInfo])
async def list_translation_memories(tm_manager: MultiTMManager = Depends(get_tm_manager)):
    """
    Lista wszystkich pamięci tłumaczeniowych.

    Returns:
        Lista TM z informacjami (name, priority, enabled, entries_count)
    """
    stats = tm_manager.get_stats()

    return [
        TMInfo(
            name=tm_info["name"],
            priority=tm_info["priority"],
            enabled=tm_info["enabled"],
            entries_count=tm_info["entries"],
            file_path=tm_info["file_path"]
        )
        for tm_info in stats["memories"]
    ]


@router.get("/stats")
async def get_tm_stats(tm_manager: MultiTMManager = Depends(get_tm_manager)):
    """
    Statystyki wszystkich TM.

    Returns:
        Dict z pełnymi statystykami
    """
    return tm_manager.get_stats()


@router.post("/upload")
async def upload_tm_file(
    file: UploadFile = File(...),
    priority: int = 4,
    enabled: bool = True,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """
    Upload i dodanie nowej pamięci tłumaczeniowej (TMX lub TBX).

    Args:
        file: Plik TMX/TBX
        priority: Priorytet 1-5 (1 = najwyższy)
        enabled: Czy włączona

    Returns:
        Info o dodanej TM
    """
    # Validate file extension
    if not file.filename.endswith(('.tmx', '.tbx')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only .tmx and .tbx files are allowed."
        )

    # Generate unique name and preserve file extension
    original_ext = Path(file.filename).suffix  # .tmx or .tbx
    tm_name = f"uploaded_{uuid.uuid4().hex[:8]}_{Path(file.filename).stem}"

    # Save file with chunk-based reading and size validation
    file_path = settings.tm_path / f"{tm_name}{original_ext}"
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    max_size = settings.max_tmx_size_mb * 1024 * 1024  # Convert MB to bytes

    try:
        with open(file_path, 'wb') as buffer:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > max_size:
                    # Clean up partial file
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.max_tmx_size_mb}MB, uploaded: {file_size / (1024 * 1024):.2f}MB"
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on any error
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

    # Add to TM Manager
    success = tm_manager.add_tm(
        name=tm_name,
        file_path=str(file_path),
        priority=priority,
        enabled=enabled,
        auto_load=True
    )

    if not success:
        file_path.unlink()  # Clean up
        raise HTTPException(status_code=500, detail="Failed to load TM file")

    # Get info about added TM
    tm = tm_manager.memories[tm_name]

    return {
        "name": tm.name,
        "priority": tm.priority,
        "enabled": tm.enabled,
        "entries_count": len(tm.entries),
        "file_path": tm.file_path,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "message": f"Successfully uploaded TM with {len(tm.entries)} entries ({file_size / (1024 * 1024):.2f}MB)"
    }


@router.put("/{tm_name}")
async def update_tm_settings(
    tm_name: str,
    update: TMUpdateRequest,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """
    Aktualizuje ustawienia TM (priority, enabled).

    Args:
        tm_name: Nazwa TM
        update: Nowe ustawienia

    Returns:
        Zaktualizowane info o TM
    """
    if tm_name not in tm_manager.memories:
        raise HTTPException(status_code=404, detail=f"TM '{tm_name}' not found")

    # Update priority if provided
    if update.priority is not None:
        if not tm_manager.set_priority(tm_name, update.priority):
            raise HTTPException(status_code=400, detail="Invalid priority value")

    # Update enabled status if provided
    if update.enabled is not None:
        if update.enabled:
            tm_manager.enable_tm(tm_name)
        else:
            tm_manager.disable_tm(tm_name)

    # Return updated info
    tm = tm_manager.memories[tm_name]

    return {
        "name": tm.name,
        "priority": tm.priority,
        "enabled": tm.enabled,
        "entries_count": len(tm.entries),
        "file_path": tm.file_path,
        "message": f"Successfully updated TM '{tm_name}'"
    }


@router.delete("/{tm_name}")
async def delete_tm(
    tm_name: str,
    delete_file: bool = False,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """
    Usuwa pamięć tłumaczeniową.

    Args:
        tm_name: Nazwa TM
        delete_file: Czy usunąć też plik TMX (default: False)

    Returns:
        Potwierdzenie usunięcia
    """
    if tm_name not in tm_manager.memories:
        raise HTTPException(status_code=404, detail=f"TM '{tm_name}' not found")

    tm = tm_manager.memories[tm_name]
    file_path = Path(tm.file_path)

    # Remove from manager
    tm_manager.remove_tm(tm_name)

    # Optionally delete file
    if delete_file and file_path.exists():
        file_path.unlink()
        message = f"Deleted TM '{tm_name}' and removed file"
    else:
        message = f"Deleted TM '{tm_name}' (file kept)"

    return {
        "message": message,
        "deleted_tm": tm_name
    }


@router.post("/{tm_name}/enable")
async def enable_tm(
    tm_name: str,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """Włącza pamięć tłumaczeniową."""
    if not tm_manager.enable_tm(tm_name):
        raise HTTPException(status_code=404, detail=f"TM '{tm_name}' not found")

    return {"message": f"Enabled TM '{tm_name}'"}


@router.post("/{tm_name}/disable")
async def disable_tm(
    tm_name: str,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """Wyłącza pamięć tłumaczeniową."""
    if not tm_manager.disable_tm(tm_name):
        raise HTTPException(status_code=404, detail=f"TM '{tm_name}' not found")

    return {"message": f"Disabled TM '{tm_name}'"}


@router.get("/{tm_name}/download")
async def download_tm(
    tm_name: str,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """
    Pobiera plik TMX.

    Args:
        tm_name: Nazwa TM

    Returns:
        Plik TMX do pobrania
    """
    if tm_name not in tm_manager.memories:
        raise HTTPException(status_code=404, detail=f"TM '{tm_name}' not found")

    tm = tm_manager.memories[tm_name]
    file_path = Path(tm.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"TM file not found: {file_path}")

    return FileResponse(
        path=str(file_path),
        media_type="application/xml",
        filename=f"{tm_name}.tmx"
    )


@router.post("/{tm_name}/save")
async def save_tm_to_file(
    tm_name: str,
    tm_manager: MultiTMManager = Depends(get_tm_manager)
):
    """
    Zapisuje TM do pliku TMX (dla runtime updates).

    Args:
        tm_name: Nazwa TM

    Returns:
        Potwierdzenie zapisu
    """
    if not tm_manager.save_tm(tm_name):
        raise HTTPException(status_code=500, detail=f"Failed to save TM '{tm_name}'")

    tm = tm_manager.memories[tm_name]

    return {
        "message": f"Saved TM '{tm_name}' with {len(tm.entries)} entries",
        "file_path": tm.file_path
    }
