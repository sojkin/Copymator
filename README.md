# Copymator

**Version:** 0.1.0


Copymator is a small cross‑platform CLI tool for copying photos from a memory card
to a destination directory, organizing them into sub‑folders based on metadata
(date and optionally camera), and logging what was copied.
The core logic is written so it can be reused from a future GUI.

---

## Features

- **Interactive CLI workflow**:
  - first run: simple menu with quick setup or detailed configuration,
  - subsequent runs: uses saved settings, with an option to quickly adjust paths.
- **Per‑machine settings** stored in a JSON file in the user config directory.
- **Dynamic directory structure** based on metadata, for example:
  - `"{year}/{year}-{month}/{year}-{month}-{day}"`,
  - `"{camera}/{year}-{month}-{day}"`.
- **Copy strategies for existing files**: skip / overwrite / rename with numeric suffix.
- **Progress reporting** in the terminal.
- **Logging** to a file plus console output, including a session summary (copied/skipped/errors per type).
- **Resume support**: the tool can continue an interrupted run by parsing the existing log, skipping already processed files.
- **Overall summary** across multiple sessions, with per-session breakdown and unsupported-file statistics.
- **Unsupported file reporting**: every skipped file due to unsupported extension is logged and counted.
- **Ready for GUI integration** via the `run_copy()` function and `ProgressReporter` interface.

---

## Requirements

### Python

- **Python**: 3.10 or newer.

Python dependencies (managed by `pyproject.toml`):

- `pillow` – used to read EXIF metadata for common image formats.

Install all Python dependencies with:

```bash
pip install .
```

from the project root directory.

### Optional: exiftool (recommended for RAW files)

For RAW formats such as **Canon CR3** Copymator prefers to read metadata using
the external `exiftool` binary. If `exiftool` is not available, it falls back
to Pillow and, if that also fails, to the file modification time.

Recommended installation per platform:

- **Linux**: install from your package manager, e.g.:
  - Fedora: `sudo dnf install perl-Image-ExifTool`
  - Debian/Ubuntu: `sudo apt install libimage-exiftool-perl`
  - Arch: `sudo pacman -S exiftool`
- **macOS** (Homebrew):
  - `brew install exiftool`
- **Windows**:
  - download ExifTool for Windows from the official site,
  - unpack and add the `exiftool.exe` directory to your `PATH`.

If `exiftool` is missing, Copymator will log a warning such as:

> No exiftool found in PATH – RAW dates may be incorrect.

---

## Settings location

Settings are stored per user / per machine in a JSON file:

- **Linux**:
  `~/.config/copymator/settings.json`
  (or `$XDG_CONFIG_HOME/copymator/settings.json` if `XDG_CONFIG_HOME` is set)
- **macOS**:
  also uses the XDG‑style config directory, for example
  `~/.config/copymator/settings.json`
- **Windows**:
  `%APPDATA%\Copymator\settings.json`
  (typically something like `C:\Users\<user>\AppData\Roaming\Copymator\settings.json`)

The same directory also contains the default log file `copymator.log`.

---

## Installation and basic usage

From the project root (`/home/marcin/Projekty/Copymator` in your case):

```bash
cd /home/marcin/Projekty/Copymator
pip install .
```

After installation you can either:

### 1. Run as installed script

```bash
copymator
```

### 2. Run directly as a module (without installing)

From the project root:

```bash
python -m copymator.cli
```

Both commands run the same CLI entry point.

---

## First run – interactive setup

On the first run there is no `settings.json`, so Copymator enters a setup mode
and shows a menu (messages are currently in Polish):

1. **Quick copy with default settings**
   - asks only for:
     - destination directory for photos,
     - source directory (memory card),
   - uses the default date‑based template
     `"{year}/{year}-{month}/{year}-{month}-{day}"`,
   - sets conflict strategy to `skip`,
   - disables asking for confirmation on every start.

2. **Detailed configuration**
   - asks for:
     - source directory (card),
     - target directory,
     - one of the predefined templates
       (`{year}/{year}-{month}/{year}-{month}-{day}` or `{camera}/{year}-{month}-{day}`),
     - conflict behaviour: skip / overwrite / rename,
     - whether to confirm settings on each run.

At the end of the wizard Copymator writes `settings.json` and immediately starts
copying, showing a progress line in the terminal.

---

## Subsequent runs

On later runs Copymator:

1. Loads `settings.json`.
2. If `ask_on_start` is **false**, it:
   - prints the current settings,
   - starts copying immediately.
3. If `ask_on_start` is **true**, it:
   - shows current settings,
   - asks if you want to use them as‑is,
   - optionally lets you quickly change:
     - source directory,
     - target directory,
   - then runs the copy.

The directory structure is generated from the configured template and metadata
(`year`, `month`, `day`, `camera`).

---

## How paths are generated

Internally Copymator:

1. Scans the source directory recursively.
2. For each file:
   - tries to read EXIF (preferably via `exiftool`, then Pillow),
   - falls back to file modification time if no usable timestamp is found.
3. Builds a mapping like:

```python
{
    "year": "2024",
    "month": "09",
    "day": "29",
    "camera": "Canon EOS R6m2",
}
```

4. Applies the configured template, e.g.:

```text
{year}/{year}-{month}/{year}-{month}-{day}
→ 2024/2024-09/2024-09-29
```

5. Copies the file to:

```text
<target>/<rendered_template>/<original_filename>
```

When a target file already exists, the configured conflict strategy is used:

- **skip** – do not copy, mark item as skipped,
- **overwrite** – copy, replacing the existing file,
- **rename** – find a free name by appending `_1`, `_2`, … before the extension.

---

## Using Copymator from other code (e.g. GUI)

The public API intended for reuse is:

- `copymator.config.AppSettings` – holds configuration for a single run.
- `copymator.progress.ProgressReporter` – interface for progress reporting.
- `copymator.copier.run_copy(settings: AppSettings, progress: ProgressReporter)` – performs the copy and returns a list of `CopyPlanItem` objects with final status.

Example skeleton for a future GUI:

```python
from copymator.config import AppSettings
from copymator.copier import run_copy
from copymator.progress import ProgressReporter


class GuiProgressReporter(ProgressReporter):
    def start(self, total_items: int) -> None:
        # initialize GUI progress bar
        ...

    def update(self, done_items: int) -> None:
        # update GUI progress bar
        ...

    def finish(self) -> None:
        # finalize UI state
        ...


settings = AppSettings(
    source_dir=...,
    target_dir=...,
    path_template="{year}/{year}-{month}/{year}-{month}-{day}",
)
items = run_copy(settings, GuiProgressReporter())
```

---

## Logging

Logging is configured by `copymator.logging_setup.configure_logging()` and is
invoked automatically from the CLI entry point.

- Log file: `copymator.log` in the same directory as `settings.json`.
- Default level: `INFO`.
- Format: timestamp, level, message.

