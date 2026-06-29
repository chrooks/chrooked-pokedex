"""Open a native OS folder picker and return the chosen absolute path.

A localhost convenience for the Target add form. A browser can't hand the
server a real filesystem path (the File System Access API only yields opaque
handles), but the server reads game files by absolute path — so the server pops
the OS dialog itself and returns the path the user picks.

Host-aware: WSL drives a Windows dialog and translates the path back to the
``/mnt`` mount the server actually reads; macOS uses ``osascript``; other Linux
uses ``zenity`` when present. Anything else raises :class:`PickerUnavailable`
and the form falls back to typing the path by hand.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# The folder dialog is modal and user-driven; give them generous time to browse.
_DIALOG_TIMEOUT_S = 600


class PickerUnavailable(RuntimeError):
    """No native folder picker is available (or usable) on this host."""


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def _pick_wsl() -> str | None:
    """Windows FolderBrowserDialog → translate the Windows path to its /mnt path.

    A throwaway top-most owner form pulls the dialog in front of the browser
    instead of letting it open behind. Returns None when the user cancels.
    """
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$o = New-Object System.Windows.Forms.Form;"
        "$o.TopMost = $true;"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description = 'Select the game directory';"
        "if ($d.ShowDialog($o) -eq [System.Windows.Forms.DialogResult]::OK)"
        " { [Console]::Out.Write($d.SelectedPath) };"
        "$o.Dispose()"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=_DIALOG_TIMEOUT_S,
    )
    windows_path = result.stdout.strip()
    if not windows_path:
        return None  # cancelled
    # D:\Games\... → /mnt/d/Games/... (the path the WSL-side server can read).
    conv = subprocess.run(
        ["wslpath", "-u", windows_path], capture_output=True, text=True
    )
    return conv.stdout.strip() or None


def _pick_macos() -> str | None:
    script = 'POSIX path of (choose folder with prompt "Select the game directory")'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=_DIALOG_TIMEOUT_S,
    )
    if result.returncode != 0:
        return None  # cancelled (osascript exits non-zero on "User canceled")
    return result.stdout.strip() or None


def _pick_zenity() -> str | None:
    result = subprocess.run(
        [
            "zenity",
            "--file-selection",
            "--directory",
            "--title=Select the game directory",
        ],
        capture_output=True,
        text=True,
        timeout=_DIALOG_TIMEOUT_S,
    )
    if result.returncode != 0:
        return None  # cancelled
    return result.stdout.strip() or None


def pick_directory() -> str | None:
    """Open the host's native folder picker; return the path, or None if cancelled.

    Raises :class:`PickerUnavailable` when no picker can be driven on this host.
    """
    try:
        if _is_wsl():
            return _pick_wsl()
        if sys.platform == "darwin":
            return _pick_macos()
        if shutil.which("zenity"):
            return _pick_zenity()
    except (subprocess.SubprocessError, OSError) as error:
        raise PickerUnavailable(f"the folder picker failed to run: {error}") from error
    raise PickerUnavailable(
        "no native folder picker on this host — type the path instead"
    )
