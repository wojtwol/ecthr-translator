"""Router dla zarządzania Translation Memory (TMX)."""

import logging
import re
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
from sqlalchemy.orm import Session

from config import settings


def split_into_sentences(text: str) -> list[str]:
    """
    Dzieli tekst na zdania.

    Używa regex do wykrywania granic zdań, uwzględniając:
    - Skróty (Mr., Mrs., Dr., etc.)
    - Numery artykułów (Article 6, art. 3)
    - Cytaty i nawiasy

    Args:
        text: Tekst do podzielenia

    Returns:
        Lista zdań
    """
    if not text or not text.strip():
        return []

    # Wzorce które NIE są końcem zdania
    # Skróty angielskie i polskie
    abbreviations = r'(?:Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|Jr|Sr|vs|etc|i\.e|e\.g|art|Art|par|Par|ust|pkt|lit|zob|por|np|tj|tzw|m\.in|ww|jw|ok|ul|al|pl|os|im)'

    # Najpierw zamień skróty na placeholdery
    placeholder = "<<<ABBR>>>"
    text_processed = re.sub(
        rf'\b({abbreviations})\.',
        rf'\1{placeholder}',
        text,
        flags=re.IGNORECASE
    )

    # Zamień też numery z kropką (np. "1.", "2.") które nie kończą zdania
    text_processed = re.sub(r'(\d+)\.(\s*\d)', rf'\1{placeholder}\2', text_processed)

    # Teraz podziel na zdania
    # Zdanie kończy się: . ! ? po którym następuje spacja i wielka litera lub koniec tekstu
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZŻŹĆĄŚĘŁÓŃ])', text_processed)

    # Przywróć skróty
    sentences = [s.replace(placeholder, '.').strip() for s in sentences]

    # Filtruj puste zdania i bardzo krótkie (mniej niż 10 znaków)
    sentences = [s for s in sentences if s and len(s) >= 10]

    return sentences
from services.tm_manager import TMManager
from db.database import get_db
from db import models

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

        # Check file size (read in chunks to avoid loading entire file in memory)
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        max_size = settings.max_tmx_size_mb * 1024 * 1024

        # Zapisz plik
        tm_path = settings.tm_path
        tm_path.mkdir(parents=True, exist_ok=True)

        file_path = tm_path / file.filename

        with open(file_path, 'wb') as buffer:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > max_size:
                    # Remove partially uploaded file
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.max_tmx_size_mb}MB"
                    )
                buffer.write(chunk)

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


