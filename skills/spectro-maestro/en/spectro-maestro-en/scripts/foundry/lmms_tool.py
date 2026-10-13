# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Finding and running LMMS, which is an optional outside program: exports work without it, and it is only
needed to open an exported project or to re-render one as a check.

LMMS ships in many forms (distribution package, Flatpak, Snap, AppImage, macOS app, Windows installer), so nothing
here assumes one of them. The configured command wins; otherwise the usual places of each form are looked at."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

from . import settings

FLATPAK_ID = "io.lmms.LMMS"
RENDER_TIMEOUT_S = 1800


def _flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    try:
        return subprocess.run(["flatpak", "info", FLATPAK_ID], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find() -> tuple:
    """(command as a list, how it was found) or (None, None)."""
    configured = settings.command("lmms")
    if configured:
        return configured, settings.lookup("lmms")[1]
    on_path = shutil.which("lmms")
    if on_path:
        return [on_path], "found on PATH"
    if _flatpak_installed():
        return ["flatpak", "run", FLATPAK_ID], "Flatpak"
    places = []
    if sys.platform == "darwin":
        places = ["/Applications/LMMS.app/Contents/MacOS/lmms", os.path.expanduser("~/Applications/LMMS.app/Contents/MacOS/lmms")]
    elif os.name == "nt":
        places = [os.path.join(os.environ.get(name, ""), "LMMS", "lmms.exe") for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
                  if os.environ.get(name)]
    else:
        tools = os.path.join(settings.cache_dir(), "tools")       # where an AppImage fetched for this toolkit is kept
        places = sorted(glob.glob(os.path.join(tools, "lmms*.AppImage")), reverse=True) + ["/snap/bin/lmms"]
    for place in places:
        if os.path.isfile(place):
            return [place], "found at its usual place"
    return None, None


def _environment(command: list) -> dict:
    env = dict(os.environ)
    if command[0].lower().endswith(".appimage"):
        env.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")           # containers have no FUSE to mount the image with
    headless = sys.platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))
    if headless:
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def render(project_path: str, wav_path: str) -> str:
    """Let LMMS render a project to a WAV file. Raises RuntimeError with LMMS's own words when it fails."""
    command, _how = find()
    if not command:
        raise FileNotFoundError("LMMS was not found")
    project_path, wav_path = os.path.abspath(project_path), os.path.abspath(wav_path)
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    if command[:2] == ["flatpak", "run"]:                          # the sandbox sees only folders it is given
        folders = {os.path.dirname(project_path), os.path.dirname(wav_path)}
        command = command[:2] + [f"--filesystem={folder}" for folder in sorted(folders)] + command[2:]
    extra = ["--allowroot"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []      # LMMS refuses to run as root otherwise
    full = command + extra + ["render", project_path, "-f", "wav", "-o", wav_path]
    if os.path.exists(wav_path):
        os.remove(wav_path)
    try:
        done = subprocess.run(full, capture_output=True, text=True, errors="replace", env=_environment(command),
                              timeout=RENDER_TIMEOUT_S)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"LMMS did not finish within {RENDER_TIMEOUT_S} s") from error
    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        tail = "\n".join((done.stdout + "\n" + done.stderr).strip().splitlines()[-8:])
        raise RuntimeError(f"LMMS wrote no audio (exit code {done.returncode}). Command: {' '.join(full)}\n{tail}")
    return wav_path


def check(project_path: str, wav_path: str, expected_seconds: float | None = None) -> dict:
    """Render through LMMS and measure the result: length, peak and clipped samples."""
    import numpy as np
    import soundfile as sf
    render(project_path, wav_path)
    audio, rate = sf.read(wav_path)
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    report = {"wav": wav_path, "seconds": round(len(audio) / rate, 1),
              "peak_dbfs": round(20 * np.log10(peak + 1e-12), 1), "clipped_samples": int(np.sum(np.abs(audio) >= 0.999))}
    if expected_seconds:
        report["song_seconds"] = round(expected_seconds, 1)
    return report
