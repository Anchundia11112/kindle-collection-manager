from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    storage_path: Path = Path("data/kindle_service.db")
    kindle_region: str = "us"
    kindle_headless: bool = False
    kindle_page_delay_ms: int = 2500
    browser_profile_path: Path = Path("data/browser-profile")
    amazon_base_url: str = "https://www.amazon.com/"
    content_library_books_url: str = (
        "https://www.amazon.com/hz/mycd/digital-console/contentlist/booksAll/dateDsc/"
    )
    content_library_docs_url: str = (
        "https://www.amazon.com/hz/mycd/digital-console/contentlist/pdocs/dateDsc/"
    )
