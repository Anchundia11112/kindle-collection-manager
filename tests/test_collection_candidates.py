from kindle_service.collection_candidates import build_collection_summaries, generate_collection_candidates
from kindle_service.models import Book


def test_generate_collection_candidates_groups_prefix_volume_titles() -> None:
    books = [
        Book(id=1, title="Zero no Tsukaima vol.16", source_type="personal_document", source_page="pdocs"),
        Book(id=2, title="Zero no Tsukaima vol.15", source_type="personal_document", source_page="pdocs"),
        Book(id=3, title="Zero no Tsukaima vol.14", source_type="personal_document", source_page="pdocs"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 1
    assert result.collections[0].collection_candidate_name == "Zero no Tsukaima"
    assert result.collections[0].book_count == 3
    assert all(record.eligible_for_collection for record in result.books)
    assert {record.rule_used for record in result.books} == {"prefix_volume_marker"}


def test_generate_collection_candidates_skips_singleton_series_candidate() -> None:
    books = [
        Book(
            id=1,
            title="Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita: Vol. 02",
            source_type="personal_document",
            source_page="pdocs",
        )
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 0
    assert result.books[0].collection_candidate_name == "Yuusha Party ni Kawaii Ko ga Ita node, Kokuhaku Shitemita"
    assert result.books[0].skip_reason == "only_one_matching_book"
    assert result.books[0].needs_review is True


def test_generate_collection_candidates_extracts_parenthetical_series() -> None:
    books = [
        Book(id=1, title="Blackflame (Cradle Book 3)", source_type="amazon_book", source_page="booksAll"),
        Book(id=2, title="Soulsmith (Cradle Book 2)", source_type="amazon_book", source_page="booksAll"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 1
    assert result.collections[0].collection_candidate_name == "Cradle"
    assert {record.rule_used for record in result.books} == {"parenthetical_series_book"}


def test_generate_collection_candidates_handles_reverse_parenthetical_book_pattern() -> None:
    books = [
        Book(id=1, title="A Fate of Dragons (Book #3 in the Sorcerer's Ring)", source_type="amazon_book"),
        Book(id=2, title="A Quest of Heroes (Book 1 in the Sorcerer's Ring)", source_type="amazon_book"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 1
    assert result.collections[0].collection_candidate_name == "the Sorcerer's Ring"
    assert all(record.rule_used == "parenthetical_series_book" for record in result.books)
    assert {record.volume_detected for record in result.books} == {"1", "3"}


def test_generate_collection_candidates_handles_prefix_book_of_series_pattern() -> None:
    books = [
        Book(id=1, title="A Sellsword's Compassion: Book One of the Seven Virtues", source_type="amazon_book"),
        Book(id=2, title="The First Rule of Cultivation: Book Two of the Seven Virtues", source_type="amazon_book"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 1
    assert result.collections[0].collection_candidate_name == "the Seven Virtues"
    assert {record.rule_used for record in result.books} == {"prefix_book_marker"}


def test_generate_collection_candidates_handles_trailing_number_series_rule_conservatively() -> None:
    books = [
        Book(id=1, title="Sword Art Online Progressive 6", source_type="personal_document"),
        Book(id=2, title="Sword Art Online Progressive 5", source_type="personal_document"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 1
    assert result.collections[0].collection_candidate_name == "Sword Art Online Progressive"
    assert {record.rule_used for record in result.books} == {"repeated_structured_prefix"}
    assert all(record.confidence == "medium" for record in result.books)


def test_generate_collection_candidates_uses_last_matching_parenthetical_group() -> None:
    books = [
        Book(
            id=1,
            title="City of Masks: (An Epic Fantasy Adventure) (The Bone Mask Cycle Book 1)",
            source_type="amazon_book",
        ),
        Book(
            id=2,
            title="Call of Kythshire: An Epic Fantasy Adventure (Keepers of the Wellsprings Book 1)",
            source_type="amazon_book",
        ),
    ]

    result = generate_collection_candidates(books)

    assert result.books[0].collection_candidate_name == "The Bone Mask Cycle"
    assert result.books[1].collection_candidate_name == "Keepers of the Wellsprings"


def test_generate_collection_candidates_extracts_full_volume_word() -> None:
    books = [
        Book(id=1, title="An Archdemon's Dilemma: How to Love Your Elf Bride: Volume 2", source_type="personal_document"),
        Book(id=2, title="An Archdemon's Dilemma: How to Love Your Elf Bride: Volume 3", source_type="personal_document"),
    ]

    result = generate_collection_candidates(books)

    assert {record.volume_detected for record in result.books} == {"2", "3"}
    assert result.collections[0].collection_candidate_name == "An Archdemon's Dilemma: How to Love Your Elf Bride"


def test_generate_collection_candidates_keeps_short_trailing_number_titles_unmatched() -> None:
    books = [
        Book(id=1, title="Decapitation 1", source_type="personal_document"),
        Book(id=2, title="Decapitation 2", source_type="personal_document"),
    ]

    result = generate_collection_candidates(books)

    assert len(result.collections) == 0
    assert all(record.rule_used == "no_series_match" for record in result.books)


def test_build_collection_summaries_uses_filtered_records() -> None:
    books = [
        Book(id=1, title="A Fate of Dragons (Book #3 in the Sorcerer's Ring)", source_type="amazon_book"),
        Book(id=2, title="Tears of Blood, Books 1-3", source_type="amazon_book"),
    ]

    result = generate_collection_candidates(books)
    low_confidence_books = [record for record in result.books if record.confidence == "low"]
    grouped = {
        record.normalized_series_key: [record]
        for record in low_confidence_books
        if record.normalized_series_key is not None
    }

    filtered_summaries = build_collection_summaries(grouped, min_books=2)

    assert filtered_summaries == []
