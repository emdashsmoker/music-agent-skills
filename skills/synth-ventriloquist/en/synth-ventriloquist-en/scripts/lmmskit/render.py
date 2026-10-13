# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Run LMMS headless: locate the binary, render a project or its stems, convert the result.

LMMS does the synthesis and mixing, so what is rendered here is exactly what a person hears
after opening the same .mmp in the LMMS editor.
"""
from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from . import settings

SAMPLE_RATE = 44100
TESTED_LMMS_SERIES = "1.2."                     # the project format and command line this toolkit was written against
_CORE_COUNTER, _CORE_LOCK = itertools.count(), threading.Lock()
SAMPLES_SUBDIR = "samples"                      # LMMS resolves relative sample paths under <workingdir>/samples
SCRATCH_PREFIX = "lmmskit-render-"
CODEC_ARGS = {".ogg": ["-c:a", "libvorbis", "-q:a", "6"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
              ".flac": ["-c:a", "flac"], ".wav": ["-c:a", "pcm_s16le"]}


class LmmsNotFound(RuntimeError):
    pass


def launcher() -> dict:
    """The way LMMS is started here: {"command": [...], "source": ..., "sandbox": None | "flatpak" | "snap"}."""
    candidates = settings.lmms_candidates()
    if not candidates:
        raise LmmsNotFound("LMMS was not found in the settings, on the PATH, in the usual folders or as a Flatpak. "
                           "Run `lmms_tool.py doctor` for what this machine offers, then see references/setup.md.")
    return candidates[0]


def find_lmms() -> str:
    """The LMMS launcher as one printable string."""
    return " ".join(part for part in launcher()["command"] if part != settings.GRANTS_TOKEN)


def find_data_dir() -> str | None:
    """Folder holding LMMS factory samples and presets, when it can be seen from here (not inside an AppImage or Flatpak)."""
    try:
        binary = launcher()["command"][0]
    except LmmsNotFound:
        binary = None
    for candidate in settings.data_dir_candidates(binary):
        if os.path.isdir(os.path.join(candidate, "samples")):
            return candidate
    return None


def lmms_version() -> str:
    try:
        output = subprocess.run(_base_command([]) + ["--version"], capture_output=True, text=True, env=_environment(),
                                timeout=settings.DISCOVERY_TIMEOUT_S * 4).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return f"could not be started: {error}"
    return output.splitlines()[0].strip() if output else "unknown"


def version_is_tested(version: str) -> bool:
    return TESTED_LMMS_SERIES in version


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def can_pin() -> bool:
    """Whether LMMS is restricted to one CPU core here (needed for bit-identical renders, see _one_core_prefix)."""
    wanted = str(settings.get("pin_cpu")).lower()
    return wanted not in ("off", "false", "0", "no") and hasattr(os, "sched_setaffinity")


def _one_core_prefix() -> list[str]:
    """Command prefix that starts LMMS restricted to one CPU core (a different core for each concurrent render).

    Some LMMS behaviour depends on the timing between its threads: in tests, several Kicker tracks sharing the
    noise source rendered differently from run to run on several cores and identically on one, and automation of
    instrument knobs differed far less often on one core. Where the operating system offers no way to set this, LMMS runs unrestricted.
    """
    if not can_pin():
        return []
    cores = sorted(os.sched_getaffinity(0))
    with _CORE_LOCK:
        core = cores[next(_CORE_COUNTER) % len(cores)]
    trampoline = f"import os, sys; os.sched_setaffinity(0, {{{core}}}); os.execv(sys.argv[1], sys.argv[1:])"
    return [sys.executable, "-c", trampoline]


def _base_command(visible_dirs: list[str]) -> list[str]:
    """The LMMS command up to its own arguments. visible_dirs are the folders a sandboxed LMMS must be allowed to use."""
    start = launcher()
    grants = [f"--filesystem={os.path.abspath(d)}" for d in dict.fromkeys(visible_dirs)] if start["sandbox"] == "flatpak" else []
    command = []
    for part in start["command"]:
        command += grants if part == settings.GRANTS_TOKEN else [part]
    command[0] = shutil.which(command[0]) or command[0]          # the one-core prefix needs a full path to start
    # Containers usually run as root, which LMMS refuses without the flag.
    return _one_core_prefix() + command + (["--allowroot"] if _is_root() else [])


def _environment() -> dict:
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", settings.get("qt_platform"))      # render without opening a window
    return environment


def _working_dir(project_dir: str, folder: str) -> str:
    """LMMS working directory for one render: a scratch folder whose 'samples' entry points at the project's samples.

    LMMS creates its standard subfolders (projects, presets, plugins ...) inside the working directory on start,
    so pointing it at the project folder itself would litter the user's folder. Where links cannot be made the
    project folder is used after all.
    """
    samples = os.path.join(os.path.abspath(project_dir), SAMPLES_SUBDIR)
    working = os.path.join(folder, "work")
    os.makedirs(working, exist_ok=True)
    if os.path.isdir(samples):
        try:
            os.symlink(samples, os.path.join(working, SAMPLES_SUBDIR), target_is_directory=True)
        except OSError:
            return os.path.abspath(project_dir)
    return working


def _write_config(project_dir: str, folder: str) -> str:
    """Config that makes <project_dir>/samples the user sample folder, so relative sample paths resolve.

    LMMS is started with this file through its -c option, so the user's own LMMS configuration is never read or changed.
    """
    as_lmms_path = lambda path: path.replace(os.sep, "/").rstrip("/") + "/"
    working = as_lmms_path(_working_dir(project_dir, folder))
    scratch = as_lmms_path(os.path.join(folder, "unused"))
    path = os.path.join(folder, "lmmsrc.xml")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0"?>\n<!DOCTYPE lmms-config-file>\n<lmms version="1.2.2">\n'
                     f'  <paths workingdir="{working}" sf2dir="{scratch}sf2/" gigdir="{scratch}gig/" '
                     f'vstdir="{scratch}vst/" laddir="{scratch}ladspa/" artwork="data:/themes/default/" '
                     'backgroundartwork="" defaultsf2=""/>\n</lmms>\n')
    return path


def _run(action: str, project_path: str, output: str, oversampling: int, loop: bool) -> None:
    project_path = os.path.abspath(project_path)
    project_dir = os.path.dirname(project_path)
    output_dir = output if action == "rendertracks" else os.path.dirname(output)
    scratch_root = settings.scratch_root(project_dir, launcher()["sandbox"] is not None)
    with tempfile.TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=scratch_root) as folder:
        command = _base_command([project_dir, output_dir, folder]) + ["-c", _write_config(project_dir, folder), action, project_path,
                                                                      "-f", "wav", "-s", str(SAMPLE_RATE), "-x", str(oversampling), "-o", output]
        if loop:
            command.append("-l")
        result = subprocess.run(command, capture_output=True, text=True, env=_environment(), timeout=int(settings.get("render_timeout_s")))
    if result.returncode != 0:
        raise RuntimeError(f"LMMS {action} failed ({result.returncode}): {result.stderr[-800:]}")


def render(project_path: str, wav_path: str, *, oversampling: int = 2, loop: bool = False) -> str:
    """Render the whole song to a 16-bit stereo WAV."""
    os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)
    _run("render", project_path, os.path.abspath(wav_path), oversampling, loop)
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
        raise RuntimeError("LMMS produced no audio; open the project in LMMS to see what fails to load")
    return wav_path


def render_stems(project_path: str, out_dir: str, *, oversampling: int = 1) -> list[str]:
    """Render each track alone (through its mixer channel and the master chain) into out_dir."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    _run("rendertracks", project_path, out_dir, oversampling, False)
    return sorted(os.path.join(out_dir, name) for name in os.listdir(out_dir) if name.endswith(".wav"))


def convert(source: str, target: str, *, gain_db: float = 0.0, metadata: dict | None = None) -> str:
    """Transcode with ffmpeg; the target extension picks the codec (.ogg, .mp3, .flac, .wav)."""
    extension = os.path.splitext(target)[1].lower()
    if extension not in CODEC_ARGS:
        raise ValueError(f"unsupported target format {extension}; use one of {sorted(CODEC_ARGS)}")
    ffmpeg = settings.ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found: WAV output still works. See references/setup.md for ways to get it")
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", source]
    if gain_db:
        command += ["-af", f"volume={gain_db:.3f}dB"]
    for key, value in (metadata or {}).items():
        command += ["-metadata", f"{key}={value}"]
    command += ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"] + CODEC_ARGS[extension] + [target]
    subprocess.run(command, check=True)
    return target
