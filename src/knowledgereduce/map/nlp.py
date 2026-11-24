"""Deterministic offline NLP mapper and optional batched spaCy mapper."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from knowledgereduce.map.base import deterministic_id
from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    ExtractionError,
    MappedBatch,
    Relation,
    ReliabilityRating,
    SourceDocument,
)

# Abbreviations protected before splitting sentences on punctuation.
_ABBREV_PATTERN = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|Mt|Inc|Ltd|Corp|Co|Dept|Univ|Fig|No|Vol|"
    r"Ed|Eds|Rev|Trans|Ch|vs|etc|ed|pp|p|ch|al|e\.g|i\.e|U\.S|U\.K)\."
)
_INITIAL_PATTERN = re.compile(r"\b([A-Z])\.(?=\s*(?:[A-Z0-9(&]|,))")
_DECIMAL_PATTERN = re.compile(r"(\d)\.(\d)")
_APA_REF_LINE_RE = re.compile(r"^[A-Z][A-Za-z'-]+,\s+[A-Z]\..*?\(\d{4}[^)]*\)\.")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

# Honorific-prefixed person names (handles mid-name initials like "Dr. Charles J. Carlsen").
_HONORIFIC_PERSON_RE = re.compile(
    r"\b(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.)\s+"
    r"(?:(?:[A-Z]\.|[A-Z][A-Za-z'-]+)\s+){1,3}"
    r"[A-Z][A-Za-z'-]+\b"
)
# Organizations with strong institutional keywords.
_ORG_RE = re.compile(
    r"\b(?:University of [A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*|"
    r"College of [A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*|"
    r"Journal (?:of|for) [A-Z][A-Za-z&'-]+(?:\s+[A-Z][A-Za-z&'-]+){0,4}|"
    r"[A-Z][A-Za-z&'-]+(?:\s+(?:[A-Z][A-Za-z&'-]+|of|for|and)){0,4}\s+"
    r"(?:University|College|Department|Institute|Foundation|Corporation|Corp\.|Inc\.|"
    r"LLC|Company|Program|Press|Journal|Hall|House|Committee|Association|Center|"
    r"Academy|Commission))\b"
)
# Guarded City, State/Country pattern (matches 1-3 word city followed by state/country/postal code).
_CITY_STATE_RE = re.compile(
    r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}),\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b"
)
# Full calendar dates and explicit standalone years.
_FULL_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}\b"
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# General capitalized multi-word phrases (fallback entity detector).
_CAP_PHRASE_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9'-]+(?:\s+(?:of|for|the)?\s*[A-Z][A-Za-z0-9'-]+){1,4}\b"
)
# CamelCase / PascalCase technical or system identifiers (e.g., KnowledgeReduce, DuckDB, MapReduce).
_CAMEL_ENTITY_RE = re.compile(r"\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b")

_US_STATE_ABBREVS = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    }
)

_US_STATES_AND_COUNTRIES = frozenset(
    {
        "alabama",
        "alaska",
        "arizona",
        "arkansas",
        "california",
        "colorado",
        "connecticut",
        "delaware",
        "florida",
        "georgia",
        "hawaii",
        "idaho",
        "illinois",
        "indiana",
        "iowa",
        "kansas",
        "kentucky",
        "louisiana",
        "maine",
        "maryland",
        "massachusetts",
        "michigan",
        "minnesota",
        "mississippi",
        "missouri",
        "montana",
        "nebraska",
        "nevada",
        "new hampshire",
        "new jersey",
        "new mexico",
        "new york",
        "north carolina",
        "north dakota",
        "ohio",
        "oklahoma",
        "oregon",
        "pennsylvania",
        "rhode island",
        "south carolina",
        "south dakota",
        "tennessee",
        "texas",
        "utah",
        "vermont",
        "virginia",
        "washington",
        "west virginia",
        "wisconsin",
        "wyoming",
        "district of columbia",
        "united states",
        "usa",
        "canada",
        "united kingdom",
        "england",
        "france",
        "germany",
        "italy",
        "spain",
        "japan",
        "china",
        "india",
        "australia",
        "mexico",
        "brazil",
    }
)

_MAJOR_CITIES = (
    "New York",
    "San Francisco",
    "Los Angeles",
    "North Scituate",
    "Upper Saddle River",
    "West Hartford",
    "Santa Monica",
    "New Haven",
    "Washington",
    "Philadelphia",
    "Lawrence",
    "Chicago",
    "Toronto",
    "Seattle",
    "Boulder",
    "Berkeley",
    "Cambridge",
    "Princeton",
    "Atlanta",
    "Glenview",
    "Denver",
    "Boston",
    "London",
    "Oxford",
    "Topeka",
    "Tokyo",
    "Paris",
    "Berlin",
)
_MAJOR_CITY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in sorted(_MAJOR_CITIES, key=lambda s: -len(s))) + r")\b"
)

_STOP_LEADING_WORDS = frozenset(
    {
        "The",
        "This",
        "These",
        "That",
        "Those",
        "Each",
        "Every",
        "Many",
        "Most",
        "Some",
        "All",
        "Both",
        "A",
        "An",
        "In",
        "On",
        "At",
        "During",
        "Since",
        "After",
        "Before",
        "Over",
        "Under",
        "For",
        "By",
        "With",
        "From",
        "To",
        "Thank",
        "Thanks",
        "However",
        "Furthermore",
        "Moreover",
        "Although",
        "Because",
        "While",
        "When",
        "Where",
        "Believing",
        "Enjoy",
        "Online",
        "Graduation",
        "Later",
        "Earlier",
        "Initially",
        "Eventually",
        "Finally",
        "Subsequently",
        "Dr",
        "Prof",
        "Mr",
        "Mrs",
        "Ms",
    }
)

_TRAILING_STOP_WORDS = frozenset(
    {
        "With",
        "For",
        "Of",
        "In",
        "To",
        "About",
        "What",
        "The",
        "And",
        "Or",
        "From",
        "On",
        "At",
        "By",
        "Dr",
        "Prof",
        "Mr",
        "Mrs",
        "Ms",
        "Jr",
        "Sr",
    }
)

_NON_PERSON_PHRASES = frozenset(
    {
        "civic honors",
        "civic engagement",
        "civic participation",
        "civil society",
        "concepts of civil society",
        "public administration",
        "semantic web",
        "knowledge graph",
        "knowledge graphs",
        "knowledge reduce",
        "knowledgereduce",
        "machine learning",
        "artificial intelligence",
        "natural language processing",
        "spring semester",
        "graduate school",
        "bowling alone",
        "apache parquet",
    }
)

_NON_PERSON_KEYWORDS = (
    "university",
    "college",
    "department",
    "institute",
    "foundation",
    "program",
    "society",
    "honors",
    "administration",
    "school",
    "class",
    "concept",
    "semester",
    "online",
    "web",
    "journal",
    "press",
    "bowling",
    "alone",
    "breaking",
    "building",
    "strong",
    "positive",
    "individual",
    "future",
    "never",
    "thinking",
    "measuring",
    "change",
    "message",
    "leadership",
    "technology",
    "collaboration",
    "community",
    "maintenance",
    "implementation",
    "connections",
    "advocate",
    "model",
    "vision",
    "action",
    "story",
    "chapter",
    "boards",
    "organizations",
    "apache",
    "parquet",
    "book",
    "guide",
    "manual",
    "rules",
    "democracy",
    "revival",
    "millennium",
    "edition",
    "execution",
    "prosperity",
    "executive",
    "bureaucracy",
    "government",
    "politics",
    "history",
    "habits",
    "volunteering",
    "charity",
)

_ENTITY_TYPE_SPECIFICITY: dict[str, int] = {
    "DATE": 5,
    "GPE": 4,
    "ORG": 3,
    "PERSON": 2,
    "CONCEPT": 1,
}

_PERSON_PREFIX_TOKEN_RE = re.compile(
    r"^(?:[A-Z][a-z]+|"
    r"(?:Mc|Mac|De|La|Le|Di|Da|O')[A-Z][a-z]+|"
    r"[A-Z][a-z]+-[A-Z][a-z]+)$"
)

_HEADING_FUNC_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
)
_HEADING_PREFIX_RE = re.compile(r"^(?:Chapter|Section|Part|Appendix)\s*(?:\d+|[IVXLCDM]+)?[:\s]")
_ABSTRACT_SUFFIX_RE = re.compile(r"(?:ing|tion|ment|ship|ness|ity|ive)$")

_NON_PERSON_PHRASE_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(p) for p in sorted(_NON_PERSON_PHRASES, key=lambda s: -len(s)) if " " in p)
    + r")\b",
    re.IGNORECASE,
)

_DEICTIC_BOOK_SUBJECTS = frozenset(
    {
        "this book",
        "the book",
        "this work",
        "the work",
        "book",
        "work",
    }
)

# Clean factual pattern extractors for (subject, predicate, object_literal/entity) grounding.
_FACTUAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?P<subj>[A-Z][A-Za-z0-9 &-]{1,50}?)\s+(?:was|were)?\s*"
            r"(?P<pred>published|released|founded|established|created|launched)\s+"
            r"(?:online\s+)?(?:in|on)\s+(?P<obj>(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+\d{1,2},\s+\d{4}|(?:19|20)\d{2})\b"
        ),
        "TEMPORAL_EVENT",
    ),
    (
        re.compile(
            r"\b(?P<subj>(?:Dr\.|Prof\.)?\s*[A-Z][A-Za-z. -]{2,50}?)\s+"
            r"(?P<pred>founded|created|authored|wrote|published|developed|led|built|introduced)\s+"
            r"(?:the\s+)?(?P<obj>[A-Z][A-Za-z0-9 &-]{2,50}?)(?=\s+(?:to|and|for|in|with)\b|[.,;!?]|$)"
        ),
        "ACTION",
    ),
    (
        re.compile(
            r"\b(?P<subj>(?:Dr\.|Prof\.)?\s*[A-Z][A-Za-z. -]{2,50}?)\s+"
            r"(?P<pred>works at|works for|is affiliated with|taught at|studied at)\s+"
            r"(?:the\s+)?(?P<obj>[A-Z][A-Za-z0-9 &-]{2,60}?)(?=\s+(?:and|under|to|in)\b|[.,;!?]|$)"
        ),
        "AFFILIATION",
    ),
    (
        re.compile(
            r"\b(?P<subj>[A-Z][A-Za-z0-9 &-]{2,50}?)\s+"
            r"(?P<pred>is located in|is based in|is headquartered in|began at|began in)\s+"
            r"(?:the\s+)?(?P<obj>[A-Z][A-Za-z0-9 ,&-]{2,60}?)(?=\s+(?:and|to|for)\b|[.;!?]|$)"
        ),
        "LOCATION_OR_ORIGIN",
    ),
]

# Non-functional descriptive predicates for Pass-2 entity-anchored triple grounding.
_ANCHORED_VERB_MAP: dict[str, str] = {
    "is": "DEFINED_AS",
    "are": "DEFINED_AS",
    "was": "DESCRIBED_AS",
    "were": "DESCRIBED_AS",
    "represents": "REPRESENTS",
    "means": "MEANS",
    "defines": "DEFINES",
    "provides": "PROVIDES",
    "creates": "CREATES",
    "create": "CREATES",
    "fosters": "FOSTERS",
    "foster": "FOSTERS",
    "encourages": "ENCOURAGES",
    "encourage": "ENCOURAGES",
    "promotes": "PROMOTES",
    "promote": "PROMOTES",
    "strengthens": "STRENGTHENS",
    "strengthen": "STRENGTHENS",
    "requires": "REQUIRES",
    "require": "REQUIRES",
    "involves": "INVOLVES",
    "involve": "INVOLVES",
    "connects": "CONNECTS",
    "connect": "CONNECTS",
    "builds": "BUILDS",
    "build": "BUILDS",
    "supports": "SUPPORTS",
    "support": "SUPPORTS",
    "benefits": "BENEFITS",
    "benefit": "BENEFITS",
    "develops": "DEVELOPS",
    "develop": "DEVELOPS",
    "spreads": "SPREADS",
    "spread": "SPREADS",
    "empowers": "EMPOWERS",
    "empower": "EMPOWERS",
    "recognizes": "RECOGNIZES",
    "recognize": "RECOGNIZES",
    "facilitates": "FACILITATES",
    "facilitate": "FACILITATES",
    "expands": "EXPANDS",
    "expand": "EXPANDS",
    "offers": "OFFERS",
    "offer": "OFFERS",
    "strives": "STRIVES",
    "taught": "TAUGHT",
    "learned": "LEARNED",
    "submitted": "SUBMITTED",
    "envisioned": "ENVISIONED",
    "brought": "BROUGHT",
    "advocates": "ADVOCATES",
    "advocate": "ADVOCATES",
    "uses": "USES",
    "use": "USES",
    "allows": "ALLOWS",
    "allow": "ALLOWS",
    "enables": "ENABLES",
    "enable": "ENABLES",
    "gives": "GIVES",
    "give": "GIVES",
    "takes": "TAKES",
    "take": "TAKES",
    "becomes": "BECOMES",
    "become": "BECOMES",
    "became": "BECAME",
    "has": "HAS_ATTRIBUTE",
    "have": "HAS_ATTRIBUTE",
    "helps": "HELPS",
    "help": "HELPS",
    "makes": "MAKES",
    "make": "MAKES",
    "needs": "NEEDS",
    "need": "NEEDS",
    "gains": "GAINS",
    "gain": "GAINS",
    "receives": "RECEIVES",
    "receive": "RECEIVES",
    "plays": "PLAYS",
    "play": "PLAYS",
    "sets": "SETS",
    "set": "SETS",
    "brings": "BRINGS",
    "bring": "BRINGS",
    "gets": "GETS",
    "get": "GETS",
    "increases": "INCREASES",
    "increase": "INCREASES",
    "motivates": "MOTIVATES",
    "motivate": "MOTIVATES",
    "rewards": "REWARDS",
    "reward": "REWARDS",
    "acknowledges": "ACKNOWLEDGES",
    "acknowledge": "ACKNOWLEDGES",
    "explores": "EXPLORES",
    "explore": "EXPLORES",
    "demonstrates": "DEMONSTRATES",
    "demonstrate": "DEMONSTRATES",
    "breaks": "BREAKS",
    "break": "BREAKS",
    "seeks": "SEEKS",
    "seek": "SEEKS",
    "achieves": "ACHIEVES",
    "achieve": "ACHIEVES",
    "serves": "SERVES",
    "serve": "SERVES",
    "works": "OPERATES",
    "operates": "OPERATES",
    "operate": "OPERATES",
    "grows": "GROWS",
    "grow": "GROWS",
    "extends": "EXTENDS",
    "extend": "EXTENDS",
    "improves": "IMPROVES",
    "improve": "IMPROVES",
    "enhances": "ENHANCES",
    "enhance": "ENHANCES",
    "ensures": "ENSURES",
    "ensure": "ENSURES",
    "continues": "CONTINUES",
    "continue": "CONTINUES",
    "remains": "REMAINS",
    "remain": "REMAINS",
    "begins": "BEGINS",
    "begin": "BEGINS",
    "shows": "SHOWS",
    "show": "SHOWS",
    "exists": "EXISTS",
    "exist": "EXISTS",
    "addresses": "ADDRESSES",
    "address": "ADDRESSES",
    "identifies": "IDENTIFIES",
    "identify": "IDENTIFIES",
    "measures": "MEASURES",
    "measure": "MEASURES",
    "tracks": "TRACKS",
    "track": "TRACKS",
    "delivers": "DELIVERS",
    "deliver": "DELIVERS",
    "relies": "RELIES",
    "rely": "RELIES",
    "determines": "DETERMINES",
    "determine": "DETERMINES",
    "shapes": "SHAPES",
    "shape": "SHAPES",
    "inspires": "INSPIRES",
    "inspire": "INSPIRES",
    "focuses on": "FOCUSES",
    "focused on": "FOCUSES",
    "depends on": "DEPENDS",
    "relies on": "DEPENDS",
    "leads to": "LEADS_TO",
    "contributes to": "CONTRIBUTES_TO",
    "participates in": "PARTICIPATES",
    "graduated with": "GRADUATED_WITH",
    "fostered": "FOSTERED_BY",
    "created": "CREATED_BY",
    "generated": "GENERATED_BY",
    "required": "REQUIRED_BY",
    "strengthened": "STRENGTHENED_BY",
    "supported": "SUPPORTED_BY",
    "recognized": "RECOGNIZED_BY",
    "rewarded": "REWARDED_BY",
    "empowered": "EMPOWERED_BY",
    "developed": "DEVELOPED_BY",
    "implemented": "IMPLEMENTED_BY",
    "measured": "MEASURED_BY",
    "tracked": "TRACKED_BY",
    "driven": "DRIVEN_BY",
    "designed": "DESIGNED_FOR",
    "discussed": "DISCUSSED_BY",
    "acknowledged": "ACKNOWLEDGED_BY",
    "expanded": "EXPANDED_BY",
    "maintained": "MAINTAINED_BY",
    "evaluated": "EVALUATED_BY",
    "connected": "CONNECTED_TO",
    "linked": "LINKED_TO",
    "encouraged": "ENCOURAGED_BY",
    "promoted": "PROMOTED_BY",
    "used": "USED_FOR",
    "offered": "OFFERED_BY",
    "adopted": "ADOPTED_BY",
    "tied": "TIED_TO",
    "based": "BASED_UPON",
    "built": "BUILT_WITH",
    "formed": "FORMED_BY",
    "organized": "ORGANIZED_BY",
    "focused": "FOCUSES",
    "improved": "IMPROVED_BY",
    "achieved": "ACHIEVED_BY",
    "sustained": "SUSTAINED_BY",
    "defined": "DEFINED_BY",
    "shared": "SHARED_BY",
}

_ANCHORED_VERB_PATTERN = "|".join(
    re.escape(k) for k in sorted(_ANCHORED_VERB_MAP, key=lambda s: -len(s))
)
_ANCHORED_AUX_RE = re.compile(
    rf"^(?:(?:,\s*[^,;]{{2,35}},)?[\s]+(?:[a-z][a-z'-]*\s+){{0,4}}"
    rf"(?:(?:can|will|may|must|should|would|could|does|do|also|often|largely|usually|typically|"
    rf"not\s+only|to|be|being|strives?\s+to|attempts?\s+to|tries?\s+to|helps?\s+to)\s+){{0,3}})"
    rf"(?P<verb>{_ANCHORED_VERB_PATTERN})\b\s+(?P<rest>.+)",
    re.IGNORECASE,
)


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split *text* into ``(sentence, start_char, end_char)`` preserving abbreviations and APA citations."""
    if not text.strip():
        return []

    sentinel = "\u0000"
    results: list[tuple[str, int, int]] = []

    for line_match in re.finditer(r"[^\n]+", text):
        line_start = line_match.start()
        line_raw = line_match.group(0)
        line_stripped = line_raw.strip()
        if not line_stripped:
            continue

        ltrim_line = len(line_raw) - len(line_raw.lstrip())
        if _APA_REF_LINE_RE.match(line_stripped):
            abs_start = line_start + ltrim_line
            results.append((line_stripped, abs_start, abs_start + len(line_stripped)))
            continue

        masked = _ABBREV_PATTERN.sub(lambda m: m.group(0).replace(".", sentinel), line_raw)
        masked = _INITIAL_PATTERN.sub(lambda m: f"{m.group(1)}{sentinel}", masked)
        masked = _DECIMAL_PATTERN.sub(lambda m: f"{m.group(1)}{sentinel}{m.group(2)}", masked)

        pos = 0
        for match in _SENTENCE_BREAK.finditer(masked):
            raw_chunk = line_raw[pos : match.start()]
            stripped = raw_chunk.strip()
            if stripped:
                ltrim = len(raw_chunk) - len(raw_chunk.lstrip())
                start = line_start + pos + ltrim
                end = start + len(stripped)
                results.append((stripped, start, end))
            pos = match.end()

        tail = line_raw[pos:]
        tail_stripped = tail.strip()
        if tail_stripped:
            ltrim = len(tail) - len(tail.lstrip())
            start = line_start + pos + ltrim
            end = start + len(tail_stripped)
            results.append((tail_stripped, start, end))

    return results


