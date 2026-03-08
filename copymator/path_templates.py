from __future__ import annotations

from pathlib import Path

from .metadata import PhotoMetadata


class PathTemplate:
    """Simple path template system for photos.

    Uses standard Python ``str.format`` syntax, e.g.:
      "{year}/{year}-{month}/{year}-{month}-{day}"
      "{camera}/{year}-{month}-{day}"
    """

    def __init__(self, template: str) -> None:
        self.template = template

    def render(self, metadata: PhotoMetadata, src_path: Path) -> Path:
        mapping = metadata.to_template_dict(src_path)
        try:
            relative = self.template.format(**mapping)
        except KeyError as exc:
            # If the template references a missing key, fall back to an "unknown" folder
            missing = str(exc)
            relative = f"unknown_missing_{missing.strip('"')}"
        return Path(relative)
