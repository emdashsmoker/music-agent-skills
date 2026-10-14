# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Bring outside material in: a MIDI file becomes a song spec that can be re-voiced, mixed and rendered.

The import is a starting sketch: pitches and rhythms are kept (quantised to a 1/48-beat grid, drums to
sixteenths), instruments and roles are guessed from register and must be reviewed."""
from __future__ import annotations

import numpy as np

from . import export, theory

GM_TO_DRUM = {35: "kick_909", 36: "kick_909", 37: "rim_808", 38: "snare_909", 39: "clap_909", 40: "snare_909",
              41: "tom_low", 42: "hat_closed_909", 43: "tom_low", 44: "hat_pedal", 45: "tom_mid", 46: "hat_open_909",
              47: "tom_mid", 48: "tom_high", 49: "crash_909", 50: "tom_high", 51: "ride_909", 54: "tambourine",
              56: "cowbell_808", 57: "crash_909", 70: "shaker", 75: "clave"}
DRUM_ROLE = {"kick": "kick", "snare": "snare", "clap": "snare", "hat": "hat", "ride": "hat", "crash": "perc"}
GRID = 48


def _beats(value: float) -> str:
    snapped = round(value * GRID) / GRID
    return f"{snapped:.4f}".rstrip("0").rstrip(".") or "0"


def _line(notes: list, total_beats: float) -> str:
    """Notes -> line notation. Notes starting together become a chord; a note is cut where the next one starts."""
    onsets = {}
    for start, dur, pitch, _velocity, _channel in notes:
        onsets.setdefault(round(start * GRID) / GRID, []).append((pitch, dur))
    tokens, cursor = [], 0.0
    ordered = sorted(onsets)
    for index, start in enumerate(ordered):
        if start - cursor > 1e-6:
            tokens.append(f"r:{_beats(start - cursor)}")
        limit = (ordered[index + 1] if index + 1 < len(ordered) else total_beats) - start
        length = max(1.0 / GRID, min(max(d for _, d in onsets[start]), limit))
        names = [theory.midi_to_name(p) for p, _ in sorted(onsets[start])]
        tokens.append((names[0] if len(names) == 1 else "[" + " ".join(names) + "]") + ":" + _beats(length))
        cursor = start + round(length * GRID) / GRID
    if total_beats - cursor > 1e-6:
        tokens.append(f"r:{_beats(total_beats - cursor)}")
    return " ".join(tokens)


def _hits(notes: list, bars: int, meter: float) -> str:
    steps = int(bars * meter * 4)
    cells = ["."] * steps
    for start, _dur, _pitch, velocity, _channel in notes:
        index = int(round(start * 4))
        if 0 <= index < steps:
            cells[index] = "X" if velocity > 0.9 else "o" if velocity < 0.45 else "x"
    per_bar = int(meter * 4)
    return "|".join("".join(cells[i:i + per_bar]) for i in range(0, steps, per_bar))


def _guess(notes: list) -> tuple:
    pitches = np.array([n[2] for n in notes])
    starts = np.array([n[0] for n in notes])
    chords = len(starts) - len(np.unique(np.round(starts * GRID))) > len(starts) * 0.2
    median = float(np.median(pitches))
    if median < 50:
        return "bass_moog", "bass"
    if chords:
        long_notes = float(np.median([n[1] for n in notes])) >= 2.0
        return ("pad_warm", "pad") if long_notes else ("chord_stab", "chord")
    return ("lead_saw", "lead") if median < 84 else ("pluck_saw", "pluck")


def midi_to_spec(path: str, bpm: float | None = None, key: str = "C major", meter: float = 4.0) -> dict:
    data = export.read_midi(path, bpm)
    bars = max(1, int(np.ceil(data["beats"] / meter - 1e-6)))
    total = bars * meter
    tracks, play = {}, {}
    for name, notes in data["tracks"].items():
        drums = [n for n in notes if n[4] == export.DRUM_CHANNEL]
        tonal = [n for n in notes if n[4] != export.DRUM_CHANNEL]
        if tonal:
            inst, role = _guess(tonal)
            tracks[name] = {"inst": inst, "role": role, "parts": {"all": {"line": _line(tonal, total), "gate": 1.0,
                                                                         "loop": False}}}
            play[name] = "all"
        by_key = {}
        for note in drums:
            by_key.setdefault(note[2], []).append(note)
        for gm_key, hits in sorted(by_key.items()):
            inst = GM_TO_DRUM.get(gm_key, "rim_808")
            role = next((r for word, r in DRUM_ROLE.items() if word in inst), "perc")
            drum_name = f"{name}_{inst}" if f"{name}_{inst}" not in tracks else f"{name}_{inst}_{gm_key}"
            tracks[drum_name] = {"inst": inst, "role": role, "parts": {"all": {"hits": _hits(hits, bars, meter), "loop": False}}}
            play[drum_name] = "all"
    return {"title": "Imported MIDI", "genre": "", "bpm": data["bpm"], "key": key, "meter": meter, "seed": 1,
            "humanize": {"velocity": 0.0}, "tracks": tracks,
            "sections": [{"name": "imported", "type": "verse", "bars": bars, "play": play}]}
