from __future__ import annotations

from pathlib import Path
from typing import Optional
import sys
import os

from .config import AppSettings, SettingsStorage
from .copier import run_copy
from .logging_setup import configure_logging, get_log_file_path, clear_log_file
from .progress import ConsoleProgressReporter
from .resume import parse_log_for_completed_files


DEFAULT_TEMPLATE_DATE = "{year}/{year}-{month}/{year}-{month}-{day}"
DEFAULT_TEMPLATE_CAMERA = "{camera}/{year}-{month}-{day}"

TEMPLATE_PARTS = {
    "1": {"value": "{year}", "desc": "Year photo was taken (YYYY)"},
    "2": {"value": "{month}", "desc": "Month photo was taken (MM)"},
    "3": {"value": "{day}", "desc": "Day photo was taken (DD)"},
    "4": {"value": "{camera}", "desc": "Camera model"},
}


def clear_screen():
    """Clears the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


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
        print("Please answer 'y' or 'n'.")


def ask_path(prompt: str, must_exist: bool = False) -> Path:
    """Ask the user for a filesystem path and optionally require it to exist."""
    while True:
        raw = input(prompt + " ").strip()
        p = Path(raw).expanduser()
        if must_exist and not p.exists():
            print("Path does not exist, please try again.")
            continue
        return p


def build_template_interactively() -> str:
    """Guide the user through building a custom path template."""
    template_parts = []
    while True:
        clear_screen()
        print("--- Path Template Builder ---\n")
        print("Available parts:")
        for key, part in TEMPLATE_PARTS.items():
            print(f"  {key}) {part['value']} - {part['desc']}")
        print("Type 's' to add a separator (e.g., / or -).")
        print("Type 'f' to finish and save the template.")
        print("Type 'c' to cancel and exit the builder.\n")

        current_template = "".join(template_parts)
        print(f"Current template: {current_template}\n")
        choice = input("Choose a part, 's' (separator), 'f' (finish), 'c' (cancel): ").strip().lower()

        if choice in TEMPLATE_PARTS:
            template_parts.append(TEMPLATE_PARTS[choice]["value"])
        elif choice == 's':
            separator = input("Enter separator: ")
            template_parts.append(separator)
        elif choice == 'f':
            if not current_template:
                print("Template cannot be empty. Press Enter to continue...")
                input()
                continue
            return current_template
        elif choice == 'c':
            return ""  # Return empty to indicate cancellation
        else:
            print("Invalid option. Press Enter to try again...")
            input()


def choose_template() -> str:
    """Let the user choose a template or build one."""
    while True:
        clear_screen()
        print("Choose a directory structure template:")
        print(f"1) {DEFAULT_TEMPLATE_DATE} (date)")
        print(f"2) {DEFAULT_TEMPLATE_CAMERA} (camera)")
        print("3) Build a custom template")

        choice = input("Choice (1/2/3): ").strip()
        if choice == "1":
            return DEFAULT_TEMPLATE_DATE
        if choice == "2":
            return DEFAULT_TEMPLATE_CAMERA
        if choice == "3":
            custom_template = build_template_interactively()
            if custom_template:
                return custom_template
            # If builder was cancelled, loop again
            print("\nTemplate creation cancelled. Please choose an option.")
            continue

        print("Invalid option, choose 1, 2, or 3.")


def first_run_config(storage: SettingsStorage) -> AppSettings:
    """Interactively create the first configuration when no settings file exists."""
    clear_screen()
    print("It looks like you are running Copymator for the first time.")
    print("Choose a mode:")
    print("1) Quick copy with default settings")
    print("2) Detailed configuration")

    mode: Optional[str] = None
    while mode not in {"1", "2"}:
        mode = input("Choice (1/2): ").strip()
        if mode not in {"1", "2"}:
            print("Invalid option, choose 1 or 2.")

    if mode == "1":
        target_dir = ask_path("Enter the target directory for photos:", must_exist=False)
        source_dir = ask_path("Enter the source directory (memory card):", must_exist=True)
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

    print("\nDetailed configuration:")
    source_dir = ask_path("Enter the source directory (memory card):", must_exist=True)
    target_dir = ask_path("Enter the target directory for photos:", must_exist=False)
    path_template = choose_template()

    print("\nFile name conflict behavior:")
    print("1) skip existing file")
    print("2) overwrite existing file")
    print("3) save with a new name (add a number)")
    conflict_choice = None
    while conflict_choice not in {"1", "2", "3"}:
        conflict_choice = input("Choice (1/2/3): ").strip()
        if conflict_choice not in {"1", "2", "3"}:
            print("Invalid option, choose 1, 2, or 3.")
    conflict_map = {"1": "skip", "2": "overwrite", "3": "rename"}
    conflict_strategy = conflict_map[conflict_choice]

    ask_on_start = ask_yes_no(
        "\nAsk for confirmation on every run?", default=True
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
    clear_screen()
    print("Current settings:")
    print(f"  Source (card): {settings.source_dir}")
    print(f"  Target: {settings.target_dir}")
    print(f"  Path template: {settings.path_template}")
    print(f"  File conflicts: {settings.conflict_strategy}\n")

    if not settings.ask_on_start:
        return settings

    if ask_yes_no("Use these settings without changes?", default=True):
        return settings

    # Allow quick source/target changes without full reconfiguration
    if ask_yes_no("\nChange source directory?", default=False):
        settings.source_dir = ask_path(
            "New source directory (memory card):", must_exist=True
        )
    if ask_yes_no("Change target directory?", default=False):
        settings.target_dir = ask_path(
            "New target directory for photos:", must_exist=False
        )
    if ask_yes_no("Change path template?", default=False):
        settings.path_template = choose_template()

    return settings


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Loads or creates settings and then runs the copy process.
    """
    if argv is None:
        argv = sys.argv[1:]

    resumed_files = None
    log_path = get_log_file_path()
    if log_path.exists() and log_path.stat().st_size > 0:
        if ask_yes_no("Previous log file found. Resume last copy?", default=True):
            # When resuming, we don't clear the log
            configure_logging()
            resumed_files = parse_log_for_completed_files()
        elif ask_yes_no("Clear previous logs?", default=True):
            clear_log_file()
            configure_logging()
        else:
            configure_logging()
    else:
        configure_logging()

    storage = SettingsStorage()

    settings = storage.load()
    if settings is None:
        settings = first_run_config(storage)
    else:
        settings = maybe_confirm_settings(settings)

    progress = ConsoleProgressReporter()
    run_copy(settings, progress, resumed_files=resumed_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

