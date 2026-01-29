"""Multi-TM Manager - zarządza wieloma pamięciami tłumaczeniowymi z priorytetami."""

import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from lxml import etree
from rapidfuzz import fuzz
from dataclasses import dataclass
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TMEntry:
    """Wpis w pamięci tłumaczeniowej."""
    source: str
    target: str
    source_lang: str = "en"
    target_lang: str = "pl"
    metadata: Optional[Dict[str, Any]] = None
    tm_name: Optional[str] = None  # Which TM this entry came from

    def __repr__(self):
        return f"TMEntry('{self.source[:30]}...' -> '{self.target[:30]}...' from {self.tm_name})"


@dataclass
class TranslationMemory:
    """Pojedyncza pamięć tłumaczeniowa z metadata."""
    name: str
    file_path: str
    priority: int  # 1-5, gdzie 1 = najwyższy priorytet
    enabled: bool = True
    entries: List[TMEntry] = None

    def __post_init__(self):
        if self.entries is None:
            self.entries = []

    def __repr__(self):
        status = "✓" if self.enabled else "✗"
        return f"TM({status} {self.name}, priority={self.priority}, {len(self.entries)} entries)"


class MultiTMManager:
    """Zarządza wieloma pamięciami tłumaczeniowymi z priorytetami."""

    def __init__(self, tm_path: Optional[Path] = None):
        """
        Inicjalizacja Multi-TM Manager.

        Args:
            tm_path: Ścieżka do katalogu z plikami TMX
        """
        self.tm_path = tm_path or settings.tm_path
        self.memories: Dict[str, TranslationMemory] = {}
        logger.info(f"Multi-TM Manager initialized with path: {self.tm_path}")

    def add_tm(
        self,
        name: str,
        file_path: str,
        priority: int = 5,
        enabled: bool = True,
        auto_load: bool = True
    ) -> bool:
        """
        Dodaje nową pamięć tłumaczeniową.

        Args:
            name: Nazwa TM (unikalna)
            file_path: Ścieżka do pliku TMX
            priority: Priorytet 1-5 (1 = najwyższy)
            enabled: Czy TM jest włączona
            auto_load: Czy automatycznie załadować wpisy

        Returns:
            True jeśli sukces
        """
        if name in self.memories:
            logger.warning(f"TM '{name}' already exists")
            return False

        if priority < 1 or priority > 5:
            logger.error(f"Invalid priority {priority}. Must be 1-5")
            return False

        # Create TM object
        tm = TranslationMemory(
            name=name,
            file_path=file_path,
            priority=priority,
            enabled=enabled,
            entries=[]
        )

        # Load entries if requested
        if auto_load:
            try:
                count = self._load_tm_file(tm)
                logger.info(f"Loaded {count} entries from TM '{name}'")
            except Exception as e:
                logger.error(f"Failed to load TM '{name}': {e}")
                return False

        self.memories[name] = tm
        logger.info(f"Added TM: {tm}")
        return True

    def remove_tm(self, name: str) -> bool:
        """Usuwa pamięć tłumaczeniową."""
        if name not in self.memories:
            logger.warning(f"TM '{name}' not found")
            return False

        del self.memories[name]
        logger.info(f"Removed TM '{name}'")
        return True

    def enable_tm(self, name: str) -> bool:
        """Włącza pamięć tłumaczeniową."""
        if name not in self.memories:
            logger.warning(f"TM '{name}' not found")
            return False

        self.memories[name].enabled = True
        logger.info(f"Enabled TM '{name}'")
        return True

    def disable_tm(self, name: str) -> bool:
        """Wyłącza pamięć tłumaczeniową."""
        if name not in self.memories:
            logger.warning(f"TM '{name}' not found")
            return False

        self.memories[name].enabled = False
        logger.info(f"Disabled TM '{name}'")
        return True

    def set_priority(self, name: str, priority: int) -> bool:
        """Ustawia priorytet pamięci tłumaczeniowej."""
        if name not in self.memories:
            logger.warning(f"TM '{name}' not found")
            return False

        if priority < 1 or priority > 5:
            logger.error(f"Invalid priority {priority}. Must be 1-5")
            return False

        self.memories[name].priority = priority
        logger.info(f"Set priority of TM '{name}' to {priority}")
        return True

    def get_enabled_tms_by_priority(self) -> List[TranslationMemory]:
        """
        Zwraca listę włączonych TM posortowanych po priorytecie.

        Returns:
            Lista TM (priorytet 1 na początku, 5 na końcu)
        """
        enabled = [tm for tm in self.memories.values() if tm.enabled]
        # Sort by priority (1 = highest, so ascending order)
        sorted_tms = sorted(enabled, key=lambda tm: tm.priority)
        return sorted_tms

    def find_exact(self, source_text: str) -> Optional[TMEntry]:
        """
        Szuka dokładnego dopasowania w TM (w kolejności priorytetów).

        Args:
            source_text: Tekst źródłowy

        Returns:
            TMEntry jeśli znaleziono (z TM o najwyższym priorytecie)
        """
        source_normalized = source_text.strip().lower()

        # Search in priority order
        for tm in self.get_enabled_tms_by_priority():
            for entry in tm.entries:
                if entry.source.strip().lower() == source_normalized:
                    logger.debug(f"Exact match found in TM '{tm.name}' (priority {tm.priority}): {entry}")
                    return entry

        return None

    def find_prefix(self, source_text: str) -> Optional[Tuple[TMEntry, str]]:
        """
        Szuka wpisu TM który jest prefiksem terminu (w kolejności priorytetów).

        Args:
            source_text: Tekst źródłowy (np. "Article 44 § 2")

        Returns:
            Tuple (TMEntry, translated_term) jeśli znaleziono
        """
        source_normalized = source_text.strip().lower()

        # Search in priority order
        for tm in self.get_enabled_tms_by_priority():
            # Sort entries by length (longest first) for best match
            sorted_entries = sorted(tm.entries, key=lambda e: len(e.source), reverse=True)

            for entry in sorted_entries:
                entry_normalized = entry.source.strip().lower()

                if source_normalized.startswith(entry_normalized + " "):
                    # Found prefix match
                    suffix = source_text[len(entry.source):].strip()
                    translated_term = f"{entry.target} {suffix}".strip()

                    logger.info(
                        f"Prefix match in TM '{tm.name}' (priority {tm.priority}): "
                        f"'{entry.source}' → '{entry.target}' | Full: '{source_text}' → '{translated_term}'"
                    )
                    return (entry, translated_term)

        return None

    def find_fuzzy(
        self,
        source_text: str,
        threshold: Optional[float] = None
    ) -> List[Tuple[TMEntry, float]]:
        """
        Szuka fuzzy dopasowań w TM (we wszystkich włączonych TM).

        Args:
            source_text: Tekst źródłowy
            threshold: Minimalny próg podobieństwa (0.0-1.0)

        Returns:
            Lista tupli (TMEntry, similarity_score) posortowana malejąco
        """
        threshold = threshold or settings.tm_fuzzy_threshold
        matches = []

        # Search across all enabled TMs
        for tm in self.get_enabled_tms_by_priority():
            for entry in tm.entries:
                similarity = fuzz.ratio(source_text.lower(), entry.source.lower()) / 100.0

                if similarity >= threshold:
                    matches.append((entry, similarity))

        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        matches = matches[:settings.tm_max_results]

        logger.debug(f"Found {len(matches)} fuzzy matches above {threshold:.2f} threshold")

        return matches

    def add_entry(
        self,
        source: str,
        target: str,
        tm_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TMEntry:
        """
        Dodaje nowy wpis do pamięci tłumaczeniowej.

        Args:
            source: Tekst źródłowy
            target: Tekst docelowy
            tm_name: Nazwa TM do której dodać (domyślnie "default")
            metadata: Metadane

        Returns:
            Utworzony TMEntry
        """
        # Ensure default TM exists
        if tm_name not in self.memories:
            logger.warning(f"TM '{tm_name}' not found, creating default TM")
            self.add_tm(
                name=tm_name,
                file_path=str(self.tm_path / f"{tm_name}.tmx"),
                priority=5,  # Lowest priority for runtime entries
                enabled=True,
                auto_load=False
            )

        entry = TMEntry(
            source=source,
            target=target,
            metadata=metadata or {},
            tm_name=tm_name
        )

        self.memories[tm_name].entries.append(entry)
        logger.debug(f"Added entry to TM '{tm_name}': {entry}")

        return entry

    def load_all_from_directory(self) -> int:
        """
        Ładuje wszystkie pliki TMX i TBX z katalogu z automatycznym priorytetem.

        Priority assignment:
        - Files matching 'legal_*', 'court_*' → priority 1 (highest)
        - Files matching 'ecthr_*', 'cjeu_*' → priority 2
        - Files matching 'project_*' → priority 3
        - Other files → priority 4
        - Runtime files ('tm_updated_*') → priority 5 (lowest)

        Returns:
            Łączna liczba załadowanych wpisów
        """
        if not self.tm_path.exists():
            logger.warning(f"TM directory does not exist: {self.tm_path}")
            return 0

        # Load both TMX and TBX files
        tm_files = list(self.tm_path.glob("*.tmx")) + list(self.tm_path.glob("*.tbx"))

        if not tm_files:
            logger.warning(f"No TMX/TBX files found in {self.tm_path}")
            return 0

        total_loaded = 0

        for file_path in tm_files:
            # Determine priority based on filename
            filename = file_path.stem.lower()

            if filename.startswith(('legal_', 'court_', 'polish_')):
                priority = 1  # Legal terminology - highest priority
            elif filename.startswith(('ecthr_', 'cjeu_', 'hudoc_', 'curia_')):
                priority = 2  # Court-specific terminology
            elif filename.startswith('project_'):
                priority = 3  # Project-specific
            elif filename.startswith('tm_updated_'):
                priority = 5  # Runtime updates - lowest priority
            else:
                priority = 4  # General terminology

            # Add TM
            success = self.add_tm(
                name=file_path.stem,
                file_path=str(file_path),
                priority=priority,
                enabled=True,
                auto_load=True
            )

            if success:
                total_loaded += len(self.memories[file_path.stem].entries)

        logger.info(f"Loaded {total_loaded} total entries from {len(self.memories)} TM files")

        return total_loaded

    def _load_tm_file(self, tm: TranslationMemory) -> int:
        """
        Ładuje wpisy z pliku TMX lub TBX do TM.

        Args:
            tm: TranslationMemory object

        Returns:
            Liczba załadowanych wpisów
        """
        file_path = Path(tm.file_path)

        if not file_path.exists():
            logger.warning(f"TM file not found: {file_path}")
            return 0

        # Determine file type
        is_tbx = file_path.suffix.lower() == '.tbx'

        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()

            if is_tbx:
                return self._parse_tbx(tm, root)
            else:
                return self._parse_tmx(tm, root)

        except Exception as e:
            logger.error(f"Error loading TM file {file_path}: {e}")
            return 0

    def _parse_tmx(self, tm: TranslationMemory, root) -> int:
        """
        Parsuje plik TMX.

        Args:
            tm: TranslationMemory object
            root: XML root element

        Returns:
            Liczba załadowanych wpisów
        """
        count = 0
        for tu in root.findall(".//tu"):
            tuvs = tu.findall("tuv")
            if len(tuvs) < 2:
                continue

            # Find EN and PL entries
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
                    # Extract metadata
                    metadata = {}
                    for prop in tu.findall("prop"):
                        prop_type = prop.get("type")
                        if prop_type and prop.text:
                            metadata[prop_type] = prop.text

                    entry = TMEntry(
                        source=source_seg.text.strip(),
                        target=target_seg.text.strip(),
                        metadata=metadata,
                        tm_name=tm.name
                    )
                    tm.entries.append(entry)
                    count += 1

        return count

    def _parse_tbx(self, tm: TranslationMemory, root) -> int:
        """
        Parsuje plik TBX (TermBase eXchange).

        Format TBX może mieć różne struktury:
        1. Podstawowy TBX:
           <termEntry>
             <langSet xml:lang="en"><tig><term>English term</term></tig></langSet>
             <langSet xml:lang="pl"><tig><term>Polish term</term></tig></langSet>
           </termEntry>

        2. SDL MultiTerm TBX:
           <conceptEntry>
             <languageEntry><termEntry><term>English term</term></termEntry></languageEntry>
           </conceptEntry>

        Args:
            tm: TranslationMemory object
            root: XML root element

        Returns:
            Liczba załadowanych wpisów
        """
        count = 0

        # Log root element info for debugging
        logger.info(f"TBX root element: {root.tag}, children: {len(list(root))}")

        # Try standard TBX format first
        term_entries = root.findall(".//{*}termEntry")
        logger.info(f"Found {len(term_entries)} termEntry elements")

        for term_entry in term_entries:
            source_term = None
            target_term = None
            metadata = {}

            # Extract metadata from termEntry level
            for descrip in term_entry.findall(".//{*}descrip"):
                descrip_type = descrip.get("type")
                if descrip_type and descrip.text:
                    metadata[descrip_type] = descrip.text

            # Find language sets
            lang_sets = term_entry.findall(".//{*}langSet")
            logger.debug(f"termEntry has {len(lang_sets)} langSet elements")

            for lang_set in lang_sets:
                # Try different lang attribute formats
                lang = (
                    lang_set.get("{http://www.w3.org/XML/1998/namespace}lang") or
                    lang_set.get("lang") or
                    ""
                ).lower()

                logger.debug(f"langSet lang attribute: '{lang}'")

                # Find term within tig or ntig
                term_elem = lang_set.find(".//{*}tig/{*}term")
                if term_elem is None:
                    term_elem = lang_set.find(".//{*}ntig/{*}termGrp/{*}term")
                if term_elem is None:
                    term_elem = lang_set.find(".//{*}term")

                if term_elem is not None and term_elem.text:
                    term_text = term_elem.text.strip()
                    logger.debug(f"Found term '{term_text}' for lang '{lang}'")

                    if "en" in lang or lang == "en-gb" or lang == "en-us":
                        source_term = term_text
                    elif "pl" in lang:
                        target_term = term_text

            # Add entry if both languages found
            if source_term and target_term:
                entry = TMEntry(
                    source=source_term,
                    target=target_term,
                    metadata=metadata,
                    tm_name=tm.name
                )
                tm.entries.append(entry)
                count += 1
                logger.debug(f"Added TBX entry: '{source_term}' -> '{target_term}'")
            else:
                logger.warning(f"Incomplete termEntry: source={source_term}, target={target_term}")

        # If no entries found, try SDL MultiTerm format
        if count == 0:
            logger.info("No entries in standard TBX format, trying SDL MultiTerm format")
            concept_entries = root.findall(".//{*}conceptEntry")
            logger.info(f"Found {len(concept_entries)} conceptEntry elements")

            # Try to extract first few entries to see structure
            for i, concept in enumerate(concept_entries[:3]):
                logger.info(f"Sample conceptEntry {i}: {etree.tostring(concept, encoding='unicode')[:200]}")

        logger.info(f"Parsed TBX file: {count} term entries")
        return count

    def save_tm(self, tm_name: str, output_path: Optional[str] = None) -> bool:
        """
        Zapisuje TM do pliku TMX.

        Args:
            tm_name: Nazwa TM do zapisania
            output_path: Opcjonalna ścieżka wyjściowa

        Returns:
            True jeśli sukces
        """
        if tm_name not in self.memories:
            logger.error(f"TM '{tm_name}' not found")
            return False

        tm = self.memories[tm_name]
        output_file = Path(output_path) if output_path else Path(tm.file_path)

        try:
            # Create TMX structure
            tmx = etree.Element("tmx", version="1.4")

            header = etree.SubElement(
                tmx,
                "header",
                creationtool="ECTHR-Translator",
                creationtoolversion="2.0",
                segtype="sentence",
                adminlang="en",
                srclang="en",
                datatype="plaintext",
            )

            body = etree.SubElement(tmx, "body")

            # Add entries
            for entry in tm.entries:
                tu = etree.SubElement(body, "tu")

                # Source
                source_tuv = etree.SubElement(tu, "tuv")
                source_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                source_seg = etree.SubElement(source_tuv, "seg")
                source_seg.text = entry.source

                # Target
                target_tuv = etree.SubElement(tu, "tuv")
                target_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", "pl")
                target_seg = etree.SubElement(target_tuv, "seg")
                target_seg.text = entry.target

                # Metadata
                if entry.metadata:
                    for key, value in entry.metadata.items():
                        prop = etree.SubElement(tu, "prop", type=key)
                        prop.text = str(value)

            # Save
            tree = etree.ElementTree(tmx)
            tree.write(
                str(output_file),
                pretty_print=True,
                xml_declaration=True,
                encoding="UTF-8",
            )

            logger.info(f"Saved TM '{tm_name}' with {len(tm.entries)} entries to {output_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving TM '{tm_name}': {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki wszystkich TM.

        Returns:
            Słownik ze statystykami
        """
        return {
            "total_memories": len(self.memories),
            "enabled_memories": len([tm for tm in self.memories.values() if tm.enabled]),
            "total_entries": sum(len(tm.entries) for tm in self.memories.values()),
            "memories": [
                {
                    "name": tm.name,
                    "priority": tm.priority,
                    "enabled": tm.enabled,
                    "entries": len(tm.entries),
                    "file_path": tm.file_path,
                }
                for tm in sorted(self.memories.values(), key=lambda t: t.priority)
            ]
        }
