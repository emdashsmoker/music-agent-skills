# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Audition sounds by measurement: render patches in isolation and describe each one in numbers.

An agent cannot listen, so this is how it learns that a patch is bright or dull, short or long,
loud or quiet before putting it in a song. One LMMS render covers any number of patches.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

from . import audio, render, sounds
from .project import Note, Project

SLOT_SECONDS = 4.0
AUDITION_BPM = 120.0
TEST_PITCH = {"kick": 60, "snare": 60, "clap": 60, "hat": 60, "cymbal": 60, "perc": 60, "fx": 60,
              "sub": 33, "bass": 33, "lead": 69, "pluck": 69, "pad": 57, "keys": 57, "vocal": 60, "vocal_bg": 60}
SUSTAIN_SECONDS = {"sub": 1.0, "bass": 1.0, "lead": 1.0, "pluck": 1.0, "pad": 2.0, "keys": 1.0}
ATTACK_FRACTION = 0.9
DECAY_DROP_DB = 20.0
SILENCE_FLOOR_DB = -60.0


def describe(x: np.ndarray, rate: int) -> dict:
    """Numbers that characterise one isolated sound."""
    start, end = audio.trim_silence(x, rate, SILENCE_FLOOR_DB)
    if end <= start:
        return {"silent": True}
    body = x[start:end]
    times, env = audio.envelope_db(body, rate, 0.002)
    peak_index = int(np.argmax(env))
    peak = float(env[peak_index])
    reach = np.flatnonzero(env >= peak + 20 * np.log10(ATTACK_FRACTION))
    after = np.flatnonzero(env[peak_index:] <= peak - DECAY_DROP_DB)
    freqs, power = audio.spectrum(body, rate, 16384)
    audible = freqs >= 25
    return {
        "silent": False, "peak_db": round(audio.sample_peak_db(body), 1), "loudness": round(audio.peak_loudness(body, rate), 1),
        "length_s": round((end - start) / rate, 3), "attack_ms": round(float(times[reach[0]]) * 1000, 1) if len(reach) else 0.0,
        "decay20_ms": round(float(times[peak_index + after[0]] - times[peak_index]) * 1000) if len(after) else None,
        "centroid_hz": round(audio.spectral_centroid(body, rate)), "rolloff_hz": round(audio.spectral_rolloff(body, rate)), "strongest_hz": round(float(freqs[audible][np.argmax(power[audible])]), 1),
        "width": round(audio.stereo_width(body), 2), "bands_db": {k: round(v, 1) for k, v in audio.band_levels(body, rate).items()},
    }


def brightness_word(centroid_hz: float) -> str:
    """Plain-language label for the spectral centroid of a pitched or noisy sound."""
    return "dark" if centroid_hz < 700 else "warm" if centroid_hz < 1800 else "balanced" if centroid_hz < 3500 else "bright" if centroid_hz < 7000 else "very bright"


def profile(patches: dict[str, dict | str], out_dir: str | None = None, pitch: int | None = None) -> dict[str, dict]:
    """Render every patch alone (one slot each) and return {name: description}. Keeps the WAV if out_dir is given."""
    project = Project.new(bpm=AUDITION_BPM)
    slot_beats = SLOT_SECONDS * AUDITION_BPM / 60.0
    resolved = {}
    for index, (name, patch) in enumerate(patches.items()):
        patch = sounds.get(patch) if isinstance(patch, str) else patch
        resolved[name] = patch
        track = sounds.add(project, name, patch)
        role = patch.get("role", "lead")
        length_seconds = patch.get("gate_s", SUSTAIN_SECONDS.get(role, 1.0))
        track.add_pattern(index * slot_beats, [Note(0.0, length_seconds * AUDITION_BPM / 60.0, pitch or TEST_PITCH.get(role, 60))])
    project.set_length(len(patches) * slot_beats)
    with tempfile.TemporaryDirectory() as scratch:
        folder = out_dir or scratch
        os.makedirs(folder, exist_ok=True)
        project.save(os.path.join(folder, "audition.mmp"))
        sounds.install_kit(project, os.path.join(folder, "audition.mmp"))
        x, rate = audio.load(render.render(os.path.join(folder, "audition.mmp"), os.path.join(folder, "audition.wav")))
    result = {}
    for index, name in enumerate(resolved):
        slot = x[int(index * SLOT_SECONDS * rate):int((index + 1) * SLOT_SECONDS * rate)]
        result[name] = {"role": resolved[name].get("role", "?"), **describe(slot, rate)}
        if not result[name]["silent"]:
            result[name]["character"] = brightness_word(result[name]["centroid_hz"])
    return result


def table(result: dict[str, dict]) -> str:
    lines = ["name                 role    peak  loud   len_s  att_ms dec20  centroid  strongest  width  character"]
    for name, d in result.items():
        if d.get("silent"):
            lines.append(f"{name:20s} {d['role']:7s} SILENT")
            continue
        lines.append(f"{name:20s} {d['role']:7s} {d['peak_db']:5.1f} {d['loudness']:6.1f} {d['length_s']:6.2f} {d['attack_ms']:6.1f} "
                     f"{str(d['decay20_ms']):>5s} {d['centroid_hz']:8d} {d['strongest_hz']:9.1f} {d['width']:6.2f}  {d['character']}")
    return "\n".join(lines)