def _strip_edge_stop_words(phrase: str) -> str:
    tokens = phrase.split()
    while tokens and (tokens[0] in _STOP_LEADING_WORDS or tokens[0][0].islower()):
        tokens = tokens[1:]
    while tokens and tokens[-1] in _TRAILING_STOP_WORDS:
        tokens = tokens[:-1]
    return " ".join(tokens)


def _strip_honorific(name: str) -> str:
    return re.sub(r"^(?:Dr|Prof|Mr|Mrs|Ms)\.\s+", "", name).strip()


def _reliability_from_trust(trust_weight: float) -> ReliabilityRating:
    if trust_weight >= 0.85:
        return ReliabilityRating.VERIFIED
    if trust_weight >= 0.65:
        return ReliabilityRating.LIKELY_TRUE
    if trust_weight >= 0.4:
        return ReliabilityRating.POSSIBLY_TRUE
    return ReliabilityRating.UNVERIFIED


def _is_heading_line(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return False
    if _HEADING_PREFIX_RE.match(stripped) and stripped[-1] not in ".!?":
        return True
    if stripped[-1] in ".!?":
        return False
    # Author/date/location bylines should keep full entity extraction.
    if _FULL_DATE_RE.search(stripped) or _YEAR_RE.search(stripped):
        return False
    words = stripped.split()
    if not (2 <= len(words) <= 12):
        return False
    content_words = [w for w in words if w.lower() not in _HEADING_FUNC_WORDS]
    if not content_words:
        return False
    cap_words = sum(1 for w in content_words if w and w[0].isupper())
    return (cap_words / len(content_words)) >= 0.70


def _is_likely_person_phrase(words: list[str], full_phrase: str) -> bool:
    if not (2 <= len(words) <= 3):
        return False
    if not all(_PERSON_PREFIX_TOKEN_RE.match(w) for w in words):
        return False
    low = full_phrase.lower()
    if any(kw in low for kw in _NON_PERSON_KEYWORDS):
        return False
    return not any(_ABSTRACT_SUFFIX_RE.search(w.lower()) for w in words)


def _extract_entities_from_sentence(sentence: str) -> list[tuple[str, str, list[str]]]:
    """Return ``[(canonical_name, entity_type, aliases)]`` found in *sentence*."""
    found: dict[str, tuple[str, str, list[str]]] = {}

    def _register(name: str, etype: str, alias: str | None = None) -> None:
        cleaned = name.strip(" ,.;:!?\"'")
        if len(cleaned) < 2:
            return
        key = cleaned.lower()
        if key in found:
            old_name, old_type, aliases = found[key]
            if alias and alias not in aliases and alias != old_name:
                aliases.append(alias)
            if _ENTITY_TYPE_SPECIFICITY.get(etype, 0) > _ENTITY_TYPE_SPECIFICITY.get(old_type, 0):
                found[key] = (old_name, etype, aliases)
            return
        init_aliases = [alias] if alias and alias != cleaned else []
        found[key] = (cleaned, etype, init_aliases)

    for m in _HONORIFIC_PERSON_RE.finditer(sentence):
        raw = m.group(0).strip()
        canonical = _strip_honorific(raw)
        _register(canonical, "PERSON", alias=raw)

    for m in _ORG_RE.finditer(sentence):
        raw = _strip_edge_stop_words(m.group(0).strip())
        if len(raw.split()) >= 2:
            _register(raw, "ORG")

    for m in _CITY_STATE_RE.finditer(sentence):
        city = _strip_edge_stop_words(m.group(1).strip())
        state = m.group(2).strip()
        state_low = state.lower()
        state_is_known = state_low in _US_STATES_AND_COUNTRIES
        state_is_abbrev = state in _US_STATE_ABBREVS
        city_is_known = bool(city and _MAJOR_CITY_RE.fullmatch(city))
        if state_is_known or state_is_abbrev or city_is_known:
            if city:
                _register(city, "GPE")
            if state_is_known:
                _register(state, "GPE")

    for m in _MAJOR_CITY_RE.finditer(sentence):
        city_hit = m.group(0).strip()
        # Skip if already inside a longer organization name (e.g., "University of California Press").
        if any(
            city_hit.lower() in existing_key and existing_type == "ORG"
            for existing_key, (_n, existing_type, _al) in found.items()
        ):
            continue
        _register(city_hit, "GPE")

    for m in _FULL_DATE_RE.finditer(sentence):
        _register(m.group(0).strip(), "DATE")

    for m in _YEAR_RE.finditer(sentence):
        yr = m.group(0).strip()
        if not any(yr in name and et == "DATE" for name, et, _ in found.values()):
            _register(yr, "DATE")

    heading_line = _is_heading_line(sentence)
    for m in _CAP_PHRASE_RE.finditer(sentence):
        candidate = _strip_edge_stop_words(m.group(0).strip())
        if not candidate or len(candidate.split()) < 2:
            continue
        words = candidate.split()
        if all(w.isupper() for w in words):
            continue
        low = candidate.lower()
        if any(low in existing_key or existing_key in low for existing_key in found):
            continue
        if low in _NON_PERSON_PHRASES:
            _register(candidate, "CONCEPT")
        elif heading_line:
            # On structural headings, skip speculative _CAP_PHRASE_RE entities.
            continue
        elif _is_likely_person_phrase(words, candidate):
            _register(candidate, "PERSON")
        else:
            _register(candidate, "CONCEPT")

    for m in _CAMEL_ENTITY_RE.finditer(sentence):
        candidate = m.group(0).strip()
        low = candidate.lower()
        if any(low in existing_key or existing_key in low for existing_key in found):
            continue
        _register(candidate, "CONCEPT")

    # Promote canonical lowercase occurrences of multi-word domain phrases when not superseded.
    for m in _NON_PERSON_PHRASE_RE.finditer(sentence):
        phrase_raw = m.group(0).strip()
        low = phrase_raw.lower()
        if any(low in existing_key or existing_key in low for existing_key in found):
            continue
        title_name = " ".join(
            w.lower() if (idx > 0 and w.lower() in _HEADING_FUNC_WORDS) else w.capitalize()
            for idx, w in enumerate(phrase_raw.split())
        )
        _register(title_name, "CONCEPT")

    return list(found.values())


def _extract_factual_triple(
    sentence: str,
    *,
    fallback_subject: str | None = None,
) -> tuple[str, str, str] | None:
    for pattern, _kind in _FACTUAL_PATTERNS:
        match = pattern.search(sentence)
        if match:
            raw_subj = match.group("subj").strip()
            if fallback_subject and raw_subj.lower() in _DEICTIC_BOOK_SUBJECTS:
                subj = fallback_subject
            else:
                subj = _strip_edge_stop_words(_strip_honorific(raw_subj))
            pred = re.sub(r"\s+", "_", match.group("pred").strip().upper())
            if pred in {"PUBLISHED", "RELEASED"}:
                pred = "PUBLISHED_IN"
            elif pred in {"FOUNDED", "ESTABLISHED", "CREATED", "LAUNCHED"} and _YEAR_RE.fullmatch(
                match.group("obj").strip()
            ):
                pred = "FOUNDED_IN"
            obj = match.group("obj").strip(" ,.;:!?\"'")
            if subj and pred and obj:
                return subj, pred, obj
    return None


def _extract_entity_anchored_triple(
    sentence: str,
    sent_entity_ids: Sequence[str],
    entities_by_id: dict[str, Entity],
    *,
    mention_regex: re.Pattern[str] | None = None,
    mention_lookup: dict[str, str] | None = None,
) -> tuple[str, str, str | None, str] | None:
    """Extract a non-functional ``(subj_id, pred, obj_id, obj_literal)`` grounded in sentence entities."""
    if not sent_entity_ids or _is_heading_line(sentence):
        return None

    sent_set = set(sent_entity_ids)
    # Build ordered occurrences of known entities within this sentence.
    occurrences: list[tuple[int, int, str]] = []
    if mention_regex is not None and mention_lookup is not None:
        for m in mention_regex.finditer(sentence):
            eid = mention_lookup.get(m.group(0).lower())
            if eid and eid in sent_set:
                occurrences.append((m.start(), m.end(), eid))

    if not occurrences:
        sent_low = sentence.lower()
        for eid in sent_entity_ids:
            ent = entities_by_id[eid]
            for surface in [ent.canonical_name, *ent.aliases]:
                pos = sent_low.find(surface.lower())
                if pos != -1:
                    occurrences.append((pos, pos + len(surface), eid))
                    break
        occurrences.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    for s_start, s_end, subj_id in occurrences:
        # Prefer narrative subjects rather than trailing parenthetical citations.
        if s_start > 220:
            break
        if entities_by_id[subj_id].entity_type == "DATE":
            continue
        trailing = sentence[s_end:]
        vm = _ANCHORED_AUX_RE.match(trailing)
        if not vm:
            continue
        verb_raw = vm.group("verb").lower()
        pred = _ANCHORED_VERB_MAP.get(verb_raw)
        if not pred:
            continue

        rest = vm.group("rest").strip()
        rest_start = s_end + vm.start("rest")
        obj_id: str | None = None
        for o_start, _o_end, cand_eid in occurrences:
            if o_start >= rest_start and cand_eid != subj_id:
                obj_id = cand_eid
                break

        if obj_id is not None:
            return subj_id, pred, obj_id, entities_by_id[obj_id].canonical_name

        clause = re.split(r"[.;!?]", rest, maxsplit=1)[0].strip(" ,;:\"'")
        if len(clause) > 80:
            clause = clause.split(",", 1)[0].strip()[:80].strip()
        if len(clause) < 4 or not re.search(r"[a-zA-Z]{3,}", clause):
            continue
        return subj_id, pred, None, clause

    return None


def _build_pass2_linker(
    entities_by_id: dict[str, Entity],
) -> tuple[re.Pattern[str] | None, dict[str, str]]:
    """Build a longest-first case-insensitive regex for document entity & surname linking."""
    surface_to_eid: dict[str, str] = {}
    surname_groups: dict[str, list[str]] = {}

    for eid, ent in entities_by_id.items():
        if ent.entity_type not in {"ORG", "CONCEPT", "GPE", "PERSON"}:
            continue
        words = ent.canonical_name.split()
        if len(words) >= 2:
            surface_to_eid.setdefault(ent.canonical_name.lower(), eid)
        for alias in ent.aliases:
            if len(alias.split()) >= 2:
                surface_to_eid.setdefault(alias.lower(), eid)
        if ent.entity_type == "PERSON" and len(words) >= 2:
            surname = re.sub(r"[^a-z'-]", "", words[-1].lower())
            if len(surname) >= 3:
                surname_groups.setdefault(surname, []).append(eid)

    # Link honorific + surname (e.g., "Dr. Frederickson") only when surname is unambiguous.
    for surname, eids in surname_groups.items():
        if len(eids) != 1:
            continue
        eid = eids[0]
        ent = entities_by_id[eid]
        has_academic_title = any(
            al.lower().startswith(("dr.", "prof.")) for al in [ent.canonical_name, *ent.aliases]
        )
        if not has_academic_title:
            continue
        for prefix in ("dr.", "prof.", "mr.", "mrs.", "ms."):
            surface_to_eid.setdefault(f"{prefix} {surname}", eid)

    # Unambiguous single-organization coreference (e.g., "the program" / "the college").
    program_orgs = [
        eid
        for eid, ent in entities_by_id.items()
        if ent.entity_type == "ORG" and ent.canonical_name.lower().endswith(" program")
    ]
    if len(program_orgs) == 1:
        surface_to_eid.setdefault("the program", program_orgs[0])

    college_orgs = [
        eid
        for eid, ent in entities_by_id.items()
        if ent.entity_type == "ORG" and ent.canonical_name.lower().endswith(" college")
    ]
    if len(college_orgs) == 1:
        surface_to_eid.setdefault("the college", college_orgs[0])

    if not surface_to_eid:
        return None, {}

    # Preserve canonical honorific dot handling inside word-boundary alternation.
    ordered_surfaces = sorted(surface_to_eid.keys(), key=lambda s: (-len(s), s))
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(surf) for surf in ordered_surfaces) + r")(?=$|\W)",
        re.IGNORECASE,
    )
    return pattern, surface_to_eid


