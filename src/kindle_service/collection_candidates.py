from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from kindle_service.models import Book


_WHITESPACE_RE = re.compile(r"\s+")
_PARENTHETICAL_SERIES_RE = re.compile(
    r"\((?P<series>[^()]+?)\s+(?P<marker>Volume|Vol\.?|Book|Part)\s*(?P<volume>#?\s*[A-Za-z0-9][A-Za-z0-9.\-]*)\)",
    re.IGNORECASE,
)
_PARENTHETICAL_REVERSE_SERIES_RE = re.compile(
    r"\((?P<marker>Book|Part)\s*(?P<volume>#?\s*[A-Za-z0-9][A-Za-z0-9.\-]*)\s+(?:of|in)\s+(?P<series>[^()]+?)\)",
    re.IGNORECASE,
)
_PREFIX_MARKER_RE = re.compile(
    r"^(?P<series>[^()]+?)(?:\s*[:,-]\s*|\s+)(?P<marker>Volume|Vol\.?|Book|Part)\s*(?P<volume>#?\s*[A-Za-z0-9][A-Za-z0-9.\-]*)\b",
    re.IGNORECASE,
)
_PREFIX_REVERSE_SERIES_RE = re.compile(
    r"^(?P<title>.+?)[:,-]\s*(?P<marker>Book|Part)\s*(?P<volume>#?\s*[A-Za-z0-9][A-Za-z0-9.\-]*)\s+(?:of|in)\s+(?P<series>.+)$",
    re.IGNORECASE,
)
_ROMAN_NUMERAL_SUFFIX_RE = re.compile(
    r"^(?P<series>.+?)\s+(?P<volume>(?:[IVXLCDM]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten))$",
    re.IGNORECASE,
)
_TRAILING_NUMBER_RE = re.compile(r"^(?P<series>.+?)\s+(?P<volume>\d+(?:\.\d+)?)$")
_PARTIAL_PART_SUFFIX_RE = re.compile(r"^(?P<series>.+?)\s+\(Part\s+(?P<volume>\d+)\)", re.IGNORECASE)
_NOISE_PATTERNS = (
    re.compile(r"\s+\((?:Z-Library|z-lib\.org)\)\s*$", re.IGNORECASE),
    re.compile(r"\s+\[?(?:Premium|Premium Ver\.?)\]?\s*$", re.IGNORECASE),
    re.compile(r"\s+\((?:Light Novel)\)\s*$", re.IGNORECASE),
    re.compile(r"â€”", re.IGNORECASE),
    re.compile(r"â€™", re.IGNORECASE),
)
_ANTHOLOGY_MARKERS = ("anthology",)
_BOX_SET_MARKERS = ("box set", "boxed set", "omnibus", "collection")


@dataclass(slots=True)
class BookCandidateRecord:
    book_id: int | None
    original_title: str
    normalized_title: str
    normalized_series_key: str | None
    collection_candidate_name: str | None
    rule_used: str
    confidence: str
    volume_detected: str | None
    needs_review: bool
    skip_reason: str | None
    source_type: str | None
    source_page: str | None
    is_expired: bool
    group_count: int = 0
    eligible_for_collection: bool = False


@dataclass(slots=True)
class CollectionCandidateSummary:
    collection_candidate_name: str
    normalized_series_key: str
    book_count: int
    confidence: str
    needs_review: bool
    rule_used_set: list[str]
    book_ids: list[int]
    book_titles: list[str]


@dataclass(slots=True)
class CandidateGenerationResult:
    books: list[BookCandidateRecord]
    collections: list[CollectionCandidateSummary]


