from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict

from .logging_setup import get_log_file_path

log = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to h m s format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs:.2f}s"
    elif minutes > 0:
        return f"{minutes}m {secs:.2f}s"
    else:
        return f"{secs:.2f}s"


def parse_log_for_completed_files() -> set[Path]:
    """Parses the log file to find files that were successfully copied or skipped.

    Returns a set of source paths of files that don't need to be copied again.
    """
    log_path = get_log_file_path()
    completed: set[Path] = set()

    if not log_path.exists():
        return completed

    log.info("Parsing log file to find previously copied files...")
    with open(log_path, encoding="utf-8") as f:
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


def parse_log_for_session_info() -> Dict[str, any]:
    """Parses the log file for session information.

    Returns a dict with:
    - total_sessions: int
    - interrupted_last: bool
    - sessions_after_interruption: int
    - total_time: float (seconds)
    - session_times: List[float]
    - session_details: List[dict] with start_time, end_time, duration, copied, skipped, errors, etc.
    """
    log_path = get_log_file_path()
    sessions = []
    current_session = None

    if not log_path.exists():
        return {
            "total_sessions": 0,
            "interrupted_last": False,
            "sessions_after_interruption": 0,
            "total_time": 0.0,
            "session_times": [],
            "session_details": [],
        }

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if "SESSION_START" in line:
                if current_session:
                    # Finish previous session if not ended
                    sessions.append(current_session)
                # Start new session
                match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
                if match:
                    start_dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                    current_session = {
                        "start_time": start_dt,
                        "end_time": None,
                        "last_file_time": None,
                        "completed": False,
                        "copied_types": defaultdict(int),
                        "skipped_types": defaultdict(int),
                        "unsupported_types": defaultdict(int),  # ← add
                        "errors": 0,
                    }
            elif "SESSION_END" in line:
                if current_session:
                    match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
                    if match:
                        end_dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                        current_session["end_time"] = end_dt
                        current_session["completed"] = True
                        sessions.append(current_session)
                        current_session = None
            elif current_session:
                # Always extract timestamp from any line in the session
                match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
                if match:
                    file_dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
                    current_session["last_file_time"] = file_dt

                if "COPIED:" in line:
                    # Extract extension from path
                    match_path = re.search(r"COPIED: (.+?) ->", line)
                    if match_path:
                        src_path = match_path.group(1)
                        ext = Path(src_path).suffix.lower().lstrip(".")
                        current_session["copied_types"][ext] += 1
                elif "SKIPPED:" in line:
                    match_path = re.search(r"SKIPPED: (.+?) \(", line)
                    if match_path:
                        src_path = match_path.group(1)
                        ext = Path(src_path).suffix.lower().lstrip(".")
                        current_session["skipped_types"][ext] += 1
                elif "ERROR" in line:
                    current_session["errors"] += 1
                elif "Skipping unsupported file:" in line:
                    match_path = re.search(r"Skipping unsupported file: (.+?)$", line)
                    if match_path:
                        src_path = match_path.group(1)
                        ext = Path(src_path).suffix.lower().lstrip(".")
                        if ext:  # ignore files without extension
                            current_session["unsupported_types"][ext] += 1

    # Handle last session if not ended
    if current_session:
        sessions.append(current_session)

    # Calculate durations
    session_times = []
    session_details = []
    for session in sessions:
        if session["completed"] and session["end_time"]:
            duration = (session["end_time"] - session["start_time"]).total_seconds()
        elif session["last_file_time"]:
            duration = (session["last_file_time"] - session["start_time"]).total_seconds()
        else:
            duration = 0.0
        session_times.append(duration)
        session_details.append(
            {
                "start_time": session["start_time"],
                "end_time": session["end_time"],
                "last_file_time": session["last_file_time"],
                "duration": duration,
                "completed": session["completed"],
                "copied_types": dict(session["copied_types"]),
                "skipped_types": dict(session["skipped_types"]),
                "unsupported_types": dict(session["unsupported_types"]),
                "errors": session["errors"],
            }
        )

    total_sessions = len([s for s in sessions if s["completed"]])
    interrupted_last = sessions and not sessions[-1]["completed"]
    sessions_after_interruption = 0
    if interrupted_last and len(sessions) > 1:
        sessions_after_interruption = len([s for s in sessions[:-1] if s["completed"]]) - (
            len(sessions) - 1
        )

    total_time = sum(session_times)

    return {
        "total_sessions": total_sessions,
        "interrupted_last": interrupted_last,
        "sessions_after_interruption": sessions_after_interruption,
        "total_time": total_time,
        "session_times": session_times,
        "session_details": session_details,
    }


def log_overall_summary() -> None:
    """Logs overall summary of all sessions from the log file."""
    info = parse_log_for_session_info()
    logging.info("=== OVERALL SUMMARY ===")
    logging.info("Total sessions completed: %d", info["total_sessions"])
    if info["interrupted_last"]:
        logging.info("Last session was interrupted")
        logging.info("Sessions after last interruption: %d", info["sessions_after_interruption"])
    else:
        logging.info("All sessions completed successfully")
    logging.info("Total time across all sessions: %s", format_duration(info["total_time"]))

    # Aggregate total statistics across all sessions
    total_copied = defaultdict(int)
    total_skipped = defaultdict(int)
    total_errors = 0
    for session in info["session_details"]:
        for ext, count in session["copied_types"].items():
            total_copied[ext] += count
        for ext, count in session["skipped_types"].items():
            total_skipped[ext] += count
        total_errors += session["errors"]

    total_copied_count = sum(total_copied.values())
    total_skipped_count = sum(total_skipped.values())

    logging.info("Total files copied: %d", total_copied_count)
    if total_copied:
        copied_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in sorted(total_copied.items())
        )
        logging.info("  Copied by type: %s", copied_str)
    logging.info("Total files skipped: %d", total_skipped_count)
    if total_skipped:
        skipped_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in sorted(total_skipped.items())
        )
        logging.info("  Skipped by type: %s", skipped_str)
    logging.info("Total errors: %d", total_errors)

    # Aggregate unsupported statistics
    total_unsupported = defaultdict(int)
    for session in info["session_details"]:
        for ext, count in session.get("unsupported_types", {}).items():
            total_unsupported[ext] += count

    total_unsupported_count = sum(total_unsupported.values())
    if total_unsupported_count > 0:
        logging.info("Total unsupported files: %d", total_unsupported_count)
        unsupported_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in sorted(total_unsupported.items())
        )
        logging.info("  Unsupported by type: %s", unsupported_str)

    logging.info("Session details:")
    for i, session in enumerate(info["session_details"], 1):
        start_str = session["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        status = "Completed" if session["completed"] else "Interrupted"
        duration_str = format_duration(session["duration"])
        copied_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in session["copied_types"].items()
        )
        skipped_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in session["skipped_types"].items()
        )
        logging.info(
            "  Session %d: Started at %s, Duration: %s, Status: %s",
            i,
            start_str,
            duration_str,
            status,
        )
        if copied_str:
            logging.info("    Copied: %s", copied_str)
        if skipped_str:
            logging.info("    Skipped: %s", skipped_str)
        if session["errors"] > 0:
            logging.info("    Errors: %d", session["errors"])
        unsupported_str = ", ".join(
            f"{ext.upper()}: {count}" for ext, count in session.get("unsupported_types", {}).items()
        )
        if unsupported_str:
            logging.info("    Unsupported: %s", unsupported_str)
    logging.info("=== END SUMMARY ===")
