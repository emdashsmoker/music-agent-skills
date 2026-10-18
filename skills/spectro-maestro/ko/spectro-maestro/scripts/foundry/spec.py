# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Compile a song spec (YAML, written by the composer) into a flat project dict.

The spec is the compact authoring form: named chord progressions, reusable parts, sections.
The project is the canonical form: every note explicit, ready to render, export or re-import.
Anything the composer got wrong is reported as SpecError with the place it happened."""
from __future__ import annotations

import copy
import re
import unicodedata
import zlib
from fractions import Fraction

import numpy as np
import yaml

from . import theory
from .theory import TheoryError

FORMAT = "spectro-maestro/1"
ROLES = ("kick", "snare", "hat", "perc", "bass", "sub", "lead", "pluck", "arp", "pad", "chord", "keys", "fx",
         "vocal", "backing")
SECTION_ENERGY = {"intro": 0.3, "verse": 0.5, "prechorus": 0.65, "build": 0.7, "drop": 1.0, "chorus": 0.9,
                  "break": 0.35, "bridge": 0.5, "outro": 0.3}
DEFAULT_OCTAVE = {"bass": None, "sub": None, "lead": 4, "pluck": 4, "arp": 4, "pad": 3, "chord": 3, "keys": 3,
                  "vocal": 4, "backing": 4}
BASS_FLOOR = 28                 # E1: lowest bass root. Below ~40 Hz most playback systems reproduce nothing.
HIT_VELOCITY = {"x": 0.8, "X": 1.0, "o": 0.45, "r": 0.75, "t": 0.75}
ROLL_HITS = {"r": 2, "t": 3}
ACCENT_VELOCITY, GHOST_VELOCITY, NORMAL_VELOCITY = 1.0, 0.5, 0.8
RISE_KINDS = ("riser", "snare_roll", "reverse_crash", "noise_sweep")
HIT_KINDS = ("impact", "crash", "downlifter", "sub_drop")
AUTO_PARAMS = ("lpf", "hpf", "volume")

TOP_KEYS = {"title", "artist", "genre", "bpm", "key", "meter", "seed", "swing", "swing_step", "humanize", "chords",
            "tracks", "sections", "mix", "master", "patches", "notes", "ending"}
ENDING_TYPES = ("hit", "fade", "none")
ENDING_BARS = {"hit": 2, "fade": 4}
ENDING_FADE_DB = -36.0          # how far the closing chord has faded when its bars are over
ENDING_ROLES = ("kick", "bass", "sub", "pad")       # one track of each, when the song has it, plays the closing hit
TRACK_KEYS = {"inst", "role", "parts", "mix", "vocal", "layers", "octave"}
PART_KEYS = {"hits", "grid", "line", "lyrics", "step", "octave", "vel", "gate", "transpose", "note", "loop", "swing"}
SECTION_KEYS = {"name", "type", "bars", "chords", "play", "energy", "gap", "rise", "hit", "auto", "vel", "transpose"}


class SpecError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    """YAML where only true/false are booleans. Plain YAML 1.1 also reads on/off/yes/no as booleans,
    which silently turns a part named `off` into the key False."""


_Loader.yaml_implicit_resolvers = {key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
                                   for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()}
_Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))


def load_yaml(path: str):
    with open(path, encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_Loader)


def load_spec(path: str) -> dict:
    spec = load_yaml(path)
    if not isinstance(spec, dict):
        raise SpecError(f"{path}: the song spec must be a mapping")
    return spec


def _check_keys(mapping: dict, allowed: set, where: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise SpecError(f"{where}: unknown key(s) {sorted(unknown)}; allowed: {sorted(allowed)}")


def stable_seed(*parts) -> int:
    """Seed that does not depend on Python's per-process hash randomisation."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def parse_beats(text: str, where: str) -> float:
    try:
        return float(Fraction(text if not text.startswith(".") else "0" + text))
    except (ValueError, ZeroDivisionError):
        raise SpecError(f"{where}: bad duration {text!r} (use beats such as 1, .5, 1.5 or 1/3)")


# ---------------------------------------------------------------- chord progressions