def generate_collection_candidates(
    books: list[Book],
    *,
    min_books: int = 2,
    review_only: bool = False,
) -> CandidateGenerationResult:
    analyzed_books = [analyze_book(book) for book in books]

    grouped: dict[str, list[BookCandidateRecord]] = {}
    for record in analyzed_books:
        if record.normalized_series_key:
            grouped.setdefault(record.normalized_series_key, []).append(record)

    collection_summaries = build_collection_summaries(grouped, min_books=min_books)

    if review_only:
        analyzed_books = [record for record in analyzed_books if record.needs_review]
        filtered_grouped: dict[str, list[BookCandidateRecord]] = {}
        for record in analyzed_books:
            if record.normalized_series_key:
                filtered_grouped.setdefault(record.normalized_series_key, []).append(record)
        collection_summaries = build_collection_summaries(filtered_grouped, min_books=min_books)

    return CandidateGenerationResult(
        books=sorted(analyzed_books, key=lambda record: record.original_title.lower()),
        collections=collection_summaries,
    )


def build_collection_summaries(
    grouped: dict[str, list[BookCandidateRecord]],
    *,
    min_books: int,
) -> list[CollectionCandidateSummary]:
    collection_summaries: list[CollectionCandidateSummary] = []
    for normalized_series_key, group in sorted(grouped.items()):
        group_count = len(group)
        for record in group:
            record.group_count = group_count
            if group_count < min_books:
                record.skip_reason = "only_one_matching_book"
                record.needs_review = True
                record.eligible_for_collection = False
            else:
                record.eligible_for_collection = not record.needs_review

        if group_count < min_books:
            continue

        first_record = group[0]
        summary = CollectionCandidateSummary(
            collection_candidate_name=first_record.collection_candidate_name or first_record.normalized_title,
            normalized_series_key=normalized_series_key,
            book_count=group_count,
            confidence=_max_confidence(record.confidence for record in group),
            needs_review=any(record.needs_review for record in group),
            rule_used_set=sorted({record.rule_used for record in group}),
            book_ids=[record.book_id for record in group if record.book_id is not None],
            book_titles=[record.original_title for record in group],
        )
        collection_summaries.append(summary)
    return sorted(collection_summaries, key=lambda summary: summary.collection_candidate_name.lower())


def analyze_book(book: Book) -> BookCandidateRecord:
    normalized_title = cleanup_title(book.title)
    extracted = extract_series_candidate(normalized_title)

    return BookCandidateRecord(
        book_id=book.id,
        original_title=book.title,
        normalized_title=normalized_title,
        normalized_series_key=extracted.normalized_series_key,
        collection_candidate_name=extracted.collection_candidate_name,
        rule_used=extracted.rule_used,
        confidence=extracted.confidence,
        volume_detected=extracted.volume_detected,
        needs_review=extracted.needs_review,
        skip_reason=extracted.skip_reason,
        source_type=book.source_type,
        source_page=book.source_page,
        is_expired=book.is_expired,
    )


@dataclass(frozen=True, slots=True)
class _ExtractionResult:
    normalized_series_key: str | None
    collection_candidate_name: str | None
    rule_used: str
    confidence: str
    volume_detected: str | None
    needs_review: bool
    skip_reason: str | None