def _pick_document_subject_entity(
    doc: SourceDocument,
    entities_by_id: dict[str, Entity],
) -> str | None:
    title_low = doc.title.lower()
    candidates = [
        ent
        for ent in entities_by_id.values()
        if ent.entity_type in {"CONCEPT", "ORG"} and ent.canonical_name.lower() in title_low
    ]
    if candidates:
        best = max(candidates, key=lambda e: len(e.canonical_name))
        return best.canonical_name
    return None


class DeterministicNLPMapper:
    """Zero-download deterministic NLP mapper producing connected entities, claims, and relations."""

    name: str = "deterministic_nlp_mapper"

    def __init__(self, min_sentence_length: int = 25) -> None:
        self.min_sentence_length = min_sentence_length

    def map_document(self, doc: SourceDocument) -> MappedBatch:
        """Extract entities, claims, and grounded relations using two-pass document linking."""
        default_reliability = _reliability_from_trust(doc.trust_weight)
        base_conf = min(1.0, max(0.5, doc.trust_weight))

        # Pass 1: Extract sentences & consolidate canonical entity types across the whole document.
        sentence_records: list[
            tuple[str, int, int, Evidence, list[tuple[str, str, list[str]]]]
        ] = []
        consolidated: dict[str, dict[str, Any]] = {}

        for sentence, start, end in split_sentences(doc.content):
            if len(sentence) < self.min_sentence_length:
                continue
            evidence = Evidence(
                source_id=doc.source_id,
                uri=doc.uri,
                excerpt=sentence[:400],
                char_span=(start, end),
                extractor_name=self.name,
                extraction_confidence=min(1.0, max(0.4, doc.trust_weight)),
            )
            extracted = _extract_entities_from_sentence(sentence)
            sentence_records.append((sentence, start, end, evidence, extracted))

            for cname, etype, aliases in extracted:
                key = " ".join(cname.strip().lower().split())
                spec = _ENTITY_TYPE_SPECIFICITY.get(etype, 0)
                if key not in consolidated:
                    consolidated[key] = {
                        "canonical_name": cname,
                        "entity_type": etype,
                        "spec": spec,
                        "aliases": list(aliases),
                        "evidences": [evidence],
                        "spans": {(evidence.source_id, evidence.char_span)},
                    }
                else:
                    entry = consolidated[key]
                    if spec > entry["spec"] or (
                        spec == entry["spec"] and len(cname) > len(entry["canonical_name"])
                    ):
                        if cname != entry["canonical_name"]:
                            entry["aliases"].append(entry["canonical_name"])
                        entry["canonical_name"] = cname
                        entry["entity_type"] = etype
                        entry["spec"] = spec
                    entry["aliases"] = list(dict.fromkeys([*entry["aliases"], *aliases]))
                    span_sig = (evidence.source_id, evidence.char_span)
                    if span_sig not in entry["spans"]:
                        entry["evidences"].append(evidence)
                        entry["spans"].add(span_sig)

        entities_by_id: dict[str, Entity] = {}
        key_to_eid: dict[str, str] = {}
        seen_ent_spans: dict[str, set[tuple[str, tuple[int, int] | None]]] = {}

        for norm_key, entry in consolidated.items():
            cname = str(entry["canonical_name"])
            etype = str(entry["entity_type"])
            ent_id = deterministic_id("ent", etype, cname)
            key_to_eid[norm_key] = ent_id
            cleaned_aliases = [a for a in entry["aliases"] if a != cname]
            if ent_id not in entities_by_id:
                entities_by_id[ent_id] = Entity(
                    entity_id=ent_id,
                    canonical_name=cname,
                    entity_type=etype,
                    aliases=cleaned_aliases,
                    evidence=list(entry["evidences"]),
                )
                seen_ent_spans[ent_id] = set(entry["spans"])
            else:
                existing = entities_by_id[ent_id]
                existing.aliases = list(dict.fromkeys([*existing.aliases, *cleaned_aliases]))
                for ev in entry["evidences"]:
                    sig = (ev.source_id, ev.char_span)
                    if sig not in seen_ent_spans[ent_id]:
                        existing.evidence.append(ev)
                        seen_ent_spans[ent_id].add(sig)

        # Pass 2: Build document-wide mention linker and ground claims + semantic/mention edges.
        mention_regex, mention_lookup = _build_pass2_linker(entities_by_id)
        doc_subject = _pick_document_subject_entity(doc, entities_by_id)

        claims: list[Claim] = []
        relations_by_id: dict[str, Relation] = {}

        for sentence, _start, _end, evidence, extracted in sentence_records:
            pass1_eids = [
                key_to_eid[" ".join(cname.strip().lower().split())]
                for cname, _etype, _aliases in extracted
            ]
            sent_entity_ids: list[str] = list(dict.fromkeys(pass1_eids))
            pass2_eids: set[str] = set()

            if mention_regex is not None:
                for m in mention_regex.finditer(sentence):
                    linked_eid = mention_lookup.get(m.group(0).lower())
                    if linked_eid and linked_eid not in sent_entity_ids:
                        sent_entity_ids.append(linked_eid)
                        pass2_eids.add(linked_eid)
                        sig = (evidence.source_id, evidence.char_span)
                        if sig not in seen_ent_spans.setdefault(linked_eid, set()):
                            entities_by_id[linked_eid].evidence.append(evidence)
                            seen_ent_spans[linked_eid].add(sig)

            subj_id: str | None = None
            pred: str | None = None
            obj_id: str | None = None
            obj_lit: str | None = None

            triple = _extract_factual_triple(sentence, fallback_subject=doc_subject)
            if triple is not None:
                subj_name, pred, obj_val = triple
                matched_subj = next(
                    (
                        eid
                        for eid in sent_entity_ids
                        if entities_by_id[eid].canonical_name.lower() == subj_name.lower()
                    ),
                    None,
                )
                if matched_subj is None:
                    matched_subj = key_to_eid.get(subj_name.lower())
                if matched_subj is None:
                    matched_subj = deterministic_id("ent", "CONCEPT", subj_name)
                    if matched_subj not in entities_by_id:
                        entities_by_id[matched_subj] = Entity(
                            entity_id=matched_subj,
                            canonical_name=subj_name,
                            entity_type="CONCEPT",
                            evidence=[evidence],
                        )
                        seen_ent_spans[matched_subj] = {(evidence.source_id, evidence.char_span)}
                if matched_subj not in sent_entity_ids:
                    sent_entity_ids.append(matched_subj)
                subj_id = matched_subj

                obj_lit = obj_val
                matched_obj = next(
                    (
                        eid
                        for eid in sent_entity_ids
                        if entities_by_id[eid].canonical_name.lower() == obj_val.lower()
                    ),
                    None,
                )
                if matched_obj is not None:
                    obj_id = matched_obj
                    if matched_obj != subj_id:
                        rel_id = deterministic_id("rel", subj_id, pred, matched_obj)
                        relations_by_id[rel_id] = Relation(
                            relation_id=rel_id,
                            source_id=subj_id,
                            target_id=matched_obj,
                            relation_type=pred,
                            confidence=base_conf,
                            evidence=[evidence],
                        )
            else:
                anchored = _extract_entity_anchored_triple(
                    sentence,
                    sent_entity_ids,
                    entities_by_id,
                    mention_regex=mention_regex,
                    mention_lookup=mention_lookup,
                )
                if anchored is not None:
                    subj_id, pred, obj_id, obj_lit = anchored
                    if obj_id is not None and obj_id != subj_id:
                        rel_id = deterministic_id("rel", subj_id, pred, obj_id)
                        relations_by_id[rel_id] = Relation(
                            relation_id=rel_id,
                            source_id=subj_id,
                            target_id=obj_id,
                            relation_type=pred,
                            confidence=min(0.85, base_conf),
                            evidence=[evidence],
                        )

            claim_id = deterministic_id("clm", doc.source_id, sentence)
            tags = list(
                dict.fromkeys(entities_by_id[eid].entity_type.lower() for eid in sent_entity_ids)
            )
            if subj_id and pred and (obj_id or obj_lit):
                claim_conf = min(0.95, base_conf + 0.10)
            elif sent_entity_ids:
                claim_conf = min(0.95, base_conf + 0.05)
            else:
                claim_conf = base_conf

            claims.append(
                Claim(
                    claim_id=claim_id,
                    statement=sentence,
                    category="ExtractedFact",
                    tags=tags,
                    reliability=default_reliability,
                    source_id=doc.source_id,
                    source_title=doc.title,
                    author_creator=doc.author,
                    url_reference=doc.uri,
                    published_at=doc.published_at,
                    confidence=claim_conf,
                    subject_id=subj_id,
                    predicate=pred,
                    object_id=obj_id,
                    object_literal=obj_lit,
                    evidence=[evidence],
                )
            )

            unique_sent_eids = list(dict.fromkeys(sent_entity_ids))
            for eid in unique_sent_eids:
                m_id = deterministic_id("rel", claim_id, "MENTIONS", eid)
                relations_by_id[m_id] = Relation(
                    relation_id=m_id,
                    source_id=claim_id,
                    target_id=eid,
                    relation_type="MENTIONS",
                    confidence=0.85 if eid in pass2_eids else 0.95,
                    evidence=[evidence],
                )

            non_date_eids = [
                eid for eid in unique_sent_eids if entities_by_id[eid].entity_type != "DATE"
            ]
            for i in range(len(non_date_eids) - 1):
                a, b = non_date_eids[i], non_date_eids[i + 1]
                if a == b:
                    continue
                already_linked = any(
                    r.source_id == a and r.target_id == b for r in relations_by_id.values()
                )
                if not already_linked:
                    co_id = deterministic_id("rel", a, "CO_OCCURS_WITH", b)
                    relations_by_id[co_id] = Relation(
                        relation_id=co_id,
                        source_id=a,
                        target_id=b,
                        relation_type="CO_OCCURS_WITH",
                        confidence=0.65,
                        evidence=[evidence],
                    )

        return MappedBatch(
            source_document=doc,
            entities=list(entities_by_id.values()),
            claims=claims,
            relations=list(relations_by_id.values()),
        )

    def map_documents(self, docs: Sequence[SourceDocument]) -> list[MappedBatch]:
        """Map multiple source documents deterministically."""
        return [self.map_document(doc) for doc in docs]


