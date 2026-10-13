# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Pitch, scale and chord arithmetic. Everything here is pure and deterministic."""
from __future__ import annotations

import re
from dataclasses import dataclass

NOTE_PCS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "phrygian_dominant": [0, 1, 4, 5, 7, 8, 10],
}
MODE_ALIASES = {"min": "minor", "maj": "major", "aeolian": "minor", "ionian": "major", "m": "minor"}

# Chord quality -> intervals in semitones. Longest suffix is matched first.
CHORD_QUALITIES = {
    "": [0, 4, 7], "maj": [0, 4, 7], "m": [0, 3, 7], "min": [0, 3, 7],
    "5": [0, 7], "dim": [0, 3, 6], "aug": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7], "sus": [0, 5, 7],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "mmaj7": [0, 3, 7, 11],
    "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10], "7sus4": [0, 5, 7, 10],
    "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14],
    "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14],
    "11": [0, 4, 7, 10, 14, 17], "m11": [0, 3, 7, 10, 14, 17],
}
_QUALITY_ORDER = sorted(CHORD_QUALITIES, key=len, reverse=True)
ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}
_NOTE_RE = re.compile(r"^([A-G])([#b]*)(-?\d+)$")
_ROOT_RE = re.compile(r"^([A-G])([#b]*)(.*)$")
_ROMAN_RE = re.compile(r"^([#b]*)([ivIV]+)(.*)$")


class TheoryError(ValueError):
    """Raised for notation the composer must fix (the 'compile error' of the song)."""


def pc_of(name: str) -> int:
    match = re.match(r"^([A-Ga-g])([#b]*)$", name.strip())
    if not match:
        raise TheoryError(f"not a pitch name: {name!r}")
    letter, accidentals = match.groups()
    return (NOTE_PCS[letter.upper()] + accidentals.count("#") - accidentals.count("b")) % 12


def note_to_midi(name: str) -> int:
    """'A4' -> 69. Middle C is C4 = 60."""
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise TheoryError(f"not a note name with octave: {name!r}")
    letter, accidentals, octave = match.groups()
    return NOTE_PCS[letter.upper()] + accidentals.count("#") - accidentals.count("b") + 12 * (int(octave) + 1)


def midi_to_name(midi: float, flats: bool = False) -> str:
    midi = int(round(midi))
    return f"{(FLAT_NAMES if flats else SHARP_NAMES)[midi % 12]}{midi // 12 - 1}"


def midi_to_hz(midi) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


