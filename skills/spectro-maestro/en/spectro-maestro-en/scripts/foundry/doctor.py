# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Environment report: what kind of machine this is, which parts of the toolkit can run here, what is missing,
and where files would go. It only looks; it installs, downloads and changes nothing.

Standard library only, so it runs before any package is installed."""
from __future__ import annotations

import importlib
import os
import platform
import shutil
import sys
import sysconfig

from . import settings

# (import name, package to install, what stops working without it)
CORE = [
    ("numpy", "numpy", "everything"),
    ("scipy", "scipy", "everything"),
    ("yaml", "PyYAML", "reading song files"),
    ("soundfile", "soundfile", "writing audio"),
    ("mido", "mido", "MIDI export and import"),
    ("matplotlib", "matplotlib", "QA pictures"),
]
VOCAL = [
    ("pyworld", "pyworld", "singing with speech voices, pitch pictures"),
    ("onnxruntime", "onnxruntime", "all vocal engines"),
    ("kokoro_onnx", "kokoro-onnx", "engine kokoro and its phonemiser"),
    ("piper", "piper-tts", "engine piper"),
    ("onnx", "onnx", "engine piper (exposing phone durations)"),
    ("faster_whisper", "faster-whisper", "vocal-check and vocal-try"),
    ("cmudict", "cmudict", "engine diffsinger: words missing from a voicebank dictionary"),
]
OPTIONAL = [
    ("lxml", "lxml", "schema check of DAWproject exports (export still works)"),
]
CONTAINER_MARKERS = ("/.dockerenv", "/run/.containerenv")
MIN_PYTHON = (3, 9)
MODEL_SPACE_NOTE_GB = 1.0       # speech voice plus recognition model, roughly


def _status(module: str) -> tuple:
    try:
        found = importlib.import_module(module)
        return True, getattr(found, "__version__", "")
    except Exception as error:                          # a broken install is reported like a missing one
        return False, f"{type(error).__name__}: {error}"


def python_environment() -> dict:
    """Facts that decide how packages may be installed here without harming the machine."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    in_conda = bool(os.environ.get("CONDA_PREFIX")) and sys.prefix.startswith(os.environ.get("CONDA_PREFIX", "\0"))
    marker = os.path.join(sysconfig.get_path("stdlib") or "", "EXTERNALLY-MANAGED")
    return {"isolated": in_venv or in_conda, "kind": "virtual environment" if in_venv else "conda environment" if in_conda else "system-wide Python",
            "os_managed": os.path.isfile(marker) and not in_venv,
            "container": any(os.path.exists(path) for path in CONTAINER_MARKERS) or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))}


def _free_gb(path: str) -> float | None:
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return None


def _install_advice(env: dict, files: list) -> list:
    install = " ".join(f'-r "{name}"' for name in files)
    lines = []
    if env["isolated"]:
        lines.append(f'install into this {env["kind"]}:  "{sys.executable}" -m pip install {install}')
    elif env["os_managed"]:
        lines.append("this Python belongs to the operating system and refuses plain pip installs.")
        lines.append(f'  on a personal machine: make an isolated environment first (python -m venv <folder>, conda, uv ...), then inside it:  python -m pip install {install}')
        lines.append("  in a throwaway container only: pip's --break-system-packages or --user is acceptable")
    else:
        lines.append(f'this is a system-wide Python. On a personal machine prefer an isolated environment (python -m venv <folder>, conda, uv ...); then:  python -m pip install {install}')
        lines.append(f'  in a throwaway container:  "{sys.executable}" -m pip install {install}')
    lines.append("  never needs administrator rights; do not use sudo for this")
    return lines


def run() -> int:
    env = python_environment()
    print(f"system  {platform.system()} {platform.release()} ({platform.machine()})" + ("  [container]" if env["container"] else ""))
    print(f"python  {sys.version.split()[0]}  {sys.executable}  [{env['kind']}" + (", managed by the OS" if env["os_managed"] else "") + "]")
    if sys.version_info < MIN_PYTHON:
        print(f"  PROBLEM this toolkit needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")
    missing = {"core": [], "vocal": []}
    for title, group, key in (("core (instrumental songs)", CORE, "core"), ("vocals (only for songs with a voice)", VOCAL, "vocal"), ("optional", OPTIONAL, None)):
        print(f"\n{title}")
        for module, package, purpose in group:
            ok, detail = _status(module)
            print(f"  {'ok     ' if ok else 'MISSING'} {package:16s} {detail if ok else '-> needed for ' + purpose}")
            if not ok and key:
                missing[key].append(package)

    print("\noutside tools (all optional)")
    problems = []
    try:
        mp3_native = "MP3" in importlib.import_module("soundfile").available_formats()
    except Exception:
        mp3_native = False
    tools = {}
    for name, fallbacks in (("ffmpeg", ("ffmpeg",)), ("compiler", ("cc", "gcc", "clang"))):
        try:
            tools[name] = settings.command(name, fallbacks)
        except settings.SettingsError as error:
            tools[name] = None
            problems.append(str(error))
    mp3 = "written by the audio library" if mp3_native else "through ffmpeg" if tools["ffmpeg"] else None
    print(f"  {'ok     ' if mp3 else 'absent '} mp3 export      {mp3 or 'not available here: install ffmpeg, or deliver ogg, flac or wav'}")
    native_off = str(settings.get("native")).lower() == "off"
    kernel = "switched off by the 'native' setting" if native_off else "fast filter kernel will be built into the cache folder" if tools["compiler"] else None
    print(f"  {'ok     ' if kernel and not native_off else 'absent '} C compiler      {kernel or 'none found: filters use the slower path, results are identical'}")
    print(f"  {'ok     ' if shutil.which('git') else 'absent '} git             only for voicebanks handed over as repository links")
    try:
        from . import lmms_tool
        lmms, how = lmms_tool.find()
    except settings.SettingsError as error:
        lmms, how = None, None
        problems.append(str(error))
    print(f"  {'ok     ' if lmms else 'absent '} LMMS            "
          f"{' '.join(lmms) + '  (' + how + ')' if lmms else 'not found: only needed to open or re-render an exported LMMS project'}")

    print("\nsettings (command line > environment variable SPECTRO_MAESTRO_<NAME> > config file > default)")
    try:
        for name, value, source, _meaning in settings.describe():
            print(f"  {name:19s} {"(not set)" if value is None else value!s:52s} [{source}]")
        print("  config files looked for: " + ", ".join(settings.config_candidates()))
        models = settings.lookup("models_dir")[0] or os.path.join(settings.lookup("cache_dir")[0] or settings.user_dir("cache"), "models")
        free = _free_gb(os.path.abspath(os.path.expanduser(str(models))))
        if free is not None:
            print(f"  free space at the models folder: {free:.1f} GB (voice and recognition models take about {MODEL_SPACE_NOTE_GB:.0f} GB, downloaded on first vocal use)")
    except settings.SettingsError as error:
        problems.append(str(error))
    for problem in problems:
        print(f"  PROBLEM {problem}")

    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = [os.path.join(here, name) for key, name in (("core", "requirements.txt"), ("vocal", "requirements-vocal.txt")) if missing[key]]
    print()
    if files:
        if missing["core"]:
            print("missing for instrumental songs: " + ", ".join(missing["core"]))
        if missing["vocal"]:
            print("missing for vocal songs only: " + ", ".join(missing["vocal"]))
        print("\n".join(_install_advice(env, files)))
    else:
        print("everything needed is installed")
    return 1 if missing["core"] or problems or sys.version_info < MIN_PYTHON else 0
