from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .copier import CopyPlanItem


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
        print("Copy finished.")

