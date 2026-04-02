# Kindle Service

Local Python CLI for planning and eventually syncing Kindle collections for a personal library.

This project is a personal-use Python CLI for importing Kindle library metadata into a local database so you can inspect your books, understand duplicates, and prepare for collection automation.

## Personal Use

This project is intended for personal use on your own Amazon/Kindle account.

It is designed for low-volume browser automation around metadata you can already access from your own library.
It is not intended for credential sharing, large-scale scraping, bot evasion, or attempts to bypass platform protections.

If you use it, you are responsible for making sure your usage is appropriate for your account and comfortable for you from a terms-of-service perspective.

## Current status

This repository is scaffolded for a CLI-first workflow with:

- SQLite for local storage
- a storage layer for books, collections, and sync runs
- Playwright Kindle integration scaffolding
- schema version tracking and migration support
- a plan to import from both Amazon purchased books and personal documents

## Planned commands

- `import-books`
- `search-books`
- `create-collection-plan`
- `sync-dry-run`
- `sync-run`

## Current commands

- `python -m kindle_service.cli init-db`
- `python -m kindle_service.cli init-db --plan`
- `python -m kindle_service.cli init-db --confirm`
- `python -m kindle_service.cli create-collection-plan "Collection Name"`
- `python -m kindle_service.cli list-collection-plans`
- `python -m kindle_service.cli add-book "Book Title"`
- `python -m kindle_service.cli list-books`
- `python -m kindle_service.cli list-books --title-only`
- `python -m kindle_service.cli list-books --show-db-id`
- `python -m kindle_service.cli list-books --expired-only`
- `python -m kindle_service.cli list-books --group-by-title`
- `python -m kindle_service.cli list-books --group-by-title --min-count 2`
- `python -m kindle_service.cli list-books --group-by-title --count 5`
- `python -m kindle_service.cli search-books "search text"`
- `python -m kindle_service.cli search-books --expired-only`
- `python -m kindle_service.cli search-books "search text" --group-by-title`
- `python -m kindle_service.cli search-books "search text" --group-by-title --min-count 2`
- `python -m kindle_service.cli import-books`
- `python -m kindle_service.cli import-books --source amazon`
- `python -m kindle_service.cli import-books --source docs`

`--source amazon` imports only Amazon-purchased books.
`--source docs` imports only personal documents.
`--source all` remains the default and imports both.

You can export titles to a file on Windows with:

```powershell
python -m kindle_service.cli list-books --title-only > bookName.txt
```

## Database workflow

Use `init-db --plan` before applying a migration when you want to preview what will change.

Common flow:

```powershell
python -m kindle_service.cli init-db --plan
python -m kindle_service.cli init-db --confirm
```

If the database does not exist yet, `init-db` will create it.

If the database already exists and needs a schema migration, `init-db` without `--confirm` will show the plan and stop.

## CLI help

You do not need to memorize every command.

Use:

```powershell
python -m kindle_service.cli --help
python -m kindle_service.cli init-db --help
```

That is normal CLI workflow and is often better than relying only on memory.

## Browser automation setup

The project is now scaffolded to use Playwright for Kindle/Amazon browser automation.

The intended setup is:

1. install Python dependencies
2. install Playwright browsers
3. use a persistent browser profile so you can log in once and reuse the session

Typical commands:

```powershell
python -m pip install -e .
python -m playwright install
```

### Browser profile requirement

The importer uses a persistent local browser profile at `data/browser-profile`.

That profile is not included in this repository and should never be committed.
Each user needs to create their own local profile by signing in with their own Amazon account in the Playwright-managed browser session.

Typical first-use flow:

1. run `python -m kindle_service.cli import-books --source amazon`
2. let the browser open using the local profile directory
3. sign in to Amazon in that browser window if needed
4. complete any normal account checks Amazon requires
5. re-run the import command after the session is established

After that, the saved local profile can usually be reused for later imports.

The `import-books` command now performs a first-pass Playwright import and saves discovered rows into SQLite.
You can also target a single source with `--source amazon` or `--source docs` when debugging or doing a narrower refresh.
Those two source modes exist because Amazon splits Kindle library content into separate views:

- `--source amazon` for Amazon-purchased Kindle books
- `--source docs` for personal documents uploaded to Kindle

`--source all` remains the default and combines both sides of the library into one local import.
The importer logs each row title as it traverses a page so pagination and row-selection issues are easier to spot, and it marks expired entries inline in those traversal logs.
Its final summary now distinguishes raw selected rows from unique records after synthetic-id deduplication, and it no longer prints one `Saved ...` line per upsert.
It also treats visible rows with alternate action sets, such as expired rentals that show `Mark as Read` instead of a deliver action, as importable library rows.
Expired entries are stored with an explicit `is_expired` flag in the local database, and the import summary reports how many expired books were found plus their titles.
When duplicate synthetic ids are detected, traversal logs show which title replaced which, and the final summary includes a duplicate-collision section with how many times each repeated item appeared.
The final summary also includes repeated-title counts from the raw selected rows, which helps when the same visible title appears multiple times but not every row collapses to the same synthetic id.

Current limitations:

- it uses stable local synthetic identifiers derived from visible row metadata when a visible ASIN is not available on the page
- only `title` is required in local storage; other fields are optional
- selectors may still need tuning if Amazon renders the pagination controls differently in your session

## Notes

The Kindle integration is intentionally isolated because it is the most likely part to change.

The local database schema is documented in [docs/database-schema.md](docs/database-schema.md).
The planned book import flow is documented in [docs/import-flow.md](docs/import-flow.md).
The planned collection-title normalization rules are documented in [docs/collection-normalization-spec.md](docs/collection-normalization-spec.md).
The planned candidate-generation and collection-creation command split is documented in [docs/collection-candidate-command-spec.md](docs/collection-candidate-command-spec.md).
The planned collection-creation dry-run and UI behavior is documented in [docs/create-collections-spec.md](docs/create-collections-spec.md).

For library import, the current plan is to investigate Amazon account-management pages for:

- purchased Kindle books
- personal documents uploaded to Kindle

These may need to be imported separately and merged locally.

## Temporary developer helper

`add-book` is temporary.

It exists only to seed local data while the real Amazon import flow is not implemented yet.

It does not mean "add this book to a collection."
It only inserts a book record into the local database.
