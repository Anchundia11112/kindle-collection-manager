from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone


@dataclass(slots=True)
class CollectionCandidateInput:
    collection_candidate_name: str
    normalized_series_key: str
    book_count: int
    confidence: str
    needs_review: bool
    rule_used_set: list[str]
    book_ids: list[int]
    book_titles: list[str]


@dataclass(slots=True)
class CollectionCreateDryRunResult:
    collection_candidate_name: str
    normalized_series_key: str
    confidence: str
    needs_review: bool
    status: str
    action_taken: str
    existing_collection_name: str | None
    book_titles: list[str]
    book_count: int
    failure_reason: str | None = None


@dataclass(slots=True)
class CollectionCreateStateRecord:
    collection_candidate_name: str
    normalized_series_key: str
    confidence: str
    current_status: str
    last_attempted_at: str | None
    last_completed_at: str | None
    notes: str | None = None


def read_collection_candidate_summary(input_path: Path) -> list[CollectionCandidateInput]:
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    candidates: list[CollectionCandidateInput] = []
    for row in rows:
        candidates.append(
            CollectionCandidateInput(
                collection_candidate_name=(row.get("collection_candidate_name") or "").strip(),
                normalized_series_key=(row.get("normalized_series_key") or "").strip(),
                book_count=int((row.get("book_count") or "0").strip() or 0),
                confidence=(row.get("confidence") or "").strip().lower(),
                needs_review=_parse_bool(row.get("needs_review")),
                rule_used_set=_split_pipe_values(row.get("rule_used_set")),
                book_ids=[int(value) for value in _split_pipe_values(row.get("book_ids")) if value.isdigit()],
                book_titles=_split_pipe_values(row.get("book_titles")),
            )
        )

    return candidates


def allowed_confidence_levels(
    *,
    include_medium: bool,
    include_low: bool,
    include_medium_and_low: bool,
) -> set[str]:
    allowed = {"high"}
    if include_medium_and_low:
        return {"high", "medium", "low"}
    if include_medium:
        allowed.add("medium")
    if include_low:
        allowed.add("low")
    return allowed


def build_create_collections_dry_run(
    candidates: list[CollectionCandidateInput],
    *,
    existing_collections: list[str] | None = None,
    include_medium: bool,
    include_low: bool,
    include_medium_and_low: bool,
    collection_name: str | None,
    collection_exact: str | None,
) -> list[CollectionCreateDryRunResult]:
    allowed_confidences = allowed_confidence_levels(
        include_medium=include_medium,
        include_low=include_low,
        include_medium_and_low=include_medium_and_low,
    )

    filtered_candidates = candidates
    if collection_exact:
        query = collection_exact.casefold()
        filtered_candidates = [
            candidate
            for candidate in filtered_candidates
            if candidate.collection_candidate_name.casefold() == query
        ]
    elif collection_name:
        query = collection_name.casefold()
        filtered_candidates = [
            candidate
            for candidate in filtered_candidates
            if query in candidate.collection_candidate_name.casefold()
        ]

    results: list[CollectionCreateDryRunResult] = []
    existing_collections = existing_collections or []
    for candidate in filtered_candidates:
        if candidate.confidence not in allowed_confidences:
            status = "skipped_by_confidence"
            action_taken = "skip"
            existing_collection_name = None
        else:
            exact_match, possible_collision = classify_collection_name_against_existing(
                candidate.collection_candidate_name,
                existing_collections,
            )
            if exact_match is not None:
                status = "already_exists"
                action_taken = "skip"
                existing_collection_name = exact_match
            elif possible_collision is not None:
                status = "manual_review_required"
                action_taken = "skip"
                existing_collection_name = possible_collision
            elif candidate.needs_review:
                status = "manual_review_required"
                action_taken = "skip"
                existing_collection_name = None
            else:
                status = "would_create"
                action_taken = "would_create"
                existing_collection_name = None

        results.append(
            CollectionCreateDryRunResult(
                collection_candidate_name=candidate.collection_candidate_name,
                normalized_series_key=candidate.normalized_series_key,
                confidence=candidate.confidence,
                needs_review=candidate.needs_review,
                status=status,
                action_taken=action_taken,
                existing_collection_name=existing_collection_name,
                book_titles=candidate.book_titles,
                book_count=candidate.book_count,
            )
        )

    return sorted(results, key=lambda result: result.collection_candidate_name.lower())