class SpacyNLPMapper:
    """Optional batched spaCy dependency + NER mapper (requires ``[nlp]`` extra)."""

    name: str = "spacy_nlp_mapper"

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        min_sentence_length: int = 25,
    ) -> None:
        self.model_name = model_name
        self.min_sentence_length = min_sentence_length
        self._nlp: Any = None

    def _get_nlp(self) -> Any:
        if self._nlp is not None:
            return self._nlp
        try:
            import spacy
        except ImportError as exc:
            raise ExtractionError(
                "spaCy is not installed. Install optional extra with `uv sync --extra nlp`."
            ) from exc
        try:
            self._nlp = spacy.load(self.model_name)
        except OSError as exc:
            raise ExtractionError(
                f"spaCy model {self.model_name!r} is not installed locally. "
                f"Install it via `python -m spacy download {self.model_name}`."
            ) from exc
        return self._nlp

    def _map_parsed_doc(self, source_doc: SourceDocument, spacy_doc: Any) -> MappedBatch:
        entities_by_id: dict[str, Entity] = {}
        claims: list[Claim] = []
        relations_by_id: dict[str, Relation] = {}
        default_reliability = _reliability_from_trust(source_doc.trust_weight)

        for sent in spacy_doc.sents:
            sentence = sent.text.strip()
            if len(sentence) < self.min_sentence_length:
                continue

            evidence = Evidence(
                source_id=source_doc.source_id,
                uri=source_doc.uri,
                excerpt=sentence[:400],
                char_span=(int(sent.start_char), int(sent.end_char)),
                extractor_name=self.name,
                extraction_confidence=min(1.0, max(0.5, source_doc.trust_weight)),
            )

            sent_eids: list[str] = []
            span_to_eid: dict[int, str] = {}
            for ent in sent.ents:
                cname = ent.text.strip()
                if not cname:
                    continue
                ent_id = deterministic_id("ent", str(ent.label_), cname)
                if ent_id not in entities_by_id:
                    entities_by_id[ent_id] = Entity(
                        entity_id=ent_id,
                        canonical_name=cname,
                        entity_type=str(ent.label_),
                        evidence=[evidence],
                    )
                else:
                    entities_by_id[ent_id].evidence.append(evidence)
                sent_eids.append(ent_id)
                for tok in ent:
                    span_to_eid[int(tok.i)] = ent_id

            # Dependency triple extraction fixing prep->pobj and AUX copulas
            subj_id: str | None = None
            pred: str | None = None
            obj_id: str | None = None
            for token in sent:
                if token.pos_ not in {"VERB", "AUX"}:
                    continue
                subjs = [c for c in token.children if c.dep_ in {"nsubj", "nsubjpass"}]
                objs = [c for c in token.children if c.dep_ in {"dobj", "obj", "attr"}]
                for prep in (c for c in token.children if c.dep_ == "prep"):
                    objs.extend([p for p in prep.children if p.dep_ == "pobj"])
                if subjs and objs:
                    s_eid = span_to_eid.get(int(subjs[0].i))
                    o_eid = span_to_eid.get(int(objs[0].i))
                    rel_type = str(token.lemma_).upper()
                    if s_eid and o_eid and s_eid != o_eid:
                        subj_id = s_eid
                        pred = rel_type
                        obj_id = o_eid
                        rel_id = deterministic_id("rel", s_eid, rel_type, o_eid)
                        relations_by_id[rel_id] = Relation(
                            relation_id=rel_id,
                            source_id=s_eid,
                            target_id=o_eid,
                            relation_type=rel_type,
                            confidence=0.8,
                            evidence=[evidence],
                        )
                        break

            claim_id = deterministic_id("clm", source_doc.source_id, sentence)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    statement=sentence,
                    category="ExtractedFact",
                    tags=list(
                        dict.fromkeys(entities_by_id[eid].entity_type.lower() for eid in sent_eids)
                    ),
                    reliability=default_reliability,
                    source_id=source_doc.source_id,
                    source_title=source_doc.title,
                    author_creator=source_doc.author,
                    url_reference=source_doc.uri,
                    published_at=source_doc.published_at,
                    confidence=min(1.0, max(0.5, source_doc.trust_weight)),
                    subject_id=subj_id,
                    predicate=pred,
                    object_id=obj_id,
                    evidence=[evidence],
                )
            )
            for eid in dict.fromkeys(sent_eids):
                m_id = deterministic_id("rel", claim_id, "MENTIONS", eid)
                relations_by_id[m_id] = Relation(
                    relation_id=m_id,
                    source_id=claim_id,
                    target_id=eid,
                    relation_type="MENTIONS",
                    confidence=0.95,
                    evidence=[evidence],
                )

        return MappedBatch(
            source_document=source_doc,
            entities=list(entities_by_id.values()),
            claims=claims,
            relations=list(relations_by_id.values()),
        )

    def map_document(self, doc: SourceDocument) -> MappedBatch:
        """Map a single source document using spaCy."""
        nlp = self._get_nlp()
        return self._map_parsed_doc(doc, nlp(doc.content))

    def map_documents(self, docs: Sequence[SourceDocument]) -> list[MappedBatch]:
        """Map multiple documents in a single batched ``nlp.pipe`` pass."""
        if not docs:
            return []
        nlp = self._get_nlp()
        parsed_docs = list(nlp.pipe([d.content for d in docs]))
        return [
            self._map_parsed_doc(src_doc, spacy_doc)
            for src_doc, spacy_doc in zip(docs, parsed_docs, strict=True)
        ]
