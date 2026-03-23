# Collection Normalization Spec

This document describes a practical first-pass normalization strategy for turning imported book titles into collection candidates.

The goal is not to perfectly identify every series in the world.
The goal is to generate useful, reviewable collection candidates from the user's existing Kindle library with conservative behavior.

## Goal

Given imported book records, produce:

- a `collection_candidate_name`
- a `normalized_series_key`
- a decision about whether a collection should be created

The default rule should be:

- only create a collection when at least 2 books share the same normalized series key

That avoids creating collections for one-off books that merely look serial.

## High-level approach

Process titles in four stages:

1. text cleanup
2. noise removal
3. series-pattern extraction
4. grouping and safety checks

## Stage 1: Text cleanup

Normalize the raw title before trying to detect a series.

Recommended cleanup rules:

- trim surrounding whitespace
- collapse repeated internal whitespace to a single space
- replace underscores with spaces
- normalize dash variants to a standard hyphen where safe
- normalize curly quotes to straight quotes where safe
- normalize obvious mojibake when it can be repaired safely

Examples:

- `Dahlia in Bloom_ Crafting a Fresh Start with Magical Tools Volume 6`
  becomes
  `Dahlia in Bloom Crafting a Fresh Start with Magical Tools Volume 6`

- `86â€”EIGHTY-SIX, Vol. 6`
  should ideally normalize to
  `86-EIGHTY-SIX, Vol. 6`

If mojibake repair is not reliable, keep both:

- original title
- cleaned title

and run matching on the cleaned title.

## Stage 2: Noise removal

Remove suffixes or fragments that should not affect collection naming.

Likely removable noise:

- `Premium`
- `Premium Ver`
- `(Z-Library)`
- `(z-lib.org)`
- author/source suffixes appended to the title
- standalone `(Light Novel)` labels when they do not identify the series

Examples:

- `A Brief History of Chronomancy (Arcane Ascension Book 6) (Andrew Rowe) (Z-Library)`
  should reduce toward
  `A Brief History of Chronomancy (Arcane Ascension Book 6)`

- `Ascendance of a Bookworm Part 5 volume 1 Premium Ver`
  should reduce toward
  `Ascendance of a Bookworm Part 5 volume 1`

Noise removal should be conservative.
Do not strip text that might actually be part of the series identity.

## Stage 3: Series-pattern extraction

Try these strategies in order.

Stop once one produces a plausible series key.

### Strategy A: Parenthetical series pattern

Detect a parenthetical fragment like:

- `(Cradle Book 3)`
- `(The Traveler's Gate Trilogy Book 3)`
- `(The Stewart Chronicle Book 1)`

Extraction rule:

- if the parenthetical contains `Book`, `Vol`, `Volume`, or `Part` with a number
- use the prefix before the volume marker inside the parentheses as the series key

Examples:

- `Blackflame (Cradle Book 3)` -> `Cradle`
- `City of Light (The Traveler's Gate Trilogy Book 3)` -> `The Traveler's Gate Trilogy`
- `A King Ensnared: A Historical Novel of Scotland (The Stewart Chronicle Book 1)` -> `The Stewart Chronicle`

Also support reversed parenthetical wording like:

- `A Fate of Dragons (Book #3 in the Sorcerer's Ring)` -> `the Sorcerer's Ring`
- `A Quest of Heroes (Book 1 in the Sorcerer's Ring)` -> `the Sorcerer's Ring`

When multiple parenthetical groups exist, prefer the last matching parenthetical group instead of greedily crossing earlier parentheses.
That helps with titles like:

- `City of Masks: (An Epic Fantasy Adventure) (The Bone Mask Cycle Book 1)` -> `The Bone Mask Cycle`

### Strategy B: Prefix + volume marker

Detect titles that start with the series name and then a volume marker.

Markers to support:

- `Vol`
- `Vol.`
- `Volume`
- `Book`
- `Part`

Examples:

- `Zero no Tsukaima vol.16` -> `Zero no Tsukaima`
- `Absolute Duo vol.01` -> `Absolute Duo`
- `How a Realist Hero Rebuilt the Kingdom: Volume 13` -> `How a Realist Hero Rebuilt the Kingdom`
- `Kieli, Vol. 5: The Sunlit Garden Where It Began, Part 1` -> `Kieli`

Also support prefix wording like:

- `A Sellsword's Compassion: Book One of the Seven Virtues` -> `the Seven Virtues`
- `The First Rule of Cultivation: Book Two of the Seven Virtues` -> `the Seven Virtues`

Volume parsing should prefer the full marker word, such as `Volume`, before shorter partial matches like `Vol`, so values like `Volume 2` do not get misread as `ume`.

### Strategy C: Roman numerals and ordinal variants

Some titles use roman numerals or uncommon numbering.

Examples:

- `Allison I`
- `Alderamin on the Sky VI`

Use a secondary matcher that detects:

- trailing roman numerals
- volume words like `One`, `Two`, `Three`