def classify_collection_name_against_existing(
    candidate_name: str,
    existing_collections: list[str],
) -> tuple[str | None, str | None]:
    candidate_casefold = candidate_name.casefold()
    for existing_name in existing_collections:
        if existing_name.casefold() == candidate_casefold:
            return existing_name, None

    candidate_loose = _normalize_loose_name(candidate_name)
    candidate_tokens = set(candidate_loose.split())
    for existing_name in existing_collections:
        existing_loose = _normalize_loose_name(existing_name)
        if not existing_loose:
            continue
        existing_tokens = set(existing_loose.split())
        if existing_loose == candidate_loose:
            return None, existing_name
        if candidate_loose and (candidate_loose in existing_loose or existing_loose in candidate_loose):
            return None, existing_name
        if candidate_tokens and existing_tokens and (
            candidate_tokens.issubset(existing_tokens) or existing_tokens.issubset(candidate_tokens)
        ):
            return None, existing_name
    return None, None


def render_create_collections_tree(results: list[CollectionCreateDryRunResult]) -> str:
    if not results:
        return "No collection candidates matched the requested filters.\n"

    sections: list[str] = []
    for result in results:
        lines = [
            f"Collection: {result.collection_candidate_name}",
            f"  status: {result.status}",
            f"  confidence: {result.confidence}",
            f"  needs review: {'yes' if result.needs_review else 'no'}",
            f"  normalized key: {result.normalized_series_key}",
            f"  books matched: {result.book_count}",
        ]
        if result.existing_collection_name:
            lines.append(f"  existing collection: {result.existing_collection_name}")
        if result.failure_reason:
            lines.append(f"  failure reason: {result.failure_reason}")
        lines.append("  books:")
        for title in result.book_titles:
            lines.append(f"    - {title}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def summarize_create_collections_results(
    results: list[CollectionCreateDryRunResult],
) -> dict[str, int]:
    summary = {
        "total": len(results),
        "would_create": 0,
        "manual_review_required": 0,
        "skipped_by_confidence": 0,
        "already_exists": 0,
        "failed": 0,
    }
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary


def summarize_candidate_inventory_by_confidence(
    candidates: list[CollectionCandidateInput],
) -> dict[str, int]:
    summary = {
        "total_candidates": len(candidates),
        "total_books": 0,
        "high_candidates": 0,
        "medium_candidates": 0,
        "low_candidates": 0,
        "high_books": 0,
        "medium_books": 0,
        "low_books": 0,
    }
    for candidate in candidates:
        summary["total_books"] += candidate.book_count
        summary[f"{candidate.confidence}_candidates"] += 1
        summary[f"{candidate.confidence}_books"] += candidate.book_count
    return summary


def summarize_state_records_by_confidence(
    state_records: list[CollectionCreateStateRecord],
) -> dict[str, int]:
    summary = {
        "completed_high_books": 0,
        "completed_medium_books": 0,
        "completed_low_books": 0,
        "missing_high_books": 0,
        "missing_medium_books": 0,
        "missing_low_books": 0,
        "manual_review_high_books": 0,
        "manual_review_medium_books": 0,
        "manual_review_low_books": 0,
        "skipped_high_books": 0,
        "skipped_medium_books": 0,
        "skipped_low_books": 0,
    }
    return summary


def write_create_collections_audit_csv(
    output_path: Path,
    *,
    results: list[CollectionCreateDryRunResult],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "collection_candidate_name",
        "normalized_series_key",
        "confidence",
        "needs_review",
        "status",
        "existing_collection_name",
        "action_taken",
        "failure_reason",
        "book_count",
        "book_titles",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "collection_candidate_name": result.collection_candidate_name,
                    "normalized_series_key": result.normalized_series_key,
                    "confidence": result.confidence,
                    "needs_review": result.needs_review,
                    "status": result.status,
                    "existing_collection_name": result.existing_collection_name or "",
                    "action_taken": result.action_taken,
                    "failure_reason": result.failure_reason or "",
                    "book_count": result.book_count,
                    "book_titles": " | ".join(result.book_titles),
                }
            )


def read_create_collections_state(input_path: Path) -> dict[str, CollectionCreateStateRecord]:
    if not input_path.exists():
        return {}

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    records: dict[str, CollectionCreateStateRecord] = {}
    for row in rows:
        normalized_series_key = (row.get("normalized_series_key") or "").strip()
        if not normalized_series_key:
            continue
        records[normalized_series_key] = CollectionCreateStateRecord(
            collection_candidate_name=(row.get("collection_candidate_name") or "").strip(),
            normalized_series_key=normalized_series_key,
            confidence=(row.get("confidence") or "").strip().lower(),
            current_status=(row.get("current_status") or "").strip(),
            last_attempted_at=(row.get("last_attempted_at") or "").strip() or None,
            last_completed_at=(row.get("last_completed_at") or "").strip() or None,
            notes=(row.get("notes") or "").strip() or None,
        )
    return records