@dataclass(frozen=True)
class Key:
    tonic: int          # pitch class
    mode: str
    scale: tuple        # semitone offsets from the tonic

    @property
    def pcs(self) -> frozenset:
        return frozenset((self.tonic + s) % 12 for s in self.scale)

    @property
    def name(self) -> str:
        return f"{self.tonic_name} {self.mode}"

    @property
    def flats(self) -> bool:
        # Minor-ish modes and flat tonics read better with flats.
        return self.tonic in (5, 10, 3, 8, 1) or (self.mode != "major" and self.tonic in (0, 7, 2))

    @property
    def tonic_name(self) -> str:
        return (FLAT_NAMES if self.flats else SHARP_NAMES)[self.tonic]

    def degree_to_midi(self, degree: int, octave: int, alter: int = 0) -> int:
        """Scale degree (1-based, may exceed 7) in the given octave of the tonic."""
        index = degree - 1
        return 12 * (octave + 1) + self.tonic + self.scale[index % 7] + 12 * (index // 7) + alter

    def step(self, midi: int, steps: int) -> int:
        """Move a pitch by diatonic steps; chromatic pitches snap to the scale tone below first."""
        ladder = sorted(12 * o + self.tonic + s for o in range(-1, 11) for s in self.scale)
        below = max(i for i, p in enumerate(ladder) if p <= midi)
        return ladder[max(0, min(len(ladder) - 1, below + steps))]


def parse_key(text: str) -> Key:
    parts = str(text).replace("_", " ").split()
    if not parts:
        raise TheoryError("empty key")
    tonic = pc_of(parts[0])
    mode = "_".join(parts[1:]).lower() or "major"
    mode = MODE_ALIASES.get(mode, mode)
    if mode not in SCALES:
        raise TheoryError(f"unknown mode {mode!r}; known: {', '.join(SCALES)}")
    return Key(tonic, mode, tuple(SCALES[mode]))


@dataclass(frozen=True)
class Chord:
    symbol: str         # as written
    name: str           # resolved absolute name, e.g. 'Fmaj7'
    root: int           # pitch class
    intervals: tuple    # semitones above the root
    bass: int           # pitch class of the bass note

    @property
    def pcs(self) -> frozenset:
        return frozenset((self.root + i) % 12 for i in self.intervals)

    def tone(self, degree: int, key: Key) -> int:
        """Semitones above the root for a chord-relative degree.
        1/3/5/7 come from the chord itself, 2/4/6 are the key's diatonic steps above the root."""
        index, octave = (degree - 1) % 7, (degree - 1) // 7
        # Which semitone spans count as this chord's own third, fifth and seventh.
        chord_spans = {0: (0,), 2: (2, 3, 4, 5), 4: (6, 7, 8), 6: (9, 10, 11)}
        own = [i % 12 for i in self.intervals[:4] if i % 12 in chord_spans.get(index, ())]
        value = own[0] if own else _diatonic_above(self.root, index, key)
        return value + 12 * octave


def _diatonic_above(root_pc: int, index: int, key: Key) -> int:
    ladder = sorted((pc - root_pc) % 12 for pc in key.pcs)
    if 0 in ladder and len(ladder) == 7:
        return ladder[index]
    return SCALES["major"][index]       # root outside the key: fall back to major-scale steps


def parse_chord(symbol: str, key: Key) -> Chord:
    """Absolute ('Am7', 'F#m/C#') or roman ('i', 'bVII', 'V7') chord symbols."""
    text = symbol.strip()
    body, _, slash = text.partition("/")
    match = _ROOT_RE.match(body)
    if match:
        letter, accidentals, quality = match.groups()
        root = pc_of(letter + accidentals)
    else:
        match = _ROMAN_RE.match(body)
        if not match or match.group(2).lower() not in ROMAN:
            raise TheoryError(f"cannot read chord {symbol!r}")
        accidentals, numeral, quality = match.groups()
        # Plain numerals follow the key's own scale (VI in A minor = F). Numerals written with an
        # accidental are read against the major scale (bVI in A minor = F too), which is how both
        # common conventions land on the same chord.
        ladder = SCALES["major"] if accidentals else key.scale
        root = (key.tonic + ladder[ROMAN[numeral.lower()]] + accidentals.count("#") - accidentals.count("b")) % 12
        if numeral.islower() and not quality.startswith(("m", "dim", "sus", "5")):
            quality = "m" + quality
        quality = {"mdim": "dim", "mdim7": "dim7", "mo": "dim", "m°": "dim"}.get(quality, quality)
    quality = quality.replace("°", "dim").replace("ø", "m7b5").replace("M7", "maj7").replace("Δ", "maj7")
    if quality not in CHORD_QUALITIES:
        raise TheoryError(f"unknown chord quality {quality!r} in {symbol!r}; known: {' '.join(q for q in _QUALITY_ORDER if q)}")
    bass = root
    if slash:
        if re.match(r"^[A-G][#b]*$", slash):
            bass = pc_of(slash)
        else:
            raise TheoryError(f"slash bass must be a note name in {symbol!r}")
    names = FLAT_NAMES if key.flats else SHARP_NAMES
    name = names[root] + quality + (f"/{names[bass]}" if bass != root else "")
    return Chord(text, name, root, tuple(CHORD_QUALITIES[quality]), bass)


def voice_chord(chord: Chord, center: int = 60, previous: list | None = None, max_notes: int = 4) -> list:
    """Close-position voicing near `center`, choosing the inversion that moves least from the previous chord.
    Smooth voice leading is what makes pads and stabs sound connected instead of jumping."""
    intervals = list(chord.intervals)
    if len(intervals) > max_notes and 7 in intervals:
        intervals.remove(7)                             # the fifth is the first tone a dense chord can lose
    pcs = [(chord.root + i) % 12 for i in intervals][:max_notes]
    candidates = []
    for start in range(len(pcs)):
        order = pcs[start:] + pcs[:start]
        low = min((12 * o + order[0] for o in range(1, 9)), key=lambda p: abs(p - (center - 4)))
        notes = [low]
        for pc in order[1:]:
            notes.append(notes[-1] + ((pc - notes[-1]) % 12 or 12))
        candidates.append(notes)
    target = previous if previous else [center] * len(pcs)

    def cost(notes):
        spread = sum(min(abs(n - t) for t in target) for n in notes)
        rub = sum(6.0 for a, b in zip(notes, notes[1:]) if b - a == 1)      # a semitone inside the voicing grinds
        return spread + 0.5 * abs(sum(notes) / len(notes) - center) + rub
    return min(candidates, key=cost)


def nearest_chord_tone(midi: int, chord: Chord, direction: int = 0) -> int:
    """Closest pitch belonging to the chord; direction +1/-1 restricts to at-or-above/at-or-below."""
    options = [midi + d for d in range(-11, 12) if (midi + d) % 12 in chord.pcs]
    if direction > 0:
        options = [p for p in options if p >= midi]
    elif direction < 0:
        options = [p for p in options if p <= midi]
    return min(options, key=lambda p: abs(p - midi))
