"""TM Manager - zarządza pamięcią tłumaczeniową (TMX)."""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from lxml import etree
from rapidfuzz import fuzz
from config import settings

logger = logging.getLogger(__name__)


class TMEntry:
    """Wpis w pamięci tłumaczeniowej."""

    def __init__(
        self,
        source: str,
        target: str,
        source_lang: str = "en",
        target_lang: str = "pl",
        metadata: Optional[Dict[str, str]] = None,
    ):
        self.source = source
        self.target = target
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.metadata = metadata or {}

    def __repr__(self):
        return f"TMEntry('{self.source[:30]}...' -> '{self.target[:30]}...')"


class TMManager:
    """Zarządza pamięcią tłumaczeniową."""

    def __init__(self, tm_path: Optional[Path] = None):
        """
        Inicjalizacja TM Manager.

        Args:
            tm_path: Ścieżka do katalogu z plikami TMX
        """
        self.tm_path = tm_path or settings.tm_path
        self.entries: List[TMEntry] = []
        logger.info(f"TM Manager initialized with path: {self.tm_path}")

    def load(self, filename: Optional[str] = None) -> int:
        """
        Ładuje pamięć tłumaczeniową z pliku TMX.

        Args:
            filename: Nazwa pliku TMX (opcjonalne, ładuje wszystkie jeśli None)

        Returns:
            Liczba załadowanych wpisów
        """
        if filename:
            files = [self.tm_path / filename]
        else:
            # Załaduj wszystkie pliki TMX
            files = list(self.tm_path.glob("*.tmx"))

        if not files:
            logger.warning(f"No TMX files found in {self.tm_path}")
            return 0

        total_loaded = 0
        for file_path in files:
            try:
                count = self._load_tmx_file(file_path)
                total_loaded += count
                logger.info(f"Loaded {count} entries from {file_path.name}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        logger.info(f"Total loaded: {total_loaded} TM entries")
        return total_loaded

    def _load_tmx_file(self, file_path: Path) -> int:
        """
        Ładuje pojedynczy plik TMX.

        Args:
            file_path: Ścieżka do pliku TMX

        Returns:
            Liczba załadowanych wpisów
        """
        tree = etree.parse(str(file_path))
        root = tree.getroot()

        # Namespace dla TMX
        ns = {"tmx": "http://www.lisa.org/tmx14"}

        count = 0
        for tu in root.findall(".//tu"):
            tuvs = tu.findall("tuv")
            if len(tuvs) < 2:
                continue

            # Zakładamy EN->PL
            source_tuv = None
            target_tuv = None

            for tuv in tuvs:
                lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower()
                if "en" in lang:
                    source_tuv = tuv
                elif "pl" in lang:
                    target_tuv = tuv

            if source_tuv is not None and target_tuv is not None:
                source_seg = source_tuv.find("seg")
                target_seg = target_tuv.find("seg")

                if (
                    source_seg is not None
                    and target_seg is not None
                    and source_seg.text
                    and target_seg.text
                ):
                    # Ekstrahuj metadata z props
                    metadata = {}
                    for prop in tu.findall("prop"):
                        prop_type = prop.get("type")
                        if prop_type and prop.text:
                            metadata[prop_type] = prop.text

                    entry = TMEntry(
                        source=source_seg.text.strip(),
                        target=target_seg.text.strip(),
                        metadata=metadata,
                    )
                    self.entries.append(entry)
                    count += 1

        return count

    def find_exact(self, source_text: str) -> Optional[TMEntry]:
        """
        Szuka dokładnego dopasowania w TM.

        Args:
            source_text: Tekst źródłowy

        Returns:
            TMEntry jeśli znaleziono, None w przeciwnym razie
        """
        source_normalized = source_text.strip().lower()

        for entry in self.entries:
            if entry.source.strip().lower() == source_normalized:
                logger.debug(f"Exact match found: {entry}")
                return entry

        return None

    def find_fuzzy(
        self, source_text: str, threshold: Optional[float] = None
    ) -> List[tuple[TMEntry, float]]:
        """
        Szuka fuzzy dopasowań w TM.

        Args:
            source_text: Tekst źródłowy
            threshold: Minimalny próg podobieństwa (0.0-1.0)

        Returns:
            Lista tupli (TMEntry, similarity_score) posortowana malejąco
        """
        threshold = threshold or settings.tm_fuzzy_threshold
        matches = []

        for entry in self.entries:
            similarity = fuzz.ratio(source_text.lower(), entry.source.lower()) / 100.0

            if similarity >= threshold:
                matches.append((entry, similarity))

        # Sortuj malejąco po podobieństwie
        matches.sort(key=lambda x: x[1], reverse=True)

        # Ogranicz do max_results
        matches = matches[: settings.tm_max_results]

        logger.debug(
            f"Found {len(matches)} fuzzy matches above {threshold:.2f} threshold"
        )

        return matches

    def add_entry(
        self, source: str, target: str, metadata: Optional[Dict[str, str]] = None
    ) -> TMEntry:
        """
        Dodaje nowy wpis do pamięci tłumaczeniowej.

        Args:
            source: Tekst źródłowy
            target: Tekst docelowy
            metadata: Metadane

        Returns:
            Utworzony TMEntry
        """
        entry = TMEntry(source=source, target=target, metadata=metadata)
        self.entries.append(entry)
        logger.debug(f"Added new TM entry: {entry}")
        return entry

    def save(self, filename: str = "ecthr_translator.tmx") -> None:
        """
        Zapisuje pamięć tłumaczeniową do pliku TMX.

        Args:
            filename: Nazwa pliku wyjściowego
        """
        output_path = self.tm_path / filename

        # Utwórz root element
        tmx = etree.Element(
            "tmx",
            version="1.4",
        )

        # Header
        header = etree.SubElement(
            tmx,
            "header",
            creationtool="ECTHR-Translator",
            creationtoolversion="1.0",
            segtype="sentence",
            adminlang="en",
            srclang="en",
            datatype="plaintext",
        )

        # Body
        body = etree.SubElement(tmx, "body")

        # Dodaj wszystkie wpisy
        for entry in self.entries:
            tu = etree.SubElement(body, "tu")

            # Source tuv
            source_tuv = etree.SubElement(tu, "tuv")
            source_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            source_seg = etree.SubElement(source_tuv, "seg")
            source_seg.text = entry.source

            # Target tuv
            target_tuv = etree.SubElement(tu, "tuv")
            target_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", "pl")
            target_seg = etree.SubElement(target_tuv, "seg")
            target_seg.text = entry.target

            # Metadata jako props
            for key, value in entry.metadata.items():
                prop = etree.SubElement(tu, "prop", type=key)
                prop.text = value

        # Zapisz do pliku
        tree = etree.ElementTree(tmx)
        tree.write(
            str(output_path),
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

        logger.info(f"Saved {len(self.entries)} entries to {output_path}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki pamięci tłumaczeniowej.

        Returns:
            Słownik ze statystykami
        """
        return {
            "total_entries": len(self.entries),
            "sources": {
                "tm": len([e for e in self.entries if "source" not in e.metadata]),
                "hudoc": len([e for e in self.entries if e.metadata.get("source") == "hudoc"]),
                "curia": len([e for e in self.entries if e.metadata.get("source") == "curia"]),
            },
        }
