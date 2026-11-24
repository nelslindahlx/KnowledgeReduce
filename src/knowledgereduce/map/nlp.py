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
    r"\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|Mt|Inc|Ltd|Corp|Co|Dept|Univ|Fig|No|Vol|vs|etc|e\.g|i\.e|U\.S|U\.K)\."
)
_INITIAL_PATTERN = re.compile(r"\b([A-Z])\.(?=\s+[A-Z])")
_DECIMAL_PATTERN = re.compile(r"(\d)\.(\d)")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

# Honorific-prefixed person names (e.g., "Dr. Nels Lindahl", "Dr. H. George Frederickson").
_HONORIFIC_PERSON_RE = re.compile(
    r"\b(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.)\s+(?:[A-Z]\.\s+)*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b"
)
# Organizations with strong institutional keywords.
_ORG_RE = re.compile(
    r"\b(?:University of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|"
    r"[A-Z][A-Za-z&]+(?:\s+(?:[A-Z][A-Za-z&]+|of|for|and)){0,4}\s+"
    r"(?:University|Department|Institute|Foundation|Corporation|Corp\.|Inc\.|LLC|Company|Program|Press))\b"
)
# City, State/Country location pattern (e.g., "Denver, Colorado", "Lawrence, Kansas").
_CITY_STATE_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)
# Full calendar dates and explicit standalone years.
_FULL_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}\b"
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# General capitalized multi-word phrases (fallback entity detector).
_CAP_PHRASE_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9-]+(?:\s+(?:of|for|the)?\s*[A-Z][A-Za-z0-9-]+){1,4}\b"
)
# CamelCase / PascalCase technical or system identifiers (e.g., KnowledgeReduce, DuckDB, MapReduce).
_CAMEL_ENTITY_RE = re.compile(r"\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b")

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
    }
)

