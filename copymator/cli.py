from __future__ import annotations

from pathlib import Path
from typing import Optional
import sys

from .config import AppSettings, SettingsStorage
from .copier import run_copy
from .logging_setup import configure_logging
from .progress import ConsoleProgressReporter


DEFAULT_TEMPLATE_DATE = "{year}/{year}-{month}/{year}-{month}-{day}"
DEFAULT_TEMPLATE_CAMERA = "{camera}/{year}-{month}-{day}"


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question in the console.

    Returns the default value when the user presses Enter.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        answer = input(prompt + suffix).strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Proszę odpowiedzieć 'y' lub 'n'.")


def ask_path(prompt: str, must_exist: bool = False) -> Path:
    """Ask the user for a filesystem path and optionally require it to exist."""
    while True:
        raw = input(prompt + " ").strip()
        p = Path(raw).expanduser()
        if must_exist and not p.exists():
            print("Ścieżka nie istnieje, spróbuj ponownie.")
            continue
        return p


def choose_template() -> str:
    """Let the user choose one of the predefined directory templates."""
    print("Wybierz szablon struktury katalogów:")
    print(f"1) {DEFAULT_TEMPLATE_DATE} (rok/miesiąc/dzień)")
    print(f"2) {DEFAULT_TEMPLATE_CAMERA} (aparat/rok-miesiąc-dzień)")
    while True:
        choice = input("Wybór (1/2): ").strip()
        if choice == "1":
            return DEFAULT_TEMPLATE_DATE
        if choice == "2":
            return DEFAULT_TEMPLATE_CAMERA
        print("Nieprawidłowa opcja, wybierz 1 lub 2.")


def first_run_config(storage: SettingsStorage) -> AppSettings:
    """Interactively create the first configuration when no settings file exists."""
    print("Wygląda na to, że uruchamiasz Copymator po raz pierwszy.")
    print("Wybierz tryb:")
    print("1) Szybkie kopiowanie z domyślnymi ustawieniami")
    print("2) Konfiguracja szczegółowa")

    mode: Optional[str] = None
    while mode not in {"1", "2"}:
        mode = input("Wybór (1/2): ").strip()
        if mode not in {"1", "2"}:
            print("Nieprawidłowa opcja, wybierz 1 lub 2.")

    if mode == "1":
        target_dir = ask_path("Podaj katalog docelowy zdjęć:", must_exist=False)
        source_dir = ask_path("Podaj katalog źródłowy (karta pamięci):", must_exist=True)
        path_template = DEFAULT_TEMPLATE_DATE
        settings = AppSettings(
            source_dir=source_dir,
            target_dir=target_dir,
            path_template=path_template,
            conflict_strategy="skip",
            ask_on_start=False,
        )
        storage.save(settings)
        return settings

    print("Konfiguracja szczegółowa:")
    source_dir = ask_path("Podaj katalog źródłowy (karta pamięci):", must_exist=True)
    target_dir = ask_path("Podaj katalog docelowy zdjęć:", must_exist=False)
    path_template = choose_template()

    print("Zachowanie przy konflikcie nazw:")
    print("1) pominąć istniejący plik")
    print("2) nadpisać istniejący plik")
    print("3) zapisać pod nową nazwą (dodaj numer)")
    conflict_choice = None
    while conflict_choice not in {"1", "2", "3"}:
        conflict_choice = input("Wybór (1/2/3): ").strip()
        if conflict_choice not in {"1", "2", "3"}:
            print("Nieprawidłowa opcja, wybierz 1, 2 lub 3.")
    conflict_map = {"1": "skip", "2": "overwrite", "3": "rename"}
    conflict_strategy = conflict_map[conflict_choice]

    ask_on_start = ask_yes_no(
        "Czy przy każdym uruchomieniu pytać o potwierdzenie ustawień?", default=True
    )

    settings = AppSettings(
        source_dir=source_dir,
        target_dir=target_dir,
        path_template=path_template,
        conflict_strategy=conflict_strategy,  # type: ignore[arg-type]
        ask_on_start=ask_on_start,
    )
    storage.save(settings)
    return settings


def maybe_confirm_settings(settings: AppSettings) -> AppSettings:
    """Display current settings and optionally let the user tweak them."""
    print("Current settings:")
    print(f"  Source (card): {settings.source_dir}")
    print(f"  Target: {settings.target_dir}")
    print(f"  Path template: {settings.path_template}")
    print(f"  File conflict strategy: {settings.conflict_strategy}")

    if not settings.ask_on_start:
        return settings

    if ask_yes_no("Use these settings without changes?", default=True):
        return settings

    # Allow quick source/target changes without full reconfiguration
    if ask_yes_no("Change source directory?", default=False):
        settings.source_dir = ask_path(
            "New source directory (memory card):", must_exist=True
        )
    if ask_yes_no("Change target directory?", default=False):
        settings.target_dir = ask_path(
            "New target directory for photos:", must_exist=False
        )

    return settings


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Loads or creates settings and then runs the copy process.
    """
    if argv is None:
        argv = sys.argv[1:]

    # For now ignore argv and run in interactive mode only.
    configure_logging()
    storage = SettingsStorage()

    settings = storage.load()
    if settings is None:
        settings = first_run_config(storage)
    else:
        settings = maybe_confirm_settings(settings)

    progress = ConsoleProgressReporter()
    run_copy(settings, progress)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