This should be lower confidence than Strategies A and B.

### Strategy D: Repeated exact-title family prefix

If multiple cleaned titles share a strong stable prefix and differ only by obvious numbering or subtitle structure, treat that prefix as the candidate series key.

Examples:

- `Campione! - Volume 1 - Heretic God`
- `Campione! - Volume 2 - Arrival of a Devil King`

Candidate key:

- `Campione!`

This strategy is useful for structured title families even when punctuation varies.

### Strategy E: Trailing numeric series pattern

Support a conservative trailing-number rule for titles that end with a plain number and have a long enough structured prefix.

Examples:

- `Sword Art Online Progressive 6` -> `Sword Art Online Progressive`
- `Sword Art Online Progressive 5` -> `Sword Art Online Progressive`

This should stay medium confidence and should be conservative enough to avoid overmatching short titles like:

- `Decapitation 1`
- `Decapitation 2`

## Stage 4: Grouping and creation rule

After extracting a normalized series key:

- group books by that key
- require at least 2 matching books before proposing a collection

Default behavior:

- 1 matching book: do not create a collection
- 2 or more matching books: collection candidate

This protects against false positives like:

- `Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita: Vol. 02`

If only one title matches that key, do not create the collection automatically.

## Normalized series key rules

The normalized key should be stable and not overly user-facing.

Recommended normalization:

- lowercase
- collapse whitespace
- strip removable noise
- standardize punctuation enough for matching

Keep a separate display name for the collection.

Example:

- normalized key: `zero no tsukaima`
- display name: `Zero no Tsukaima`

## Collection display name rules

Once a series key is accepted, generate a clean collection name.

Recommended display-name rules:

- use title casing only if it does not damage the source naming
- preserve intentional capitalization where possible
- remove trailing volume markers
- remove source/noise suffixes

Examples:

- `zero no tsukaima` -> `Zero no Tsukaima`
- `cradle` -> `Cradle`
- `how a realist hero rebuilt the kingdom` -> `How a Realist Hero Rebuilt the Kingdom`

## Categories that should be conservative

These should be detected, but not necessarily auto-created without review.

### Box sets and omnibuses

Examples:

- `Cradle, Foundation: Box Set (Cradle Collection Book 1)`
- `The Dragon Blood Collection, Books 1-3`
- `Beyond the Wall, Books One and Two ...`

These may belong to a collection, but they are not clean single-volume entries.

Suggested rule:

- include them in grouping
- but mark them as low-confidence or review-needed

### Anthologies

Examples:

- `Hall of Heroes: A Fellowship of Fantasy Anthology`
- `Fantastic Creatures: A Fellowship of Fantasy Anthology`

These may be related, but they do not necessarily represent a clean series.

Suggested rule:

- do not auto-create unless multiple titles strongly match and the pattern is consistent

### Source-tagged imports

Examples:

- `(Z-Library)`
- author names embedded in title

Suggested rule:

- strip source tags before matching
- keep original title in storage for display/debugging

## Confidence model

Each candidate collection should receive a confidence level.

Suggested levels:

- `high`
  - explicit `Vol` / `Volume` / `Book` pattern
  - 2+ matching titles
- `medium`
  - strong repeated prefix pattern
  - some punctuation inconsistency
- `low`
  - omnibus/anthology/single unusual match

For early versions:

- auto-create only `high`
- review `medium`
- ignore `low`

## Suggested output shape

For each book:

- `book_id`
- `original_title`
- `cleaned_title`
- `normalized_series_key` or `null`
- `collection_candidate_name` or `null`
- `series_confidence`
- `volume_label` if detected
- `needs_review`

## Good early wins from the current library

These series families should work well with rule-based normalization:

- `Zero no Tsukaima`
- `Absolute Duo`
- `Campione!`
- `Chrome Shelled Regios`
- `How a Realist Hero Rebuilt the Kingdom`
- `In Another World With My Smartphone`
- `Cooking with Wild Game`
- `Isekai Tensei Soudouki`
- `Kamisama no Memochou`
- `Kieli`
- `Altina the Sword Princess`
- `Demon Lord, Retry!`
- `Der Werwolf: The Annals of Veight`
- `The Rising of the Shield Hero`
- `Ascendance of a Bookworm`

## Known problem areas in the current library

These need extra care:

- mojibake and encoding damage
- inconsistent punctuation like `_`, `:`, `-`
- `Premium` / source-tag suffixes
- duplicated local rows from earlier imports
- anthologies and omnibuses
- titles where the true series name only appears in parentheses

## Recommended implementation order

1. build deterministic text cleanup
2. add explicit volume-marker extraction
3. support parenthetical series extraction
4. group by normalized series key
5. require at least 2 matches
6. mark ambiguous cases for review instead of auto-creating

## Non-goal for v1

Do not try to perfectly infer every possible series from natural language.

The v1 goal is:

- high-confidence automated grouping
- conservative behavior
- reviewability for ambiguous titles
