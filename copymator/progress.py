from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING

from .resume import format_duration

if TYPE_CHECKING:
    from .copier import CopyPlanItem


class ProgressReporter(ABC):
    """Abstract interface for reporting copy progress."""

    @abstractmethod
    def start(self, total_items: int) -> None: ...

    @abstractmethod
    def update(self, done_items: int) -> None: ...

    @abstractmethod
    def finish(self) -> None: ...

    def log_item(self, item: CopyPlanItem) -> None:  # type: ignore[unused-argument]
        """Optional hook for logging a single item."""
        # Default implementation is a no-op; subclasses may override.
        return


class ConsoleProgressReporter(ProgressReporter):
    """Simple console-based progress reporter.

    Designed so it can be easily replaced by a GUI implementation that updates
    a progress bar in a window.
    """

    def __init__(self) -> None:
        self.total: int = 0
        self.done: int = 0
        self.start_time: float | None = None
        self.copied_types = defaultdict(int)
        self.skipped_types = defaultdict(int)
        self.errors = 0

    def start(self, total_items: int) -> None:
        self.total = total_items
        self.done = 0
        self.start_time = time.time()
        logging.info("Starting copy of %d files.", total_items)
        print(f"Files to copy: {self.total}")

    def update(self, done_items: int) -> None:
        self.done = done_items
        if self.total <= 0:
            percent = 100
        else:
            percent = int(self.done / self.total * 100)
        print(f"\rProgress: {self.done}/{self.total} ({percent}%) ", end="", flush=True)

    def finish(self) -> None:
        end_time = time.time()
        duration = end_time - (self.start_time or end_time)
        print()
        logging.info("Copy finished.")
        print("Copy finished.")

        # Log session statistics
        copied = sum(self.copied_types.values())
        skipped = sum(self.skipped_types.values())
        logging.info(
            "Session statistics: Duration: %s, Copied: %d, Skipped: %d, Errors: %d",
            format_duration(duration),
            copied,
            skipped,
            self.errors,
        )
        for ext, count in self.copied_types.items():
            logging.info("Copied file type %s: %d", ext, count)
        for ext, count in self.skipped_types.items():
            logging.info("Skipped file type %s: %d", ext, count)

    def log_item(self, item: CopyPlanItem) -> None:
        from .copier import CopyStatus

        ext = item.src.suffix.lower()
        if item.status == CopyStatus.COPIED:
            self.copied_types[ext] += 1
            logging.info("COPIED: %s -> %s", item.src, item.dst)
        elif item.status == CopyStatus.SKIPPED:
            self.skipped_types[ext] += 1
            logging.info("SKIPPED: %s (destination exists)", item.src)
        elif item.status == CopyStatus.ERROR:
            self.errors += 1
            logging.error("ERROR copying %s: %s", item.src, item.error)