@router.get("/export/{document_id}")
async def export_project_tm(document_id: str, db: Session = Depends(get_db)):
    """
    Eksport pamięci tłumaczeniowej tylko z danego projektu.

    Args:
        document_id: ID dokumentu/projektu
        db: Sesja bazy danych

    Returns:
        Plik TMX z segmentami tylko z tego projektu
    """
    try:
        logger.info(f"Exporting TM for document: {document_id}")

        # Sprawdź czy dokument istnieje
        db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
        if not db_document:
            logger.error(f"Document not found: {document_id}")
            raise HTTPException(status_code=404, detail="Document not found")

        logger.info(f"Found document: {db_document.filename}, status: {db_document.status}")

        # Pobierz wszystkie segmenty z tego projektu
        # First check total segments
        total_segments = (
            db.query(models.Segment)
            .filter(models.Segment.document_id == document_id)
            .count()
        )
        logger.info(f"Total segments in DB for document: {total_segments}")

        segments = (
            db.query(models.Segment)
            .filter(models.Segment.document_id == document_id)
            .filter(models.Segment.target_text.isnot(None))
            .filter(models.Segment.target_text != "")
            .order_by(models.Segment.index)
            .all()
        )

        logger.info(f"Found {len(segments)} translated segments (with non-empty target_text)")

        if not segments:
            logger.error(f"No translated segments found for document: {document_id}")
            # Return more detailed error
            raise HTTPException(
                status_code=404,
                detail=f"No translated segments found. Total segments in DB: {total_segments}. Document status: {db_document.status}"
            )

        # Utwórz nowy TMManager i dodaj segmenty z projektu
        tm_manager = TMManager()
        sentence_count = 0

        for seg in segments:
            if seg.source_text and seg.target_text:
                # Podziel segmenty na zdania (1 segment TM = 1 zdanie)
                source_sentences = split_into_sentences(seg.source_text)
                target_sentences = split_into_sentences(seg.target_text)

                # Jeśli liczba zdań się zgadza, sparuj je 1:1
                if len(source_sentences) == len(target_sentences) and len(source_sentences) > 0:
                    for i, (src_sent, tgt_sent) in enumerate(zip(source_sentences, target_sentences)):
                        metadata = {
                            "document_id": document_id,
                            "document_name": db_document.filename,
                            "segment_index": str(seg.index),
                            "sentence_index": str(i),
                        }
                        tm_manager.add_entry(
                            source=src_sent,
                            target=tgt_sent,
                            metadata=metadata
                        )
                        sentence_count += 1
                else:
                    # Jeśli liczba zdań się nie zgadza, dodaj cały segment
                    # (bezpieczniejsze niż błędne parowanie)
                    metadata = {
                        "document_id": document_id,
                        "document_name": db_document.filename,
                        "segment_index": str(seg.index),
                    }
                    tm_manager.add_entry(
                        source=seg.source_text,
                        target=seg.target_text,
                        metadata=metadata
                    )
                    sentence_count += 1

        logger.info(f"Split {len(segments)} segments into {sentence_count} TM entries (sentences)")

        # Zapisz do pliku TMX
        export_filename = f"tm_export_{document_id}.tmx"
        logger.info(f"Saving TMX to: {settings.tm_path / export_filename}")
        tm_manager.save(export_filename)

        file_path = settings.tm_path / export_filename

        if not file_path.exists():
            logger.error(f"TMX file was not created: {file_path}")
            raise HTTPException(status_code=500, detail="Failed to create TMX file")

        logger.info(f"Exported {len(segments)} segments from document {document_id} to {export_filename}")

        return FileResponse(
            path=str(file_path),
            filename=export_filename,
            media_type="application/xml"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting project TM: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-from-project/{document_id}")
async def update_tm_from_project(document_id: str, db: Session = Depends(get_db)):
    """
    Aktualizacja globalnej pamięci tłumaczeniowej segmentami z danego projektu.

    Args:
        document_id: ID dokumentu/projektu
        db: Sesja bazy danych

    Returns:
        Informacje o liczbie dodanych segmentów
    """
    try:
        # Sprawdź czy dokument istnieje
        db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
        if not db_document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Pobierz wszystkie segmenty z tego projektu
        segments = (
            db.query(models.Segment)
            .filter(models.Segment.document_id == document_id)
            .filter(models.Segment.target_text.isnot(None))
            .order_by(models.Segment.index)
            .all()
        )

        if not segments:
            raise HTTPException(
                status_code=404,
                detail="No translated segments found for this document"
            )

        # Załaduj istniejącą TM
        tm_manager = TMManager()
        existing_count = tm_manager.load()

        # Dodaj nowe segmenty z projektu (podzielone na zdania)
        added_count = 0
        skipped_count = 0

        for seg in segments:
            if seg.source_text and seg.target_text:
                # Podziel segmenty na zdania (1 segment TM = 1 zdanie)
                source_sentences = split_into_sentences(seg.source_text)
                target_sentences = split_into_sentences(seg.target_text)

                # Przygotuj pary do dodania
                if len(source_sentences) == len(target_sentences) and len(source_sentences) > 0:
                    pairs = list(zip(source_sentences, target_sentences))
                else:
                    # Fallback: cały segment jako jedna para
                    pairs = [(seg.source_text, seg.target_text)]

                for src, tgt in pairs:
                    # Sprawdź czy już istnieje dokładne dopasowanie
                    existing = tm_manager.find_exact(src)

                    if existing is None:
                        # Dodaj nowy wpis
                        metadata = {
                            "source": "project",
                            "document_id": document_id,
                            "document_name": db_document.filename,
                        }
                        tm_manager.add_entry(
                            source=src,
                            target=tgt,
                            metadata=metadata
                        )
                        added_count += 1
                    else:
                        skipped_count += 1
                        logger.debug(f"Skipped duplicate sentence: {src[:50]}...")

        # Zapisz zaktualizowaną TM do głównego pliku
        tm_manager.save("ecthr_translator.tmx")

        logger.info(
            f"Updated global TM from document {document_id}: "
            f"added {added_count}, skipped {skipped_count} duplicates"
        )

        return {
            "status": "success",
            "document_id": document_id,
            "existing_entries": existing_count,
            "added": added_count,
            "skipped": skipped_count,
            "total_entries": len(tm_manager.entries),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating TM from project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
