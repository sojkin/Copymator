from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

ConflictStrategy = Literal["skip", "overwrite", "rename"]


@dataclass
class AppSettings:
    """Application settings stored per machine.

    Describes the full set of parameters needed for a single copy run
    and is shared between the CLI and any future GUI.
    """

    source_dir: Path
    target_dir: Path
    path_template: str
    conflict_strategy: ConflictStrategy = "skip"
    ask_on_start: bool = True
    separate_log_file: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        return cls(
            source_dir=Path(data["source_dir"]),
            target_dir=Path(data["target_dir"]),
            path_template=data["path_template"],
            conflict_strategy=data.get("conflict_strategy", "skip"),
            ask_on_start=bool(data.get("ask_on_start", True)),
            separate_log_file=bool(data.get("separate_log_file", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_dir"] = str(self.source_dir)
        data["target_dir"] = str(self.target_dir)
        return data


class SettingsStorage:
    """Locates and reads/writes the ``settings.json`` file."""

    app_dir_name = "copymator"
    settings_file_name = "settings.json"

    def __init__(self) -> None:
        self.base_dir = self._detect_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.base_dir / self.settings_file_name

    @staticmethod
    def _detect_base_dir() -> Path:
        from platform import system

        system_name = system()
        home = Path.home()

        if system_name == "Windows":
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "Copymator"
            return home / "AppData" / "Roaming" / "Copymator"
        # Linux, macOS and other Unix-like systems – XDG
        xdg_config_home = os.getenv("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / "copymator"
        return home / ".config" / "copymator"

    def load(self) -> AppSettings | None:
        if not self.settings_path.exists():
            return None
        with self.settings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        data = settings.to_dict()
        with self.settings_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
