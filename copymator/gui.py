from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .backend import CopyManager
from .progress import ProgressReporter

if TYPE_CHECKING:
    from .config import AppSettings


class GUICopyInterface:
    """Basic interface for GUI to use CopyManager.

    Placeholder for future GUI implementation.
    """

    def __init__(self, progress: ProgressReporter) -> None:
        self.manager = CopyManager(progress)

    def start_copy(self, settings: AppSettings, resumed_files: set[Path] | None = None) -> None:
        """Start the copy process via GUI."""
        self.manager.execute_copy(settings, resumed_files)
