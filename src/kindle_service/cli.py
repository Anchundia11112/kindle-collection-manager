from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from kindle_service.config import Settings
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

    print(f"Command '{args.command}' is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
