"""
Terminology API routes.
"""
from fastapi import APIRouter, HTTPException
from loguru import logger

from backend.models.api_models import (
    TermSearchRequest,
    TermSearchResponse,
    BatchSearchRequest,
    BatchSearchResponse,
    SourceResult,
    HealthCheckResponse
)
from backend.agents.case_law_researcher import CaseLawResearcher
from backend.config import settings

router = APIRouter(prefix="/api/terminology", tags=["terminology"])

# Global researcher instance
researcher = CaseLawResearcher()


@router.post("/search", response_model=TermSearchResponse)
async def search_term(request: TermSearchRequest):
    """
    Search for a legal term across enabled databases.

    - **term**: The legal term to search for
    - **source_lang**: Source language code (default: en)
    - **target_lang**: Target language code (default: pl)
    - **sources**: Optional list of databases to search (hudoc, curia, iate)
    """
    try:
        logger.info(f"API: Searching term '{request.term}'")

        enriched_term = await researcher.search_term(
            term=request.term,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            sources=request.sources
        )

        # Convert to response model
        return TermSearchResponse(
            term=enriched_term.term,
            best_translation=enriched_term.best_translation,
            best_confidence=enriched_term.best_confidence,
            best_source=enriched_term.best_source,
            all_results=[
                SourceResult(
                    source=r.source,
                    translation=r.translation,
                    confidence=r.confidence,
                    references=r.references,
                    domain=r.domain
                )
                for r in enriched_term.all_results
            ]
        )

    except Exception as e:
        logger.error(f"API: Error searching term '{request.term}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/batch", response_model=BatchSearchResponse)
async def search_batch(request: BatchSearchRequest):
    """
    Search for multiple legal terms in batch.

    - **terms**: List of legal terms to search for
    - **source_lang**: Source language code (default: en)
    - **target_lang**: Target language code (default: pl)
    - **sources**: Optional list of databases to search (hudoc, curia, iate)
    """
    try:
        logger.info(f"API: Batch searching {len(request.terms)} terms")

        enriched_terms = await researcher.search_batch(
            terms=request.terms,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            sources=request.sources
        )

        # Convert to response models
        results = [
            TermSearchResponse(
                term=et.term,
                best_translation=et.best_translation,
                best_confidence=et.best_confidence,
                best_source=et.best_source,
                all_results=[
                    SourceResult(
                        source=r.source,
                        translation=r.translation,
                        confidence=r.confidence,
                        references=r.references,
                        domain=r.domain
                    )
                    for r in et.all_results
                ]
            )
            for et in enriched_terms
        ]

        # Calculate summary
        total_terms = len(results)
        found_translations = sum(1 for r in results if r.best_translation)
        avg_confidence = sum(r.best_confidence for r in results) / total_terms if total_terms > 0 else 0

        summary = {
            "total_terms": total_terms,
            "found_translations": found_translations,
            "average_confidence": round(avg_confidence, 2),
            "success_rate": round(found_translations / total_terms * 100, 1) if total_terms > 0 else 0
        }

        return BatchSearchResponse(
            results=results,
            summary=summary
        )

    except Exception as e:
        logger.error(f"API: Error in batch search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Check health status of all services.
    """
    services = {
        "hudoc": {
            "enabled": settings.hudoc_enabled,
            "mock_mode": settings.hudoc_use_mock
        },
        "curia": {
            "enabled": settings.curia_enabled,
            "mock_mode": settings.curia_use_mock
        },
        "iate": {
            "enabled": settings.iate_enabled,
            "mock_mode": settings.iate_use_mock,
            "has_credentials": bool(settings.iate_username and settings.iate_api_key)
        }
    }

    return HealthCheckResponse(
        status="healthy",
        services=services
    )


@router.get("/sources")
async def get_sources():
    """
    Get list of available terminology sources and their status.
    """
    return {
        "sources": [
            {
                "name": "hudoc",
                "display_name": "HUDOC (ECHR)",
                "enabled": settings.hudoc_enabled,
                "mock_mode": settings.hudoc_use_mock,
                "description": "European Court of Human Rights case law database"
            },
            {
                "name": "curia",
                "display_name": "CURIA (CJEU)",
                "enabled": settings.curia_enabled,
                "mock_mode": settings.curia_use_mock,
                "description": "Court of Justice of the European Union case law via EUR-Lex"
            },
            {
                "name": "iate",
                "display_name": "IATE",
                "enabled": settings.iate_enabled,
                "mock_mode": settings.iate_use_mock,
                "description": "Interactive Terminology for Europe - EU terminology database"
            }
        ]
    }
