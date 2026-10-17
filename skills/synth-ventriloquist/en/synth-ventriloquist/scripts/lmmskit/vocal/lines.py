# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Lyric lines: the melody notation, and rendering one line to a sung WAV with any engine.

Melody notation, one token per sung syllable (tokens separated by spaces):
    E4/1            the syllable is sung on E4 for 1 beat
    E4/0.5~G4/0.5   one syllable slurred over two notes
    R/0.5           rest, no syllable (also '-/0.5')
The words of the line are matched to the tokens in order, by syllable.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

from .. import theory
from . import ending, singing, tts, world
from .singing import Style, SungLine, SungNote

REST_TOKENS = ("r", "-")


@dataclass
class Line:
    text: str
    melody: str
    start_beat: float = 0.0                       # song position of the line's first token (in beats)
    harmony: int = 0                              # diatonic steps above the melody (0 = lead, 2 = a third up)
    meta: dict = field(default_factory=dict)


def parse_melody(melody: str) -> list[list[tuple[int, float]] | float]:
    """Tokens to a list of note groups [(pitch, beats), ...] and rests (float beats)."""
    items: list = []
    for token in melody.split():
        if token.split("/")[0].lower() in REST_TOKENS:
            items.append(float(token.split("/")[1]))
            continue
        group = []
        for part in token.split("~"):
            name, _, beats = part.partition("/")
            if not beats:
                raise ValueError(f"melody token '{token}' needs a length, e.g. {name}/1")
            group.append((theory.note(name), float(beats)))
        items.append(group)
    return items


def note_groups(melody: str, bpm: float, transpose: int = 0) -> tuple[list[list[SungNote]], float, float]:
    """(note groups in seconds from the first sung note, beats of leading rest, total beats)."""
    seconds_per_beat = 60.0 / bpm
    cursor, first, groups = 0.0, None, []
    for item in parse_melody(melody):
        if isinstance(item, float):
            cursor += item
            continue
        first = cursor if first is None else first
        group = []
        for pitch, beats in item:
            group.append(SungNote((cursor - first) * seconds_per_beat, beats * seconds_per_beat, pitch + transpose))
            cursor += beats
        groups.append(group)
    if first is None:
        raise ValueError("the melody has no notes")
    return groups, first, cursor


def melody_in_seconds(melody: str, bpm: float, first_note_s: float, transpose: int = 0) -> list[tuple[float, float, int]]:
    """Every note of a melody as (start_s, duration_s, midi) on the song clock, given when its first sung note falls.

    render_part() records that moment per line as first_note_s, so the notes land on the same clock as the part's
    stem and the syllable spans, which is what the pitch checks and the vocal_line figure compare them with.
    """
    groups, _lead_beats, _total = note_groups(melody, bpm, transpose)
    return [(first_note_s + note.start, note.duration, note.pitch) for group in groups for note in group]


def _clear_of_chord(pitch: int, lead: int, tones: set[int], steps: int) -> int:
    """A harmony pitch a semitone away from a chord tone grinds against the chord: move it onto the nearest chord
    tone that is not the lead's own note, looking first in the direction the harmony moves."""
    if not tones or pitch % 12 in tones or not any((pitch - tone) % 12 in (1, 11) for tone in tones):
        return pitch
    direction = 1 if steps > 0 else -1
    for distance in range(1, 7):
        for candidate in (pitch + direction * distance, pitch - direction * distance):
            if candidate % 12 in tones and candidate != lead:
                return candidate
    return pitch


