"""Test script for CitationDetector - safe to run without affecting production."""

import sys
import logging
from agents.citation_detector import CitationDetector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Sample text with various citation formats
SAMPLE_TEXT = """
The Court notes that in Smith v. United Kingdom, the applicant complained
about the length of proceedings. In Case of Müller and Others v. Austria,
similar issues were raised.

The Grand Chamber judgment in [GC] López Ribalda and Others v. Spain established
important principles. Reference was also made to Jones v. UK, no. 12345/67.

Regarding EU law, see Case C-555/07 (Kücükdeveci) and the Joined Cases
C-411/10 and C-493/10. The Court in Case C-144/04 (Mangold) held that...

In the present case, as in Smith v. United Kingdom, the Court must assess...
"""

def test_citation_detection():
    """Test basic citation detection functionality."""
    print("=" * 80)
    print("CITATION DETECTOR TEST")
    print("=" * 80)

    # Initialize detector
    detector = CitationDetector()

    # Detect citations
    print("\n📄 Analyzing sample text for citations...\n")
    citations = detector.detect_citations(SAMPLE_TEXT)

    # Print summary
    summary = detector.get_summary(citations)
    print(summary)

    # Detailed output
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)

    if citations["hudoc"]:
        print("\n⚖️ HUDOC Citations (detailed):")
        for cite in citations["hudoc"]:
            print(f"\n  Citation: {cite['citation']}")
            print(f"  Position: {cite['position']}")
            if 'applicant' in cite:
                print(f"  Applicant: {cite['applicant']}")
            if 'respondent' in cite:
                print(f"  Respondent: {cite['respondent']}")
            print(f"  Context: {cite['context'][:100]}...")

    if citations["curia"]:
        print("\n🏛️ CURIA Citations (detailed):")
        for cite in citations["curia"]:
            print(f"\n  Citation: {cite['citation']}")
            print(f"  Position: {cite['position']}")
            if 'case_number' in cite:
                print(f"  Case Number: {cite['case_number']}")
            print(f"  Context: {cite['context'][:100]}...")

    # Test results
    print("\n" + "=" * 80)
    print("TEST RESULTS")
    print("=" * 80)

    expected_hudoc = 4  # Adjust based on patterns
    expected_curia = 4  # Adjust based on patterns

    print(f"\nHUDOC citations found: {len(citations['hudoc'])}")
    print(f"CURIA citations found: {len(citations['curia'])}")
    print(f"Total citations: {citations['total']}")

    if citations['total'] > 0:
        print("\n✅ SUCCESS: Citations detected!")
        return 0
    else:
        print("\n❌ FAILURE: No citations detected!")
        return 1

if __name__ == "__main__":
    sys.exit(test_citation_detection())
