# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Settings and discovery: where LMMS, ffmpeg, caches and scratch space are on this machine.

Environments differ too much to hard-code (a distro package, an AppImage in the home folder, a Flatpak, a macOS
app bundle, a Windows installer, a throwaway container). Every value is therefore looked up in this order:

1. an environment variable (good for containers and one-off runs),
2. a settings file (good for a desktop that keeps its setup),
3. discovery on the machine.

Nothing in this module installs, moves or deletes anything. The only file it ever writes is the settings file,
and only when save() is called (the `configure` command).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

SETTINGS_ENV = "LMMSKIT_CONFIG"                 # path of a settings file to use instead of the standard places
PROJECT_SETTINGS_NAME = "lmmskit.json"          # a settings file in the current folder wins over the user's
APP_NAME = "lmmskit"
GRANTS_TOKEN = "{grants}"                       # in an LMMS command: replaced by the sandbox's folder permissions
DISCOVERY_TIMEOUT_S = 15

# key: (environment variable, default, what it is)
KEYS = {
    "lmms_command": ("LMMS_BIN", None, "LMMS launcher: a path, or a command as a list such as "
                                       '["flatpak", "run", "--command=lmms", "{grants}", "<app id>"]'),
    "lmms_data_dir": ("LMMS_DATA_DIR", None, "folder with the LMMS factory samples/ and presets/"),
    "ffmpeg": ("LMMSKIT_FFMPEG", None, "path of the ffmpeg binary"),
    "cache_dir": ("LMMSKIT_CACHE", None, "where downloaded speech models and vocal caches are kept"),
    "kit_dir": ("LMMSKIT_KIT_DIR", None, "where the drum kit made on this machine is kept (default: <cache_dir>/kit)"),
    "scratch_dir": ("LMMSKIT_SCRATCH", None, "where temporary render folders are made (default: beside the project "
                                             "for a sandboxed LMMS, else the system temp folder)"),
    "pin_cpu": ("LMMSKIT_PIN_CPU", "auto", "hold each LMMS process to one CPU core: auto, on or off"),
    "stem_workers": ("LMMSKIT_STEM_WORKERS", 0, "parallel LMMS renders for stems (0 = one per CPU core)"),
    "render_timeout_s": ("LMMSKIT_RENDER_TIMEOUT", 3600, "longest a single LMMS render may take, in seconds"),
    "qt_platform": ("QT_QPA_PLATFORM", "offscreen", "Qt platform plugin LMMS starts with when rendering"),
    "asr_model": ("LMMSKIT_ASR_MODEL", None, "faster-whisper model for the vocal checks (default base.en); an English-only "
                                            "model (.en) switches to its multilingual twin for lyrics in other languages"),
    "kokoro_revision": ("LMMSKIT_KOKORO_REVISION", None, "Hugging Face revision of the Kokoro model and voices: a commit id, or "
                                                        "main for the newest (default: the tested commit)"),
    "figure_fonts": ("LMMSKIT_FONTS", ["NanumGothic", "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic", "DejaVu Sans"],
                     "font families tried in order for the review figures"),
}
LMMS_NAMES = ("lmms", "lmms.exe")
APPIMAGE_PATTERNS = ("*[Ll][Mm][Mm][Ss]*.[Aa]pp[Ii]mage", os.path.join("squashfs-root", "AppRun"))
PACKAGE_MANAGERS = ("apt-get", "dnf", "yum", "zypper", "pacman", "apk", "xbps-install", "emerge", "nix-env", "flatpak", "snap",
                    "brew", "port", "winget", "choco", "scoop", "conda", "mamba", "uv", "pipx")


# -- places ---------------------------------------------------------------------------------------------
def _home() -> str:
    return os.path.expanduser("~")


def user_config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(_home(), "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(_home(), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_home(), ".config")
    return os.path.join(base, APP_NAME)


def user_cache_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(_home(), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(_home(), "Library", "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(_home(), ".cache")
    return os.path.join(base, APP_NAME)


def settings_files() -> list[str]:
    """Settings files in the order they are read: later ones override earlier ones."""
    files = [os.path.join(user_config_dir(), "config.json"), os.path.abspath(PROJECT_SETTINGS_NAME)]
    if os.environ.get(SETTINGS_ENV):
        files.append(os.environ[SETTINGS_ENV])
    return files


def _stored() -> dict:
    merged = {}
    for path in settings_files():
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                merged.update(json.load(handle))
    return merged


def _typed(key: str, text: str):
    """An environment variable or command-line value as the type of the key's default."""
    default = KEYS[key][1]
    if key == "lmms_command":
        return json.loads(text) if text.strip().startswith("[") else text
    if isinstance(default, list):
        return [part.strip() for part in text.split(",") if part.strip()]
    if isinstance(default, int):
        return int(text)
    return text


def get(key: str):
    variable, default, _ = KEYS[key]
    if os.environ.get(variable):
        return _typed(key, os.environ[variable])
    return _stored().get(key, default)


def save(values: dict, path: str | None = None) -> str:
    """Merge values into a settings file (default: the user's). A value of None removes the key."""
    unknown = set(values) - set(KEYS)
    if unknown:
        raise KeyError(f"unknown setting(s) {sorted(unknown)}; known: {sorted(KEYS)}")
    path = path or settings_files()[0]
    current = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            current = json.load(handle)
    for key, value in values.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=1, ensure_ascii=False)
    return path


# -- LMMS -----------------------------------------------------------------------------------------------
def _search_dirs() -> list[str]:
    """Folders where people keep an LMMS that is not on the PATH (AppImages, app bundles, installers)."""
    home = _home()
    dirs = [os.getcwd(), os.path.join(home, "Applications"), os.path.join(home, "AppImages"), os.path.join(home, ".local", "bin"),
            os.path.join(home, "bin"), os.path.join(home, "Downloads"), os.path.join(home, "Desktop"), "/opt", "/usr/local/bin"]
    if sys.platform == "darwin":
        dirs += ["/Applications/LMMS.app/Contents/MacOS", os.path.join(home, "Applications", "LMMS.app", "Contents", "MacOS")]
    if sys.platform == "win32":
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
            if os.environ.get(variable):
                dirs += [os.path.join(os.environ[variable], "LMMS"), os.path.join(os.environ[variable], "Programs", "LMMS")]
    return [d for d in dict.fromkeys(dirs) if os.path.isdir(d)]


def _flatpak_apps() -> list[str]:
    """Installed Flatpak application ids that look like LMMS."""
    if not shutil.which("flatpak"):
        return []
    try:
        listing = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True,
                                 timeout=DISCOVERY_TIMEOUT_S).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in listing.splitlines() if "lmms" in line.lower()]


