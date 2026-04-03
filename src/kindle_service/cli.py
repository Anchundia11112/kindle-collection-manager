from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from kindle_service.collection_candidates import (
    build_collection_summaries,
    generate_collection_candidates,
    render_book_record,
    render_collection_summary,
    write_candidate_output,
    write_candidate_jsonl,
    write_candidate_review_csv,
    write_candidate_summary_csv,
)
from kindle_service.config import Settings
from kindle_service.create_collections import (
    build_create_collections_dry_run,
    read_collection_candidate_summary,
    read_create_collections_state,
    render_create_collections_tree,
    summarize_create_collections_results,
    summarize_candidate_inventory_by_confidence,
    summarize_persisted_state_books,
    update_state_from_dry_run,
    write_create_collections_audit_csv,
    write_create_collections_state_csv,
)
from kindle_service.models import Book
from kindle_service.storage import (
    CURRENT_SCHEMA_VERSION,
    DatabaseUpdatePlan,
    DuplicateBookError,
    DuplicateCollectionPlanError,
    create_collection_plan,
    initialize_database,
    inspect_database,
    list_books,
    list_collection_plans,
    search_books,
    upsert_book,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def configure_standard_streams() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kindle-service")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db_parser = subparsers.add_parser(
        "init-db",
        help="Initialize the local SQLite database",
    )
    init_db_parser.add_argument(
        "--plan",
        action="store_true",
        help="Show the planned database changes without applying them",
    )
    init_db_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apply a required schema migration",
    )

    create_collection_parser = subparsers.add_parser(
        "create-collection-plan",
        help="Create a local collection plan",
    )
    create_collection_parser.add_argument("name", help="Collection plan name")

    subparsers.add_parser(
        "list-collection-plans",
        help="List local collection plans",
    )

    add_book_parser = subparsers.add_parser(
        "add-book",
        help="Temporarily add one local book record for development only",
    )
    add_book_parser.add_argument("title", help="Book title")
    add_book_parser.add_argument("--author", help="Book author")
    add_book_parser.add_argument("--asin", help="Amazon ASIN or local unique identifier")
    add_book_parser.add_argument(
        "--source-type",
        choices=["amazon_book", "personal_document", "manual_temp"],
        help="Book source type",
    )
    add_book_parser.add_argument("--source", help="Import source label")
    add_book_parser.add_argument("--source-page", help="Source page identifier")

    list_books_parser = subparsers.add_parser("list-books", help="List books in local storage")
    list_books_parser.add_argument(
        "--show-db-id",
        action="store_true",
        help="Show the local database id for each book",
    )
    list_books_parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Show only expired books",
    )
    list_books_parser.add_argument(
        "--group-by-title",
        action="store_true",
        help="Group matching rows by title and show how many local records exist for each title",
    )
    list_books_parser.add_argument(
        "--title-only",
        action="store_true",
        help="Print only book titles",
    )
    list_books_parser.add_argument(
        "--count",
        type=int,
        help="When grouping by title, show only groups with exactly this many local records",
    )
    list_books_parser.add_argument(
        "--min-count",
        type=int,
        help="When grouping by title, show only groups with at least this many local records",
    )
    search_books_parser = subparsers.add_parser(
        "search-books",
        help="Search books in local storage",
    )
    search_books_parser.add_argument("query", nargs="?", default="", help="Search text")
    search_books_parser.add_argument(
        "--show-db-id",
        action="store_true",
        help="Show the local database id for each book",
    )
    search_books_parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Search only expired books",
    )
    search_books_parser.add_argument(
        "--group-by-title",
        action="store_true",
        help="Group matching rows by title and show how many local records exist for each title",
    )
    search_books_parser.add_argument(
        "--count",
        type=int,
        help="When grouping by title, show only groups with exactly this many local records",
    )
    search_books_parser.add_argument(
        "--min-count",
        type=int,
        help="When grouping by title, show only groups with at least this many local records",
    )

    import_books_parser = subparsers.add_parser("import-books", help="Import books from the Kindle source")
    import_books_parser.add_argument(
        "--source",
        choices=["all", "amazon", "docs"],
        default="all",
        help="Choose which source to import",
    )
    generate_candidates_parser = subparsers.add_parser(
        "generate-collection-candidates",
        aliases=["generate-collection-candidate"],
        help="Analyze imported books and generate collection candidates",
    )
    generate_candidates_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write candidate output",
    )
    generate_candidates_parser.add_argument(
        "--format",
        choices=["text", "jsonl"],
        default="text",
        help="Output file format when --output is provided",
    )
    generate_candidates_parser.add_argument(
        "--min-books",
        type=int,
        default=2,
        help="Minimum matching books required before a collection is proposed",
    )
    generate_candidates_parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Analyze only expired books",
    )
    generate_candidates_parser.add_argument(
        "--source",
        choices=["all", "amazon", "docs"],
        default="all",
        help="Analyze all books or only one Kindle source split",
    )
    generate_candidates_parser.add_argument(
        "--review-only",
        action="store_true",
        help="Show only medium/low-confidence or skipped cases that need review",
    )
    generate_candidates_parser.add_argument(
        "--confidence",
        choices=["high", "medium", "low"],
        help="Show only books with this confidence level",
    )
    generate_candidates_parser.add_argument(
        "--title-contains",
        help="Show only books whose original or normalized title contains this text",
    )
    generate_candidates_parser.add_argument(
        "--show-collection-candidates",
        action="store_true",
        help="Include the detailed collection candidate list in the final summary",
    )
    generate_candidates_parser.add_argument(
        "--no-files",
        action="store_true",
        help="Do not write the default JSONL and CSV review artifacts",
    )
    create_collections_parser = subparsers.add_parser(
        "create-collections",
        help="Dry-run planned collection creation from the generated summary artifact",
    )
    create_collections_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/collection_candidates_summary.csv"),
        help="Path to the collection candidate summary CSV",
    )
    create_collections_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview collection creation without writing anything to Amazon",
    )
    create_collections_parser.add_argument(
        "--confirm-create",
        action="store_true",
        help="Actually create missing collections in Amazon",
    )
    create_collections_parser.add_argument(
        "--include-medium",
        action="store_true",
        help="Include medium-confidence collection candidates in addition to high-confidence ones",
    )
    create_collections_parser.add_argument(
        "--include-low",
        action="store_true",
        help="Include low-confidence collection candidates in addition to high-confidence ones",
    )
    create_collections_parser.add_argument(
        "--include-medium-and-low",
        action="store_true",
        help="Include all confidence levels",
    )
    create_collections_parser.add_argument(
        "--collection",
        help="Limit the run to collection candidates whose name contains this text",
    )
    create_collections_parser.add_argument(
        "--collection-exact",
        help="Limit the run to one collection candidate whose name exactly matches this text",
    )
    create_collections_parser.add_argument(
        "--audit-output",
        type=Path,
        default=Path("data/create_collections_audit.csv"),
        help="Path to write the dry-run audit CSV",
    )
    create_collections_parser.add_argument(
        "--state-output",
        type=Path,
        default=Path("data/create_collections_state.csv"),
        help="Path to write the persistent collection state CSV",
    )
    subparsers.add_parser("sync-dry-run", help="Preview planned sync actions")
    subparsers.add_parser("sync-run", help="Run Kindle sync actions")

    return parser


