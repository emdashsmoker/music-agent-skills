# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Music theory helpers: note names, scales, chords, progressions, voicing, step sequences.

Pitches are MIDI note numbers (C4 = 60). Durations are beats (quarter notes).
"""
from __future__ import annotations

import re

from .project import Note

NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MIDDLE_C = 60

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11], "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "phrygian_dominant": [0, 1, 4, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10], "minor_pentatonic": [0, 3, 5, 7, 10], "major_pentatonic": [0, 2, 4, 7, 9],
    "blues": [0, 3, 5, 6, 7, 10], "whole_tone": [0, 2, 4, 6, 8, 10], "chromatic": list(range(12)),
}
SCALE_ALIASES = {"aeolian": "minor", "ionian": "major", "natural_minor": "minor", "min": "minor", "maj": "major", "m": "minor"}

# Chord quality -> semitone intervals from the root.
CHORDS = {
    "": [0, 4, 7], "m": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "5": [0, 7], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10],
    "mmaj7": [0, 3, 7, 11], "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
    "m9": [0, 3, 7, 10, 14], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14], "7sus4": [0, 5, 7, 10], "11": [0, 4, 7, 10, 14, 17],
    "m11": [0, 3, 7, 10, 14, 17], "13": [0, 4, 7, 10, 14, 21],
}
ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)?$")
_CHORD_RE = re.compile(r"^([A-G])([#b]*)(.*?)(?:/([A-G][#b]*))?$")
_ROMAN_RE = re.compile(r"^([b#]?)([ivIV]+)(.*)$")


def pitch_class(name: str) -> int:
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise ValueError(f"not a note name: '{name}'")
    letter, accidentals, _ = match.groups()
    return (NOTE_OFFSETS[letter.upper()] + accidentals.count("#") - accidentals.count("b")) % 12


def note(name: str | int, default_octave: int = 4) -> int:
    """'A2' -> 45, 'C#4' -> 61, 'Eb' -> default octave. Integers pass through."""
    if isinstance(name, int):
        return name
    match = _NOTE_RE.match(name.strip())
    if not match:
        raise ValueError(f"not a note name: '{name}'")
    letter, accidentals, octave = match.groups()
    octave = int(octave) if octave is not None else default_octave
    return 12 * (octave + 1) + NOTE_OFFSETS[letter.upper()] + accidentals.count("#") - accidentals.count("b")


def name(pitch: int) -> str:
    return f"{SHARP_NAMES[pitch % 12]}{pitch // 12 - 1}"


def parse_key(key: str) -> tuple[int, str]:
    """'A minor', 'F# dorian', 'Cm', 'Eb' -> (root pitch class, scale name)."""
    parts = key.replace("-", " ").split()
    head = parts[0]
    mode = "_".join(p.lower() for p in parts[1:]) if len(parts) > 1 else ""
    if not mode and head.endswith("m") and len(head) > 1:
        head, mode = head[:-1], "minor"
    mode = SCALE_ALIASES.get(mode, mode) or "major"
    if mode not in SCALES:
        raise ValueError(f"unknown scale '{mode}'; known: {sorted(SCALES)}")
    return pitch_class(head), mode


def scale_pitch_classes(key: str) -> set[int]:
    root, mode = parse_key(key)
    return {(root + step) % 12 for step in SCALES[mode]}


def scale(key: str, octave: int = 4, octaves: int = 1) -> list[int]:
    """Ascending scale pitches starting from the root in the given octave."""
    root, mode = parse_key(key)
    base = 12 * (octave + 1) + root
    return [base + 12 * o + step for o in range(octaves) for step in SCALES[mode]] + [base + 12 * octaves]


def degree(key: str, number: int, octave: int = 4) -> int:
    """Scale degree as a pitch: 1 = tonic. Degrees above 7 or below 1 continue into other octaves."""
    root, mode = parse_key(key)
    steps = SCALES[mode]
    index = number - 1
    return 12 * (octave + 1) + root + 12 * (index // len(steps)) + steps[index % len(steps)]


def chord(symbol: str, octave: int = 3, inversion: int = 0) -> list[int]:
    """'Am7' -> [57, 60, 64, 67] (root in the given octave). 'C/E' puts E in the bass below the chord."""
    match = _CHORD_RE.match(symbol.strip())
    if not match:
        raise ValueError(f"not a chord symbol: '{symbol}'")
    letter, accidentals, quality, bass = match.groups()
    quality = {"min": "m", "maj": "", "M7": "maj7", "min7": "m7", "o": "dim", "+": "aug"}.get(quality, quality)
    if quality not in CHORDS:
        raise ValueError(f"unknown chord quality '{quality}' in '{symbol}'; known: {sorted(CHORDS)}")
    root = 12 * (octave + 1) + NOTE_OFFSETS[letter] + accidentals.count("#") - accidentals.count("b")
    pitches = [root + interval for interval in CHORDS[quality]]
    for _ in range(inversion):
        pitches = pitches[1:] + [pitches[0] + 12]
    if bass:
        bass_pitch = 12 * (octave + 1) + pitch_class(bass)
        while bass_pitch >= pitches[0]:
            bass_pitch -= 12
        pitches = [bass_pitch] + pitches
    return pitches


def chord_root(symbol: str) -> int:
    """Pitch class of the note the bass should play (the slash bass if given)."""
    match = _CHORD_RE.match(symbol.strip())
    letter, accidentals, _, bass = match.groups()
    return pitch_class(bass) if bass else pitch_class(letter + accidentals)


def chord_pitch_classes(symbol: str) -> set[int]:
    return {p % 12 for p in chord(symbol)}


def roman(key: str, numeral: str) -> str:
    """Roman numeral in a key -> chord symbol. Case sets major/minor: in A minor 'i'->'Am', 'VI'->'F', 'bVII'->'G'."""
    match = _ROMAN_RE.match(numeral.strip())
    if not match or match.group(2).lower() not in ROMAN:
        raise ValueError(f"not a roman numeral: '{numeral}'")
    accidental, digits, suffix = match.groups()
    root, mode = parse_key(key)
    # A bare numeral is diatonic to the key's own scale (VI in A minor = F). A numeral with an
    # accidental is measured from the major scale (bII = one semitone above the tonic in any key).
    steps = SCALES[mode] if len(SCALES[mode]) == 7 and not accidental else SCALES["major"]
    semitone = steps[ROMAN[digits.lower()]] + {"b": -1, "#": 1, "": 0}[accidental]
    quality = suffix if digits.isupper() else ("m" + suffix if not suffix.startswith(("dim", "m7b5")) else suffix)
    use_flats = mode not in ("major", "lydian", "mixolydian") or accidental == "b"
    flat_names = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    return (flat_names if use_flats else SHARP_NAMES)[(root + semitone) % 12] + quality


def progression(text: str, key: str | None = None) -> list[str]:
    """'Am F C G' or, with a key, 'i VI III VII' -> list of chord symbols. '|' separators are ignored."""
    symbols = []
    for token in text.replace("|", " ").split():
        is_roman = key is not None and not re.match(r"^[A-G]", token) and _ROMAN_RE.match(token)
        symbols.append(roman(key, token) if is_roman else token)
    return symbols


def voice_lead(chords: list[list[int]], low: int = 48, high: int = 76) -> list[list[int]]:
    """Re-voice each chord near the previous one (smallest total movement), keeping notes inside low..high."""
    result = []
    previous = None
    for pitches in chords:
        classes = sorted({p % 12 for p in pitches})
        candidates = []
        for start in range(low, high - 11):
            voicing = []
            current = start
            ordered = sorted(classes, key=lambda c: (c - start) % 12)
            for pc in ordered:
                while current % 12 != pc:
                    current += 1
                voicing.append(current)
            if voicing[-1] <= high:
                candidates.append(voicing)
        if not candidates:
            candidates = [sorted(pitches)]
        if previous is None:
            centre = (low + high) / 2
            best = min(candidates, key=lambda v: abs(sum(v) / len(v) - centre))
        else:
            best = min(candidates, key=lambda v: sum(min(abs(p - q) for q in previous) for p in v) + abs(sum(v) / len(v) - sum(previous) / len(previous)))
        result.append(best)
        previous = best
    return result


# -- note list builders ---------------------------------------------------------------------------------
def seq(text: str, step: float = 0.25, vol: float = 100, gate: float = 1.0, octave: int = 3, start: float = 0.0) -> list[Note]:
    """Step-sequencer notation, one token per step.

    'A2 . . C3 _ _ . E3'  ->  note name = play, '.' or '-' = rest, '_' = hold the previous note one more step.
    '[A2 C3 E3]' plays a chord on one step; a trailing '!' accents (+25% volume), '?' ghosts (-40%).
    '|' is ignored so bars can be marked. gate scales note length (0.5 = staccato).
    """
    tokens = re.findall(r"\[[^\]]+\][!?]?|\S+", text.replace("|", " "))
    notes: list[Note] = []
    open_notes: list[Note] = []
    for index, token in enumerate(tokens):
        position = start + index * step
        if token in (".", "-"):
            open_notes = []
            continue
        if token == "_":
            for held in open_notes:
                held.length += step
            continue
        level = vol * (1.25 if token.endswith("!") else 0.6 if token.endswith("?") else 1.0)
        body = token.rstrip("!?")
        names = body[1:-1].split() if body.startswith("[") else [body]
        open_notes = [Note(position, step, note(n, octave), level) for n in names]
        notes.extend(open_notes)
    for item in notes:
        item.length *= gate
    return notes


CHORD_TONE_INDEX = {"R": 0, "1": 0, "3": 1, "5": 2, "7": 3, "9": 4}


def chord_tone(symbol: str, token: str, octave: int = 2) -> int:
    """Pitch of a chord degree: 'R' root, '3', '5', '7', '9', '8' (root an octave up); '+' / '-' suffixes shift octaves."""
    shift = 12 * (token.count("+") - token.count("-"))
    core = token.strip("+-")
    tones = chord(symbol.split("/")[0], octave)
    if core == "8":
        return tones[0] + 12 + shift
    if core not in CHORD_TONE_INDEX:
        raise ValueError(f"unknown chord degree '{token}'; use R 3 5 7 9 8 with optional + or -")
    index = CHORD_TONE_INDEX[core]
    return (tones[index] if index < len(tones) else tones[index % len(tones)] + 12) + shift


def degree_seq(pattern: str, symbol: str, step: float = 0.25, octave: int = 2, vol: float = 100, gate: float = 1.0,
               start: float = 0.0) -> list[Note]:
    """Step sequence written in chord degrees so one pattern follows any chord.

    'R . R 5 | 8 _ 5 .'  ->  R/3/5/7/8 play that chord tone, '.' rests, '_' holds, '!' accents, '?' ghosts.
    """
    notes: list[Note] = []
    last: Note | None = None
    for index, token in enumerate(pattern.replace("|", " ").split()):
        position = start + index * step
        if token in (".", "-"):
            last = None
        elif token == "_":
            if last is not None:
                last.length += step
        else:
            level = vol * (1.25 if token.endswith("!") else 0.6 if token.endswith("?") else 1.0)
            last = Note(position, step, chord_tone(symbol, token.rstrip("!?"), octave), level)
            notes.append(last)
    for item in notes:
        item.length *= gate
    return notes


def hits(grid: str, pitch: int = MIDDLE_C, step: float = 0.25, vol: float = 100, start: float = 0.0, length: float | None = None) -> list[Note]:
    """Drum grid, one character per step: 'x' hit, 'X' accent, 'o' ghost, '-' or '.' rest. Spaces and '|' ignored."""
    levels = {"x": 1.0, "X": 1.25, "o": 0.5}
    cleaned = grid.replace(" ", "").replace("|", "")
    return [Note(start + i * step, length or step, pitch, vol * levels[c]) for i, c in enumerate(cleaned) if c in levels]


def chord_notes(pitches: list[int], start: float, length: float, vol: float = 100, strum: float = 0.0) -> list[Note]:
    return [Note(start + i * strum, length - i * strum, p, vol) for i, p in enumerate(sorted(pitches))]


def arp(pitches: list[int], length: float, step: float = 0.25, mode: str = "up", octaves: int = 1, gate: float = 0.9,
        vol: float = 100, start: float = 0.0) -> list[Note]:
    """Arpeggiate chord tones for `length` beats. mode: up, down, updown, converge or an index string like '0 2 1 2'."""
    pool = sorted(p + 12 * o for o in range(octaves) for p in pitches)
    if mode == "down":
        order = pool[::-1]
    elif mode == "updown":
        order = pool + pool[-2:0:-1]
    elif mode == "converge":
        order = [pool[i // 2] if i % 2 == 0 else pool[-1 - i // 2] for i in range(len(pool))]
    elif mode == "up":
        order = pool
    else:
        order = [pool[int(i) % len(pool)] + 12 * (int(i) // len(pool)) for i in mode.split()]
    count = int(round(length / step))
    return [Note(start + i * step, step * gate, order[i % len(order)], vol) for i in range(count)]


def transpose(notes: list[Note], semitones: int) -> list[Note]:
    return [Note(n.start, n.length, n.pitch + semitones, n.vol, n.pan) for n in notes]


def shift(notes: list[Note], beats: float) -> list[Note]:
    return [Note(n.start + beats, n.length, n.pitch, n.vol, n.pan) for n in notes]


def repeat(notes: list[Note], times: int, period: float) -> list[Note]:
    """Tile a phrase `times` times, each copy `period` beats later."""
    return [Note(n.start + k * period, n.length, n.pitch, n.vol, n.pan) for k in range(times) for n in notes]


def humanize(notes: list[Note], seed: int, timing: float = 0.0, volume: float = 0.0) -> list[Note]:
    """Seeded small random offsets (beats, volume units) so repeated hits are not machine-identical."""
    import random
    rng = random.Random(seed)
    return [Note(max(0.0, n.start + rng.uniform(-timing, timing)), n.length, n.pitch,
                 max(1.0, n.vol + rng.uniform(-volume, volume)), n.pan) for n in notes]


def swing(notes: list[Note], amount: float = 0.33, step: float = 0.25) -> list[Note]:
    """Delay every second step by `amount` of a step (0.33 is a triplet feel)."""
    result = []
    for n in notes:
        index = round(n.start / step)
        late = step * amount if index % 2 == 1 and abs(n.start - index * step) < 1e-6 else 0.0
        result.append(Note(n.start + late, n.length, n.pitch, n.vol, n.pan))
    return result
