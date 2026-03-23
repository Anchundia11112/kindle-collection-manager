from pathlib import Path
import sqlite3

from kindle_service.storage import (
    DuplicateCollectionPlanError,
    build_database_update_plan,
    create_collection_plan,
    get_schema_version,
    initialize_database,
    list_collection_plans,
    upsert_book,
)


def test_initialize_database_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"

    initialize_database(db_path)

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        assert get_schema_version(connection) == 5


def test_create_and_list_collection_plans(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"
    initialize_database(db_path)

    created = create_collection_plan(db_path, "My Favorites")
    collection_plans = list_collection_plans(db_path)

    assert created.id is not None
    assert created.name == "My Favorites"
    assert len(collection_plans) == 1
    assert collection_plans[0].name == "My Favorites"


def test_create_collection_plan_rejects_duplicates(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"
    initialize_database(db_path)

    create_collection_plan(db_path, "My Favorites")

    try:
        create_collection_plan(db_path, "My Favorites")
    except DuplicateCollectionPlanError:
        pass
    else:
        raise AssertionError("Expected DuplicateCollectionPlanError to be raised")


def test_initialize_database_migrates_v3_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_version (
                version INTEGER NOT NULL
            );

            INSERT INTO schema_version (version) VALUES (3);

            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                author TEXT NOT NULL CHECK (length(trim(author)) > 0),
                asin TEXT NOT NULL CHECK (length(trim(asin)) > 0),
                source_type TEXT NOT NULL CHECK (
                    source_type IN ('amazon_book', 'personal_document', 'manual_temp')
                ),
                source_page TEXT,
                source TEXT NOT NULL CHECK (length(trim(source)) > 0)
            );

            CREATE TABLE collection_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE collection_plan_books (
                collection_plan_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                PRIMARY KEY (collection_plan_id, book_id),
                FOREIGN KEY (collection_plan_id) REFERENCES collection_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );

            CREATE TABLE sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failed'))
            );

            CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_source_type ON books(source_type);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
            ON books(asin);
            """
        )

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        version = get_schema_version(connection)
        books_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'books'"
        ).fetchone()["sql"]
        books_index = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_books_asin_unique'"
        ).fetchone()["sql"]

    assert version == 5
    assert "author TEXT" in books_sql
    assert "author TEXT NOT NULL" not in books_sql
    assert "asin TEXT" in books_sql
    assert "asin TEXT NOT NULL" not in books_sql
    assert "WHERE asin IS NOT NULL" in books_index


def test_build_database_update_plan_for_fresh_database(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        plan = build_database_update_plan(connection)

    assert plan.current_version == 0
    assert plan.target_version == 5
    assert plan.requires_changes is True
    assert plan.requires_migration is False
    assert "Create schema_version table" in plan.actions


def test_upsert_book_inserts_with_only_title_required(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"
    initialize_database(db_path)

    inserted = upsert_book(
        db_path,
        title="Deep Work",
    )

    assert inserted == "inserted"


def test_upsert_book_updates_when_asin_is_present(tmp_path: Path) -> None:
    db_path = tmp_path / "kindle_service.db"
    initialize_database(db_path)

    inserted = upsert_book(
        db_path,
        title="Deep Work",
        author="Cal Newport",
        asin="amazon_book-test-1",
        source_type="amazon_book",
        source="playwright_import",
        source_page="booksAll",
    )
    updated = upsert_book(
        db_path,
        title="Deep Work Revised",
        author="Cal Newport",
        asin="amazon_book-test-1",
        source_type="amazon_book",
        source="playwright_import",
        source_page="booksAll",
    )

    assert inserted == "inserted"
    assert updated == "updated"
