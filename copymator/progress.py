from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .copier import CopyPlanItem, CopyStatus


class ProgressReporter(ABC):
    """Abstract interface for reporting copy progress."""

    @abstractmethod
    def start(self, total_items: int) -> None:
        ...

    @abstractmethod
    def update(self, done_items: int) -> None:
        ...

    @abstractmethod
    def finish(self) -> None:
        ...

    def log_item(self, item: "CopyPlanItem") -> None:  # type: ignore[unused-argument]
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

    def start(self, total_items: int) -> None:
        self.total = total_items
        self.done = 0
        logging.info("Starting copy of %d files.", total_items)
        print(f"Files to copy: {self.total}")

    def update(self, done_items: int) -> None:
        self.done = done_items
        if self.total <= 0:
            percent = 100
        else:
            percent = int(self.done / self.total * 100)
        print(f"\rProgress: {self.done}/{self.total} ({percent}%)", end="", flush=True)

    def finish(self) -> None:
        print()
        logging.info("Copy finished.")
        print("Copy finished.")

    def log_item(self, item: "CopyPlanItem") -> None:
        from .copier import CopyStatus

        if item.status == CopyStatus.COPIED:
            logging.info("COPIED: %s -> %s", item.src, item.dst)
        elif item.status == CopyStatus.SKIPPED:
            logging.info("SKIPPED: %s (destination exists)", item.src)
        elif item.status == CopyStatus.ERROR:
            logging.error("ERROR copying %s: %s", item.src, item.error)

