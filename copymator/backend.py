from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .copier import run_copy
from .progress import ProgressReporter

if TYPE_CHECKING:
    from .config import AppSettings


class CopyManager:
    """Manages the copy process, including planning and execution."""

    def __init__(self, progress: ProgressReporter) -> None:
        self.progress = progress

    def execute_copy(
        self,
        settings: AppSettings,
        resumed_files: set[Path] | None = None,
    ) -> list[CopyPlanItem]:
        """Executes the copy process."""
        return run_copy(settings, self.progress, resumed_files)