def parse_progression(text: str, key: theory.Key, bar_beats: float, where: str) -> list:
    """'Am | F | C G | %' -> [(start_beat, dur_beats, Chord)] for one pass of the progression.
    Without bar lines each chord takes one bar. Chords sharing a bar split it evenly unless 'Am:3 G:1'."""
    bars = [b.split() for b in text.split("|")] if "|" in text else [[token] for token in text.split()]
    bars = [b for b in bars if b]
    if not bars:
        raise SpecError(f"{where}: empty chord progression")
    timeline, previous_bar = [], None
    for index, tokens in enumerate(bars):
        if tokens == ["%"]:
            if previous_bar is None:
                raise SpecError(f"{where}: '%' needs a bar before it")
            tokens = previous_bar
        previous_bar = tokens
        explicit = [t.partition(":") for t in tokens]
        given = [parse_beats(d, where) if d else None for _, _, d in explicit]
        rest = bar_beats - sum(g for g in given if g)
        free = sum(1 for g in given if g is None)
        cursor = index * bar_beats
        for (symbol, _, _), beats in zip(explicit, given):
            beats = beats if beats is not None else rest / free
            try:
                chord = theory.parse_chord(symbol, key)
            except TheoryError as error:
                raise SpecError(f"{where}: {error}")
            timeline.append((cursor, beats, chord))
            cursor += beats
        if abs(cursor - (index + 1) * bar_beats) > 1e-6:
            raise SpecError(f"{where}: bar {index + 1} holds {cursor - index * bar_beats:g} beats, expected {bar_beats:g}")
    return timeline


def _transpose_chord(chord: theory.Chord, semitones: int, key: theory.Key) -> theory.Chord:
    if not semitones:
        return chord
    names = theory.FLAT_NAMES if key.flats else theory.SHARP_NAMES
    root, bass = (chord.root + semitones) % 12, (chord.bass + semitones) % 12
    quality = re.sub(r"^[A-G][#b]*", "", chord.name.split("/")[0])
    name = names[root] + quality + (f"/{names[bass]}" if bass != root else "")
    return theory.Chord(chord.symbol, name, root, chord.intervals, bass)


# ---------------------------------------------------------------- part notations

def _pitch_from_token(token: str, key: theory.Key, octave: int, where: str) -> int:
    if re.match(r"^[A-G][#b]*-?\d+$", token):            # note names are upper case, so b3 is always a flat third
        return theory.note_to_midi(token)
    match = re.match(r"^([#b]*)(\d+)([',]*)$", token)
    if not match:
        raise SpecError(f"{where}: cannot read pitch {token!r} (use C4, F#3 or a scale degree such as 5, b3, 1')")
    accidentals, degree, shifts = match.groups()
    alter = accidentals.count("#") - accidentals.count("b")
    octaves = 12 * (shifts.count("'") - shifts.count(","))
    if alter:
        # A degree written with an accidental is read against the major scale, so b3, b6 and b7 are the
        # minor third, sixth and seventh in every key (in A minor both 3 and b3 are C).
        major = theory.Key(key.tonic, "major", tuple(theory.SCALES["major"]))
        return major.degree_to_midi(int(degree), octave, alter) + octaves
    return key.degree_to_midi(int(degree), octave) + octaves


def parse_line(text: str, key: theory.Key, octave: int, bar_beats: float, where: str) -> tuple:
    """Melody notation -> (events, total_beats). Event: dict(start, dur, pitches, tie, vel).
    'A4:1 C5:.5 r:.5 | [A3 C4 E4]:2 E4:1~D4:1'  ('~' ties into the next note, '|' is a checked bar line)."""
    flat = re.sub(r"\[([^\]]*)\]", lambda m: "[" + ",".join(m.group(1).split()) + "]", str(text))
    events, cursor, last_beats = [], 0.0, None
    for chunk in flat.split():
        if chunk == "|":
            if abs(cursor / bar_beats - round(cursor / bar_beats)) > 1e-6:
                raise SpecError(f"{where}: bar line reached at beat {cursor:g}, which is not a multiple of {bar_beats:g}. "
                                f"Check the durations before it.")
            continue
        pieces = chunk.split("~")
        for index, piece in enumerate(pieces):
            if not piece:
                continue
            body, _, beats_text = piece.partition(":")
            if not body:
                raise SpecError(f"{where}: {chunk!r} has a duration without a pitch; write a tie as E4:1~D4:1")
            beats = parse_beats(beats_text, where) if beats_text else last_beats
            if beats is None:
                raise SpecError(f"{where}: first note {piece!r} needs a duration, e.g. {piece}:1")
            last_beats = beats
            velocity = NORMAL_VELOCITY
            while body and body[-1] in "!?":
                velocity = ACCENT_VELOCITY if body[-1] == "!" else GHOST_VELOCITY
                body = body[:-1]
            if body.lower() != "r":
                names = body[1:-1].split(",") if body.startswith("[") else [body]
                pitches = [_pitch_from_token(n, key, octave, where) for n in names if n]
                tie = index < len(pieces) - 1
                events.append({"start": cursor, "dur": beats, "pitches": pitches, "tie": tie, "vel": velocity})
            cursor += beats
    return events, cursor


