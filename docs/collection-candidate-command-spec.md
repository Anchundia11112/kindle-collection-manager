# Collection Candidate Command Spec

This document defines the recommended command split and output format for turning imported books into collection candidates and then creating collections later.

## Recommendation

Use two commands:

1. `generate-collection-candidates`
2. `create-collections`

Do not combine normalization and collection creation into one command by default.

## Why split the commands

Normalization and grouping are the most ambiguous part of the workflow.
Collection creation is the side-effecting part.

Keeping them separate gives these benefits:

- easier debugging
- easier review before making changes in Amazon
- safer retries
- easier future support for manual approval or AI-assisted review
- better logs and better testability

## Command 1: `generate-collection-candidates`

Purpose:

- read imported books from the local database
- normalize titles
- detect likely series groups
- decide which books belong to candidate collections
- write a structured artifact for review

This command should be read-only with respect to Amazon.

### Suggested CLI shape

```powershell
python -m kindle_service.cli generate-collection-candidates
python -m kindle_service.cli generate-collection-candidates --output data/collection_candidates.jsonl
python -m kindle_service.cli generate-collection-candidates --format jsonl
python -m kindle_service.cli generate-collection-candidates --format text
python -m kindle_service.cli generate-collection-candidates --min-books 2
python -m kindle_service.cli generate-collection-candidates --expired-only
python -m kindle_service.cli generate-collection-candidates --source amazon
python -m kindle_service.cli generate-collection-candidates --source docs
python -m kindle_service.cli generate-collection-candidates --review-only
```

### Recommended options

- `--output`
  - path to write structured candidate output
- `--format`
  - `jsonl` or `text`
- `--min-books`
  - minimum number of matching books required to propose a collection
  - default: `2`
- `--source`
  - `all`, `amazon`, or `docs`
- `--expired-only`
  - optional filter if needed later
- `--review-only`
  - emit only ambiguous or medium/low-confidence candidates

## Command 2: `create-collections`

Purpose:

- read approved/generated collection candidates
- check whether a collection already exists in Amazon
- create missing collections
- later, add books to the collection

This command performs side effects and should be treated as the write path.

### Suggested CLI shape

```powershell
python -m kindle_service.cli create-collections --input data/collection_candidates.jsonl
python -m kindle_service.cli create-collections --input data/collection_candidates.jsonl --dry-run
python -m kindle_service.cli create-collections --input data/collection_candidates.jsonl --only-high-confidence
python -m kindle_service.cli create-collections --input data/collection_candidates.jsonl --collection "Zero no Tsukaima"
```

### Recommended options

- `--input`
  - required path to candidate file
- `--dry-run`
  - show what would be created without changing Amazon
- `--only-high-confidence`
  - ignore lower-confidence candidates
- `--collection`
  - run only one collection candidate by name

## Output philosophy

The output of `generate-collection-candidates` should be:

- easy for a human to inspect
- easy for another command to consume
- explicit about which rule produced the result

That means the command should support:

- human-readable console logs
- machine-readable file output

## Per-book structured record

Each analyzed book should produce a structured record with at least:

- `book_id`
- `original_title`
- `normalized_title`
- `normalized_series_key`
- `collection_candidate_name`
- `rule_used`
- `confidence`
- `volume_detected`
- `needs_review`
- `skip_reason`
- `source_type`
- `source_page`
- `is_expired`

### Recommended meanings

- `original_title`
  - title exactly as stored in the DB
- `normalized_title`
  - cleaned title after punctuation/noise normalization
- `normalized_series_key`
  - stable machine-facing grouping key
- `collection_candidate_name`
  - human-facing name to use for collection creation
- `rule_used`
  - which extraction rule matched
- `confidence`
  - `high`, `medium`, or `low`
- `volume_detected`
  - extracted number or label if one was found
- `needs_review`
  - whether the result should be manually checked before collection creation
- `skip_reason`
  - why no collection candidate was produced

## Human-readable logging format

Console output should explicitly explain how each book was handled.

Recommended shape:

```text
Found Book title: Zero no Tsukaima vol.16
Normalized Book title: Zero no Tsukaima vol.16
Normalized Series key: zero no tsukaima
Collection Candidate name: Zero no Tsukaima
Rule used to normalize: prefix_volume_marker
Detected volume: 16
Confidence: high
Needs review: no
Skip reason: none
```

For a skipped singleton:

```text
Found Book title: Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita: Vol. 02
Normalized Book title: Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita: Vol. 02
Normalized Series key: yuusha party ni kawaii ko ga ita node kokuhaku shitemita
Collection Candidate name: Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita
Rule used to normalize: prefix_volume_marker
Detected volume: 2
Confidence: medium
Needs review: yes
Skip reason: only_one_matching_book
```

## JSONL output format

Each line should represent one analyzed book.

Example:

```json
{"book_id":123,"original_title":"Zero no Tsukaima vol.16","normalized_title":"Zero no Tsukaima vol.16","normalized_series_key":"zero no tsukaima","collection_candidate_name":"Zero no Tsukaima","rule_used":"prefix_volume_marker","confidence":"high","volume_detected":"16","needs_review":false,"skip_reason":null,"source_type":"personal_document","source_page":"pdocs","is_expired":false}
```

## Candidate collection summary output

In addition to per-book records, the command should emit collection-level summaries.

Recommended fields:

- `collection_candidate_name`
- `normalized_series_key`
- `book_count`
- `confidence`
- `needs_review`
- `rule_used_set`
- `book_ids`
- `book_titles`

Example:

```text
Collection Candidate: Zero no Tsukaima
Normalized Series key: zero no tsukaima
Books matched: 14
Confidence: high
Needs review: no
Rules used: prefix_volume_marker
```

## Recommended rule names

Use short stable rule ids in logs and output.

Suggested rule ids:

- `parenthetical_series_book`
- `prefix_volume_marker`
- `prefix_book_marker`
- `prefix_part_marker`
- `roman_numeral_suffix`
- `repeated_structured_prefix`
- `noise_cleanup_only`
- `no_series_match`

## Recommended skip reasons

Suggested stable skip reasons:

- `only_one_matching_book`
- `no_series_pattern_detected`
- `ambiguous_box_set`
- `ambiguous_anthology`
- `low_confidence_match`
- `duplicate_local_record_only`

## Confidence guidance

Suggested confidence rules:

- `high`
  - explicit volume/book marker
  - 2+ matching books
- `medium`
  - plausible pattern but inconsistent punctuation or noisy variants
- `low`
  - weak inference, anthology, omnibus, or title family without stable numbering

## Execution flow

Recommended user flow:

1. run `generate-collection-candidates`
2. inspect output
3. optionally edit/filter candidates
4. run `create-collections --dry-run`
5. run `create-collections`

## Design boundary

Keep one shared normalization module in code.

Recommended separation:

- normalization code in domain/service layer
- `generate-collection-candidates` calls that code and writes output
- `create-collections` reads the output and performs writes

This keeps the logic centralized while preserving command-level separation.

## Future extension

Later, the pipeline can support:

- manual approvals
- AI-assisted normalization review
- cached accepted overrides for known series
- per-series ignore rules

The two-command structure supports those additions cleanly.