def get_settings() -> Settings:
    return Settings()

def build_kindle_adapter(settings: Settings):
    from kindle_service.kindle.playwright_sync import PlaywrightKindleAdapter

    return PlaywrightKindleAdapter(
        browser_profile_path=settings.browser_profile_path,
        amazon_base_url=settings.amazon_base_url,
        books_url=settings.content_library_books_url,
        docs_url=settings.content_library_docs_url,
        collections_url=settings.content_library_collections_url,
        headless=settings.kindle_headless,
        page_delay_ms=settings.kindle_page_delay_ms,
    )


def print_database_update_plan(plan: DatabaseUpdatePlan, storage_path: Path) -> None:
    print(f"Database path: {storage_path}")
    print(f"Current schema version: {plan.current_version}")
    print(f"Target schema version: {plan.target_version}")
    if not plan.actions:
        print("Planned changes: none")
        return

    print("Planned changes:")
    for action in plan.actions:
        print(f"- {action}")


def initialize_db_command(storage_path: Path, *, show_plan: bool, confirm: bool) -> int:
    plan = inspect_database(storage_path)

    if show_plan:
        print_database_update_plan(plan, storage_path)
        return 0

    if plan.requires_migration and not confirm:
        print_database_update_plan(plan, storage_path)
        print("Migration not applied. Re-run with --confirm to proceed.")
        return 1

    initialize_database(storage_path)
    if plan.current_version == 0:
        print(f"Initialized database at {storage_path}")
    elif plan.requires_changes:
        print(
            f"Updated database at {storage_path} "
            f"from schema version {plan.current_version} to {CURRENT_SCHEMA_VERSION}"
        )
    else:
        print(f"Database at {storage_path} is already up to date")
    return 0