def parse_hits(text: str, steps_per_bar: int, where: str) -> list:
    """'x...x...|x.o.X...' -> [(step_index, token)]. With bar lines every bar must be complete."""
    if "|" in text:
        for index, bar in enumerate(b for b in text.split("|") if b.strip()):
            count = len(bar.replace(" ", ""))
            if count != steps_per_bar:
                raise SpecError(f"{where}: bar {index + 1} has {count} steps, expected {steps_per_bar}")
    steps = text.replace("|", "").replace(" ", "")
    bad = set(steps) - set(HIT_VELOCITY) - {"."}
    if bad:
        raise SpecError(f"{where}: unknown hit symbol(s) {sorted(bad)}; use x X o r t .")
    return [(i, c) for i, c in enumerate(steps) if c != "."], len(steps)


def parse_grid(text: str, steps_per_bar: int, where: str) -> tuple:
    """Chord-relative step notation -> ([(step, n_steps, degree|'c', octave_shift, vel, slide)], total_steps)."""
    if "|" in text:
        for index, bar in enumerate(b for b in text.split("|") if b.strip()):
            if len(bar.split()) != steps_per_bar:
                raise SpecError(f"{where}: bar {index + 1} has {len(bar.split())} steps, expected {steps_per_bar}")
    tokens = text.replace("|", " ").split()
    events = []
    for step, token in enumerate(tokens):
        if token == ".":
            continue
        if token in ("-", "-~"):
            if not events or events[-1][0] + events[-1][1] != step:
                raise SpecError(f"{where}: '-' at step {step + 1} has no note to extend")
            events[-1][1] += 1
            events[-1][5] = events[-1][5] or token == "-~"       # a held note may still slide into the next
            continue
        match = re.match(r"^([#b]*)(\d+|c)([',]*)([!?~]*)$", token)
        if not match:
            raise SpecError(f"{where}: cannot read grid token {token!r} (use 1 3 5 7, c, ', ,, !, ?, ~, - or .)")
        accidentals, degree, shifts, marks = match.groups()
        velocity = ACCENT_VELOCITY if "!" in marks else GHOST_VELOCITY if "?" in marks else NORMAL_VELOCITY
        alter = accidentals.count("#") - accidentals.count("b")
        events.append([step, 1, degree if degree == "c" else int(degree), shifts.count("'") - shifts.count(","),
                       velocity, "~" in marks, alter])
    return events, len(tokens)


# ---------------------------------------------------------------- compiler