def _sandbox_of(command: list[str]) -> str | None:
    """Launchers that hide most of the file system from LMMS, so render folders must be chosen with care."""
    first = os.path.basename(command[0]).lower()
    resolved = os.path.realpath(shutil.which(command[0]) or command[0])
    if first == "flatpak":
        return "flatpak"
    if first == "snap" or "/snap/" in resolved.replace(os.sep, "/") or os.path.basename(resolved) == "snap":
        return "snap"
    return None


def _launcher(command: list[str], source: str) -> dict:
    return {"command": command, "source": source, "sandbox": _sandbox_of(command)}


def lmms_candidates() -> list[dict]:
    """Every way to start LMMS that was found, best first: settings, PATH, known folders, Flatpak."""
    found = []
    configured = get("lmms_command")
    if configured:
        command = configured if isinstance(configured, list) else [configured]
        if shutil.which(command[0]) or os.path.exists(command[0]):
            found.append(_launcher(command, "settings"))
    for name in LMMS_NAMES:
        if shutil.which(name):
            found.append(_launcher([shutil.which(name)], "PATH"))
    for folder in _search_dirs():
        for pattern in LMMS_NAMES + APPIMAGE_PATTERNS:
            for path in sorted(glob.glob(os.path.join(folder, pattern)), reverse=True):          # newest version name first
                if os.path.isfile(path):
                    found.append(_launcher([path], "AppImage" if "app" in os.path.basename(path).lower() else "folder"))
    for app in _flatpak_apps():
        found.append(_launcher(["flatpak", "run", "--command=lmms", GRANTS_TOKEN, app], "Flatpak"))
    unique = {}
    for launcher in found:
        unique.setdefault(tuple(launcher["command"]), launcher)
    return list(unique.values())


def data_dir_candidates(lmms_path: str | None) -> list[str]:
    """Places where the LMMS factory samples and presets may be: settings, beside the binary, standard prefixes."""
    places = [get("lmms_data_dir")]
    if lmms_path and os.path.isabs(lmms_path):
        folder = os.path.dirname(os.path.realpath(lmms_path))
        places += [os.path.join(folder, "data"), os.path.join(folder, "..", "share", "lmms"), os.path.join(folder, "usr", "share", "lmms")]
    places += ["/usr/share/lmms", "/usr/local/share/lmms", "/opt/homebrew/share/lmms", "/Applications/LMMS.app/Contents/share/lmms"]
    return [os.path.normpath(p) for p in places if p]


# -- other tools ----------------------------------------------------------------------------------------
def ffmpeg_path() -> str | None:
    """ffmpeg from the settings, the PATH, or the imageio-ffmpeg Python package (a way to get it without admin rights)."""
    configured = get("ffmpeg")
    if configured and (shutil.which(configured) or os.path.exists(configured)):
        return shutil.which(configured) or configured
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:          # not installed, or it ships no binary for this platform
        return None


def cache_dir() -> str:
    return get("cache_dir") or user_cache_dir()


def scratch_root(project_dir: str, sandboxed: bool) -> str | None:
    """Parent folder for temporary render folders. None means the system temp folder.

    A sandboxed LMMS (Flatpak, Snap) has its own private temp folder and cannot see the system one, so its
    scratch space goes beside the project, which the sandbox is given access to anyway.
    """
    return get("scratch_dir") or (project_dir if sandboxed else None)


def stem_workers() -> int:
    return int(get("stem_workers")) or os.cpu_count() or 1


# -- description of the machine, for the doctor ------------------------------------------------------------
def environment() -> dict:
    """Facts that decide how to install missing pieces. Read-only."""
    in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv") or bool(os.environ.get("container"))
    return {
        "os": sys.platform,
        "python": sys.version.split()[0],
        "isolated_python": sys.prefix != sys.base_prefix or bool(os.environ.get("CONDA_PREFIX")),
        "administrator": hasattr(os, "geteuid") and os.geteuid() == 0,
        "looks_like_container": in_container,
        "display": bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) or sys.platform in ("win32", "darwin"),
        "package_managers": [name for name in PACKAGE_MANAGERS if shutil.which(name)],
        "temp_dir": tempfile.gettempdir(),
        "settings_files": [path + ("" if os.path.isfile(path) else " (not present)") for path in settings_files()],
    }