_NON_PERSON_PHRASES = frozenset(
    {
        "civic honors",
        "civic engagement",
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


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split *text* into ``(sentence, start_char, end_char)`` preserving abbreviations."""
    if not text.strip():
        return []

    sentinel = "\u0000"
    masked = _ABBREV_PATTERN.sub(lambda m: m.group(0).replace(".", sentinel), text)
    masked = _INITIAL_PATTERN.sub(lambda m: f"{m.group(1)}{sentinel}", masked)
    masked = _DECIMAL_PATTERN.sub(lambda m: f"{m.group(1)}{sentinel}{m.group(2)}", masked)

    results: list[tuple[str, int, int]] = []
    pos = 0
    for match in _SENTENCE_BREAK.finditer(masked):
        raw_chunk = text[pos : match.start()]
        stripped = raw_chunk.strip()
        if stripped:
            ltrim = len(raw_chunk) - len(raw_chunk.lstrip())
            start = pos + ltrim
            end = start + len(stripped)
            results.append((stripped, start, end))
        pos = match.end()

    tail = text[pos:]
    tail_stripped = tail.strip()
    if tail_stripped:
        ltrim = len(tail) - len(tail.lstrip())
        start = pos + ltrim
        end = start + len(tail_stripped)
        results.append((tail_stripped, start, end))

    return results


def _strip_leading_stop_words(phrase: str) -> str:
    tokens = phrase.split()
    while tokens and (tokens[0] in _STOP_LEADING_WORDS or tokens[0][0].islower()):
        tokens = tokens[1:]
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
            # Upgrade CONCEPT to more specific ORG/PERSON/GPE/DATE if matched
            if old_type == "CONCEPT" and etype != "CONCEPT":
                found[key] = (old_name, etype, aliases)
            return
        init_aliases = [alias] if alias and alias != cleaned else []
        found[key] = (cleaned, etype, init_aliases)

    for m in _HONORIFIC_PERSON_RE.finditer(sentence):
        raw = m.group(0).strip()
        canonical = _strip_honorific(raw)
        _register(canonical, "PERSON", alias=raw)

    for m in _ORG_RE.finditer(sentence):
        raw = _strip_leading_stop_words(m.group(0).strip())
        if len(raw.split()) >= 2:
            _register(raw, "ORG")

    for m in _CITY_STATE_RE.finditer(sentence):
        city = _strip_leading_stop_words(m.group(1).strip())
        state = m.group(2).strip()
        if city:
            _register(city, "GPE")
        if state:
            _register(state, "GPE")

    for m in _FULL_DATE_RE.finditer(sentence):
        _register(m.group(0).strip(), "DATE")

    for m in _YEAR_RE.finditer(sentence):
        yr = m.group(0).strip()
        # Avoid registering year separately if already inside an extracted full date
        if not any(yr in name and et == "DATE" for name, et, _ in found.values()):
            _register(yr, "DATE")

    for m in _CAP_PHRASE_RE.finditer(sentence):
        candidate = _strip_leading_stop_words(m.group(0).strip())
        if not candidate or len(candidate.split()) < 2:
            continue
        words = candidate.split()
        if all(w.isupper() for w in words):
            continue
        low = candidate.lower()
        # Skip if already part of a longer extracted entity
        if any(low in existing_key or existing_key in low for existing_key in found):
            continue
        if low in _NON_PERSON_PHRASES:
            _register(candidate, "CONCEPT")
        else:
            if (
                2 <= len(words) <= 3
                and all(w[0].isupper() and w[1:].islower() for w in words)
                and not any(
                    kw in low
                    for kw in (
                        "university",
                        "department",
                        "institute",
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
                    )
                )
            ):
                _register(candidate, "PERSON")
            else:
                _register(candidate, "CONCEPT")

    for m in _CAMEL_ENTITY_RE.finditer(sentence):
        candidate = m.group(0).strip()
        low = candidate.lower()
        if any(low in existing_key or existing_key in low for existing_key in found):
            continue
        _register(candidate, "CONCEPT")

    return list(found.values())


def _extract_factual_triple(sentence: str) -> tuple[str, str, str] | None:
    for pattern, _kind in _FACTUAL_PATTERNS:
        match = pattern.search(sentence)
        if match:
            subj = _strip_leading_stop_words(_strip_honorific(match.group("subj").strip()))
            pred = re.sub(r"\s+", "_", match.group("pred").strip().upper())
            # Normalize temporal predicates cleanly
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


class DeterministicNLPMapper:
    """Zero-download deterministic NLP mapper producing connected entities, claims, and relations."""

    name: str = "deterministic_nlp_mapper"

    def __init__(self, min_sentence_length: int = 25) -> None:
        self.min_sentence_length = min_sentence_length

    def map_document(self, doc: SourceDocument) -> MappedBatch:
        """Extract entities, claims, and grounded relations from *doc*."""
        entities_by_id: dict[str, Entity] = {}
        claims: list[Claim] = []
        relations_by_id: dict[str, Relation] = {}

        default_reliability = _reliability_from_trust(doc.trust_weight)

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

            extracted_ents = _extract_entities_from_sentence(sentence)
            sent_entity_ids: list[str] = []

            for cname, etype, aliases in extracted_ents:
                ent_id = deterministic_id("ent", etype, cname)
                if ent_id not in entities_by_id:
                    entities_by_id[ent_id] = Entity(
                        entity_id=ent_id,
                        canonical_name=cname,
                        entity_type=etype,
                        aliases=aliases,
                        evidence=[evidence],
                    )
                else:
                    existing = entities_by_id[ent_id]
                    existing.aliases = list(dict.fromkeys([*existing.aliases, *aliases]))
                    existing.evidence.append(evidence)
                sent_entity_ids.append(ent_id)

            triple = _extract_factual_triple(sentence)
            subj_id: str | None = None
            pred: str | None = None
            obj_id: str | None = None
            obj_lit: str | None = None

            if triple is not None:
                subj_name, pred, obj_val = triple
                # Match existing extracted entity if possible, otherwise register CONCEPT
                matched_subj = next(
                    (
                        eid
                        for eid in sent_entity_ids
                        if entities_by_id[eid].canonical_name.lower() == subj_name.lower()
                    ),
                    None,
                )
                if matched_subj is None:
                    matched_subj = deterministic_id("ent", "CONCEPT", subj_name)
                    if matched_subj not in entities_by_id:
                        entities_by_id[matched_subj] = Entity(
                            entity_id=matched_subj,
                            canonical_name=subj_name,
                            entity_type="CONCEPT",
                            evidence=[evidence],
                        )
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
                            confidence=min(1.0, max(0.5, doc.trust_weight)),
                            evidence=[evidence],
                        )

            claim_id = deterministic_id("clm", doc.source_id, sentence)
            tags = list(
                dict.fromkeys(entities_by_id[eid].entity_type.lower() for eid in sent_entity_ids)
            )
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
                    confidence=min(1.0, max(0.5, doc.trust_weight)),
                    subject_id=subj_id,
                    predicate=pred,
                    object_id=obj_id,
                    object_literal=obj_lit,
                    evidence=[evidence],
                )
            )

            # Link Claim -> every Entity mentioned in the sentence so the graph is connected.
            unique_sent_eids = list(dict.fromkeys(sent_entity_ids))
            for eid in unique_sent_eids:
                m_id = deterministic_id("rel", claim_id, "MENTIONS", eid)
                relations_by_id[m_id] = Relation(
                    relation_id=m_id,
                    source_id=claim_id,
                    target_id=eid,
                    relation_type="MENTIONS",
                    confidence=0.95,
                    evidence=[evidence],
                )

            # Emit co-occurrence edges between non-DATE entities if no explicit predicate connected them
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
