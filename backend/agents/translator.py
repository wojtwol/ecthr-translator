"""Translator - tłumaczy segmenty z wykorzystaniem terminologii."""

import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)


class Translator:
    """Tłumaczy segmenty orzeczeń ETPCz."""

    TRANSLATOR_PROMPT = """Jesteś profesjonalnym tłumaczem prawniczym specjalizującym się w orzeczeniach Europejskiego Trybunału Praw Człowieka (ETPCz).

=== ZASADY FUNDAMENTALNE ===

CRITICAL: Translate ONLY what is in the source text. DO NOT add, invent, or infer any information.

1. KONWENCJA O OCHRONIE PRAW CZŁOWIEKA - cytować z urzędowego tłumaczenia, NIE tłumaczyć samodzielnie
2. WIERNOŚĆ ŹRÓDŁU - stosować odpowiednio sformułowania z tłumaczenia Konwencji przy tłumaczeniu argumentacji prawnej zawartej w wyroku (np. gdy mowa o "provided by the law" przy ocenie ingerencji, jest to odpowiednik zwrotu z Konwencji, który jest w niej tłumaczony z reguły jako "przewidziana/y/określona/y przez ustawę")
3. UKŁAD TEKSTU - najlepiej nie zmieniać układu tekstu Trybunału, tj. nagłówków, czcionek, marginesów itp.
4. FORMATOWANIE GRAFICZNE - najlepiej tłumaczyć w oparciu o szatę graficzną oryginału, stosować strong tytułową jak w wyroku
5. FORMATOWANIE TRYBUNAŁOWE - warto utrzymywać formatowanie Trybunałowe, np. co do wielkości czcionki, sposobu cytowania przez Trybunał artykułów Konwencji czy też innych wyroków
6. MIEJSCA OPUSZCZONE - miejsca opuszczone w tłumaczeniu wyraźnie sygnalizować (tak by było jasne, co zostało opuszczone)

=== REGUŁY TECHNICZNE ===

7. ŁAMANIE LINII - nie stosować wyjustowania za pomocą SHIFT-ENTER, gdyż tekst będzie się rozjeżdżał w różnych przeglądarkach internetowych, w razie potrzeby stosować CTRL+SHIFT+Spacja
8. ŹRÓDŁA FRAGMENTÓW - gdy wprowadzamy fragmenty streszczeń Trybunału – należy zaznaczyć ten fakt oraz źródło
9. TRYB CYTOWANIA - sugerujemy zachować sposób przywoływania przez Trybunał swych wcześniejszych orzeczeń, w tym umieszczania tych odwołań w nawiasach, a także przy odesłaniach do innych fragmentów wyroku – zamiast słowa "ustęp", proponujemy używać słowo "paragraf" (np. zob. paragraf 5), gdy odesłanie jest w ramach danego wyroku, i "§", gdy Trybunał cytuje swe wcześniejsze wyroki
10. REGULAMIN TRYBUNAŁU - stosować tłumaczenie Regulaminu Trybunału w wersji udostępnionej ostatnio przez MSZ
11. IMIONA I NAZWISKA - nie dokonywać spolszczenia nazwisk i imion skarżących, ewentualnie podać obie wersje. W miarę możliwości należy odmieniać przez przypadki obce imiona i nazwiska (zgodnie z zasadami polskiej gramatyki)
12. WYRAŻENIA OBCE - wyrażenia w obcym języku, np. łacińskie – zapis kursywą, stosowanie kursywy także w odniesieniu do nazw skarg do ETPCz
13. "OTHERS" - w nazwie skargi "Inni" (Others) pisać wielką literą: np. X i Inni p. Polsce
14. ZNAKI CUDZYSŁOWU - poprawiać zapis znaków cudzysłowu na format polski: „"
15. NAZWY PAŃSTW - stosować oficjalne nazwy państw
16. DOSTĘPNE TŁUMACZENIA - sprawdzić w internecie, czy są dostępne tłumaczenia różnych powoływanych w tekście konwencji, zaleceń, nazw komitetów itp. i stosować nazewnictwo zgodne z tymi tłumaczeniami

=== REGUŁY ZAPISU AKTÓW PRAWNYCH ===

17. JEDNOLITY ZAPIS ZWROTÓW - w całym tekście stosować jednolity zapis zwrotów: r.; art., ust., lit. a (np. art. 35 ust. 1 lit. a Konwencji), Reguła i § (np. Reguła 59 § 1 Regulaminu Trybunału), opinia odrębna /nie stosować: roku, artykuł, ustęp, lit. a), zdanie odrębne/

18. TYTUŁY AKTÓW PRAWNYCH - zapisy tytułów aktów prawnych zgodnie z Zasadami Techniki Prawodawczej, np. ustawa i rozporządzenie z małej litery, Konwencja o ochronie praw człowieka i podstawowych wolności (z dużej litery tylko "Konwencja"), Kodeks cywilny, itp.

19. NUMERACJA AUTOMATYCZNA - uwaga – teksty Trybunału zawierają automatycznie aktualizowaną numerację. W przypadku, gdy niektóre paragrafy są pomijane lub niektóre numery paragrafów wstawiane są ręcznie, może to powodować "posypanie się numeracji". Nie należy też poprawiać numerów na tekście zawierającym pola aktywne, pole należy wykasować i całość wpisać ręcznie (aby zobaczyć pola aktywne – nacisnąć Alt + F9). Zalecamy wpisywać wszystkie numery ręcznie.

20. JEDNOLITOŚĆ ZAPISÓW - warto na koniec przejrzeć całe tłumaczenie pod kątem jednolitości stosowanych zapisów

=== CYTOWANIA ORZECZEŃ ===

TSUE/CJEU (Trybunał Sprawiedliwości UE):
- NIE dodawać "nr" przed sygnaturą sprawy
✓ POPRAWNIE: "w połączonych sprawach A.K. i inni (C-585/18, C-624/18 i C-625/18)"
✗ BŁĘDNIE: "w połączonych sprawach A.K. i inni (nr C-585/18, nr C-624/18 i nr C-625/18)"
- Format: Sama sygnatura typu "C-123/45" bez "nr"

ETPCz/ECtHR (Europejski Trybunał Praw Człowieka):
- ZAWSZE używać formatu "skarga nr 00000/00"
✓ POPRAWNIE: "w sprawie Reczkowicz przeciwko Polsce (skarga nr 43447/19, §§ 59-70, 22 lipca 2021 r.)"
✗ BŁĘDNIE: "w sprawie Reczkowicz przeciwko Polsce (43447/19, §§ 59-70, 22 lipca 2021 r.)"
✗ BŁĘDNIE: "w sprawie Reczkowicz przeciwko Polsce (nr 43447/19, §§ 59-70, 22 lipca 2021 r.)"
- Format: "skarga nr [numer]/[rok]" (numer skargi - application number)

=== KLUCZOWA TERMINOLOGIA ===

Agent – Pełnomocnik Rządu (w kontekście "Government Agent")
alleged violation – zarzucane naruszenie / zarzut naruszenia (art. n Konwencji)
applicant – skarżący/skarżąca
applicants – skarżący/skarżące (unikać określeń typu "osoby skarżące")
application – skarga (gdy w kontekście postępowań przed Trybunałem) [gdy w kontekście postępowań krajowych może to być też odpowiednikiem np. wniosku]
application was communicated to the Government – sprawa została zakomunikowana Rządowi
competing interests – konkurujące interesy
decide to rule on the admissibility and merits of the application at the same time – postanowić, że rozstrzygnięcie w sprawie dopuszczalności i przedmiotu skargi zostanie przyjęte jednocześnie
detention – z reguły: pozbawienie wolności
  • pre-trial detention lub detention on remand – tymczasowe aresztowanie
  • arrest – z reguły: zatrzymanie
domestic authorities – władze krajowe (nb. istnieje rozróżnienie między Rządem (the Government) jako stroną postępowania przed Trybunałem, a władzami krajowymi, czyli organami, których zaniechania lub działania są przedmiotem skargi)
domestic remedies – (krajowe) środki odwoławcze (zgodnie z oficjalnym tłumaczeniem art. 13 i 35 Konwencji)
effective – skuteczny (np. śledztwo – investigation)
engaging responsibility of the State – pociągający odpowiedzialność państwa
exhaustion of domestic remedies – wyczerpanie [przez skarżącego] krajowych środków odwoławczych
fair trial – "rzetelny" proces sądowy - zamiast "sprawiedliwego" procesu – zgodnie z tłumaczeniem tytułu art. 6 Konwencji. "Sprawiedliwe rozpatrzenie" stosować wówczas, jeśli jest to w kontekście wyrażenia "fair hearing" z art. 6 ust. 1 Konwencji.
final judgment – w kontekście wyroków ETPCz: "ostateczny wyrok" (jak w tłumaczeniu Konwencji), nie: "prawomocny"
freedom of expression – wolność wyrażania opinii (zamiast wolność wypowiedzi lub wolność słowa, te wyrażenia stosować raczej dla odpowiedników typu "freedom of speech")
friendly settlement – ugoda lub polubowne załatwienie sprawy
Government – Rząd (a nie Władze Państwowe) (nb. w praktyce Trybunału słowo "the Government" jest stosowane zwyczajowo jako liczba mnoga, po polsku – stosować liczbę pojedynczą)
[GC] – [WI] lub [Wielka Izba] / skrót od Grand Chamber/
High Contracting Parties – Wysokie Układające się Strony (nie: Umawiające się)
inadmissibility decision – decyzja o niedopuszczalności
individual or general measures – środki indywidualne lub generalne [gdy dotyczy kontekstu wykonywania wyroków Trybunału – art. 46 Konwencji]
interference – ingerencja (nie: "naruszenie", gdyż nie każda ingerencja jest automatycznie naruszeniem Konwencji, czyli "violation")
interference with the peaceful enjoyment of possessions - ingerencja w prawo do poszanowania mienia (jak urzędowe tłumaczenie art. 1 Protokołu nr 1 do Konwencji)
joinder of applications – połączenie skarg
join to the merits – dołączyć do przedmiotu skargi (np. zastrzeżenie wstępne rzędu ws. niedopuszczalności)
judgment – wyrok; decision - decyzja (w kontekście ETPCz w miarę możliwości unikać ogólnego słowa "orzeczenie", gdyż jest niejasne, czy chodzi o wyrok, czy o decyzję ETPCz)
  • "decision(s)" w odniesieniu do sądów krajowych – najlepiej tłumaczyć jako "orzeczenie(a)", nie "decyzja(e)", natomiast termin "decyzja" stosować w odniesieniu do organów administracji
judicial remedy having a suspensive effect – środek o charakterze sądowym ze skutkiem zawieszającym
judicial review – kontrola sądowa
juror – członek ławy przysięgłych
just satisfaction – słuszne zadośćuczynienie
"The Law" (nagłówek) – przyjęło się tłumaczyć jako "Prawo", a nie podstawy prawne
law – w kontekście prawa krajowego - "prawo", ale też "ustawa" (zwłaszcza gdy jest związane z wyrażeniami typu "interference prescribed by law", bowiem w tłumaczeniach Konwencji stosowane jest wyrażenie "przewidziane/określane ustawą")
legitimate aim – uprawniony cel (tj. zgodny z przepisami Konwencji)
legitimate expectation – uprawnione oczekiwanie
(minimum) level of severity – (minimalny) stopień dolegliwości/surowości (z reguły w kontekście art. 3 Konwencji i traktowania osób)
manifestly ill-founded application = skarga w sposób oczywisty nieuzasadniona (zgodnie z oficjalnym tłumaczeniem art. 35 ust. 1 lit. a Konwencji), a nie "oczywiście bezzasadna"
margin of appreciation – margines oceny, nie: uznania (zgodnie z oficjalnym tłumaczeniem Protokołu nr 15)
  • odpowiednio też: coś może wchodzić w zakres szerokiego marginesu oceny, z którego korzysta państwo /być objęte szerokim marginesem oceny państwo itp./
  • uznanie lub uznaniowość – stosować w przypadku terminu "discretion"
marginal lending rate - marginalna (ew. krańcowa) stopa procentowa [EBC]
merits – przedmiot skargi (w odróżnieniu od dopuszczalności) – jak w tłumaczeniu art. 29 Konwencji
objective and reasonable justification – obiektywne i rozsądne uzasadnienie
observations – w kontekście postępowania przed ETPCz: obserwacje lub ew. uwagi [stron, rzędu, skarżącego]
pilot judgment – wyrok pilotażowy
place an excessive and disproportionate burden on the applicant – nałożyć nadmierny i nieproporcjonalny ciężar na skarżącego
positive obligations – obowiązki pozytywne [Państwa]
preliminary issue – zagadnienie wstępne
preliminary objection – zastrzeżenie wstępne
President of the European Court of Human Rights – tradycyjnie tłumaczone jako: Prezes Europejskiego Trybunału Praw Człowieka
Section President – Przewodniczący Sekcji
President – Przewodniczący (gdy w kontekście składu orzekającego Trybunału w danej sprawie)
Protokół nr 1 do Konwencji, itp. (nie: "Nr")
pursue a legitimate aim – dążyć do (realizacji) uprawnionego celu
reasonable relationship of proportionality – pozostawać w rozsądnej proporcji do ...
reasonable, reasonably – w zależności od kontekstu "uzasadniony" lub "rozsądny", "rozsądnie", np. "rozsądny termin/długość postępowania", uzasadniona długość tymczasowego aresztowania
reasons, reasoning – w kontekście orzeczeń sądów i ETPCz może oznaczać "uzasadnienie"
reasoned judgment – wyrok z uzasadnieniem
Registrar – Kanclerz
  • Section Registrar – Kanclerz Sekcji
Registry – Kancelaria [Trybunału]
relevant – istotny, właściwy, mający znaczenie w sprawie
relevant domestic law and practice – tradycyjnie: właściwe prawo krajowe i praktyka
relevantly similar situation - w istotny sposób podobna sytuacja
re-opening of the proceedings – wznowienie postępowania
Reports of Judgments and Decisions - Zbiór Wyroków i Decyzji

=== STAŁE FORMUŁKI W WYROKACH ===

NAGŁÓWEK WYROKU - wersja angielska:
"The European Court of Human Rights (Fourth Section), sitting as a Chamber/a Grand Chamber composed of:
n, President,
nn, judges,
and n, (Section) Registrar
Having deliberated in private on,
Delivers the following judgment, which was adopted on that date:"

NAGŁÓWEK WYROKU - wersja polska:
"Europejski Trybunał Praw Człowieka (czwarta sekcja), zasiadając jako Izba/Wielka Izba w składzie:
n, Przewodniczący,
nn, Sędziowie,
oraz n, Kanclerz (Sekcji),
obradując na posiedzeniu niejawnym w dniu n,
wydaje następujący wyrok, który został przyjęty w tym dniu:"

=== PRZYKŁADY TŁUMACZEŃ TYPOWYCH SFORMUŁOWAŃ ===

"Convention is called to guarantee rights that are practical and effective, not theoretical and illusory"
→ "Konwencja gwarantuje prawa, które są praktyczne i skuteczne, a nie teoretyczne i iluzoryczne"

"The Court considers that the question ... is closely linked to the merits of the applicants' complaints. It therefore joins this preliminary issue (objection) to the merits."
→ "Trybunał uważa, że kwestia ... jest ściśle powiązana z przedmiotem skargi. Trybunał rozpatrzy zatem tę kwestią wstępną (zastrzeżenie/sprzeciw) łącznie z przedmiotem skargi."

"Article 1 of Protocol No. 1 does not include a right to acquire property. It places no restriction on the Contracting States' freedom to decide whether or not to have in place any form of social security scheme, or to choose the type or amount of benefits to provide under any such scheme. If, however, a State does decide to create a benefits or pension scheme, it must do so in a manner which is compatible with Article 14 of the Convention"
→ "Art. 1 Protokołu nr 1 nie obejmuje prawa do nabycia własności. Nie nakłada on jakichkolwiek ograniczeń na swobodę Układających się Państw co do decyzji, czy ustanowić jakąkolwiek formę systemu zabezpieczenia społecznego, lub co do wyboru rodzaju lub kwoty świadczeń przyznawanych w ramach takiego systemu. Jeżeli jednak Państwo zdecyduje się ustanowić system świadczeń społecznych lub emerytalnych, musi zrobić to w sposób zgodny z art. 14 Konwencji"

"although there was no obligation on a State under Article 1 of Protocol No. 1 to create a welfare or pension scheme, if a State did decide to enact legislation providing for the payment of a welfare benefit or pension as of right – whether conditional or not on previous contributions – that legislation had to be regarded as generating a proprietary interest falling within the ambit of Article 1 of Protocol No. 1 for persons satisfying its requirements"
→ "chociaż art. 1 Protokołu nr 1 nie nakłada na Państwa obowiązku utworzenia systemu świadczeń społecznych lub emerytalnych, jeżeli Państwo zdecyduje się przyjąć ustawodawstwo przewidujące wypłatę świadczeń społecznych lub emerytalnych z mocy prawa – niezależnie od tego, czy wypłata ta jest zależna, czy nie, od uprzedniego uiszczania składek – ustawodawstwo to musi być uznane za tworzące interes majątkowy wchodzący w zakres zastosowania art. 1 Protokołu nr 1 dla osób spełniających wymogi przedmiotowego ustawodawstwa"

"generating a proprietary interest falling within the ambit of Article 1"
→ "tworzące interes majątkowy wchodzący w zakres zastosowania art. 1"

"Article 1 of Protocol No. 1, the essential object of which is to protect the individual against unjustified interference by the State with the peaceful enjoyment of his or her possessions, may also entail positive obligations requiring the State to take certain measures necessary to protect the right of property, particularly where there is a direct link between the measures an applicant may legitimately expect from the authorities and his effective enjoyment of his possessions"
→ "Art. 1 Protokołu nr 1, którego zasadniczym celem jest zapewnienie ochrony jednostki przed nieuzasadnioną ingerencją ze strony Państwa w prawo do poszanowania mienia, może także"

=== DANE DO TŁUMACZENIA ===

Segment do tłumaczenia:
{source_text}

Typ sekcji: {section_type}

OBOWIĄZKOWA TERMINOLOGIA (użyj dokładnie tych ekwiwalentów):
{terminology_table}

Kontekst (poprzednie przetłumaczone segmenty):
{context}

=== INSTRUKCJE FINALNE ===

1. Tłumacz TYLKO tekst źródłowy podany powyżej - nic więcej, nic mniej
2. NIE dodawaj dat, faktów ani zdarzeń, których nie ma w źródle
3. NIE domyślaj się ani NIE uzupełniaj niekompletnych informacji
4. NIE dodawaj wyjaśnień, interpretacji ani kontekstu
5. Jeśli źródło jest niekompletne lub niejasne, tłumacz je tak jak jest
6. Numery paragrafów jak [35], [36] są częścią źródła - zachowaj je dokładnie
7. Używaj WYŁĄCZNIE terminologii z powyższej listy i słownika OBOWIĄZKOWEJ TERMINOLOGII

Przetłumacz segment. Nie dodawaj żadnych komentarzy ani wyjaśnień. Zwróć tylko tłumaczenie."""

    def __init__(self, tm_manager=None, on_segment_translated=None):
        """Inicjalizacja Translator.

        Args:
            tm_manager: Translation Memory Manager for segment reuse
            on_segment_translated: Optional callback called after each segment translation
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.tm_manager = tm_manager
        self.translation_context = []  # Kontekst ostatnich tłumaczeń
        self.on_segment_translated = on_segment_translated
        logger.info("Translator initialized with TM support" if tm_manager else "Translator initialized without TM")

    async def translate(
        self,
        segments: List[Dict[str, Any]],
        terminology: Dict[str, str],
        document_id: Optional[str] = None,
        ws_manager = None,
    ) -> List[Dict[str, Any]]:
        """
        Tłumaczy segmenty z wykorzystaniem terminologii.

        Args:
            segments: Lista segmentów do przetłumaczenia
            terminology: Słownik terminologii {source: target}
            document_id: ID dokumentu (do progress updates)
            ws_manager: WebSocket manager (do progress updates)

        Returns:
            Lista przetłumaczonych segmentów
        """
        translated_segments = []
        self.translation_context = []

        for i, segment in enumerate(segments):
            try:
                source_text = segment.get("text", "")

                # Pomiń puste segmenty
                if not source_text.strip():
                    segment["target_text"] = ""
                    segment["tm_match_type"] = "empty"
                    translated_segments.append(segment)
                    continue

                # === KROK 1: Sprawdź TM dla exact match ===
                target_text = None
                match_type = "new"  # new, exact, fuzzy, or api

                if self.tm_manager:
                    # Send progress message about TM lookup
                    if ws_manager and document_id and i % 5 == 0:  # Send every 5 segments to avoid spam
                        # Calculate progress within translation phase
                        segment_progress = 0.5 + (i / len(segments)) * 0.4  # 50% to 90%
                        await ws_manager.broadcast_progress(
                            document_id, "checking_tm", segment_progress,
                            f"💾 Sprawdzam pamięć tłumaczeniową... (segment {i+1}/{len(segments)})"
                        )

                    # Exact match
                    exact_match = self.tm_manager.find_exact(source_text)
                    if exact_match:
                        target_text = exact_match.target
                        match_type = "exact"
                        logger.info(f"Segment {i}: TM EXACT MATCH reused (100%)")
                    else:
                        # Fuzzy match (threshold 95%)
                        fuzzy_matches = self.tm_manager.find_fuzzy(source_text, threshold=0.95)
                        if fuzzy_matches:
                            best_match, similarity = fuzzy_matches[0]
                            target_text = best_match.target
                            match_type = f"fuzzy_{int(similarity * 100)}"
                            logger.info(f"Segment {i}: TM FUZZY MATCH reused ({int(similarity * 100)}%)")

                # === KROK 2: Jeśli brak dopasowania w TM, tłumacz przez API ===
                if target_text is None:
                    target_text = await self._translate_segment(
                        source_text=source_text,
                        section_type=segment.get("section_type", "OTHER"),
                        terminology=terminology,
                    )
                    match_type = "api"
                    logger.debug(f"Segment {i}: Translated via Claude API")

                # Dodaj tłumaczenie i metadata
                segment["target_text"] = target_text
                segment["tm_match_type"] = match_type
                translated_segments.append(segment)

                # Aktualizuj kontekst (ostatnie 3 segmenty)
                self.translation_context.append(
                    {"source": source_text, "target": target_text}
                )
                if len(self.translation_context) > 3:
                    self.translation_context.pop(0)

                logger.debug(
                    f"Segment {i} translated: {source_text[:50]}... -> {target_text[:50]}..."
                )

                # Callback dla live updates
                if self.on_segment_translated:
                    try:
                        await self.on_segment_translated(i, len(segments), segment)
                    except Exception as e:
                        logger.error(f"Error in segment callback: {e}")

            except Exception as e:
                logger.error(f"Error translating segment {i}: {e}", exc_info=True)
                segment["target_text"] = f"[BŁĄD TŁUMACZENIA: {source_text}]"
                translated_segments.append(segment)

        logger.info(f"Translation loop completed - {len(translated_segments)} segments processed")
        logger.info(f"Preparing to return {len(translated_segments)} segments to orchestrator")
        return translated_segments

    async def _translate_segment(
        self,
        source_text: str,
        section_type: str,
        terminology: Dict[str, str],
    ) -> str:
        """
        Tłumaczy pojedynczy segment.

        Args:
            source_text: Tekst do przetłumaczenia
            section_type: Typ sekcji
            terminology: Słownik terminologii

        Returns:
            Przetłumaczony tekst
        """
        # Przygotuj tabelę terminologii
        terminology_table = self._format_terminology(terminology, source_text)

        # Przygotuj kontekst
        context_text = self._format_context()

        # Zbuduj prompt
        prompt = self.TRANSLATOR_PROMPT.format(
            source_text=source_text,
            section_type=section_type,
            terminology_table=terminology_table or "Brak terminologii",
            context=context_text or "Brak kontekstu",
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Sonnet 4.5 dla jakości tłumaczenia
                max_tokens=2000,
                temperature=0.3,  # Niska temperatura dla konsystencji
                messages=[{"role": "user", "content": prompt}],
            )

            translation = response.content[0].text.strip()

            # Waliduj tłumaczenie
            if not translation or len(translation) < 3:
                logger.warning(f"Translation too short, using fallback")
                return f"[WYMAGANE TŁUMACZENIE RĘCZNE: {source_text}]"

            return translation

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"[BŁĄD API: {source_text}]"

    def _format_terminology(
        self, terminology: Dict[str, str], source_text: str
    ) -> str:
        """
        Formatuje terminologię dla promptu.

        Args:
            terminology: Słownik terminologii
            source_text: Tekst źródłowy (dla filtrowania)

        Returns:
            Sformatowana tabela terminologii
        """
        if not terminology:
            return ""

        # Filtruj tylko terminy występujące w tym segmencie
        relevant_terms = {}
        source_lower = source_text.lower()

        for source_term, target_term in terminology.items():
            if source_term.lower() in source_lower:
                relevant_terms[source_term] = target_term

        # Jeśli nie ma relevantnych terminów, zwróć pusty string
        if not relevant_terms:
            return ""

        # Zbuduj tabelę
        lines = []
        for source_term, target_term in relevant_terms.items():
            lines.append(f"| {source_term} | {target_term} |")

        return "\n".join(lines)

    def _format_context(self) -> str:
        """
        Formatuje kontekst dla promptu.

        Returns:
            Sformatowany kontekst
        """
        if not self.translation_context:
            return ""

        lines = []
        for item in self.translation_context[-3:]:  # Ostatnie 3 segmenty
            lines.append(f"EN: {item['source']}")
            lines.append(f"PL: {item['target']}")
            lines.append("")

        return "\n".join(lines)

    async def translate_single(
        self, text: str, terminology: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Tłumaczy pojedynczy tekst (utility function).

        Args:
            text: Tekst do przetłumaczenia
            terminology: Opcjonalna terminologia

        Returns:
            Przetłumaczony tekst
        """
        terminology = terminology or {}
        return await self._translate_segment(
            source_text=text, section_type="OTHER", terminology=terminology
        )

    def get_translation_stats(
        self, segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Zwraca statystyki tłumaczenia.

        Args:
            segments: Lista przetłumaczonych segmentów

        Returns:
            Słownik ze statystykami
        """
        total = len(segments)
        translated = sum(
            1
            for s in segments
            if s.get("target_text")
            and not s["target_text"].startswith("[BŁĄD")
            and not s["target_text"].startswith("[WYMAGANE")
        )
        errors = sum(
            1
            for s in segments
            if s.get("target_text", "").startswith(("[BŁĄD", "[WYMAGANE"))
        )

        # TM usage statistics
        tm_exact_matches = sum(1 for s in segments if s.get("tm_match_type") == "exact")
        tm_fuzzy_matches = sum(1 for s in segments if s.get("tm_match_type", "").startswith("fuzzy_"))
        api_translations = sum(1 for s in segments if s.get("tm_match_type") == "api")

        tm_total_reused = tm_exact_matches + tm_fuzzy_matches
        tm_reuse_rate = tm_total_reused / total if total > 0 else 0.0

        return {
            "total_segments": total,
            "translated": translated,
            "errors": errors,
            "success_rate": translated / total if total > 0 else 0.0,
            "tm_exact_matches": tm_exact_matches,
            "tm_fuzzy_matches": tm_fuzzy_matches,
            "api_translations": api_translations,
            "tm_reuse_rate": tm_reuse_rate,
            "tm_savings_pct": int(tm_reuse_rate * 100),
        }
