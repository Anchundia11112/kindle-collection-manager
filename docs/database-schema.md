# Database Schema

This document describes the planned local SQLite schema for Kindle Service.

It is not the source of truth for migrations. The source of truth is the schema and migration logic in `src/kindle_service/storage.py`.

Use this file as a human-readable reference when thinking about table design and relationships.

## Why keep this document?

Yes, it is useful to keep a schema design note.

Code tells the database what to do.
This document tells humans why the tables exist and how they relate.

That helps when:

- you come back to the project later
- you add new tables
- you need to reason about migrations
- you want to avoid accidental duplication or weak relationships

## Current schema version

`5`

## Tables

### `schema_version`

Tracks which schema version the local database is using.

Columns:

- `version`: integer, one row only

### `books`

Stores books imported from Kindle or another source.

Columns:

- `id`: integer primary key
- `title`: required text
- `author`: optional text
- `asin`: optional text, unique when present
- `source_type`: optional text such as `amazon_book`, `personal_document`, or temporary `manual_temp`
- `source_page`: optional text describing where the record was imported from
- `source`: optional text describing where the row came from
- `is_expired`: required boolean-like integer flag that marks expired visible library entries such as rentals

Notes:

- `title` must not be blank
- index on `title`
- index on `source_type`
- unique index on `asin` when present

### `collection_plans`

Stores the local desired collections created by this tool.

Columns:

- `id`: integer primary key
- `name`: required unique text
- `created_at`: timestamp text

Notes:

- `name` must not be blank

### `collection_plan_books`

Join table connecting books to collection plans.

Columns:

- `collection_plan_id`: foreign key to `collection_plans.id`
- `book_id`: foreign key to `books.id`

Notes:

- composite primary key prevents duplicate links
- delete cascades remove orphaned relationships

### `sync_runs`

Stores top-level sync attempts.

Columns:

- `id`: integer primary key
- `started_at`: timestamp text
- `status`: required text

Allowed statuses:

- `pending`
- `success`
- `failed`

## Relationship summary

- one collection plan can include many books
- one book can belong to many collection plans
- `collection_plan_books` models that many-to-many relationship

## Future likely additions

- `sync_actions` for per-book sync outcomes
- `book_source_payloads` if raw imported metadata needs to be retained
- more fields on `books` such as subtitle, series, or author_sort