def harmonize(melody: str, key: str, steps: int, chord_tones=None) -> str:
    """Melody moved by diatonic steps inside the key (2 = a third above, -2 = a third below).

    chord_tones(beat) -> pitch classes of the chord sounding `beat` beats after the melody starts (or None);
    with it, harmony notes that would sit a semitone from a chord tone are moved onto the chord.
    """
    root, mode = theory.parse_key(key)
    scale = theory.SCALES[mode]
    ladder = sorted(12 * octave + root + step for octave in range(-1, 10) for step in scale)
    tokens, beat = [], 0.0
    for token in melody.split():
        if token.split("/")[0].lower() in REST_TOKENS:
            tokens.append(token)
            beat += float(token.split("/")[1])
            continue
        parts = []
        for part in token.split("~"):
            name, _, beats = part.partition("/")
            pitch = theory.note(name)
            nearest = min(range(len(ladder)), key=lambda i: abs(ladder[i] - pitch))
            moved = ladder[nearest + steps]
            if chord_tones is not None:
                moved = _clear_of_chord(moved, pitch, chord_tones(beat) or set(), steps)
            parts.append(f"{theory.name(moved)}/{beats}")
            beat += float(beats)
        tokens.append("~".join(parts))
    return " ".join(tokens)


def speak_line(voice: str, text: str, speed: float = 1.0, seed: int = 0, cache: str | None = None, fix_ending: bool = True):
    """Spoken unit for a line, its WORLD analysis, and what happened to the ending. Cached on disk when cache is set."""
    backend = tts.backend(voice)
    unit = tts.speak(voice, text, speed, seed, cache)
    analysis = _analysis(unit, cache, tts.unit_key(backend.identity, text, speed, seed))
    report = ending.ending_report(unit, analysis[0])
    report["repaired"] = False
    if fix_ending and report["dying"]:
        key = tts.unit_key(backend.identity + ":ending", text, speed, seed)
        path = os.path.join(cache, key + ".npz") if cache else None
        marker = path + ".none" if path else None
        if path and os.path.exists(path):
            fixed = tts.load_unit(path)
        elif marker and os.path.exists(marker):
            fixed = None
        else:
            fixed = ending.repair(backend, unit, speed, seed)
            if path:
                tts.save_unit(path, fixed) if fixed is not None else open(marker, "w").close()
        if fixed is not None:
            unit, analysis = fixed, _analysis(fixed, cache, key)
            report.update({"repaired": True, "after": ending.ending_report(fixed, analysis[0])})
    return unit, analysis, report


def _analysis(unit: tts.Unit, cache: str | None, key: str):
    if unit.analysis is not None:                   # made with the unit, to measure its lag
        return unit.analysis
    if cache is None:
        return world.analyze(unit.audio, unit.sr)
    path = os.path.join(cache, key + ".world.npz")
    if os.path.exists(path):
        data = np.load(path)
        return data["f0"], data["envelope"].astype(np.float64), data["aperiodicity"].astype(np.float64)
    f0, envelope, aperiodicity = world.analyze(unit.audio, unit.sr)
    np.savez_compressed(path, f0=f0, envelope=envelope.astype(np.float32), aperiodicity=aperiodicity.astype(np.float32))
    return f0, envelope, aperiodicity


def sing_line(voice: str, line: Line, bpm: float, *, key: str | None = None, speed: float = 1.0, style: Style | None = None,
              cache: str | None = None, fix_ending: bool = True) -> tuple[SungLine, dict]:
    """Render one line with a TTS voice. Returns the sung audio and a small report (lag, ending, natural pitch)."""
    style = style or Style()
    melody = harmonize(line.melody, key, line.harmony) if line.harmony and key else line.melody
    groups, lead_beats, _ = note_groups(melody, bpm)
    unit, analysis, ending_info = speak_line(voice, line.text, speed, style.seed, cache, fix_ending)
    sung = singing.sing(unit, groups, style, analysis)
    report = {"text": line.text, "lag_ms": round(unit.lag * 1000), "ending": ending_info,
              "natural_pitch": theory.name(int(round(singing.natural_pitch(unit, analysis)))), "lead_rest_beats": lead_beats,
              "squeezed_syllables": [item["text"] for item in sung.layout if item["squeezed"]]}
    return sung, report


def write_wav(path: str, audio: np.ndarray, sr: int = singing.OUTPUT_SR) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sf.write(path, np.clip(audio, -1.0, 1.0), sr, subtype="PCM_16")
    return path
