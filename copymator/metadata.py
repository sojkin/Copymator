from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Protocol
import json
import shutil
import subprocess
import logging
import platform

try:
    from PIL import Image, ExifTags
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ExifTags = None  # type: ignore[assignment]


@dataclass
class PhotoMetadata:
    """Basic photo metadata required to build output paths."""

    taken_at: Optional[datetime]
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None

    def to_template_dict(self, src_path: Path) -> Dict[str, str]:
        """Build a dictionary of fields that can be used in a path template."""
        dt = self.taken_at
        if dt is None:
            # Fallback: use the file modification time
            stat = src_path.stat()
            dt = datetime.fromtimestamp(stat.st_mtime)

        year = f"{dt.year:04d}"
        month = f"{dt.month:02d}"
        day = f"{dt.day:02d}"

        return {
            "year": year,
            "month": month,
            "day": day,
            "camera": (self.camera_model or self.camera_make or "unknown_camera"),
        }


class MetadataReader(Protocol):
    """Interface for reading photo metadata.

    The default implementation uses only the standard library, but this
    protocol allows swapping in richer implementations (e.g. Pillow-based).
    """

    def read(self, path: Path) -> PhotoMetadata:
        ...


class StatOnlyMetadataReader:
    """Simple MetadataReader that relies only on file ``stat()``.

    It does not read EXIF – instead it uses the file modification time as
    an approximation of when the photo was taken and leaves camera info unset.
    """

    def read(self, path: Path) -> PhotoMetadata:
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime)
        return PhotoMetadata(taken_at=dt)


class ExifMetadataReader:
    """MetadataReader that prefers EXIF data with a fallback to ``stat()``."""

    def __init__(self) -> None:
        self._fallback = StatOnlyMetadataReader()
        self._exiftool_path = shutil.which("exiftool")
        if self._exiftool_path is None:
            system = platform.system()
            if system == "Linux":
                hint = "Install exiftool using your package manager (e.g. dnf/apt/pacman)."
            elif system == "Darwin":
                hint = "Install exiftool via Homebrew: brew install exiftool."
            elif system == "Windows":
                hint = "Download exiftool for Windows from the author and add it to PATH."
            else:
                hint = "Install exiftool for your system and add it to PATH."
            logging.warning(
                "No exiftool found in PATH – RAW dates may be incorrect. %s", hint
            )

    def _read_with_exiftool(self, path: Path) -> Optional[PhotoMetadata]:
        """Try to read metadata via the external ``exiftool`` binary.

        exiftool has excellent support for RAW formats (e.g. CR3), which Pillow
        may not handle well.
        """
        if self._exiftool_path is None:
            return None

        try:
            output = subprocess.check_output(
                [
                    self._exiftool_path,
                    "-j",
                    "-DateTimeOriginal",
                    "-DateTime",
                    "-Make",
                    "-Model",
                    str(path),
                ],
                text=True,
            )
        except Exception:  # noqa: BLE001
            return None

        try:
            data_list = json.loads(output)
            if not data_list:
                return None
            data = data_list[0]
        except Exception:  # noqa: BLE001
            return None

        date_str = data.get("DateTimeOriginal") or data.get("DateTime")
        taken_at: Optional[datetime] = None
        if isinstance(date_str, str):
            try:
                taken_at = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except Exception:  # noqa: BLE001
                taken_at = None

        meta = self._fallback.read(path)
        if taken_at is not None:
            meta.taken_at = taken_at

        make = data.get("Make")
        model = data.get("Model")
        if isinstance(make, str):
            meta.camera_make = make.strip()
        if isinstance(model, str):
            meta.camera_model = model.strip()

        return meta

    def read(self, path: Path) -> PhotoMetadata:
        # Prefer exiftool first (handles RAW formats such as CR3)
        meta = self._read_with_exiftool(path)
        if meta is not None:
            return meta

        if Image is None or ExifTags is None:
            # Pillow is not available – fall back to stat()-only metadata.
            return self._fallback.read(path)

        try:
            with Image.open(path) as img:  # type: ignore[call-arg]
                exif_raw = img._getexif() or {}
        except Exception:  # noqa: BLE001
            return self._fallback.read(path)

        # Convert numeric EXIF tag IDs to readable names
        tags: Dict[str, str] = {}
        for tag_id, value in exif_raw.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))  # type: ignore[index]
            tags[name] = value

        taken_at: Optional[datetime] = None
        date_str = tags.get("DateTimeOriginal") or tags.get("DateTime")
        if isinstance(date_str, str):
            # EXIF timestamp format: "YYYY:MM:DD HH:MM:SS"
            try:
                taken_at = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except Exception:  # noqa: BLE001
                taken_at = None

        meta = self._fallback.read(path)
        if taken_at is not None:
            meta.taken_at = taken_at
        # Also fill camera_make / camera_model from EXIF if present
        make = tags.get("Make")
        model = tags.get("Model")
        if isinstance(make, str):
            meta.camera_make = make.strip()
        if isinstance(model, str):
            meta.camera_model = model.strip()

        return meta


