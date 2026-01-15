"""Test script for Case Law Research functionality (Sprint 3)."""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.hudoc_client import HUDOCClient
from services.curia_client import CURIAClient
from agents.case_law_researcher import CaseLawResearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_hudoc_client():
    """Test HUDOC Client."""
    logger.info("=" * 60)
    logger.info("TEST 1: HUDOC Client")
    logger.info("=" * 60)

    client = HUDOCClient()

    # Test search for known term
    term = "margin of appreciation"
    logger.info(f"Searching HUDOC for: '{term}'")
    results = await client.search_term(term, max_results=2)

    logger.info(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        logger.info(f"  {i}. {result['term_en']} → {result['term_pl']}")
        logger.info(f"     Confidence: {result['confidence']}")
        logger.info(f"     Cases: {', '.join(result['cases'][:2])}")

    # Test find_term_translation
    logger.info(f"\nFinding translation for: '{term}'")
    translation = await client.find_term_translation(term)
    if translation:
        logger.info(f"  Translation: {translation['term_en']} → {translation['term_pl']}")
    else:
        logger.info("  No translation found")

    # Get stats
    stats = client.get_stats()
    logger.info(f"\nHUDOC Stats: {stats}")

    return results


async def test_curia_client():
    """Test CURIA Client."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: CURIA Client")
    logger.info("=" * 60)

    client = CURIAClient()

    # Test search for known term
    term = "proportionality"
    logger.info(f"Searching CURIA for: '{term}'")
    results = await client.search_term(term, max_results=2)

    logger.info(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        logger.info(f"  {i}. {result['term_en']} → {result['term_pl']}")
        logger.info(f"     Confidence: {result['confidence']}")

    # Test find_term_translation
    logger.info(f"\nFinding translation for: '{term}'")
    translation = await client.find_term_translation(term)
    if translation:
        logger.info(f"  Translation: {translation['term_en']} → {translation['term_pl']}")
    else:
        logger.info("  No translation found")

    # Test multilingual term
    logger.info(f"\nGetting multilingual term for: '{term}'")
    multilingual = await client.get_multilingual_term(term)
    if multilingual:
        logger.info(f"  Multilingual: {multilingual}")
    else:
        logger.info("  No multilingual term found")

    # Get stats
    stats = client.get_stats()
    logger.info(f"\nCURIA Stats: {stats}")

    return results


async def test_case_law_researcher():
    """Test Case Law Researcher."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Case Law Researcher")
    logger.info("=" * 60)

    researcher = CaseLawResearcher()

    # Test with mock terms
    mock_terms = [
        {
            "source_term": "margin of appreciation",
            "proposed_translation": "margines uznania",  # Incorrect translation
            "confidence": 0.7,
            "term_type": "ecthr_specific",
        },
        {
            "source_term": "proportionality",
            "proposed_translation": "proporcjonalność",  # Correct translation
            "confidence": 0.9,
            "term_type": "convention",
        },
        {
            "source_term": "unknown term",
            "proposed_translation": "nieznany termin",
            "confidence": 0.5,
            "term_type": "other",
        },
    ]

    logger.info(f"Enriching {len(mock_terms)} terms...")
    enriched_terms = await researcher.enrich_terms(mock_terms)

    logger.info(f"\nEnriched {len(enriched_terms)} terms:")
    for i, term in enumerate(enriched_terms, 1):
        logger.info(f"\n{i}. {term['source_term']}")
        logger.info(f"   Proposed: {term['proposed_translation']}")

        if "official_translation" in term:
            logger.info(f"   Official: {term['official_translation']}")
            logger.info(f"   Source: {term['translation_source']}")
            logger.info(f"   Confidence: {term['translation_confidence']}")

            if term.get("has_alternative"):
                logger.info(f"   ⚠️  Alternative found: {term['alternative_explanation']}")

        ref_count = term.get("reference_count", 0)
        logger.info(f"   References: {ref_count}")

        if ref_count > 0:
            refs = term.get("case_law_references", [])
            for j, ref in enumerate(refs[:2], 1):
                logger.info(f"     {j}. {ref['source'].upper()}: {ref['term_pl']}")

    # Test search_term
    logger.info("\n" + "-" * 60)
    logger.info("Testing search_term method")

    term = "just satisfaction"
    logger.info(f"Searching for: '{term}'")
    results = await researcher.search_term(term)
    logger.info(f"Found {len(results)} results across all sources")

    # Search in specific source
    logger.info(f"\nSearching for '{term}' in HUDOC only")
    hudoc_results = await researcher.search_term(term, source="hudoc")
    logger.info(f"Found {len(hudoc_results)} results in HUDOC")

    # Get stats
    stats = researcher.get_stats()
    logger.info(f"\nCase Law Researcher Stats:")
    logger.info(f"  HUDOC: {stats['hudoc']}")
    logger.info(f"  CURIA: {stats['curia']}")

    return enriched_terms


async def test_integration():
    """Test integration with Term Extractor."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Integration Test")
    logger.info("=" * 60)

    try:
        from agents.term_extractor import TermExtractor

        # Create Term Extractor with case law research enabled
        logger.info("Creating Term Extractor with case law research enabled...")
        extractor = TermExtractor(enable_case_law_research=True)

        logger.info(f"Case law research enabled: {extractor.enable_case_law_research}")

        # Verify that researcher can be initialized
        researcher = extractor._get_case_law_researcher()
        if researcher:
            logger.info("✓ Case Law Researcher successfully initialized")
            stats = researcher.get_stats()
            logger.info(f"  Stats: {stats}")
        else:
            logger.warning("✗ Case Law Researcher not initialized")

        logger.info("\n✓ Integration test passed")

    except Exception as e:
        logger.error(f"✗ Integration test failed: {e}", exc_info=True)


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("CASE LAW RESEARCH TEST SUITE - SPRINT 3")
    logger.info("=" * 60)

    try:
        # Test individual clients
        await test_hudoc_client()
        await test_curia_client()

        # Test Case Law Researcher
        await test_case_law_researcher()

        # Test integration
        await test_integration()

        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\nTest suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