def create_collection_plan_command(storage_path: Path, name: str) -> int:
    try:
        collection_plan = create_collection_plan(storage_path, name)
        print(
            f"Created collection plan #{collection_plan.id}: {collection_plan.name}"
        )
        return 0
    except DuplicateCollectionPlanError as exc:
        logger.warning("%s", exc)
        print(str(exc))
        return 1
    except ValueError as exc:
        logger.warning("%s", exc)
        print(str(exc))
        return 1


def list_collection_plans_command(storage_path: Path) -> int:
    collection_plans = list_collection_plans(storage_path)
    if not collection_plans:
        print("No collection plans found.")
        return 0

    for collection_plan in collection_plans:
        print(
            f"[{collection_plan.id}] {collection_plan.name} "
            f"(created {collection_plan.created_at})"
        )
    return 0


def add_book_command(
    storage_path: Path,
    *,
    title: str,
    author: str | None,
    asin: str | None,
    source_type: str | None,
    source: str | None,
    source_page: str | None,
) -> int:
    try:
        outcome = upsert_book(
            storage_path,
            title=title,
            author=author,
            asin=asin,
            source_type=source_type,
            source=source,
            source_page=source_page,
        )
        print(f"Added temporary local book '{title}' ({outcome}).")
        return 0
    except DuplicateBookError as exc:
        logger.warning("%s", exc)
        print(str(exc))
        return 1
    except ValueError as exc:
        logger.warning("%s", exc)
        print(str(exc))
        return 1


def print_books(books: list[Book], *, show_db_id: bool) -> int:
    if not books:
        print("No books found.")
        return 0

    for book in books:
        prefix = f"[{book.id}] " if show_db_id else ""
        print(f"{prefix}{book.title}")
        if book.author:
            print(f"  author: {book.author}")
        if book.source_type:
            print(f"  source type: {book.source_type}")
        if book.source_page:
            print(f"  source page: {book.source_page}")
        if book.is_expired:
            print("  expired: yes")
        if book.asin:
            print(f"  import id: {book.asin}")
        if book.source:
            print(f"  source: {book.source}")
        print()
    return 0


def print_book_titles(books: list[Book]) -> int:
    if not books:
        print("No books found.")
        return 0

    for book in books:
        print(book.title)
    return 0


