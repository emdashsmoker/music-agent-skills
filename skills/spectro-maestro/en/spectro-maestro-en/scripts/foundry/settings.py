# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Where things live and which external tools to use, decided per machine instead of written into the code.

Every setting is looked up in this order and the first hit wins:
  1. a command-line option of the running command (--models, --config ...)
  2. an environment variable SPECTRO_MAESTRO_<NAME>
  3. a JSON config file: the one named by --config or SPECTRO_MAESTRO_CONFIG, else ./spectro-maestro.json,
     else <user config folder>/spectro-maestro/config.json
  4. a default that follows the conventions of the operating system

This module uses the standard library only, so `studio.py doctor` works before any package is installed."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import tempfile

APP = "spectro-maestro"
ENV_PREFIX = "SPECTRO_MAESTRO_"
CONFIG_NAME = "spectro-maestro.json"

# name -> (default, what it is)
SETTINGS = {
    "cache_dir": (None, "folder for caches this toolkit may rebuild at any time (compiled filter kernel, tools)"),
    "models_dir": (None, "folder for downloaded voice and recognition models (default: <cache_dir>/models)"),
    "offline": (False, "true = never download anything; missing models are reported with the path to put them at"),
    "download_timeout_s": (60, "seconds to wait for a download server before giving up"),
    "native": ("auto", "auto = compile the fast filter kernel when a C compiler exists; off = always use the slower path"),
    "compiler": (None, "C compiler command (default: cc, gcc or clang found on PATH)"),
    "ffmpeg": (None, "ffmpeg command, used for mp3 only when the audio library cannot write mp3 itself"),
    "lmms": (None, "command that starts LMMS, e.g. a path to an AppImage or 'flatpak run io.lmms.LMMS' (optional tool)"),
    "asr_model": ("base.en", "faster-whisper model for vocal checks; 'base' or 'small' for languages other than English"),
}
TRUE_WORDS = ("1", "true", "yes", "on")
FALSE_WORDS = ("0", "false", "no", "off", "")

_overrides: dict = {}
_config: dict | None = None
_config_path: str | None = None


class SettingsError(ValueError):
    pass


def user_dir(kind: str) -> str:
    """Per-user 'cache' or 'config' folder of this toolkit, by the convention of the operating system."""
    home = os.path.expanduser("~")
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA" if kind == "cache" else "APPDATA") or os.path.join(home, "AppData", "Local" if kind == "cache" else "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Caches" if kind == "cache" else "Application Support")
    else:
        base = os.environ.get("XDG_CACHE_HOME" if kind == "cache" else "XDG_CONFIG_HOME") or os.path.join(home, ".cache" if kind == "cache" else ".config")
    return os.path.join(base, APP)


def config_candidates() -> list:
    named = _overrides.get("config") or os.environ.get(ENV_PREFIX + "CONFIG")
    if named:
        return [os.path.abspath(os.path.expanduser(named))]
    return [os.path.abspath(CONFIG_NAME), os.path.join(user_dir("config"), "config.json")]


def _load_config() -> dict:
    global _config, _config_path
    if _config is not None:
        return _config
    _config, _config_path = {}, None
    named = _overrides.get("config") or os.environ.get(ENV_PREFIX + "CONFIG")
    for path in config_candidates():
        if not os.path.isfile(path):
            if named:
                raise SettingsError(f"config file not found: {path}")
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise SettingsError(f"config file {path} cannot be read: {error}") from error
        if not isinstance(data, dict):
            raise SettingsError(f"config file {path} must hold one JSON object of settings")
        unknown = sorted(set(data) - set(SETTINGS))
        if unknown:
            raise SettingsError(f"config file {path}: unknown settings {unknown}; known: {sorted(SETTINGS)}")
        _config, _config_path = data, path
        break
    return _config


def override(name: str, value) -> None:
    """A command-line option of the running command; None leaves the setting alone."""
    global _config
    if value is None:
        return
    _overrides[name] = value
    if name == "config":
        _config = None


def lookup(name: str) -> tuple:
    """(value, where it came from)."""
    if name in _overrides:
        return _overrides[name], "command line"
    env = os.environ.get(ENV_PREFIX + name.upper())
    if env is not None and env != "":
        return env, f"environment variable {ENV_PREFIX}{name.upper()}"
    config = _load_config()
    if name in config and config[name] is not None:
        return config[name], f"config file {_config_path}"
    return SETTINGS[name][0], "default"


def get(name: str):
    value = lookup(name)[0]
    default = SETTINGS[name][0]
    if isinstance(default, bool):
        if isinstance(value, str):
            if value.strip().lower() not in TRUE_WORDS + FALSE_WORDS:
                raise SettingsError(f"setting {name}: {value!r} is not true or false")
            return value.strip().lower() in TRUE_WORDS
        return bool(value)
    if isinstance(default, int) and value is not None:
        return int(value)
    return value


def _writable_dir(path: str, fallback_name: str) -> str:
    """The folder, created. A home folder that cannot be written (read-only sandboxes) falls back to the temp folder."""
    path = os.path.abspath(os.path.expanduser(str(path)))
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        fallback = os.path.join(tempfile.gettempdir(), APP, fallback_name)
        os.makedirs(fallback, exist_ok=True)
        print(f"[settings] {path} cannot be created; using {fallback}", file=sys.stderr)
        return fallback


def cache_dir() -> str:
    return _writable_dir(get("cache_dir") or user_dir("cache"), "cache")


def models_dir() -> str:
    chosen = get("models_dir")
    return _writable_dir(chosen, "models") if chosen else _writable_dir(os.path.join(get("cache_dir") or user_dir("cache"), "models"), "models")


def command(name: str, fallbacks: tuple = ()) -> list | None:
    """An external tool as an argument list: the configured command (which may carry arguments, such as
    'flatpak run io.lmms.LMMS'), else the first of `fallbacks` found on PATH, else None."""
    configured = get(name)
    if configured:
        text = os.path.expanduser(str(configured))
        if os.path.isfile(text):                         # a plain path, possibly with spaces in it
            return [text]
        parts = shlex.split(text, posix=os.name != "nt")
        if parts and (shutil.which(parts[0]) or os.path.isfile(parts[0])):
            return parts
        raise SettingsError(f"setting {name}: {configured!r} is not a program that can be started here")
    for candidate in fallbacks:
        found = shutil.which(candidate)
        if found:
            return [found]
    return None


def describe() -> list:
    """[(name, value, source, meaning)] for the environment report."""
    rows = []
    for name, (_default, meaning) in SETTINGS.items():
        value, source = lookup(name)
        if name == "cache_dir" and value is None:
            value = user_dir("cache")
        if name == "models_dir" and value is None:
            value = os.path.join(lookup("cache_dir")[0] or user_dir("cache"), "models")
        rows.append((name, value, source, meaning))
    return rows
