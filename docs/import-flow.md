# Import Flow

This document describes the planned read-only import flow for getting books into the local SQLite database.

The goal of this flow is not to sync collections yet.
The goal is only to discover and normalize the user's available Kindle content.

## Current source assumption

The import will use Amazon account-management pages instead of `read.amazon.com`.

Known content surfaces:

- purchased Kindle books
- personal documents uploaded to Kindle

## User-described navigation flow

1. Go to `https://www.amazon.com/`
2. Hover over `Hello, <Name> Account & Lists`
3. Click `Content Library`
4. Click `Books`
   - this shows Amazon-purchased Kindle books
5. Click `Docs`
   - this shows uploaded personal documents

## Planned automation flow

1. Open a persistent logged-in browser profile
2. Navigate to `https://www.amazon.com/`
3. Open the `Account & Lists` menu
4. Navigate to `Content Library`
5. Collect purchased books from the `Books` view
6. Collect personal documents from the `Docs` view
7. Follow pagination or lazy-loading as needed for each view
8. Normalize both sources into one shared imported-book shape
9. Save the normalized records into the local database
10. Print an import summary

## Current implementation status

The browser automation layer is now partially implemented.

What exists now:

- config for a persistent browser profile
- config for the base Amazon URL
- config for the purchased-books and docs URLs
- a Playwright adapter that opens the direct Books and Docs URLs
- row extraction for the current page
- numeric paginator navigation for page-by-page traversal
- an `import-books` command that saves extracted rows into SQLite
- source-specific import support through `import-books --source amazon|docs|all`
- support for visible library rows whose action buttons differ from standard purchased items, such as expired rentals

What is still missing:

- stronger selectors if Amazon changes the DOM
- extraction of hidden identifiers if available
- write-path automation for collections

## Normalized imported-book shape

Each imported record should provide:

- `title`
- `author` when available
- `asin` or a synthetic local identifier derived from visible row metadata when a visible Amazon identifier is unavailable
- `source_type` when available
- `source` when available
- `source_page`
- `is_expired`

Expected source types:

- `amazon_book`
- `personal_document`

## Import summary expectations

The `import-books` command should report at least:

- purchased-book rows selected from the page
- personal-document rows selected from the page
- unique records kept after synthetic-id deduplication
- total inserted
- total updated

During debugging, the scraper may also log each selected row title, label expired entries inline, and warn when multiple visible rows collapse to the same synthetic identifier.
The final import summary also lists expired titles that were found during the run.
After import, expired records can be reviewed from the CLI with `list-books --expired-only` or narrowed further with `search-books --expired-only`.
When duplicates are collapsed, traversal logs show which visible title replaced which earlier row, and the final summary reports how many times each repeated item appeared.
The summary also reports repeated selected titles by raw title count, even when those rows do not all collapse into a single synthetic-id collision group.

## Open questions

- Does `Content Library` use pagination, lazy-loading, or both?
- Does every row expose a stable ASIN or some other unique identifier?
- Do personal documents expose the same metadata fields as purchased books?
- Is there a simpler direct URL path that avoids the hover menu once logged in?