def print_grouped_books(
    books: list[Book],
    *,
    show_db_id: bool,
    exact_count: int | None = None,
    min_count: int | None = None,
) -> int:
    if not books:
        print("No books found.")
        return 0

    grouped: dict[tuple[str, str | None, str | None, str | None, bool], list[Book]] = {}
    for book in books:
        group_key = (
            book.title,
            book.author,
            book.source_type,
            book.source_page,
            book.is_expired,
        )
        grouped.setdefault(group_key, []).append(book)

    filtered_groups = [
        item
        for item in grouped.items()
        if (exact_count is None or len(item[1]) == exact_count)
        and (min_count is None or len(item[1]) >= min_count)
    ]

    if not filtered_groups:
        print("No books found.")
        return 0

    sorted_groups = sorted(
        filtered_groups,
        key=lambda item: (
            item[0][0].lower(),
            (item[0][1] or "").lower(),
            item[1][0].id or 0,
        ),
    )

    for (title, author, source_type, source_page, is_expired), group_books in sorted_groups:
        print(f"{title} ({len(group_books)} records)")
        if author:
            print(f"  author: {author}")
        if source_type:
            print(f"  source type: {source_type}")
        if source_page:
            print(f"  source page: {source_page}")
        if is_expired:
            print("  expired: yes")
        if show_db_id:
            db_ids = ", ".join(str(book.id) for book in group_books if book.id is not None)
            if db_ids:
                print(f"  db ids: {db_ids}")
        import_ids = ", ".join(
            book.asin for book in group_books if book.asin
        )
        if import_ids:
            print(f"  import ids: {import_ids}")
        print()
    return 0


def list_books_command(
    storage_path: Path,
    *,
    show_db_id: bool,
    expired_only: bool,
    group_by_title: bool,
    title_only: bool,
    exact_count: int | None,
    min_count: int | None,
) -> int:
    books = list_books(storage_path, expired_only=expired_only)
    if title_only:
        return print_book_titles(books)
    if group_by_title:
        return print_grouped_books(
            books,
            show_db_id=show_db_id,
            exact_count=exact_count,
            min_count=min_count,
        )
    return print_books(books, show_db_id=show_db_id)


def search_books_command(
    storage_path: Path,
    query: str,
    *,
    show_db_id: bool,
    expired_only: bool,
    group_by_title: bool,
    exact_count: int | None,
    min_count: int | None,
) -> int:
    books = search_books(storage_path, query, expired_only=expired_only)
    if group_by_title:
        return print_grouped_books(
            books,
            show_db_id=show_db_id,
            exact_count=exact_count,
            min_count=min_count,
        )
    return print_books(books, show_db_id=show_db_id)


def filter_books_for_source(books: list[Book], source: str) -> list[Book]:
    if source == "all":
        return books
    if source == "amazon":
        return [book for book in books if book.source_type == "amazon_book"]
    return [book for book in books if book.source_type == "personal_document"]


def rebuild_filtered_collection_summaries(result, *, min_books: int) -> None:
    grouped: dict[str, list] = {}
    for record in result.books:
        if record.normalized_series_key:
            grouped.setdefault(record.normalized_series_key, []).append(record)
    result.collections = build_collection_summaries(grouped, min_books=min_books)