def extract_series_candidate(normalized_title: str) -> _ExtractionResult:
    lower_title = normalized_title.lower()
    needs_review = False
    skip_reason: str | None = None

    if any(marker in lower_title for marker in _ANTHOLOGY_MARKERS):
        return _ExtractionResult(
            normalized_series_key=None,
            collection_candidate_name=None,
            rule_used="no_series_match",
            confidence="low",
            volume_detected=None,
            needs_review=True,
            skip_reason="ambiguous_anthology",
        )

    parenthetical_match = _last_match(_PARENTHETICAL_SERIES_RE, normalized_title)
    if parenthetical_match:
        collection_name = cleanup_display_series(parenthetical_match.group("series"))
        if _looks_ambiguous_box_set(normalized_title):
            needs_review = True
            skip_reason = "ambiguous_box_set"
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="parenthetical_series_book",
            confidence="high",
            volume_detected=parenthetical_match.group("volume"),
            needs_review=needs_review,
            skip_reason=skip_reason,
        )

    parenthetical_reverse_match = _last_match(_PARENTHETICAL_REVERSE_SERIES_RE, normalized_title)
    if parenthetical_reverse_match:
        collection_name = cleanup_display_series(parenthetical_reverse_match.group("series"))
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="parenthetical_series_book",
            confidence="high",
            volume_detected=_clean_volume(parenthetical_reverse_match.group("volume")),
            needs_review=False,
            skip_reason=None,
        )

    prefix_reverse_match = _PREFIX_REVERSE_SERIES_RE.search(normalized_title)
    if prefix_reverse_match:
        collection_name = cleanup_display_series(prefix_reverse_match.group("series"))
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="prefix_book_marker",
            confidence="high",
            volume_detected=_clean_volume(prefix_reverse_match.group("volume")),
            needs_review=False,
            skip_reason=None,
        )

    prefix_match = _PREFIX_MARKER_RE.search(normalized_title)
    if prefix_match:
        collection_name = cleanup_display_series(prefix_match.group("series"))
        confidence = "high"
        if _looks_ambiguous_box_set(normalized_title):
            needs_review = True
            skip_reason = "ambiguous_box_set"
            confidence = "low"
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used=_rule_for_marker(prefix_match.group("marker")),
            confidence=confidence,
            volume_detected=_clean_volume(prefix_match.group("volume")),
            needs_review=needs_review,
            skip_reason=skip_reason,
        )

    part_match = _PARTIAL_PART_SUFFIX_RE.search(normalized_title)
    if part_match:
        collection_name = cleanup_display_series(part_match.group("series"))
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="prefix_part_marker",
            confidence="medium",
            volume_detected=_clean_volume(part_match.group("volume")),
            needs_review=True,
            skip_reason="low_confidence_match",
        )

    trailing_number_match = _TRAILING_NUMBER_RE.search(normalized_title)
    if trailing_number_match and _can_use_trailing_number_rule(trailing_number_match.group("series")):
        collection_name = cleanup_display_series(trailing_number_match.group("series"))
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="repeated_structured_prefix",
            confidence="medium",
            volume_detected=_clean_volume(trailing_number_match.group("volume")),
            needs_review=True,
            skip_reason="low_confidence_match",
        )

    roman_match = _ROMAN_NUMERAL_SUFFIX_RE.search(normalized_title)
    if roman_match:
        collection_name = cleanup_display_series(roman_match.group("series"))
        return _ExtractionResult(
            normalized_series_key=normalize_series_key(collection_name),
            collection_candidate_name=collection_name,
            rule_used="roman_numeral_suffix",
            confidence="medium",
            volume_detected=roman_match.group("volume"),
            needs_review=True,
            skip_reason="low_confidence_match",
        )

    return _ExtractionResult(
        normalized_series_key=None,
        collection_candidate_name=None,
        rule_used="no_series_match",
        confidence="low",
        volume_detected=None,
        needs_review=False,
        skip_reason="no_series_pattern_detected",
    )


def cleanup_title(title: str) -> str:
    cleaned = title.strip()
    replacements = {
        "_": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "â€”": "-",
        "â€™": "'",
    }
    for source, replacement in replacements.items():
        cleaned = cleaned.replace(source, replacement)

    for pattern in _NOISE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" -,:")


def cleanup_display_series(value: str) -> str:
    cleaned = cleanup_title(value)
    return cleaned.strip(" -,:")


