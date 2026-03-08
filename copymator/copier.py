from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import AppSettings, ConflictStrategy
from .metadata import ExifMetadataReader, MetadataReader
from .path_templates import PathTemplate
from .progress import ProgressReporter

# Supported extensions, grouped by category
DEFAULT_SUPPORTED_EXTENSIONS: set[str] = {
    # Raster / jpg-like files
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".heic",
    ".heif",
    ".webp",
    # Raw formats from cameras
    ".arw",
    ".cr2",
    ".cr3",
    ".nef",
    ".orf",
    ".raf",
    ".rw2",
    ".dng",
    # Video files with metadata/Exif (mp4 and related)
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
}


class CopyStatus(str, Enum):
    """Status of a single file in the copy plan."""

    PENDING = "pending"
    COPIED = "copied"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CopyPlanItem:
    """Description of a single file in the copy plan."""

    src: Path
    dst: Path
    status: CopyStatus = CopyStatus.PENDING
    error: str | None = None


class CopyPlanner:
    """Builds a copy plan from a source directory and a path template.

    Performs no I/O other than reading metadata and walking the source tree,
    so it can be safely reused from a GUI or tests.
    """

    def __init__(
        self,
        metadata_reader: MetadataReader | None = None,
        supported_extensions: set[str] | None = None,
        resumed_files: set[Path] | None = None,
    ) -> None:
        self._metadata_reader = metadata_reader or ExifMetadataReader()
        self._supported_extensions = supported_extensions or DEFAULT_SUPPORTED_EXTENSIONS
        self._resumed_files = resumed_files or set()
        self._log = logging.getLogger(__name__)

    def build_plan(
        self,
        source_dir: Path,
        target_dir: Path,
        template: PathTemplate,
    ) -> list[CopyPlanItem]:
        items: list[CopyPlanItem] = []
        for src in source_dir.rglob("*"):
            if not src.is_file():
                continue

            if src in self._resumed_files:
                self._log.info("Skipping already copied file (from log): %s", src)
                continue

            if src.suffix.lower() not in self._supported_extensions:
                self._log.info("Skipping unsupported file: %s", src)
                continue

            try:
                metadata = self._metadata_reader.read(src)
            except Exception as e:
                self._log.warning("Could not read metadata for %s: %s", src, e)
                continue  # Skip files that cause metadata reading errors

            rel = template.render(metadata, src)
            dst = target_dir.joinpath(rel, src.name)
            items.append(CopyPlanItem(src=src, dst=dst))
        return items


class FileCopier:
    """Executes the copy plan and updates progress and item statuses."""

    def __init__(
        self,
        progress: ProgressReporter,
        conflict_strategy: ConflictStrategy = "skip",
    ) -> None:
        self.progress = progress
        self.conflict_strategy: ConflictStrategy = conflict_strategy

    def copy_all(self, items: list[CopyPlanItem]) -> None:
        """Copy all files from the plan, updating their status and reporting progress."""
        total = len(items)
        self.progress.start(total)
        done = 0

        for item in items:
            try:
                item.dst.parent.mkdir(parents=True, exist_ok=True)

                if item.dst.exists():
                    if self.conflict_strategy == "skip":
                        item.status = CopyStatus.SKIPPED
                    elif self.conflict_strategy == "overwrite":
                        shutil.copy2(item.src, item.dst)
                        item.status = CopyStatus.COPIED
                    elif self.conflict_strategy == "rename":
                        final_dst = self._find_non_conflicting_path(item.dst)
                        shutil.copy2(item.src, final_dst)
                        item.dst = final_dst
                        item.status = CopyStatus.COPIED
                    else:
                        item.status = CopyStatus.ERROR
                        item.error = f"Unknown conflict strategy: {self.conflict_strategy}"
                else:
                    shutil.copy2(item.src, item.dst)
                    item.status = CopyStatus.COPIED
            except Exception as exc:
                item.status = CopyStatus.ERROR
                item.error = str(exc)

            done += 1
            self.progress.update(done)
            self.progress.log_item(item)

        self.progress.finish()

    @staticmethod
    def _find_non_conflicting_path(path: Path) -> Path:
        base = path.with_suffix("")
        suffix = path.suffix
        counter = 1
        candidate = path
        while candidate.exists():
            candidate = base.with_name(f"{base.name}_{counter}").with_suffix(suffix)
            counter += 1
        return candidate


def run_copy(
    settings: AppSettings,
    progress: ProgressReporter,
    resumed_files: set[Path] | None = None,
) -> list[CopyPlanItem]:
    """Executes the full copy process based on the given settings.

    This function is independent of the CLI and can be reused in a future GUI.
    """
    template = PathTemplate(settings.path_template)
    planner = CopyPlanner(resumed_files=resumed_files)
    items = planner.build_plan(settings.source_dir, settings.target_dir, template)

    copier = FileCopier(progress, conflict_strategy=settings.conflict_strategy)
    copier.copy_all(items)
    return items