def summarize_candidate_records(records) -> dict[str, int]:
    summary = {
        "normalized": 0,
        "skipped": 0,
        "eligible": 0,
        "needs_review": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    for record in records:
        if record.normalized_series_key:
            summary["normalized"] += 1
        else:
            summary["skipped"] += 1
        if record.eligible_for_collection:
            summary["eligible"] += 1
        if record.needs_review:
            summary["needs_review"] += 1
        summary[record.confidence] += 1
    return summary


def generate_collection_candidates_command(
    storage_path: Path,
    *,
    output: Path | None,
    output_format: str,
    min_books: int,
    expired_only: bool,
    source: str,
    review_only: bool,
    confidence: str | None,
    title_contains: str | None,
    show_collection_candidates: bool,
    no_files: bool,
) -> int:
    if min_books < 2:
        print("--min-books must be 2 or greater.")
        return 1

    books = list_books(storage_path, expired_only=expired_only)
    books = filter_books_for_source(books, source)
    result = generate_collection_candidates(
        books,
        min_books=min_books,
        review_only=review_only,
    )

    if confidence is not None:
        result.books = [record for record in result.books if record.confidence == confidence]
        rebuild_filtered_collection_summaries(result, min_books=min_books)

    if title_contains:
        query = title_contains.casefold()
        result.books = [
            record
            for record in result.books
            if query in record.original_title.casefold() or query in record.normalized_title.casefold()
        ]
        rebuild_filtered_collection_summaries(result, min_books=min_books)

    if not result.books:
        print("No books found.")
        return 0

    for record in result.books:
        print(render_book_record(record))
        print()

    rollup = summarize_candidate_records(result.books)
    print("Candidate summary:")
    print(f"- Books analyzed: {len(result.books)}")
    print(f"- Books normalized into a series key: {rollup['normalized']}")
    print(f"- Books skipped without a series key: {rollup['skipped']}")
    print(f"- Eligible for collection creation: {rollup['eligible']}")
    print(f"- Needs review: {rollup['needs_review']}")
    print(f"- Confidence high: {rollup['high']}")
    print(f"- Confidence medium: {rollup['medium']}")
    print(f"- Confidence low: {rollup['low']}")
    print(f"- Collections proposed: {len(result.collections)}")
    if confidence is not None:
        print(f"- Confidence filter: {confidence}")
    if title_contains:
        print(f"- Title filter: {title_contains}")
    if result.collections and show_collection_candidates:
        print("- Collection candidates:")
        for summary in result.collections:
            rendered_summary = render_collection_summary(summary).splitlines()
            for line in rendered_summary:
                print(f"  {line}")

    if output is not None:
        write_candidate_output(output, result=result, output_format=output_format)
        print(f"- Candidate output written to: {output}")

    if not no_files:
        default_base_dir = storage_path.parent
        jsonl_path = default_base_dir / "collection_candidates.jsonl"
        review_csv_path = default_base_dir / "collection_candidates_review.csv"
        summary_csv_path = default_base_dir / "collection_candidates_summary.csv"
        write_candidate_jsonl(jsonl_path, result=result)
        write_candidate_review_csv(review_csv_path, result=result)
        write_candidate_summary_csv(summary_csv_path, result=result)
        print(f"- JSONL written to: {jsonl_path}")
        print(f"- Review CSV written to: {review_csv_path}")
        print(f"- Summary CSV written to: {summary_csv_path}")

    return 0


def create_collections_command(
    settings: Settings,
    *,
    input_path: Path,
    dry_run: bool,
    confirm_create: bool,
    include_medium: bool,
    include_low: bool,
    include_medium_and_low: bool,
    collection_name: str | None,
    collection_exact: str | None,
    audit_output: Path,
    state_output: Path,
) -> int:
    if dry_run and confirm_create:
        print("Use either --dry-run or --confirm-create, not both.")
        return 1
    if not dry_run and not confirm_create:
        print("Specify either --dry-run or --confirm-create.")
        return 1
    if collection_name and collection_exact:
        print("Use either --collection or --collection-exact, not both.")
        return 1

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    candidates = read_collection_candidate_summary(input_path)
    inventory_summary = summarize_candidate_inventory_by_confidence(candidates)
    adapter = build_kindle_adapter(settings)
    existing_collections = adapter.list_collections()
    results = build_create_collections_dry_run(
        candidates,
        existing_collections=existing_collections,
        include_medium=include_medium,
        include_low=include_low,
        include_medium_and_low=include_medium_and_low,
        collection_name=collection_name,
        collection_exact=collection_exact,
    )

    if confirm_create:
        executed_results = []
        for result in results:
            if result.status != "would_create":
                executed_results.append(result)
                continue
            try:
                adapter.create_collection(result.collection_candidate_name)
                executed_results.append(
                    type(result)(
                        collection_candidate_name=result.collection_candidate_name,
                        normalized_series_key=result.normalized_series_key,
                        confidence=result.confidence,
                        needs_review=result.needs_review,
                        status="created",
                        action_taken="create",
                        existing_collection_name=result.existing_collection_name,
                        book_titles=result.book_titles,
                        book_count=result.book_count,
                        failure_reason=None,
                    )
                )
            except Exception as exc:
                executed_results.append(
                    type(result)(
                        collection_candidate_name=result.collection_candidate_name,
                        normalized_series_key=result.normalized_series_key,
                        confidence=result.confidence,
                        needs_review=result.needs_review,
                        status="failed",
                        action_taken="failed",
                        existing_collection_name=result.existing_collection_name,
                        book_titles=result.book_titles,
                        book_count=result.book_count,
                        failure_reason=str(exc),
                    )
                )
        results = executed_results

    existing_state = read_create_collections_state(state_output)
    updated_state = update_state_from_dry_run(existing_state, candidates=candidates, results=results)
    persisted_summary = summarize_persisted_state_books(updated_state, candidates=candidates)

    print(render_create_collections_tree(results), end="")

    summary = summarize_create_collections_results(results)
    total_books_considered = sum(result.book_count for result in results)
    books_target_success = sum(
        result.book_count for result in results if result.status in {"would_create", "created"}
    )
    books_manual_review = sum(
        result.book_count for result in results if result.status == "manual_review_required"
    )
    books_skipped_by_confidence = sum(
        result.book_count for result in results if result.status == "skipped_by_confidence"
    )
    books_already_exists = sum(
        result.book_count for result in results if result.status == "already_exists"
    )
    books_failed = sum(
        result.book_count for result in results if result.status == "failed"
    )
    print("Create collections dry-run summary:" if dry_run else "Create collections summary:")
    print(f"- Input file: {input_path}")
    print(f"- Existing collections fetched from UI: {len(existing_collections)}")
    print(f"- Total candidates loaded from summary artifact: {inventory_summary['total_candidates']}")
    print(f"- Total books across all confidence levels: {inventory_summary['total_books']}")
    print(f"- High-confidence books total: {inventory_summary['high_books']}")
    print(f"- Medium-confidence books total: {inventory_summary['medium_books']}")
    print(f"- Low-confidence books total: {inventory_summary['low_books']}")
    print(f"- Total candidates evaluated in this dry run: {summary['total']}")
    if dry_run:
        print(f"- Would create: {summary['would_create']}")
    else:
        print(f"- Created: {summary.get('created', 0)}")
    print(f"- Already exists: {summary['already_exists']}")
    print(f"- Manual review required: {summary['manual_review_required']}")
    print(f"- Skipped by confidence: {summary['skipped_by_confidence']}")
    if not dry_run:
        print(f"- Failed: {summary['failed']}")
    print(f"- Total books represented by considered candidates: {total_books_considered}")
    if dry_run:
        print(f"- Books covered by would-create collections: {books_target_success}")
    else:
        print(f"- Books covered by created collections: {books_target_success}")
    print(f"- Books already covered by existing collections: {books_already_exists}")
    print(f"- Books blocked for manual review: {books_manual_review}")
    print(f"- Books skipped by confidence gate: {books_skipped_by_confidence}")
    if not dry_run:
        print(f"- Books failed during creation: {books_failed}")

    if include_medium_and_low:
        print("- Confidence gate: high, medium, low")
    elif include_medium and include_low:
        print("- Confidence gate: high, medium, low")
    elif include_medium:
        print("- Confidence gate: high, medium")
    elif include_low:
        print("- Confidence gate: high, low")
    else:
        print("- Confidence gate: high only")

    if collection_exact:
        print(f"- Exact collection filter: {collection_exact}")
    elif collection_name:
        print(f"- Collection filter: {collection_name}")

    uncovered_books = total_books_considered - books_target_success - books_already_exists
    if dry_run:
        print(f"- Books not currently covered by would-create or existing collections: {uncovered_books}")
    else:
        print(f"- Books not currently covered by created or existing collections: {uncovered_books}")
    print("- Persisted collection state:")
    print(f"  - High completed: {persisted_summary['completed_high_books']}")
    print(f"  - High missing: {persisted_summary['missing_high_books']}")
    print(f"  - High manual review: {persisted_summary['manual_review_high_books']}")
    print(f"  - High skipped: {persisted_summary['skipped_high_books']}")
    print(f"  - Medium completed: {persisted_summary['completed_medium_books']}")
    print(f"  - Medium missing: {persisted_summary['missing_medium_books']}")
    print(f"  - Medium manual review: {persisted_summary['manual_review_medium_books']}")
    print(f"  - Medium skipped: {persisted_summary['skipped_medium_books']}")
    print(f"  - Low completed: {persisted_summary['completed_low_books']}")
    print(f"  - Low missing: {persisted_summary['missing_low_books']}")
    print(f"  - Low manual review: {persisted_summary['manual_review_low_books']}")
    print(f"  - Low skipped: {persisted_summary['skipped_low_books']}")

    manual_review_results = [
        result for result in results if result.status == "manual_review_required"
    ]
    skipped_by_confidence_results = [
        result for result in results if result.status == "skipped_by_confidence"
    ]

    if manual_review_results:
        print("- Manual review collections:")
        for result in manual_review_results:
            print(
                f"  - {result.collection_candidate_name} "
                f"(confidence: {result.confidence}, needs review: yes)"
            )

    if skipped_by_confidence_results:
        print("- Skipped by confidence collections:")
        for result in skipped_by_confidence_results:
            print(
                f"  - {result.collection_candidate_name} "
                f"(confidence: {result.confidence})"
            )

    failed_results = [
        result for result in results if result.status == "failed"
    ]
    if failed_results:
        print("- Failed collections:")
        for result in failed_results:
            print(
                f"  - {result.collection_candidate_name}: {result.failure_reason or 'unknown failure'}"
            )

    already_exists_results = [
        result for result in results if result.status == "already_exists"
    ]
    if already_exists_results:
        print("- Existing collections:")
        for result in already_exists_results:
            print(
                f"  - {result.collection_candidate_name} "
                f"(matched existing: {result.existing_collection_name})"
            )

    write_create_collections_audit_csv(audit_output, results=results)
    print(f"- Audit CSV written to: {audit_output}")
    write_create_collections_state_csv(state_output, state_records=updated_state)
    print(f"- State CSV written to: {state_output}")
    return 0


def import_books_command(settings: Settings, *, source: str) -> int:
    adapter = build_kindle_adapter(settings)
    try:
        result = adapter.import_books(source=source)
    except NotImplementedError as exc:
        print(str(exc))
        return 1

    records = result.all_books
    purchased_selected_count = result.purchased_books_selected_count
    docs_selected_count = result.personal_documents_selected_count
    total_records = len(records)
    duplicate_count = result.total_duplicate_count
    duplicate_details = result.duplicate_details
    repeated_title_details = result.repeated_title_details
    expired_records = [record for record in records if record.is_expired]

    inserted = 0
    updated = 0
    for record in records:
        outcome = upsert_book(
            settings.storage_path,
            title=record.title,
            author=record.author,
            asin=record.asin,
            source_type=record.source_type,
            source=record.source,
            source_page=record.source_page,
            is_expired=record.is_expired,
        )
        if outcome == "inserted":
            inserted += 1
        else:
            updated += 1

    summary = (
        "Import complete:\n"
        f"- Amazon purchased books (selected rows): {purchased_selected_count}\n"
        f"- Downloaded docs (selected rows): {docs_selected_count}\n"
        f"- Unique records after dedupe: {total_records}\n"
        f"- Duplicates collapsed during import: {duplicate_count}\n"
        f"- Expired books found: {len(expired_records)}\n"
        f"- Inserted: {inserted}\n"
        f"- Updated: {updated}"
    )

    if expired_records:
        expired_titles = "\n".join(f"  - {record.title}" for record in expired_records)
        summary = f"{summary}\n- Expired titles:\n{expired_titles}"

    if duplicate_details:
        grouped_duplicates: dict[tuple[str, str], list] = {}
        for detail in duplicate_details:
            group_key = (detail.source_page, detail.synthetic_id)
            grouped_duplicates.setdefault(group_key, []).append(detail)

        duplicate_lines = []
        for (source_page, _synthetic_id), details in grouped_duplicates.items():
            first_detail = details[0]
            titles: list[str] = []

            first_title = first_detail.previous_title
            if first_detail.previous_is_expired:
                first_title = f"{first_title} [expired]"
            titles.append(first_title)

            for detail in details:
                current_title = detail.current_title
                if detail.current_is_expired:
                    current_title = f"{current_title} [expired]"
                if current_title not in titles:
                    titles.append(current_title)

            appearance_count = len(details) + 1
            duplicate_lines.append(
                f"  - {source_page}: appeared {appearance_count} times; kept 1 record; titles: "
                + " | ".join(titles)
            )
        summary = f"{summary}\n- Duplicate collisions:\n" + "\n".join(duplicate_lines)

    if repeated_title_details:
        repeated_title_lines = []
        for detail in repeated_title_details:
            expired_suffix = " [expired]" if detail.is_expired else ""
            repeated_title_lines.append(
                f"  - {detail.source_page}: {detail.title}{expired_suffix} appeared {detail.count} times; "
                f"produced {detail.unique_record_count} unique records"
            )
        summary = f"{summary}\n- Repeated selected titles:\n" + "\n".join(repeated_title_lines)

    print(summary)
    return 0


def main() -> int:
    configure_standard_streams()
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    storage_path = settings.storage_path

    if args.command == "init-db":
        return initialize_db_command(
            storage_path,
            show_plan=args.plan,
            confirm=args.confirm,
        )
    if args.command == "create-collection-plan":
        return create_collection_plan_command(storage_path, args.name)
    if args.command == "list-collection-plans":
        return list_collection_plans_command(storage_path)
    if args.command == "add-book":
        return add_book_command(
            storage_path,
            title=args.title,
            author=args.author,
            asin=args.asin,
            source_type=args.source_type,
            source=args.source,
            source_page=args.source_page,
        )
    if args.command == "list-books":
        return list_books_command(
            storage_path,
            show_db_id=args.show_db_id,
            expired_only=args.expired_only,
            group_by_title=args.group_by_title,
            title_only=args.title_only,
            exact_count=args.count,
            min_count=args.min_count,
        )
    if args.command == "search-books":
        return search_books_command(
            storage_path,
            args.query,
            show_db_id=args.show_db_id,
            expired_only=args.expired_only,
            group_by_title=args.group_by_title,
            exact_count=args.count,
            min_count=args.min_count,
        )
    if args.command == "import-books":
        return import_books_command(settings, source=args.source)
    if args.command in {"generate-collection-candidates", "generate-collection-candidate"}:
        return generate_collection_candidates_command(
            storage_path,
            output=args.output,
            output_format=args.format,
            min_books=args.min_books,
            expired_only=args.expired_only,
            source=args.source,
            review_only=args.review_only,
            confidence=args.confidence,
            title_contains=args.title_contains,
            show_collection_candidates=args.show_collection_candidates,
            no_files=args.no_files,
        )
    if args.command == "create-collections":
        return create_collections_command(
            settings,
            input_path=args.input,
            dry_run=args.dry_run,
            confirm_create=args.confirm_create,
            include_medium=args.include_medium,
            include_low=args.include_low,
            include_medium_and_low=args.include_medium_and_low,
            collection_name=args.collection,
            collection_exact=args.collection_exact,
            audit_output=args.audit_output,
            state_output=args.state_output,
        )

    print(f"Command '{args.command}' is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
