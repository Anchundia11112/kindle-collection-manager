from __future__ import annotations

import hashlib
import logging
import math
import re
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from kindle_service.kindle.adapter import (
    ImportDuplicateDetail,
    ImportRepeatedTitleDetail,
    ImportResult,
    ImportedBookRecord,
    KindleAdapter,
)

logger = logging.getLogger(__name__)


class PlaywrightKindleAdapter(KindleAdapter):
    """Playwright-backed Kindle adapter."""

    DEFAULT_PAGE_SIZE = 25

    def __init__(
        self,
        *,
        browser_profile_path: Path,
        amazon_base_url: str,
        books_url: str,
        docs_url: str,
        headless: bool,
        page_delay_ms: int,
    ) -> None:
        self.browser_profile_path = browser_profile_path
        self.amazon_base_url = amazon_base_url
        self.books_url = books_url
        self.docs_url = docs_url
        self.headless = headless
        self.page_delay_ms = page_delay_ms

    def import_books(self, source: str = "all") -> ImportResult:
        self.browser_profile_path.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.browser_profile_path),
                headless=self.headless,
            )
            try:
                page = context.new_page()
                purchased_books: list[ImportedBookRecord] = []
                personal_documents: list[ImportedBookRecord] = []
                purchased_selected_count = 0
                personal_selected_count = 0
                purchased_duplicate_count = 0
                personal_duplicate_count = 0
                purchased_duplicate_details: list[ImportDuplicateDetail] = []
                personal_duplicate_details: list[ImportDuplicateDetail] = []
                purchased_repeated_title_details: list[ImportRepeatedTitleDetail] = []
                personal_repeated_title_details: list[ImportRepeatedTitleDetail] = []

                if source in {"all", "amazon"}:
                    logger.info("Starting Amazon purchased books import")
                    (
                        purchased_books,
                        purchased_selected_count,
                        purchased_duplicate_count,
                        purchased_duplicate_details,
                        purchased_repeated_title_details,
                    ) = self._collect_paginated_records(
                        page=page,
                        url=self.books_url,
                        source_type="amazon_book",
                        source_page="booksAll",
                    )

                if source in {"all", "docs"}:
                    logger.info("Starting personal documents import")
                    (
                        personal_documents,
                        personal_selected_count,
                        personal_duplicate_count,
                        personal_duplicate_details,
                        personal_repeated_title_details,
                    ) = self._collect_paginated_records(
                        page=page,
                        url=self.docs_url,
                        source_type="personal_document",
                        source_page="pdocs",
                    )
            finally:
                context.close()

        return ImportResult(
            purchased_books=purchased_books,
            personal_documents=personal_documents,
            purchased_books_selected_count=purchased_selected_count,
            personal_documents_selected_count=personal_selected_count,
            purchased_books_duplicate_count=purchased_duplicate_count,
            personal_documents_duplicate_count=personal_duplicate_count,
            purchased_books_duplicate_details=purchased_duplicate_details,
            personal_documents_duplicate_details=personal_duplicate_details,
            purchased_books_repeated_title_details=purchased_repeated_title_details,
            personal_documents_repeated_title_details=personal_repeated_title_details,
        )

    def sync_collection(self, collection_name: str, book_ids: list[int]) -> None:
        raise NotImplementedError("Playwright sync is not implemented yet.")

    def _collect_paginated_records(
        self,
        *,
        page: Page,
        url: str,
        source_type: str,
        source_page: str,
    ) -> tuple[
        list[ImportedBookRecord],
        int,
        int,
        list[ImportDuplicateDetail],
        list[ImportRepeatedTitleDetail],
    ]:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        self._move_mouse_to_neutral_position(page)
        page.wait_for_function(
            "() => /Showing\\s+\\d+\\s+to\\s+\\d+\\s+of\\s+\\d+\\s+items/.test(document.body.innerText)",
            timeout=15000,
        )

        records_by_id: dict[str, ImportedBookRecord] = {}
        selected_count = 0
        duplicate_count = 0
        duplicate_details: list[ImportDuplicateDetail] = []
        title_counts: dict[str, int] = {}
        title_unique_ids: dict[str, set[str]] = {}
        title_expired_flags: dict[str, bool] = {}
        page_number = 1
        while True:
            summary_before = self._get_summary_text(page)
            current_page_records = self._collect_current_page_records(
                page=page,
                source_type=source_type,
                source_page=source_page,
            )
            logger.info(
                "%s page %s -> %s rows (%s)",
                source_page,
                page_number,
                len(current_page_records),
                summary_before,
            )
            selected_count += len(current_page_records)

            for index, record in enumerate(current_page_records, start=1):
                expired_suffix = " [expired]" if record.is_expired else ""
                logger.info(
                    "%s page %s selected %s of %s: %s%s",
                    source_page,
                    page_number,
                    index,
                    len(current_page_records),
                    record.title,
                    expired_suffix,
                )

            for record in current_page_records:
                title_counts[record.title] = title_counts.get(record.title, 0) + 1
                title_unique_ids.setdefault(record.title, set()).add(record.asin)
                title_expired_flags[record.title] = (
                    title_expired_flags.get(record.title, False) or record.is_expired
                )
                if record.asin in records_by_id:
                    duplicate_count += 1
                    previous_record = records_by_id[record.asin]
                    duplicate_details.append(
                        ImportDuplicateDetail(
                            source_page=source_page,
                            synthetic_id=record.asin,
                            previous_title=previous_record.title,
                            current_title=record.title,
                            previous_is_expired=previous_record.is_expired,
                            current_is_expired=record.is_expired,
                        )
                    )
                    previous_expired_suffix = " [expired]" if previous_record.is_expired else ""
                    current_expired_suffix = " [expired]" if record.is_expired else ""
                    logger.warning(
                        "%s page %s duplicate synthetic id %s: replacing '%s'%s with '%s'%s",
                        source_page,
                        page_number,
                        record.asin,
                        previous_record.title,
                        previous_expired_suffix,
                        record.title,
                        current_expired_suffix,
                    )
                records_by_id[record.asin] = record

            next_page_number = page_number + 1
            if not self._go_to_next_page(
                page,
                summary_text=summary_before,
                next_page_number=next_page_number,
            ):
                logger.info("%s pagination stopped at page %s", source_page, page_number)
                break

            expected_summary = self._build_expected_summary(
                summary_text=summary_before,
                next_page_number=next_page_number,
            )
            self._wait_for_next_page(
                page,
                previous_summary=summary_before,
                expected_summary=expected_summary,
                expected_page_number=next_page_number,
            )
            self._move_mouse_to_neutral_position(page)
            page.wait_for_timeout(self.page_delay_ms)
            page_number = next_page_number

        logger.info(
            "%s selected %s rows and kept %s unique records (%s duplicates collapsed)",
            source_page,
            selected_count,
            len(records_by_id),
            duplicate_count,
        )
        for detail in duplicate_details:
            previous_expired_suffix = " [expired]" if detail.previous_is_expired else ""
            current_expired_suffix = " [expired]" if detail.current_is_expired else ""
            logger.info(
                "%s duplicate summary: '%s'%s -> '%s'%s",
                detail.source_page,
                detail.previous_title,
                previous_expired_suffix,
                detail.current_title,
                current_expired_suffix,
            )
        repeated_title_details = [
            ImportRepeatedTitleDetail(
                source_page=source_page,
                title=title,
                count=count,
                unique_record_count=len(title_unique_ids[title]),
                is_expired=title_expired_flags.get(title, False),
            )
            for title, count in sorted(title_counts.items())
            if count > 1
        ]
        for detail in repeated_title_details:
            expired_suffix = " [expired]" if detail.is_expired else ""
            logger.info(
                "%s repeated title summary: '%s'%s appeared %s times and produced %s unique records",
                detail.source_page,
                detail.title,
                expired_suffix,
                detail.count,
                detail.unique_record_count,
            )
        return (
            list(records_by_id.values()),
            selected_count,
            duplicate_count,
            duplicate_details,
            repeated_title_details,
        )

    def _collect_current_page_records(
        self,
        *,
        page: Page,
        source_type: str,
        source_page: str,
    ) -> list[ImportedBookRecord]:
        rows = page.evaluate(
            """
            () => {
              const uniqueRows = [];
              const seen = new Set();

              const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox']"));

              for (const checkbox of checkboxes) {
                let candidate = checkbox.parentElement;
                while (candidate && candidate !== document.body) {
                  const text = (candidate.innerText || '').trim();
                  const rect = candidate.getBoundingClientRect();
                  const hasCommonActions =
                    text.includes('Delete') &&
                    text.includes('More actions');
                  const hasBookActions =
                    text.includes('Deliver to Device') ||
                    text.includes('Deliver or remove from device');
                  const hasExpiredRentalActions =
                    text.includes('Mark as Read');
                  const looksLikeRow =
                    rect.width > 500 &&
                    rect.height > 60 &&
                    hasCommonActions &&
                    (hasBookActions || hasExpiredRentalActions);

                  if (looksLikeRow) {
                    if (!seen.has(candidate)) {
                      seen.add(candidate);
                      uniqueRows.push(text);
                    }
                    break;
                  }
                  candidate = candidate.parentElement;
                }
              }

              return uniqueRows;
            }
            """
        )

        records: list[ImportedBookRecord] = []
        for raw_text in rows:
            record = self._parse_row_text(
                raw_text=raw_text,
                source_type=source_type,
                source_page=source_page,
            )
            if record is not None:
                records.append(record)
        return records

    def _get_summary_text(self, page: Page) -> str:
        summary = page.evaluate(
            """
            () => {
              const match = document.body.innerText.match(/Showing\\s+\\d+\\s+to\\s+\\d+\\s+of\\s+\\d+\\s+items/);
              return match ? match[0] : '';
            }
            """
        )
        return str(summary)

    def _go_to_next_page(
        self,
        page: Page,
        *,
        summary_text: str,
        next_page_number: int,
    ) -> bool:
        summary_parts = self._parse_summary_text(summary_text)
        if summary_parts is None:
            logger.info("Could not parse summary text: %s", summary_text)
            return False

        _, _, total_items = summary_parts
        total_pages = math.ceil(total_items / self.DEFAULT_PAGE_SIZE)
        logger.info(
            "Pagination state: next target page %s of %s based on '%s'",
            next_page_number,
            total_pages,
            summary_text,
        )

        if next_page_number > total_pages:
            logger.info("Already on last page according to summary")
            return False

        if self._click_paginator_control(page, str(next_page_number)):
            logger.info("Clicking page %s", next_page_number)
            return True

        if self._click_paginator_control(page, ">"):
            logger.info("Clicking jump control to reveal page %s", next_page_number)
            page.wait_for_timeout(self.page_delay_ms)
            if self._click_paginator_control(page, str(next_page_number)):
                logger.info("Clicking page %s after jump", next_page_number)
                return True

        logger.info("Could not find visible paginator control for page %s", next_page_number)
        return False

    def _click_paginator_control(self, page: Page, label: str) -> bool:
        selector = "#pagination #page-RIGHT_PAGE" if label == ">" else f"#pagination #page-{label}"
        control = page.locator(selector).first
        if control.count() == 0 or not control.is_visible():
            return False

        control.click()
        return True

    def _build_expected_summary(self, *, summary_text: str, next_page_number: int) -> str | None:
        summary_parts = self._parse_summary_text(summary_text)
        if summary_parts is None:
            return None

        _, _, total_items = summary_parts
        start_index = ((next_page_number - 1) * self.DEFAULT_PAGE_SIZE) + 1
        end_index = min(next_page_number * self.DEFAULT_PAGE_SIZE, total_items)
        return f"Showing {start_index} to {end_index} of {total_items} items"

    def _wait_for_next_page(
        self,
        page: Page,
        *,
        previous_summary: str,
        expected_summary: str | None,
        expected_page_number: int,
    ) -> None:
        try:
            page.wait_for_function(
                """
                expectedPageNumber => {
                  const activePage = document.querySelector("#pagination .page-item.active");
                  return activePage && activePage.textContent.trim() === String(expectedPageNumber);
                }
                """,
                arg=expected_page_number,
                timeout=10000,
            )

            if expected_summary:
                page.wait_for_function(
                    """
                    ([previousSummary, targetSummary]) => {
                      const match = document.body.innerText.match(/Showing\\s+\\d+\\s+to\\s+\\d+\\s+of\\s+\\d+\\s+items/);
                      if (!match) {
                        return false;
                      }

                      return match[0] === targetSummary || match[0] !== previousSummary;
                    }
                    """,
                    arg=[previous_summary, expected_summary],
                    timeout=20000,
                )
            else:
                page.wait_for_function(
                    """
                    previousSummary => {
                      const match = document.body.innerText.match(/Showing\\s+\\d+\\s+to\\s+\\d+\\s+of\\s+\\d+\\s+items/);
                      return match && match[0] !== previousSummary;
                    }
                    """,
                    arg=previous_summary,
                    timeout=20000,
                )
        except PlaywrightTimeoutError:
            current_summary = self._get_summary_text(page)
            logger.info(
                "Timed out waiting for page %s. Previous summary='%s', expected summary='%s', current summary='%s'",
                expected_page_number,
                previous_summary,
                expected_summary or "",
                current_summary,
            )
            raise

    def _move_mouse_to_neutral_position(self, page: Page) -> None:
        viewport = page.viewport_size or {"width": 1280, "height": 720}
        x = max(10, viewport["width"] - 40)
        y = max(10, viewport["height"] - 40)
        page.mouse.move(x, y)

    def _parse_row_text(
        self,
        *,
        raw_text: str,
        source_type: str,
        source_page: str,
    ) -> ImportedBookRecord | None:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        filtered_lines: list[str] = []
        for line in lines:
            if line in {
                "Deliver or remove from device",
                "Deliver to Device",
                "Delete",
                "More actions",
                "Mark as Read",
                "Add or Remove from Collection",
            }:
                continue
            filtered_lines.append(line)

        if len(filtered_lines) < 2:
            return None

        title = filtered_lines[0]
        author = filtered_lines[1]
        if title == "Digital Content":
            return None
        is_expired = any(line.startswith("Expired on ") for line in filtered_lines)

        unique_id = self._build_record_id(
            filtered_lines=filtered_lines,
            source_type=source_type,
            source_page=source_page,
        )

        return ImportedBookRecord(
            title=title,
            author=author,
            asin=unique_id,
            source_type=source_type,
            source="playwright_import",
            source_page=source_page,
            is_expired=is_expired,
        )

    def _build_record_id(
        self,
        *,
        filtered_lines: list[str],
        source_type: str,
        source_page: str,
    ) -> str:
        raw = "|".join([source_type, source_page, *filtered_lines])
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"{source_type}-{digest}"

    def _parse_summary_text(self, summary_text: str) -> tuple[int, int, int] | None:
        match = re.search(
            r"Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+items",
            summary_text,
        )
        if match is None:
            return None

        start_index = int(match.group(1))
        end_index = int(match.group(2))
        total_items = int(match.group(3))
        return start_index, end_index, total_items
