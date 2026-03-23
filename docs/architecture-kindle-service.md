# Kindle Service Architecture

## Context

This project is a personal automation tool for organizing a large Kindle library into collections.

Because there is no known official public API for personal Kindle collection management, the architecture needs to separate stable internal logic from unstable Kindle integration logic.

## Overview

The recommended architecture is a local Python CLI application with a small internal data model and one or more adapter layers for Kindle integration.

The most important design choice is to avoid tying the whole system directly to Amazon's web requests. Instead, the application should have its own internal model for books, desired collections, and sync actions. Kindle integration should be treated as an adapter that reads data from Kindle and, later, attempts writes back to Kindle.

## Goals

- Keep the core app stable even if the Kindle integration changes
- Support incremental progress from read-only to write-capable automation
- Make failures debuggable
- Allow manual review before risky sync actions

## Non-Goals

- Building a distributed system
- Supporting multiple deployment environments in v1
- Designing for many users

## System Components

### CLI entry points

Provide local commands that coordinate reads, planning, and sync operations.

Examples:

- `import-books`
- `search-books`
- `plan-collection`
- `sync-collection`

### Domain layer

Contains internal business logic:

- book normalization
- matching and search
- collection planning
- dry-run generation
- sync result tracking

### Storage layer

Stores local application state such as:

- imported books
- desired collections
- collection membership plans
- sync history

SQLite is a good first choice because this is a personal local tool, it requires no separate database server, and it gives cleaner querying for thousands of books.

Suggested storage path:

- `data/kindle_service.db`

### Kindle adapter

Responsible for reading from Kindle and eventually writing collection changes back.

This layer should be isolated because it is the part most likely to break.

Possible implementations:

- web request adapter based on observed browser traffic
- browser automation adapter using Playwright
- local metadata adapter if useful Kindle data exists on disk

For read import, the current best candidates are Amazon account-management content pages rather than `read.amazon.com`.

Likely sources:

- purchased books page
- personal documents page

The adapter should be able to import from both and merge them into one local model.

The currently planned navigation path is:

1. open `amazon.com`
2. open `Account & Lists`
3. click `Content Library`
4. read `Books`
5. read `Docs`

### Optional simple frontend

A minimal UI could help with searching books and selecting many titles at once, but it is not required for the first version.

## Data Flow

1. User runs a local import command
2. Kindle adapter reads available book metadata from one or more Amazon content pages
3. The application normalizes and stores books locally
4. User searches books and creates a target collection plan
5. User previews the intended sync actions
6. Sync process attempts to apply the changes to Kindle
7. Results are logged for inspection and retry

## Interfaces and Boundaries

### Stable internal command surface

The core application should expose commands such as:

- `import-books`
- `show-book`
- `create-collection-plan`
- `add-books-to-plan`
- `sync-dry-run`
- `sync-run`

The adapter boundary should return normalized imported records, not raw Amazon page fragments.

### Unstable external boundary

All Kindle-specific request formats, selectors, cookies, and anti-bot workarounds should stay inside the adapter layer.

This prevents Amazon-specific details from leaking across the codebase.

## Data Model Notes

Suggested core entities:

- `Book`
- `Collection`
- `CollectionMembership`
- `SyncRun`
- `SyncAction`

Suggested book fields:

- local id
- title
- author
- asin or external identifier if available
- source type such as `amazon_book` or `personal_document`
- source page or source system identifier if available
- source metadata blob

## Security Considerations

- Authentication secrets or cookies should never be hardcoded
- The tool should prefer a saved browser session or persistent browser profile over storing the Amazon password directly
- Session material should be stored carefully and rotated when invalid
- Logs should avoid leaking sensitive cookies or tokens

## Reliability Considerations

- Kindle integration should support retries
- Sync should be previewable before execution
- Partial failure should be recorded per action
- Idempotency matters because retries are expected

## Performance Considerations

- Local search over 2,000 to 5,000 books should be fast in SQLite
- Bulk selection and planning should happen locally whenever possible
- External Kindle calls should be minimized

## Tradeoffs

- Browser automation is likely slower than a direct API, but may be easier to keep working initially
- Reverse-engineered web requests may be faster, but more brittle and harder to debug
- A local canonical model adds complexity, but protects the app from external instability

## Alternatives Considered

### Direct unofficial API only

Pros:

- potentially faster
- fewer moving parts during sync

Cons:

- tightly coupled to Amazon request details
- fragile when web flows change

### Local Kindle data only

Pros:

- avoids web automation complexity

Cons:

- may not expose enough information or write capability
- may differ by device or app platform

## Open Questions

- Which Kindle surface provides the most reliable read access?
- Is write access easier through web requests or browser-driven UI automation?
- What identifiers are available consistently enough for reliable matching?