def update_state_from_dry_run(
    existing_state: dict[str, CollectionCreateStateRecord],
    *,
    candidates: list[CollectionCandidateInput],
    results: list[CollectionCreateDryRunResult],
) -> dict[str, CollectionCreateStateRecord]:
    updated_state = dict(existing_state)
    candidate_lookup = {candidate.normalized_series_key: candidate for candidate in candidates}
    result_lookup = {result.normalized_series_key: result for result in results}
    attempted_at = _utc_timestamp()

    for normalized_series_key, candidate in candidate_lookup.items():
        existing_record = updated_state.get(normalized_series_key)
        result = result_lookup.get(normalized_series_key)

        if existing_record and existing_record.current_status == "completed":
            updated_state[normalized_series_key] = CollectionCreateStateRecord(
                collection_candidate_name=candidate.collection_candidate_name,
                normalized_series_key=normalized_series_key,
                confidence=candidate.confidence,
                current_status="completed",
                last_attempted_at=attempted_at,
                last_completed_at=existing_record.last_completed_at,
                notes=existing_record.notes,
            )
            continue

        current_status = "missing"
        notes: str | None = None
        if result is None:
            current_status = "missing"
        elif result.status in {"already_exists", "created"}:
            current_status = "completed"
        elif result.status == "manual_review_required":
            current_status = "manual_review_required"
        elif result.status == "skipped_by_confidence":
            current_status = "skipped_by_confidence"
        elif result.status == "would_create":
            current_status = "missing"
        elif result.status == "failed":
            current_status = "missing"
            notes = result.failure_reason

        updated_state[normalized_series_key] = CollectionCreateStateRecord(
            collection_candidate_name=candidate.collection_candidate_name,
            normalized_series_key=normalized_series_key,
            confidence=candidate.confidence,
            current_status=current_status,
            last_attempted_at=attempted_at,
            last_completed_at=existing_record.last_completed_at if existing_record else None,
            notes=notes if notes else (existing_record.notes if existing_record else None),
        )

    return updated_state


def write_create_collections_state_csv(
    output_path: Path,
    *,
    state_records: dict[str, CollectionCreateStateRecord],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "collection_candidate_name",
        "normalized_series_key",
        "confidence",
        "current_status",
        "last_attempted_at",
        "last_completed_at",
        "notes",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for normalized_series_key in sorted(state_records):
            record = state_records[normalized_series_key]
            writer.writerow(
                {
                    "collection_candidate_name": record.collection_candidate_name,
                    "normalized_series_key": record.normalized_series_key,
                    "confidence": record.confidence,
                    "current_status": record.current_status,
                    "last_attempted_at": record.last_attempted_at or "",
                    "last_completed_at": record.last_completed_at or "",
                    "notes": record.notes or "",
                }
            )


def summarize_persisted_state_books(
    state_records: dict[str, CollectionCreateStateRecord],
    *,
    candidates: list[CollectionCandidateInput],
) -> dict[str, int]:
    summary = {
        "completed_high_books": 0,
        "completed_medium_books": 0,
        "completed_low_books": 0,
        "missing_high_books": 0,
        "missing_medium_books": 0,
        "missing_low_books": 0,
        "manual_review_high_books": 0,
        "manual_review_medium_books": 0,
        "manual_review_low_books": 0,
        "skipped_high_books": 0,
        "skipped_medium_books": 0,
        "skipped_low_books": 0,
    }
    candidate_lookup = {candidate.normalized_series_key: candidate for candidate in candidates}
    for normalized_series_key, record in state_records.items():
        candidate = candidate_lookup.get(normalized_series_key)
        if candidate is None:
            continue
        books = candidate.book_count
        confidence = record.confidence
        if record.current_status == "completed":
            summary[f"completed_{confidence}_books"] += books
        elif record.current_status == "manual_review_required":
            summary[f"manual_review_{confidence}_books"] += books
        elif record.current_status == "skipped_by_confidence":
            summary[f"skipped_{confidence}_books"] += books
        else:
            summary[f"missing_{confidence}_books"] += books
    return summary


def _split_pipe_values(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    return [value.strip() for value in raw_value.split("|") if value.strip()]


def _parse_bool(raw_value: str | None) -> bool:
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes"}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_loose_name(value: str) -> str:
    lowered = value.casefold()
    lowered = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return " ".join(lowered.split())
