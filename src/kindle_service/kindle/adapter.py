from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportedBookRecord:
    title: str
    author: str
    asin: str
    source_type: str
    source: str
    source_page: str | None = None
    is_expired: bool = False


@dataclass(frozen=True, slots=True)
class ImportDuplicateDetail:
    source_page: str
    synthetic_id: str
    previous_title: str
    current_title: str
    previous_is_expired: bool = False
    current_is_expired: bool = False


@dataclass(frozen=True, slots=True)
class ImportRepeatedTitleDetail:
    source_page: str
    title: str
    count: int
    unique_record_count: int
    is_expired: bool = False


@dataclass(frozen=True, slots=True)
class ImportResult:
    purchased_books: list[ImportedBookRecord]
    personal_documents: list[ImportedBookRecord]
    purchased_books_selected_count: int = 0
    personal_documents_selected_count: int = 0
    purchased_books_duplicate_count: int = 0
    personal_documents_duplicate_count: int = 0
    purchased_books_duplicate_details: list[ImportDuplicateDetail] | None = None
    personal_documents_duplicate_details: list[ImportDuplicateDetail] | None = None
    purchased_books_repeated_title_details: list[ImportRepeatedTitleDetail] | None = None
    personal_documents_repeated_title_details: list[ImportRepeatedTitleDetail] | None = None

    @property
    def all_books(self) -> list[ImportedBookRecord]:
        return [*self.purchased_books, *self.personal_documents]

    @property
    def total_selected_count(self) -> int:
        return self.purchased_books_selected_count + self.personal_documents_selected_count

    @property
    def total_duplicate_count(self) -> int:
        return self.purchased_books_duplicate_count + self.personal_documents_duplicate_count

    @property
    def duplicate_details(self) -> list[ImportDuplicateDetail]:
        return [
            *(self.purchased_books_duplicate_details or []),
            *(self.personal_documents_duplicate_details or []),
        ]

    @property
    def repeated_title_details(self) -> list[ImportRepeatedTitleDetail]:
        return [
            *(self.purchased_books_repeated_title_details or []),
            *(self.personal_documents_repeated_title_details or []),
        ]


class KindleAdapter:
    """Base adapter for Kindle import and sync operations."""

    def import_books(self, source: str = "all") -> ImportResult:
        raise NotImplementedError

    def list_collections(self) -> list[str]:
        raise NotImplementedError

    def create_collection(self, collection_name: str) -> None:
        raise NotImplementedError

    def sync_collection(self, collection_name: str, book_ids: list[int]) -> None:
        raise NotImplementedError
