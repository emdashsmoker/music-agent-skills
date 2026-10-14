# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Harmony and arrangement lint: the 'compile errors' of music theory, read from the project's notes.

Rules flag what usually sounds wrong (semitone clashes, bass off the chord, mud in the low register).
Each finding names the bar and the tracks so it can be checked in a piano-roll figure; chromatic
writing that is intended stays, with a note in the report.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import compose, render, theory
from .findings import finding
from .mix import guess_roles
from .project import Note, Project

PITCHED_ROLES = ("sub", "bass", "lead", "pluck", "pad", "keys", "vocal", "vocal_bg")
LOW_ROLES = ("sub", "bass")
GRID = 0.25                                   # analysis step in beats (16th notes)
OUT_OF_SCALE_SHARE = 0.10
CLASH_MIN_BEATS = 0.5
MUD_BELOW_PITCH = 48                          # C3: close intervals below here blur together
MUD_MAX_INTERVAL = 6                          # smaller than a perfect fifth
MUD_MIN_BEATS = 1.0
LOWEST_USEFUL_PITCH = 28                      # E1, 41 Hz: lower fundamentals vanish on most speakers
BASS_HIGH_PITCH = 60
STRONG_NOTE_BEATS = 1.0
MONOTONY_BLOCK_BARS = 8
MONOTONY_REPEATS = 4
MAX_EXAMPLES = 8
OVERLAP_TOLERANCE = 0.3                       # share of a grid step a note may spill into without counting
IN_KEY_SHARE = 0.9
ROLE_RANGES = {"vocal": (48, 81), "vocal_bg": (48, 84), "lead": (55, 96), "pad": (36, 88), "pluck": (48, 96)}
# Krumhansl-Kessler key profiles.
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _where(project: Project, beat: float) -> str:
    bar = int(beat // project.beats_per_bar)
    return f"bar {bar + 1} beat {beat - bar * project.beats_per_bar + 1:.2f}".rstrip("0").rstrip(".")


def pitched_notes(project: Project, roles: dict[str, str]) -> dict[str, list[Note]]:
    """Notes of every pitched part. Vocal parts contribute their sung melody; other audio-file parts are left out."""
    sung = compose.sung_notes(project.path) if project.path else {}
    audio_parts = {t.name for t in project.tracks(0) if t.plugin == "audiofileprocessor"} - set(sung)
    return {name: notes for name, notes in compose.notes_with_vocals(project, project.path).items()
            if roles.get(name, "lead") in PITCHED_ROLES and name not in audio_parts}


def detect_key(notes: list[Note]) -> tuple[str, float]:
    """Best-fitting major or minor key by duration-weighted pitch-class profile, with its correlation."""
    weights = np.zeros(12)
    for n in notes:
        weights[n.pitch % 12] += n.length
    if weights.sum() == 0:
        return "unknown", 0.0
    best = ("unknown", -2.0)
    for root in range(12):
        for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            score = float(np.corrcoef(weights, np.roll(profile, root))[0, 1])
            if score > best[1]:
                best = (f"{theory.SHARP_NAMES[root]} {mode}", score)
    return best


def _sounding(notes_by_track: dict[str, list[Note]], total_beats: float):
    """For every grid step: list of (track, pitch) that sound through it."""
    steps = int(np.ceil(total_beats / GRID)) + 1
    grid: list[list[tuple[str, int]]] = [[] for _ in range(steps)]
    for track, notes in notes_by_track.items():
        for n in notes:
            # A note counts for a step only if it fills a good part of it, so legato overlaps and slides are not clashes.
            first, last = int(round(n.start / GRID)), int(np.ceil((n.start + n.length) / GRID - OVERLAP_TOLERANCE))
            for step in range(first, min(max(last, first + 1), steps)):
                grid[step].append((track, n.pitch))
    return grid


def _runs(steps: list[int]) -> list[tuple[int, int]]:
    """Merge consecutive grid steps into (first step, length)."""
    result, start, previous = [], None, None
    for step in sorted(steps):
        if start is None or step != previous + 1:
            if start is not None:
                result.append((start, previous - start + 1))
            start = step
        previous = step
    if start is not None:
        result.append((start, previous - start + 1))
    return result


def check_scale(project, notes_by_track, key) -> list[dict]:
    allowed = theory.scale_pitch_classes(key)
    found = []
    for track, notes in notes_by_track.items():
        total = sum(n.length for n in notes)
        outside = [n for n in notes if n.pitch % 12 not in allowed]
        share = sum(n.length for n in outside) / total if total else 0.0
        if share > OUT_OF_SCALE_SHARE:
            examples = [f"{theory.name(n.pitch)} at {_where(project, n.start)}" for n in outside[:MAX_EXAMPLES]]
            found.append(finding("warn", "out_of_scale", f"'{track}': {share:.0%} of note time is outside {key}", examples=examples))
        elif outside:
            found.append(finding("info", "chromatic_notes", f"'{track}': {len(outside)} notes outside {key} (fine if intended)",
                                 examples=[f"{theory.name(n.pitch)} at {_where(project, n.start)}" for n in outside[:MAX_EXAMPLES]]))
    return found


def check_key(notes_by_track, key) -> list[dict]:
    """The declared key holds when nearly all note time lies in its scale; otherwise report the better-fitting key."""
    everything = [n for notes in notes_by_track.values() for n in notes]
    detected, score = detect_key(everything)
    if detected == "unknown":
        return []
    allowed = theory.scale_pitch_classes(key)
    total = sum(n.length for n in everything)
    inside = sum(n.length for n in everything if n.pitch % 12 in allowed) / total if total else 1.0
    if inside >= IN_KEY_SHARE:
        return [finding("info", "key", f"{inside:.0%} of note time lies in the declared key {key} (closest major/minor profile: {detected})")]
    return [finding("warn", "key_mismatch", f"only {inside:.0%} of note time lies in the declared key {key}; the notes fit {detected} "
                    f"(r={score:.2f}). Check the plan or the parts that leave the key")]


def check_chords(project, notes_by_track, roles, chord_plan) -> list[dict]:
    """Bass must land on a chord tone at each chord change; long strong-beat notes of other parts should be chord tones."""
    found, bass_misses, tension = [], [], defaultdict(list)
    beats_per_bar = project.beats_per_bar
    for entry in chord_plan:
        start, end = entry["bar"] * beats_per_bar, (entry["bar"] + entry["bars"]) * beats_per_bar
        tones, root = theory.chord_pitch_classes(entry["symbol"]), theory.chord_root(entry["symbol"])
        for track, notes in notes_by_track.items():
            inside = [n for n in notes if start <= n.start < end]
            if not inside:
                continue
            if roles.get(track) in LOW_ROLES:
                first = min(inside, key=lambda n: n.start)
                if first.pitch % 12 not in tones:
                    bass_misses.append(f"{_where(project, first.start)}: '{track}' plays {theory.name(first.pitch)} under {entry['symbol']}")
            else:
                for n in inside:
                    on_beat = abs(n.start - round(n.start)) < 1e-6
                    if n.length >= STRONG_NOTE_BEATS and on_beat and n.pitch % 12 not in tones:
                        clash = any((n.pitch - tone) % 12 == 1 for tone in tones)      # a semitone above a chord tone: harsh
                        if clash:
                            tension[track].append(f"{theory.name(n.pitch)} over {entry['symbol']} at {_where(project, n.start)}")
    if bass_misses:
        found.append(finding("warn", "bass_off_chord", f"bass starts {len(bass_misses)} chord(s) on a note outside the chord",
                             examples=bass_misses[:MAX_EXAMPLES]))
    for track, items in tension.items():
        found.append(finding("warn", "avoid_note", f"'{track}': {len(items)} long strong-beat note(s) a semitone above a chord tone",
                             examples=items[:MAX_EXAMPLES]))
    return found


def check_clashes(project, notes_by_track) -> list[dict]:
    """Semitone (and minor ninth) rubs that last, and close intervals in the low register."""
    total = project.length_beats()
    grid = _sounding(notes_by_track, total)
    semitone, mud = defaultdict(list), defaultdict(list)          # (track, note, track, note) -> grid steps
    for step, voices in enumerate(grid):
        distinct = sorted(set(voices), key=lambda v: v[1])
        for i, (track_a, low) in enumerate(distinct):
            for track_b, high in distinct[i + 1:]:
                interval = high - low
                pair = (track_a, theory.name(low), track_b, theory.name(high))
                if interval in (1, 13):
                    semitone[pair].append(step)
                if high < MUD_BELOW_PITCH and 0 < interval < MUD_MAX_INTERVAL:
                    mud[pair].append(step)

    def lasting(flags, minimum_beats):
        hits = [(start, length, pair) for pair, steps in flags.items() for start, length in _runs(steps) if length * GRID >= minimum_beats]
        return sorted(hits)
    found = []
    rubs = lasting(semitone, CLASH_MIN_BEATS)
    if rubs:
        found.append(finding("warn", "semitone_clash", f"{len(rubs)} sustained semitone clash(es) between sounding notes",
                             examples=[f"{_where(project, s * GRID)}: {p[0]} {p[1]} against {p[2]} {p[3]} for {l * GRID:g} beats" for s, l, p in rubs[:MAX_EXAMPLES]]))
    muddy = lasting(mud, MUD_MIN_BEATS)
    if muddy:
        found.append(finding("warn", "low_mud", f"{len(muddy)} close interval(s) below {theory.name(MUD_BELOW_PITCH)}: move the upper note up an octave or thin the voicing",
                             examples=[f"{_where(project, s * GRID)}: {p[0]} {p[1]} with {p[2]} {p[3]}" for s, l, p in muddy[:MAX_EXAMPLES]]))
    return found


def check_ranges(project, notes_by_track, roles) -> list[dict]:
    found = []
    for track, notes in notes_by_track.items():
        role = roles.get(track, "lead")
        pitches = [n.pitch for n in notes]
        if role in LOW_ROLES:
            too_low = [n for n in notes if n.pitch < LOWEST_USEFUL_PITCH]
            if too_low:
                found.append(finding("warn", "bass_too_low", f"'{track}': {len(too_low)} note(s) below {theory.name(LOWEST_USEFUL_PITCH)} (under 41 Hz); raise an octave",
                                     examples=[f"{theory.name(n.pitch)} at {_where(project, n.start)}" for n in too_low[:MAX_EXAMPLES]]))
            if np.median(pitches) > BASS_HIGH_PITCH:
                found.append(finding("warn", "bass_too_high", f"'{track}' has a bass role but sits around {theory.name(int(np.median(pitches)))}"))
            overlaps = _overlaps(notes)
            if overlaps:
                found.append(finding("warn", "bass_polyphony", f"'{track}': {overlaps} overlapping bass notes (low chords turn to mud; keep bass monophonic)"))
        elif role in ROLE_RANGES:
            low, high = ROLE_RANGES[role]
            outside = [n for n in notes if not low <= n.pitch <= high]
            if outside:
                found.append(finding("info", "range", f"'{track}' ({role}): {len(outside)} note(s) outside the usual range {theory.name(low)}-{theory.name(high)}",
                                     examples=[f"{theory.name(n.pitch)} at {_where(project, n.start)}" for n in outside[:MAX_EXAMPLES]]))
    return found


def _overlaps(notes: list[Note]) -> int:
    ordered = sorted(notes, key=lambda n: n.start)
    return sum(1 for a, b in zip(ordered, ordered[1:]) if b.start < a.start + a.length - OVERLAP_TOLERANCE * GRID and b.pitch != a.pitch)


def check_arrangement(project: Project, plan: dict | None) -> list[dict]:
    """Empty tracks, silent stretches, long unchanged repetition, and a density table per section."""
    found = []
    notes = compose.notes_with_vocals(project, project.path)
    beats_per_bar = project.beats_per_bar
    names = [t.name for t in project.tracks(0)]
    empty = [name for name in names if name not in notes]
    if empty:
        found.append(finding("info", "empty_tracks", f"{len(empty)} track(s) have no notes", tracks=empty[:20]))
    total_bars = int(np.ceil(max((n.start + n.length for items in notes.values() for n in items), default=0) / beats_per_bar))
    active = defaultdict(set)
    signature = defaultdict(list)
    for track, items in notes.items():
        if "trigger" in track.lower():
            continue
        for n in items:
            bar = int(n.start // beats_per_bar)
            signature[bar].append((track, round(n.start - bar * beats_per_bar, 3), n.pitch, round(n.length, 3)))
            for sounding in range(bar, int((n.start + n.length - 1e-6) // beats_per_bar) + 1):
                active[sounding].add(track)
    silent = [bar + 1 for bar in range(total_bars) if not active[bar]]
    if silent:
        found.append(finding("warn", "silent_bars", f"{len(silent)} bar(s) in which no note sounds", lmms_bars=silent[:24]))
    blocks = [hash(tuple(tuple(sorted(signature[bar])) for bar in range(start, start + MONOTONY_BLOCK_BARS)))
              for start in range(0, max(total_bars - MONOTONY_BLOCK_BARS + 1, 0), MONOTONY_BLOCK_BARS)]
    run = longest = 1
    for previous, current in zip(blocks, blocks[1:]):
        run = run + 1 if current == previous else 1
        longest = max(longest, run)
    if longest >= MONOTONY_REPEATS:
        found.append(finding("warn", "monotony", f"the same {MONOTONY_BLOCK_BARS} bars repeat {longest} times in a row with no change in any part; "
                             "add or remove a layer, vary a fill, or automate a filter"))
    if plan and plan.get("sections"):
        rows = []
        for section in plan["sections"]:
            bars = range(section["start_bar"], section["start_bar"] + section["bars"])
            tracks = set().union(*(active[bar] for bar in bars)) if bars else set()
            rows.append({"section": section["name"], "lmms_bar": section["start_bar"] + 1, "bars": section["bars"],
                         "active_parts": len(tracks), "parts": sorted(tracks)})
        table = [f"{row['section']:14s} from bar {row['lmms_bar']:3d}, {row['bars']:3d} bars: {row['active_parts']:2d} parts" for row in rows]
        found.append(finding("info", "section_density", "parts playing in each section (the energy plan in numbers)", sections=rows, table=table))
    return found


def check_repeatability(project: Project) -> list[dict]:
    """Things LMMS renders differently on every run (found by rendering the same file repeatedly).

    They do not make a song wrong, but the same project then no longer gives the same audio file twice.
    The Kicker noise case depends on thread timing only and was repeatable in tests when LMMS ran on one CPU
    core, which lmmskit.render arranges wherever the operating system allows; it is reported only where it cannot.
    """
    found = []
    automated = {obj.get("id") for clip in project.automation_clips() for obj in clip.findall("object")}
    knobs, noisy_kicks, acid_synths = [], [], []
    for track in project.root.iter("track"):
        instrument = track.find("instrumenttrack/instrument")
        if instrument is None:
            continue
        knobs += [f"{track.get('name')}: {element.tag}" for element in instrument.iter() if element.get("id") in automated]
        plugin = instrument[0] if len(instrument) else None
        if plugin is not None and plugin.tag == "audiofileprocessor" and plugin.get("src", "").lower().endswith(".ds"):
            found.append(finding("warn", "unrepeatable_drumsynth", f"'{track.get('name')}' plays a DrumSynth preset ({plugin.get('src')}), which LMMS "
                                 "re-synthesises with fresh random noise on every render; use a kit one-shot or a rendered WAV of it"))
        if plugin is not None and plugin.tag == "kicker" and float(plugin.get("noise", "0") or 0) > 0:
            noisy_kicks.append(track.get("name"))
        if plugin is not None and plugin.tag == "lb302":
            acid_synths.append(track.get("name"))
    if acid_synths:
        found.append(finding("info", "lb302_start_state", f"LB302 parts ({', '.join(acid_synths)}) sometimes start a render with slightly different internal "
                             "state: measured as a low-frequency residue 65 to 72 dB under the mix between two renders, which cannot be heard"))
    if any("peak" in controller.tag.lower() for controller in project.root.iter() if controller.tag.lower().endswith("controller")):
        found.append(finding("warn", "unrepeatable_peak_controller", "a peak controller (LMMS sidechain) reacts with timing that differs on every render; "
                             "Song.sidechain writes the same ducking as automation, which renders identically every time"))
    if knobs:
        found.append(finding("warn", "unrepeatable_automation", f"{len(knobs)} automated instrument knob(s): LMMS hands such changes to the instrument at "
                             "slightly different moments, so some renders of the same project differ. Automate the track filter (shaping_param 'fcut'), "
                             "track volume or pan, or a mixer-channel effect instead (Song.sweep, Song.fade)", examples=knobs[:8]))
    if not render.can_pin():
        if len(noisy_kicks) > 1:
            found.append(finding("warn", "unrepeatable_kicker_noise", f"Kicker tracks with the noise knob up ({', '.join(noisy_kicks)}) share one noise source, "
                                 "which they consume in a different order on each render on this system; set noise to 0 or freeze the kicks to WAV"))
    return found


def lint(project: Project, plan: dict | None = None, key: str | None = None, roles: dict[str, str] | None = None) -> list[dict]:
    """Run every check. key and roles default to the plan file, then to detection/guessing."""
    if roles is None:
        roles = {name: part["role"] for name, part in plan["parts"].items()} if plan else {}
        roles = {**guess_roles(project), **roles}
    notes_by_track = pitched_notes(project, roles)
    key = key or (plan or {}).get("key")
    found = []
    if not notes_by_track:
        return [finding("info", "no_pitched_notes", "no pitched parts to analyse")] + check_arrangement(project, plan) + check_repeatability(project)
    if key is None:
        key, score = detect_key([n for notes in notes_by_track.values() for n in notes])
        found.append(finding("info", "key_detected", f"no key declared; the notes fit {key} best (r={score:.2f})"))
    else:
        found += check_key(notes_by_track, key)
    found += check_scale(project, notes_by_track, key)
    if plan and plan.get("chords"):
        found += check_chords(project, notes_by_track, roles, plan["chords"])
    found += check_clashes(project, notes_by_track)
    found += check_ranges(project, notes_by_track, roles)
    found += check_arrangement(project, plan)
    found += check_repeatability(project)
    return found
