# Create Collections Spec

This document defines the intended behavior for the future `create-collections` command.

The focus of this command is to take reviewed/generated collection candidates and decide, safely, whether a Kindle collection should be created in the UI.

## Purpose

`create-collections` should:

- read reviewed/generated collection summary data
- iterate through normalized series candidates
- check whether a matching collection already exists in Amazon
- create only missing collections
- avoid risky guesses when a possible name collision exists

This command is the write path and should be more conservative than candidate generation.

## Input

The command should consume the summary artifact, not rescan books from the local database.

Recommended input:

- `data/collection_candidates_summary.csv`

Why:

- the summary artifact is already human-reviewable
- it contains the collection-facing information needed for creation
- it keeps creation separate from normalization

## Default confidence behavior

Default behavior should be:

- allow `high` confidence only

Optional flags:

- `--include-medium`
- `--include-low`
- `--include-medium-and-low`

Recommended behavior:

- `--include-medium` includes `medium` in addition to `high`
- `--include-low` includes `low` in addition to `high`
- `--include-medium-and-low` includes all three confidence levels

This keeps the safe path obvious while still allowing controlled expansion later.

## Collection existence checks

Before creating any collection, the command should first fetch the list of collections that already exist in the Kindle UI.

Default behavior:

- refresh collection state from the UI for each run

Optional performance behavior:

- allow reuse of a collection cache with an explicit opt-in flag

Suggested flags:

- `--use-collection-cache`
- `--refresh-collection-cache`

Cache rule:

- the cache is a convenience only
- it must not be blindly trusted as the permanent source of truth

## Name matching rules

The command should distinguish between:

1. exact existing match
2. no match
3. possible/ambiguous collision

### Exact existing match

If the candidate collection name exactly matches an existing collection according to the chosen comparison rule, mark it as:

- `already_exists`

and do not create it again.

### No match

If there is no existing match, mark it as:

- `would_create`

in dry-run mode, or create it in write mode.

### Possible collision

If the candidate appears close to an existing collection but is not a safe exact match, mark it as:

- `manual_review_required`

Examples:

- `Zero no Tsukaima` vs `Zero No Tsukaima`
- `The Seven Virtues` vs `Seven Virtues`
- punctuation-only or whitespace-only variants

For these cases, the command should:

- report the collision clearly
- take no action automatically

The user can then decide whether to rename the existing collection manually or create the desired collection manually.

## Dry-run behavior

Dry-run should be the default-safe workflow for early development and review.

Suggested CLI shape:

```powershell
python -m kindle_service.cli create-collections --input data/collection_candidates_summary.csv --dry-run
```

The dry-run output should show, per collection:

- collection candidate name
- normalized series key
- confidence
- whether it already exists
- whether it would be created
- whether it is skipped by confidence gating
- whether it requires manual review because of a possible collision
- the book titles belonging to that collection

## Tree view output

Console output should favor a tree-like structure for readability.

Recommended shape:

```text
Collection: Zero no Tsukaima
  status: would_create
  confidence: high
  normalized key: zero no tsukaima
  books:
    - Zero no Tsukaima vol.14
    - Zero no Tsukaima vol.15
    - Zero no Tsukaima vol.16
```

For an existing collection:

```text
Collection: Cradle
  status: already_exists
  confidence: high
  normalized key: cradle
  books:
    - House of Blades (Cradle Book 1)
    - Soulsmith (Cradle Book 2)
```

For a possible collision:

```text
Collection: The Seven Virtues
  status: manual_review_required
  confidence: high
  similar existing collection: Seven Virtues
  books:
    - A Sellsword's Compassion: Book One of the Seven Virtues
    - The First Rule of Cultivation: Book Two of the Seven Virtues
```

## Output artifacts

After each dry run or write run, the command should write an audit file.

Suggested output:

- `data/create_collections_audit.csv`

Suggested columns:

- `collection_candidate_name`
- `normalized_series_key`
- `confidence`
- `status`
- `existing_collection_name`
- `action_taken`
- `book_titles`

Suggested status values:

- `already_exists`
- `would_create`
- `created`
- `skipped_by_confidence`
- `manual_review_required`
- `failed`

## Recovery and resumability

This can be improved later.

For now, the code should include a comment or obvious extension point noting that resumability and more advanced recovery should be added later.

It is not necessary to fully solve partial-run recovery in the first version of `create-collections`.

## Non-goals for first implementation

The first implementation should not yet:

- add books to collections
- auto-resolve ambiguous collection name collisions
- rely on stale cache data by default
- handle every failure mode perfectly

## Recommended first implementation order

1. read `collection_candidates_summary.csv`
2. filter by confidence flags
3. fetch existing collections from the UI
4. compare candidates to existing collections
5. produce tree-view dry-run output
6. write audit CSV
7. only after that, add actual collection creation
