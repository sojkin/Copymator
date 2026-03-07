from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Set

from .logging_setup import get_log_file_path

log = logging.getLogger(__name__)


def parse_log_for_completed_files() -> Set[Path]:
    """
    Parses the log file to find files that were successfully copied or skipped.

    Returns a set of source paths of files that don't need to be copied again.
    """
    log_path = get_log_file_path()
    completed: Set[Path] = set()

    if not log_path.exists():
        return completed

    log.info("Parsing log file to find previously copied files...")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "COPIED:" in line:
                try:
                    # Expected format: "INFO: COPIED: <src> -> <dst>"
                    # or "COPIED: <src> -> <dst>" from older versions
                    src_part = line.split("COPIED:")[1].strip()
                    src_str = src_part.split(" -> ")[0]
                    completed.add(Path(src_str))
                except (IndexError, ValueError):
                    # Ignore lines that can't be parsed
                    pass
            elif "SKIPPED:" in line:
                try:
                    # Expected format: "INFO: SKIPPED: <src> (destination exists)"
                    src_part = line.split("SKIPPED:")[1].strip()
                    src_str = src_part.split(" (")[0]
                    completed.add(Path(src_str))
                except (IndexError, ValueError):
                    # Ignore lines that can't be parsed
                    pass

    log.info("Found %d previously copied/skipped files in the log.", len(completed))
    return completed
