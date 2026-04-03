from pathlib import Path
import tempfile

from kindle_service.create_collections import (
    allowed_confidence_levels,
    build_create_collections_dry_run,
    classify_collection_name_against_existing,
    read_collection_candidate_summary,
    summarize_candidate_inventory_by_confidence,
    summarize_persisted_state_books,
    update_state_from_dry_run,
)


def test_allowed_confidence_levels_defaults_to_high_only() -> None:
    allowed = allowed_confidence_levels(
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
    )

    assert allowed == {"high"}


def test_allowed_confidence_levels_supports_all_when_requested() -> None:
    allowed = allowed_confidence_levels(
        include_medium=False,
        include_low=False,
        include_medium_and_low=True,
    )

    assert allowed == {"high", "medium", "low"}


def test_read_collection_candidate_summary_parses_pipe_delimited_fields(tmp_path: Path) -> None:
    input_path = tmp_path / "collection_candidates_summary.csv"
    input_path.write_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Zero no Tsukaima,zero no tsukaima,3,high,False,prefix_volume_marker,1 | 2 | 3,Zero no Tsukaima vol.14 | Zero no Tsukaima vol.15 | Zero no Tsukaima vol.16\n",
        encoding="utf-8",
    )

    candidates = read_collection_candidate_summary(input_path)

    assert len(candidates) == 1
    assert candidates[0].collection_candidate_name == "Zero no Tsukaima"
    assert candidates[0].book_ids == [1, 2, 3]
    assert len(candidates[0].book_titles) == 3


def test_build_create_collections_dry_run_skips_lower_confidence_by_default() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
        "Allison III,allison iii,2,medium,True,prefix_part_marker,4 | 5,Allison III (Part 1) | Allison III (Part 2)\n"
    )

    results = build_create_collections_dry_run(
        candidates,
        existing_collections=None,
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
        collection_name=None,
        collection_exact=None,
    )

    assert [result.status for result in results] == ["skipped_by_confidence", "would_create"]


def test_build_create_collections_dry_run_filters_by_collection_name() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
        "Zero no Tsukaima,zero no tsukaima,3,high,False,prefix_volume_marker,4 | 5 | 6,Zero no Tsukaima vol.14 | Zero no Tsukaima vol.15 | Zero no Tsukaima vol.16\n"
    )

    results = build_create_collections_dry_run(
        candidates,
        existing_collections=None,
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
        collection_name="crad",
        collection_exact=None,
    )

    assert len(results) == 1
    assert results[0].collection_candidate_name == "Cradle"


def test_classify_collection_name_against_existing_matches_case_insensitive_exact() -> None:
    exact_match, possible_collision = classify_collection_name_against_existing(
        "Zero no Tsukaima",
        ["Zero No Tsukaima"],
    )

    assert exact_match == "Zero No Tsukaima"
    assert possible_collision is None


def test_classify_collection_name_against_existing_flags_possible_collision() -> None:
    exact_match, possible_collision = classify_collection_name_against_existing(
        "The Seven Virtues",
        ["Seven Virtues"],
    )

    assert exact_match is None
    assert possible_collision == "Seven Virtues"


def test_build_create_collections_dry_run_marks_existing_collections() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
    )

    results = build_create_collections_dry_run(
        candidates,
        existing_collections=["cradle"],
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
        collection_name=None,
        collection_exact=None,
    )

    assert len(results) == 1
    assert results[0].status == "already_exists"


def test_summarize_candidate_inventory_counts_books_across_all_confidences() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
        "Allison III,allison iii,2,medium,True,prefix_part_marker,4 | 5,Allison III (Part 1) | Allison III (Part 2)\n"
        "Decapitation,decapitation,4,low,True,repeated_structured_prefix,6 | 7 | 8 | 9,Decapitation 1 | Decapitation 2 | Decapitation 3 | Decapitation 4\n"
    )

    summary = summarize_candidate_inventory_by_confidence(candidates)

    assert summary["total_books"] == 9
    assert summary["high_books"] == 3
    assert summary["medium_books"] == 2
    assert summary["low_books"] == 4


def test_update_state_from_dry_run_marks_missing_and_skipped_statuses() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
        "Allison III,allison iii,2,medium,True,prefix_part_marker,4 | 5,Allison III (Part 1) | Allison III (Part 2)\n"
    )
    results = build_create_collections_dry_run(
        candidates,
        existing_collections=None,
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
        collection_name=None,
        collection_exact=None,
    )

    state = update_state_from_dry_run({}, candidates=candidates, results=results)
    persisted_summary = summarize_persisted_state_books(state, candidates=candidates)

    assert state["cradle"].current_status == "missing"
    assert state["allison iii"].current_status == "skipped_by_confidence"
    assert persisted_summary["missing_high_books"] == 3
    assert persisted_summary["skipped_medium_books"] == 2


def test_build_create_collections_dry_run_filters_by_exact_collection_name() -> None:
    candidates = read_collection_candidate_summary_from_text(
        "collection_candidate_name,normalized_series_key,book_count,confidence,needs_review,rule_used_set,book_ids,book_titles\n"
        "Cradle,cradle,3,high,False,parenthetical_series_book,1 | 2 | 3,Unsouled | Soulsmith | Blackflame\n"
        "Cradle Collection,cradle collection,2,high,False,prefix_volume_marker,4 | 5,Cradle Collection 1 | Cradle Collection 2\n"
    )

    results = build_create_collections_dry_run(
        candidates,
        existing_collections=None,
        include_medium=False,
        include_low=False,
        include_medium_and_low=False,
        collection_name=None,
        collection_exact="Cradle",
    )

    assert len(results) == 1
    assert results[0].collection_candidate_name == "Cradle"


def read_collection_candidate_summary_from_text(csv_text: str):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "collection_candidates_summary.csv"
        temp_path.write_text(csv_text, encoding="utf-8")
        return read_collection_candidate_summary(temp_path)