class Compiler:
    def __init__(self, spec: dict, drum_instruments: set):
        _check_keys(spec, TOP_KEYS, "song")
        for required in ("bpm", "key", "tracks", "sections"):
            if required not in spec:
                raise SpecError(f"song: missing required key {required!r}")
        self.spec = spec
        self.drums = drum_instruments
        try:
            self.key = theory.parse_key(spec["key"])
        except TheoryError as error:
            raise SpecError(f"song.key: {error}")
        self.bar_beats = float(spec.get("meter", 4))
        self.seed = int(spec.get("seed", 1))
        self.swing = float(spec.get("swing", 0.0))
        self.swing_step = float(spec.get("swing_step", 0.25))
        humanize = spec.get("humanize") or {}
        self.jitter_beats = float(humanize.get("timing_ms", 0.0)) / 1000.0 * float(spec["bpm"]) / 60.0
        self.jitter_velocity = float(humanize.get("velocity", 0.04))
        self.tracks = {}
        self.chords = []
        self.sections = []

    # -- helpers
    def _track(self, name: str, inst, role: str, mix: dict | None = None) -> dict:
        if name not in self.tracks:
            self.tracks[name] = {"name": name, "role": role, "inst": inst, "notes": [], "mix": dict(mix or {}),
                                 "automation": []}
        return self.tracks[name]

    def _chord_at(self, beat: float) -> theory.Chord | None:
        for start, dur, chord in reversed(self.chords):
            if start <= beat + 1e-9:
                return chord if beat < start + dur + 1e-9 else None
        return None

    def _humanized(self, notes: list, name: str, section: str, swing: float, is_drum: bool) -> list:
        rng = np.random.default_rng(stable_seed(self.seed, name, section))
        out = []
        for start, dur, pitch, velocity, flags in notes:
            position = start / self.swing_step
            if swing and abs(position - round(position)) < 1e-6 and int(round(position)) % 2 == 1:
                start += swing * self.swing_step
            if self.jitter_beats:
                start = max(0.0, start + float(rng.normal(0.0, self.jitter_beats)))
            if self.jitter_velocity:
                velocity = float(np.clip(velocity * (1.0 + rng.normal(0.0, self.jitter_velocity)), 0.05, 1.0))
            out.append([round(start, 5), round(dur, 5), pitch, round(velocity, 3)] + ([flags] if flags else []))
        return out

    # -- part expansion
    def _expand(self, name: str, track: dict, part_name: str, part: dict, section: dict, where: str) -> list:
        _check_keys(part, PART_KEYS, where)
        role = track.get("role", "lead")
        is_drum = self._is_drum(track)
        step = float(part.get("step", 0.25))
        steps_per_bar = int(round(self.bar_beats / step))
        gate = float(part.get("gate", 0.9))
        level = float(part.get("vel", 1.0)) * float((section.get("vel") or {}).get(name, 1.0))
        shift = int(part.get("transpose", 0)) + int(section.get("transpose", 0))
        octave = part.get("octave", track.get("octave", DEFAULT_OCTAVE.get(role, 4)))
        start, length = section["start"], section["bars"] * self.bar_beats
        loop = part.get("loop", True)
        notes = []

        def repeats(pattern_beats: float):
            if pattern_beats <= 0:
                raise SpecError(f"{where}: empty pattern")
            count = int(np.ceil(length / pattern_beats - 1e-9)) if loop else 1
            return [k * pattern_beats for k in range(count)]

        if "hits" in part:
            hits, total = parse_hits(str(part["hits"]), steps_per_bar, where)
            pitch = theory.note_to_midi(part["note"]) if "note" in part else 60
            for offset in repeats(total * step):
                for index, symbol in hits:
                    count = ROLL_HITS.get(symbol, 1)
                    for sub in range(count):
                        at = offset + (index + sub / count) * step
                        if at < length - 1e-9:
                            notes.append([start + at, step / count, pitch + (0 if is_drum else shift),
                                          HIT_VELOCITY[symbol] * level * (0.8 if sub else 1.0), None])
        elif "grid" in part:
            events, total = parse_grid(str(part["grid"]), steps_per_bar, where)
            previous_voicing = None
            for offset in repeats(total * step):
                for index, held, degree, octave_shift, velocity, slide, alter in events:
                    at = offset + index * step
                    if at >= length - 1e-9:
                        continue
                    chord = self._chord_at(start + at)
                    if chord is None:
                        raise SpecError(f"{where}: section {section['name']!r} has no chord at beat {at:g}; give it 'chords'")
                    dur = min(held * step * (1.0 if slide else gate), length - at)
                    flags = {"slide": 1} if slide else None
                    if degree == "c":
                        center = 12 * ((octave if octave is not None else 3) + 1) + 7 + 12 * octave_shift
                        voicing = theory.voice_chord(chord, center, previous_voicing)
                        previous_voicing = voicing
                        pitches = voicing
                    else:
                        root_pc = chord.bass if (role in ("bass", "sub") and degree == 1) else chord.root
                        if octave is None:
                            base = BASS_FLOOR + (root_pc - BASS_FLOOR) % 12
                        else:
                            base = 12 * (octave + 1) + root_pc
                        if root_pc != chord.root:
                            tone = 0
                        elif alter:                      # b7, b3, #4 ...: counted from the major scale above the chord root
                            tone = theory.SCALES["major"][(degree - 1) % 7] + 12 * ((degree - 1) // 7) + alter
                        else:
                            tone = chord.tone(degree, self.key)
                        pitches = [base + tone + 12 * octave_shift]
                    for pitch in pitches:
                        notes.append([start + at, dur, pitch + shift, velocity * level, flags])
        elif "line" in part:
            events, total = parse_line(str(part["line"]), self.key, octave if octave is not None else 2,
                                       self.bar_beats, where)
            if total > length + 1e-6 and loop:
                raise SpecError(f"{where}: line is {total:g} beats but section {section['name']!r} is only {length:g}")
            for offset in repeats(total):
                for event in events:
                    at = offset + event["start"]
                    if at >= length - 1e-9:
                        continue
                    dur = min(event["dur"] * (1.0 if event["tie"] else gate), length - at)
                    flags = {"slide": 1} if event["tie"] else None
                    for pitch in event["pitches"]:
                        notes.append([start + at, dur, pitch + shift, event["vel"] * level, flags])
        else:
            raise SpecError(f"{where}: a part needs one of hits, grid, line or lyrics")
        return self._humanized(notes, name, section["name"], float(part.get("swing", self.swing)), is_drum)

    def _is_drum(self, track: dict) -> bool:
        inst = track.get("inst")
        base = inst.get("base") if isinstance(inst, dict) else inst
        return base in self.drums or track.get("role") in ("kick", "snare", "hat", "perc")

    def _vocal_lines(self, name: str, part: dict, section: dict, where: str) -> list:
        lines = []
        octave = part.get("octave", 4)
        shift = int(part.get("transpose", 0)) + int(section.get("transpose", 0))
        for index, entry in enumerate(part["lyrics"]):
            here = f"{where}.lyrics[{index}]"
            if not isinstance(entry, dict) or "text" not in entry or "notes" not in entry:
                raise SpecError(f"{here}: each lyric line needs 'text' and 'notes'")
            _check_keys(entry, {"bar", "beat", "text", "notes", "phonemes"}, here)
            events, _ = parse_line(str(entry["notes"]), self.key, octave, self.bar_beats, here)
            if not events:
                raise SpecError(f"{here}: no notes")
            offset = (float(entry.get("bar", 1)) - 1) * self.bar_beats + float(entry.get("beat", 1)) - 1
            if offset + events[-1]["start"] + events[-1]["dur"] > section["bars"] * self.bar_beats + self.bar_beats + 1e-6:
                raise SpecError(f"{here}: line runs past the end of section {section['name']!r}")
            lines.append({
                # Text from another system can arrive decomposed (NFD: 한 as ㅎ ㅏ ㄴ, й as и plus a breve); the engines,
                # dictionaries and the recogniser read composed text.
                "text": unicodedata.normalize("NFC", str(entry["text"])), "section": section["name"],
                "start": round(section["start"] + offset + events[0]["start"], 5),
                "notes": [[round(e["start"] - events[0]["start"], 5), round(e["dur"], 5), e["pitches"][0] + shift,
                           1 if e["tie"] else 0] for e in events],
                **({"phonemes": entry["phonemes"]} if "phonemes" in entry else {}),
            })
        return lines

    # -- transitions
    def _transitions(self, section: dict, raw: dict) -> None:
        start, length = section["start"], section["bars"] * self.bar_beats
        end = start + length
        rise = raw.get("rise") or {}
        rise = {k: None for k in rise} if isinstance(rise, list) else dict(rise)
        for kind, bars in rise.items():
            if kind not in RISE_KINDS:
                raise SpecError(f"section {section['name']!r}: unknown rise {kind!r}; use {RISE_KINDS}")
            bars = float(bars) if bars else min(section["bars"], {"reverse_crash": 1}.get(kind, 4))
            beats = min(bars * self.bar_beats, length)
            if kind == "snare_roll":
                track = self._track("fx_roll", "snare_roll", "snare")
                track["notes"] += self._snare_roll(end - beats, beats)
            else:
                track = self._track(f"fx_{kind}", kind, "fx")
                track["notes"].append([round(end - beats, 5), round(beats, 5), 60, 0.8])
        hit = raw.get("hit") or []
        hit = list(hit) if isinstance(hit, (list, dict)) else [hit]
        for kind in hit:
            if kind not in HIT_KINDS:
                raise SpecError(f"section {section['name']!r}: unknown hit {kind!r}; use {HIT_KINDS}")
            track = self._track(f"fx_{kind}", kind, "fx")
            beats = {"impact": 8, "crash": 8, "downlifter": 8, "sub_drop": 4}[kind]
            track["notes"].append([round(start, 5), float(beats), 60, 0.8])

    def _snare_roll(self, start: float, beats: float) -> list:
        """8ths, then 16ths, then 32nds in the last beat, getting louder: the standard build-up roll."""
        notes, cursor = [], 0.0
        while cursor < beats - 1e-9:
            progress = cursor / beats
            step = 0.5 if progress < 0.5 else 0.25 if beats - cursor > 1.0 + 1e-9 else 0.125
            notes.append([round(start + cursor, 5), step, 60, round(0.35 + 0.6 * progress, 3)])
            cursor += step
        return notes

    # -- ending
    def _ending(self, raw, at_bar: float) -> dict:
        """`ending: hit` closes the song with one tonic downbeat that fades over two bars (kick, bass, pad and a
        crash, taken from the tracks the song already uses); `ending: fade` fades the last bars out.
        Either may be written as {type: ..., bars: N}."""
        setting = dict(raw) if isinstance(raw, dict) else {"type": raw or "none"}
        kind = str(setting.get("type", "none"))
        if kind not in ENDING_TYPES:
            raise SpecError(f"song.ending: {kind!r} is not one of {ENDING_TYPES}")
        bars = float(setting.get("bars", ENDING_BARS.get(kind, 0)))
        if kind != "hit":
            return {"type": kind, "bars": bars}
        start, length = at_bar * self.bar_beats, bars * self.bar_beats
        tonic = theory.parse_chord("i" if self.key.scale[2] == 3 else "I", self.key)
        self.chords.append((start, length, tonic))
        self.sections.append({"name": "end", "type": "outro", "start": start, "bars": bars, "energy": 0.3,
                              "transpose": 0, "vel": {}})
        for role in ENDING_ROLES:
            played = [t for t in self.tracks.values() if t["role"] == role and t["notes"]]
            if not played:
                continue
            track = max(played, key=lambda t: len(t["notes"]))
            if role == "kick":
                track["notes"].append([start, 0.25, 60, 1.0])
            elif role == "pad":
                octave = self.spec["tracks"].get(track["name"], {}).get("octave", DEFAULT_OCTAVE["pad"])
                for pitch in theory.voice_chord(tonic, 12 * (octave + 1) + 7):
                    track["notes"].append([start, length, pitch, 0.8])
            else:
                octave = self.spec["tracks"].get(track["name"], {}).get("octave")
                root = BASS_FLOOR + (tonic.root - BASS_FLOOR) % 12 if octave is None else 12 * (octave + 1) + tonic.root
                track["notes"].append([start, length, root, 0.8])
        self._track("fx_crash", "crash", "fx")["notes"].append([start, 8.0, 60, 0.8])
        self._track("master", None, "fx")["automation"].append(["volume", start, start + length, 0.0, ENDING_FADE_DB])
        return {"type": kind, "bars": bars}

    # -- main
    def compile(self) -> dict:
        spec = self.spec
        named = {name: str(text) for name, text in (spec.get("chords") or {}).items()}
        for name, track in spec["tracks"].items():
            _check_keys(track, TRACK_KEYS, f"tracks.{name}")
            if track.get("role", "lead") not in ROLES:
                raise SpecError(f"tracks.{name}.role: {track.get('role')!r} is not one of {ROLES}")
        cursor_bar = 0.0
        vocal_lines = {}
        for index, raw in enumerate(spec["sections"]):
            where = f"sections[{index}]"
            _check_keys(raw, SECTION_KEYS, where)
            if "bars" not in raw:
                raise SpecError(f"{where}: missing 'bars'")
            kind = raw.get("type", raw.get("name", "verse"))
            section = {"name": str(raw.get("name", f"s{index + 1}")), "type": str(kind),
                       "start": cursor_bar * self.bar_beats, "bars": float(raw["bars"]),
                       "energy": float(raw.get("energy", SECTION_ENERGY.get(str(kind), 0.5))),
                       "transpose": int(raw.get("transpose", 0)),
                       "vel": raw.get("vel") or {}}
            self.sections.append(section)
            length = section["bars"] * self.bar_beats
            if raw.get("chords"):
                text = named.get(str(raw["chords"]), str(raw["chords"]))
                one_pass = parse_progression(text, self.key, self.bar_beats, f"{where}.chords")
                pass_beats = one_pass[-1][0] + one_pass[-1][1]
                offset = 0.0
                while offset < length - 1e-9:
                    for start, dur, chord in one_pass:
                        if offset + start < length - 1e-9:
                            dur = min(dur, length - offset - start)
                            self.chords.append((section["start"] + offset + start, dur,
                                                _transpose_chord(chord, section["transpose"], self.key)))
                    offset += pass_beats
            for name, part_names in (raw.get("play") or {}).items():
                if name not in spec["tracks"]:
                    raise SpecError(f"{where}.play: no track named {name!r}")
                track_spec = spec["tracks"][name]
                for part_name in (part_names if isinstance(part_names, list) else [part_names]):
                    parts = track_spec.get("parts") or {}
                    if part_name not in parts:
                        raise SpecError(f"{where}.play.{name}: no part {part_name!r}; parts: {sorted(parts)}")
                    part, here = parts[part_name], f"tracks.{name}.parts.{part_name}"
                    if "lyrics" in part:
                        _check_keys(part, PART_KEYS, here)
                        vocal_lines.setdefault(name, []).extend(self._vocal_lines(name, part, section, here))
                        track = self._track(name, track_spec.get("inst"), track_spec.get("role", "vocal"),
                                            track_spec.get("mix"))
                        continue
                    track = self._track(name, track_spec.get("inst"), track_spec.get("role", "lead"),
                                        track_spec.get("mix"))
                    track["notes"] += self._expand(name, track_spec, part_name, part, section, here)
            for name, beats in (raw.get("gap") or {}).items():
                if name in self.tracks:
                    cut = section["start"] + length - float(beats)
                    self.tracks[name]["notes"] = [n for n in self.tracks[name]["notes"]
                                                  if not (cut - 1e-9 <= n[0] < section["start"] + length)]
            for name, params in (raw.get("auto") or {}).items():
                for param, (first, last) in params.items():
                    if param not in AUTO_PARAMS:
                        raise SpecError(f"{where}.auto.{name}: unknown parameter {param!r}; use {AUTO_PARAMS}")
                    if name != "master" and name not in spec["tracks"]:
                        raise SpecError(f"{where}.auto: no track named {name!r}")
                    target = self._track(name, None, "fx") if name == "master" else self._track(
                        name, spec["tracks"][name].get("inst"), spec["tracks"][name].get("role", "lead"),
                        spec["tracks"][name].get("mix"))
                    target["automation"].append([param, section["start"], section["start"] + length,
                                                 float(first), float(last)])
            self._transitions(section, raw)
            cursor_bar += section["bars"]

        ending = self._ending(spec.get("ending"), cursor_bar)
        cursor_bar += ending["bars"] if ending["type"] == "hit" else 0
        master_automation = self.tracks.pop("master", {"automation": []})["automation"]
        tracks = []
        for name, track in self.tracks.items():
            track["notes"].sort(key=lambda n: (n[0], n[2]))
            track_spec = spec["tracks"].get(name, {})
            if name in vocal_lines or track_spec.get("vocal"):
                track["kind"] = "vocal"
                track["vocal"] = copy.deepcopy(track_spec.get("vocal") or {})
                track["lines"] = sorted(vocal_lines.get(name, []), key=lambda l: l["start"])
                track["layers"] = copy.deepcopy(track_spec.get("layers") or [])
            else:
                track["kind"] = "drums" if self._is_drum(track_spec or track) or track["inst"] == "snare_roll" else "synth"
            tracks.append(track)
        total_beats = cursor_bar * self.bar_beats
        return {
            "format": FORMAT,
            "meta": {"title": spec.get("title", "untitled"), "artist": spec.get("artist", ""),
                     "genre": spec.get("genre", ""), "bpm": float(spec["bpm"]),
                     "key": self.key.name, "meter": self.bar_beats, "seed": self.seed,
                     "beats": total_beats, "notes": spec.get("notes", ""), "ending": ending["type"]},
            "sections": [{k: v for k, v in s.items() if k != "vel"} for s in self.sections],
            "chords": [{"start": round(s, 5), "dur": round(d, 5), "name": c.name, "root": c.root,
                        "intervals": list(c.intervals), "bass": c.bass} for s, d, c in self.chords],
            "tracks": tracks,
            "patches": copy.deepcopy(spec.get("patches") or {}),
            "mix": copy.deepcopy(spec.get("mix") or {}),
            "master": {**({"fade_out": ending["bars"] * self.bar_beats} if ending["type"] == "fade" else {}),
                       **copy.deepcopy(spec.get("master") or {})},
            "master_automation": master_automation,
        }


def compile_spec(spec: dict, drum_instruments: set) -> dict:
    return Compiler(spec, drum_instruments).compile()
