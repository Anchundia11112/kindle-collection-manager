from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from kindle_service.models import Book, CollectionPlan

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 5


class DuplicateCollectionPlanError(ValueError):
    """Raised when a collection plan already exists."""


class DuplicateBookError(ValueError):
    """Raised when a unique book record already exists."""


@dataclass(frozen=True, slots=True)
class DatabaseUpdatePlan:
    current_version: int
    target_version: int
    actions: list[str]

    @property
    def requires_changes(self) -> bool:
        return self.current_version != self.target_version

    @property
    def requires_migration(self) -> bool:
        return 0 < self.current_version < self.target_version


SCHEMA_V5 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    author TEXT,
    asin TEXT,
    source_type TEXT CHECK (
        source_type IS NULL OR source_type IN ('amazon_book', 'personal_document', 'manual_temp')
    ),
    source_page TEXT,
    source TEXT,
    is_expired INTEGER NOT NULL DEFAULT 0 CHECK (is_expired IN (0, 1))
);

CREATE TABLE IF NOT EXISTS collection_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_plan_books (
    collection_plan_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    PRIMARY KEY (collection_plan_id, book_id),
    FOREIGN KEY (collection_plan_id) REFERENCES collection_plans(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_source_type ON books(source_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
ON books(asin) WHERE asin IS NOT NULL AND length(trim(asin)) > 0;
CREATE INDEX IF NOT EXISTS idx_collection_plan_books_book_id
ON collection_plan_books(book_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status_started_at
ON sync_runs(status, started_at);
"""

LEGACY_TABLE_MARKERS = ("books", "collection_plans", "collection_plan_books", "sync_runs")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as connection:
        plan = build_database_update_plan(connection)
        logger.info(
            "Initializing database at %s with schema version %s",
            db_path,
            plan.current_version,
        )

        if plan.current_version == 0:
            apply_schema_v5(connection)
            set_schema_version(connection, CURRENT_SCHEMA_VERSION)
            logger.info(
                "Initialized fresh database with schema version %s",
                CURRENT_SCHEMA_VERSION,
            )
            return

        if plan.current_version < CURRENT_SCHEMA_VERSION:
            migrate_database(connection, plan.current_version)
            logger.info("Migrated database to schema version %s", CURRENT_SCHEMA_VERSION)
            return

        logger.info("Database already up to date")


def create_collection_plan(db_path: Path, name: str) -> CollectionPlan:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Collection plan name cannot be empty.")

    with connect(db_path) as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO collection_plans (name)
                VALUES (?)
                RETURNING id, name, created_at
                """,
                (normalized_name,),
            )
            row = cursor.fetchone()
            assert row is not None
            logger.info("Created collection plan '%s' with id %s", row["name"], row["id"])
            return CollectionPlan(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
            )
        except sqlite3.IntegrityError as exc:
            if "collection_plans.name" in str(exc) or "UNIQUE constraint failed" in str(exc):
                logger.warning("Collection plan '%s' already exists", normalized_name)
                raise DuplicateCollectionPlanError(
                    f"Collection plan '{normalized_name}' already exists."
                ) from exc
            logger.exception("Failed to create collection plan '%s'", normalized_name)
            raise


def list_collection_plans(db_path: Path) -> list[CollectionPlan]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, created_at
            FROM collection_plans
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
    return [
        CollectionPlan(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def insert_book(
    db_path: Path,
    *,
    title: str,
    author: str | None = None,
    asin: str | None = None,
    source_type: str | None = None,
    source: str | None = None,
    source_page: str | None = None,
    is_expired: bool = False,
) -> Book:
    normalized_title = title.strip()
    normalized_author = normalize_optional_text(author)
    normalized_asin = normalize_optional_text(asin)
    normalized_source_type = normalize_optional_text(source_type)
    normalized_source = normalize_optional_text(source)
    normalized_source_page = normalize_optional_text(source_page)
    normalized_is_expired = int(is_expired)

    if not normalized_title:
        raise ValueError("Book title cannot be empty.")

    with connect(db_path) as connection:
        try:
            cursor = connection.execute(
                """
                INSERT INTO books (title, author, asin, source_type, source_page, source, is_expired)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id, title, author, asin, source_type, source_page, source, is_expired
                """,
                (
                    normalized_title,
                    normalized_author,
                    normalized_asin,
                    normalized_source_type,
                    normalized_source_page,
                    normalized_source,
                    normalized_is_expired,
                ),
            )
            row = cursor.fetchone()
            assert row is not None
            logger.info("Inserted book '%s' with id %s", row["title"], row["id"])
            return row_to_book(row)
        except sqlite3.IntegrityError as exc:
            if normalized_asin and ("books.asin" in str(exc) or "UNIQUE constraint failed" in str(exc)):
                logger.warning("Book with ASIN '%s' already exists", normalized_asin)
                raise DuplicateBookError(
                    f"Book with ASIN '{normalized_asin}' already exists."
                ) from exc
            logger.exception("Failed to insert book '%s'", normalized_title)
            raise


def upsert_book(
    db_path: Path,
    *,
    title: str,
    author: str | None = None,
    asin: str | None = None,
    source_type: str | None = None,
    source: str | None = None,
    source_page: str | None = None,
    is_expired: bool = False,
) -> str:
    normalized_title = title.strip()
    normalized_author = normalize_optional_text(author)
    normalized_asin = normalize_optional_text(asin)
    normalized_source_type = normalize_optional_text(source_type)
    normalized_source = normalize_optional_text(source)
    normalized_source_page = normalize_optional_text(source_page)
    normalized_is_expired = int(is_expired)

    if not normalized_title:
        raise ValueError("Book title cannot be empty.")

    if not normalized_asin:
        insert_book(
            db_path,
            title=normalized_title,
            author=normalized_author,
            asin=None,
            source_type=normalized_source_type,
            source=normalized_source,
            source_page=normalized_source_page,
            is_expired=bool(normalized_is_expired),
        )
        return "inserted"

    with connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM books WHERE asin = ?",
            (normalized_asin,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO books (title, author, asin, source_type, source_page, source, is_expired)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_title,
                    normalized_author,
                    normalized_asin,
                    normalized_source_type,
                    normalized_source_page,
                    normalized_source,
                    normalized_is_expired,
                ),
            )
            return "inserted"

        connection.execute(
            """
            UPDATE books
            SET title = ?, author = ?, source_type = ?, source_page = ?, source = ?, is_expired = ?
            WHERE asin = ?
            """,
            (
                normalized_title,
                normalized_author,
                normalized_source_type,
                normalized_source_page,
                normalized_source,
                normalized_is_expired,
                normalized_asin,
            ),
        )
        return "updated"


def list_books(db_path: Path, *, expired_only: bool = False) -> list[Book]:
    with connect(db_path) as connection:
        if expired_only:
            rows = connection.execute(
                """
                SELECT id, title, author, asin, source_type, source_page, source, is_expired
                FROM books
                WHERE is_expired = 1
                ORDER BY title COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, title, author, asin, source_type, source_page, source, is_expired
                FROM books
                ORDER BY title COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
    return [row_to_book(row) for row in rows]


def search_books(db_path: Path, query: str, *, expired_only: bool = False) -> list[Book]:
    normalized_query = query.strip()
    if not normalized_query:
        return list_books(db_path, expired_only=expired_only)

    with connect(db_path) as connection:
        if expired_only:
            rows = connection.execute(
                """
                SELECT id, title, author, asin, source_type, source_page, source, is_expired
                FROM books
                WHERE
                    is_expired = 1
                    AND (
                        title LIKE ?
                        OR COALESCE(author, '') LIKE ?
                        OR COALESCE(asin, '') LIKE ?
                    )
                ORDER BY title COLLATE NOCASE ASC, id ASC
                """,
                (
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                ),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, title, author, asin, source_type, source_page, source, is_expired
                FROM books
                WHERE
                    title LIKE ?
                    OR COALESCE(author, '') LIKE ?
                    OR COALESCE(asin, '') LIKE ?
                ORDER BY title COLLATE NOCASE ASC, id ASC
                """,
                (
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                    f"%{normalized_query}%",
                ),
            ).fetchall()
    return [row_to_book(row) for row in rows]


def get_schema_version(connection: sqlite3.Connection) -> int:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'schema_version'
        """
    ).fetchone()
    if table_exists:
        row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return int(row["version"]) if row is not None else 0

    legacy_table_exists = any(
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        for table_name in LEGACY_TABLE_MARKERS
    )
    return 1 if legacy_table_exists else 0


def inspect_database(db_path: Path) -> DatabaseUpdatePlan:
    with connect(db_path) as connection:
        return build_database_update_plan(connection)


def build_database_update_plan(connection: sqlite3.Connection) -> DatabaseUpdatePlan:
    current_version = get_schema_version(connection)
    actions = get_update_actions(current_version)
    return DatabaseUpdatePlan(
        current_version=current_version,
        target_version=CURRENT_SCHEMA_VERSION,
        actions=actions,
    )


def get_update_actions(current_version: int) -> list[str]:
    if current_version == 0:
        return [
            "Create schema_version table",
            "Create books table with only title required",
            "Create collection_plans table with unique non-empty names",
            "Create collection_plan_books join table with cascading foreign keys",
            "Create sync_runs table with constrained statuses",
            "Create indexes for title, source type, optional ASIN, join lookups, and sync status",
        ]

    if current_version == 1:
        return [
            "Add schema_version table",
            "Rebuild books table so only title is required",
            "Rebuild collection_plans table with non-empty name constraint",
            "Rebuild collection_plan_books with cascading foreign keys",
            "Rebuild sync_runs with allowed status values: pending, success, failed",
            "Create indexes for title, source type, optional ASIN, join lookups, and sync status",
        ]

    if current_version in {2, 3}:
        return [
            "Rebuild books table so only title is required",
            "Keep source_page column",
            "Change ASIN uniqueness to apply only when ASIN is present",
        ]

    if current_version == 4:
        return [
            "Add books.is_expired flag with a default of false",
        ]

    if current_version >= CURRENT_SCHEMA_VERSION:
        return []

    return [f"Upgrade schema from version {current_version} to {CURRENT_SCHEMA_VERSION}"]


def set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    connection.execute("DELETE FROM schema_version")
    connection.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def apply_schema_v5(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_V5)


def migrate_database(connection: sqlite3.Connection, current_version: int) -> None:
    if current_version == 1:
        migrate_v1_to_v2(connection)
        current_version = 2
    if current_version == 2:
        migrate_v2_to_v3(connection)
        current_version = 3
    if current_version == 3:
        migrate_v3_to_v4(connection)
        current_version = 4
    if current_version == 4:
        migrate_v4_to_v5(connection)
        current_version = 5

    if current_version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported schema version after migration: {current_version}")


def migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    logger.info("Migrating database from schema version 1 to 2")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );

        CREATE TABLE books_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            author TEXT,
            asin TEXT,
            source TEXT
        );

        INSERT INTO books_new (id, title, author, asin, source)
        SELECT id, trim(title), author, asin, source
        FROM books
        WHERE title IS NOT NULL AND length(trim(title)) > 0;

        DROP TABLE books;
        ALTER TABLE books_new RENAME TO books;

        CREATE TABLE collection_plans_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO collection_plans_new (id, name, created_at)
        SELECT id, trim(name), COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM collection_plans
        WHERE name IS NOT NULL AND length(trim(name)) > 0;

        DROP TABLE collection_plans;
        ALTER TABLE collection_plans_new RENAME TO collection_plans;

        CREATE TABLE collection_plan_books_new (
            collection_plan_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            PRIMARY KEY (collection_plan_id, book_id),
            FOREIGN KEY (collection_plan_id) REFERENCES collection_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        );

        INSERT OR IGNORE INTO collection_plan_books_new (collection_plan_id, book_id)
        SELECT collection_plan_id, book_id
        FROM collection_plan_books;

        DROP TABLE collection_plan_books;
        ALTER TABLE collection_plan_books_new RENAME TO collection_plan_books;

        CREATE TABLE sync_runs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failed'))
        );

        INSERT INTO sync_runs_new (id, started_at, status)
        SELECT
            id,
            COALESCE(started_at, CURRENT_TIMESTAMP),
            CASE
                WHEN status IN ('pending', 'success', 'failed') THEN status
                ELSE 'pending'
            END
        FROM sync_runs;

        DROP TABLE sync_runs;
        ALTER TABLE sync_runs_new RENAME TO sync_runs;

        CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
        ON books(asin) WHERE asin IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_collection_plan_books_book_id
        ON collection_plan_books(book_id);
        CREATE INDEX IF NOT EXISTS idx_sync_runs_status_started_at
        ON sync_runs(status, started_at);
        """
    )
    set_schema_version(connection, 2)


def migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    logger.info("Migrating database from schema version 2 to 3")
    connection.executescript(
        """
        CREATE TABLE books_new (
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

        INSERT INTO books_new (id, title, author, asin, source_type, source_page, source)
        SELECT
            id,
            title,
            COALESCE(NULLIF(trim(author), ''), 'Unknown Author'),
            COALESCE(NULLIF(trim(asin), ''), 'legacy-' || id),
            'manual_temp',
            NULL,
            COALESCE(NULLIF(trim(source), ''), 'legacy_migration')
        FROM books;

        DROP TABLE books;
        ALTER TABLE books_new RENAME TO books;

        CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
        CREATE INDEX IF NOT EXISTS idx_books_source_type ON books(source_type);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
        ON books(asin);
        """
    )
    set_schema_version(connection, 3)


def migrate_v3_to_v4(connection: sqlite3.Connection) -> None:
    logger.info("Migrating database from schema version 3 to 4")
    connection.executescript(
        """
        CREATE TABLE books_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            author TEXT,
            asin TEXT,
            source_type TEXT CHECK (
                source_type IS NULL OR source_type IN ('amazon_book', 'personal_document', 'manual_temp')
            ),
            source_page TEXT,
            source TEXT
        );

        INSERT INTO books_new (id, title, author, asin, source_type, source_page, source)
        SELECT id, title, author, asin, source_type, source_page, source
        FROM books;

        DROP TABLE books;
        ALTER TABLE books_new RENAME TO books;

        CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
        CREATE INDEX IF NOT EXISTS idx_books_source_type ON books(source_type);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
        ON books(asin) WHERE asin IS NOT NULL AND length(trim(asin)) > 0;
        """
    )
    set_schema_version(connection, 4)


def migrate_v4_to_v5(connection: sqlite3.Connection) -> None:
    logger.info("Migrating database from schema version 4 to 5")
    connection.executescript(
        """
        CREATE TABLE books_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            author TEXT,
            asin TEXT,
            source_type TEXT CHECK (
                source_type IS NULL OR source_type IN ('amazon_book', 'personal_document', 'manual_temp')
            ),
            source_page TEXT,
            source TEXT,
            is_expired INTEGER NOT NULL DEFAULT 0 CHECK (is_expired IN (0, 1))
        );

        INSERT INTO books_new (id, title, author, asin, source_type, source_page, source, is_expired)
        SELECT id, title, author, asin, source_type, source_page, source, 0
        FROM books;

        DROP TABLE books;
        ALTER TABLE books_new RENAME TO books;

        CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
        CREATE INDEX IF NOT EXISTS idx_books_source_type ON books(source_type);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_asin_unique
        ON books(asin) WHERE asin IS NOT NULL AND length(trim(asin)) > 0;
        """
    )
    set_schema_version(connection, 5)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def row_to_book(row: sqlite3.Row) -> Book:
    return Book(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        asin=row["asin"],
        source_type=row["source_type"],
        source=row["source"],
        source_page=row["source_page"],
        is_expired=bool(row["is_expired"]),
    )