def normalize_series_key(value: str) -> str:
    normalized = cleanup_title(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def _rule_for_marker(marker: str) -> str:
    lowered = marker.lower().rstrip(".")
    if lowered == "book":
        return "prefix_book_marker"
    if lowered == "part":
        return "prefix_part_marker"
    return "prefix_volume_marker"


def _looks_ambiguous_box_set(title: str) -> bool:
    lower_title = title.lower()
    if any(marker in lower_title for marker in _BOX_SET_MARKERS):
        return True
    return bool(re.search(r"books?\s+\d+\s*-\s*\d+", lower_title))


def _last_match(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    match: re.Match[str] | None = None
    for current in pattern.finditer(text):
        match = current
    return match


def _clean_volume(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("#", "").strip()
    return normalized or None


def _can_use_trailing_number_rule(series: str) -> bool:
    cleaned = cleanup_display_series(series)
    if len(cleaned.split()) < 3:
        return False
    if cleaned.endswith(("Book", "Vol", "Volume", "Part")):
        return False
    return True


def _max_confidence(confidences: list[str] | tuple[str, ...] | object) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    best = "low"
    for confidence in confidences:
        if order.get(confidence, -1) > order[best]:
            best = confidence
    return best


def write_candidate_output(
    output_path: Path,
    *,
    result: CandidateGenerationResult,
    output_format: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        lines = [json.dumps(asdict(record), ensure_ascii=False) for record in result.books]
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return

    output_path.write_text(render_candidate_text(result), encoding="utf-8")


def write_candidate_jsonl(output_path: Path, *, result: CandidateGenerationResult) -> None:
    write_candidate_output(output_path, result=result, output_format="jsonl")


def write_candidate_review_csv(output_path: Path, *, result: CandidateGenerationResult) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "book_id",
        "original_title",
        "normalized_title",
        "normalized_series_key",
        "collection_candidate_name",
        "rule_used",
        "confidence",
        "volume_detected",
        "needs_review",
        "skip_reason",
        "eligible_for_collection",
        "group_count",
        "source_type",
        "source_page",
        "is_expired",
    ]
    review_records = [
        record
        for record in result.books
        if record.needs_review or record.confidence in {"medium", "low"}
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in review_records:
            writer.writerow(asdict(record))


def write_candidate_summary_csv(output_path: Path, *, result: CandidateGenerationResult) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "collection_candidate_name",
        "normalized_series_key",
        "book_count",
        "confidence",
        "needs_review",
        "rule_used_set",
        "book_ids",
        "book_titles",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in result.collections:
            writer.writerow(
                {
                    "collection_candidate_name": summary.collection_candidate_name,
                    "normalized_series_key": summary.normalized_series_key,
                    "book_count": summary.book_count,
                    "confidence": summary.confidence,
                    "needs_review": summary.needs_review,
                    "rule_used_set": " | ".join(summary.rule_used_set),
                    "book_ids": " | ".join(str(book_id) for book_id in summary.book_ids),
                    "book_titles": " | ".join(summary.book_titles),
                }
            )


def render_book_record(record: BookCandidateRecord) -> str:
    return (
        f"Found Book title: {record.original_title}\n"
        f"Book id: {record.book_id if record.book_id is not None else 'none'}\n"
        f"Source type: {record.source_type or 'none'}\n"
        f"Source page: {record.source_page or 'none'}\n"
        f"Expired: {'yes' if record.is_expired else 'no'}\n"
        f"Normalized Book title: {record.normalized_title}\n"
        f"Normalized Series key: {record.normalized_series_key or 'none'}\n"
        f"Collection Candidate name: {record.collection_candidate_name or 'none'}\n"
        f"Rule used to normalize: {record.rule_used}\n"
        f"Detected volume: {record.volume_detected or 'none'}\n"
        f"Confidence: {record.confidence}\n"
        f"Needs review: {'yes' if record.needs_review else 'no'}\n"
        f"Eligible for collection: {'yes' if record.eligible_for_collection else 'no'}\n"
        f"Matching books found: {record.group_count}\n"
        f"Skip reason: {record.skip_reason or 'none'}"
    )


def render_collection_summary(summary: CollectionCandidateSummary) -> str:
    rules = ", ".join(summary.rule_used_set)
    return (
        f"Collection Candidate: {summary.collection_candidate_name}\n"
        f"Normalized Series key: {summary.normalized_series_key}\n"
        f"Books matched: {summary.book_count}\n"
        f"Confidence: {summary.confidence}\n"
        f"Needs review: {'yes' if summary.needs_review else 'no'}\n"
        f"Rules used: {rules}"
    )


def render_candidate_text(result: CandidateGenerationResult) -> str:
    sections: list[str] = []
    for record in result.books:
        sections.append(render_book_record(record))

    sections.append(
        "Candidate summary:\n"
        f"Books analyzed: {len(result.books)}\n"
        f"Collections proposed: {len(result.collections)}"
    )

    if result.collections:
        for summary in result.collections:
            sections.append(render_collection_summary(summary))

    return "\n\n".join(sections) + "\n"
