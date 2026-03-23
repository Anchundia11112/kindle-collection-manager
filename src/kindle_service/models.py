from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Book:
    id: int | None
    title: str
    author: str | None = None
    asin: str | None = None
    source_type: str | None = None
    source: str | None = None
    source_page: str | None = None
    is_expired: bool = False


@dataclass(slots=True)
class CollectionPlan:
    id: int | None
    name: str
    created_at: str | None = None


@dataclass(slots=True)
class SyncRun:
    id: int | None
    started_at: str | None = None
    status: str = "pending"
