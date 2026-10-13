# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Pre-render checks: the 'compiler warnings' of a song.

Harmony is a documented craft: which notes sit well on which chord, where low intervals turn to mud,
what a bass should play when the chord changes. These checks restate that craft as rules over the
note data. Errors must be fixed. Warnings are places where convention is broken: fix them, or keep
them when the break is the point (and say so to the user)."""
from __future__ import annotations

import numpy as np

from . import instruments, theory

MELODIC_ROLES = ("lead", "vocal", "pluck", "arp", "backing")
HARMONIC_ROLES = ("pad", "chord", "keys")
RANGES = {"bass": (26, 60), "sub": (24, 50), "lead": (52, 98), "pluck": (48, 98), "arp": (48, 98),
          "pad": (40, 88), "chord": (43, 88), "keys": (33, 98)}
LOW_INTERVAL_LIMIT = 48         # below C3, intervals smaller than a fifth blur into mud
SUSTAINED_BEATS = 0.75          # a note this long is heard as harmony, not as a passing tone
OUT_OF_KEY_SHARE = 0.15
STRONG_BEAT_CHORD_SHARE = 0.5
VOCAL_MIN_NOTE_S = 0.11         # shorter syllables smear in a sung voice
VOCAL_LEAP = 9
EXAMPLES = 6
BUSY_LAST_BAR = 4               # this many notes in the final bar mean the song is still in full flow


def _issue(level: str, code: str, where: str, message: str) -> dict:
    return {"level": level, "code": code, "where": where, "message": message}


def _position(project: dict, beat: float) -> str:
    meter = project["meta"]["meter"]
    section = next((s for s in reversed(project["sections"]) if s["start"] <= beat + 1e-6), project["sections"][0])
    inside = beat - section["start"]
    return f"{section['name']} bar {int(inside // meter) + 1} beat {inside % meter + 1:g}"


def _chord_at(project: dict, beat: float):
    beat = round(beat * 8) / 8                          # judge a humanised note by the grid position it was written on
    for chord in reversed(project["chords"]):
        if chord["start"] <= beat + 1e-6:
            return chord if beat < chord["start"] + chord["dur"] + 1e-6 else None
    return None


def _chord_pcs(chord: dict) -> set:
    return {(chord["root"] + i) % 12 for i in chord["intervals"]}


def _scale_at(project: dict, key: theory.Key, beat: float) -> set:
    section = next((s for s in reversed(project["sections"]) if s["start"] <= beat + 1e-6), project["sections"][0])
    return {(pc + section.get("transpose", 0)) % 12 for pc in key.pcs}


def _pitched_notes(track: dict) -> list:
    """(start, dur, pitch) for synth notes and vocal line notes alike."""
    notes = [(n[0], n[1], n[2]) for n in track["notes"]]
    notes += [(line["start"] + n[0], n[1], n[2]) for line in track.get("lines", []) for n in line["notes"]]
    return sorted(notes)


def _examples(project: dict, beats: list) -> str:
    shown = ", ".join(_position(project, b) for b in beats[:EXAMPLES])
    return shown + (f" and {len(beats) - EXAMPLES} more" if len(beats) > EXAMPLES else "")


def check_project(project: dict) -> list:
    issues = []
    key = theory.parse_key(project["meta"]["key"])
    meter = project["meta"]["meter"]
    spb = 60.0 / project["meta"]["bpm"]
    pitched = [t for t in project["tracks"] if t.get("kind") != "drums" and t.get("role") != "fx"]

    # --- instruments and effects must exist before anything is rendered
    from . import fx
    for track in project["tracks"]:
        if track.get("kind") != "vocal":
            try:
                resolved = instruments.resolve(track["inst"], project.get("patches"))
            except KeyError as error:
                issues.append(_issue("error", "inst.unknown", track["name"], str(error).strip('"')))
                continue
            if resolved["kind"] == "synth" and resolved["patch"].get("engine") == "mono":
                notes = _pitched_notes(track)
                stacked = [a[0] for a, b in zip(notes, notes[1:]) if abs(a[0] - b[0]) < 1e-6]
                if stacked:
                    issues.append(_issue("warn", "mono.chord", track["name"],
                                         f"instrument is monophonic but chords are written at {_examples(project, stacked)}; "
                                         f"use a polyphonic patch or one note at a time"))
        for step in (track.get("mix") or {}).get("inserts") or []:
            if step.get("fx") not in fx.EFFECTS:
                issues.append(_issue("error", "fx.unknown", track["name"], f"unknown effect {step.get('fx')!r}; known: {sorted(fx.EFFECTS)}"))

    # --- harmony per track
    if pitched and not project["chords"]:
        issues.append(_issue("warn", "chords.missing", "song", "no section defines chords; harmony checks are skipped"))
    for track in pitched:
        notes = _pitched_notes(track)
        if not notes:
            continue
        role = track.get("role", "lead")
        outside, avoid, strong_total, strong_fit, bass_off = [], [], 0, 0, []
        for start, dur, pitch in notes:
            chord = _chord_at(project, start)
            pc = pitch % 12
            scale = _scale_at(project, key, start)
            chord_pcs = _chord_pcs(chord) if chord else set()
            if pc not in scale and pc not in chord_pcs:
                outside.append(start)
            if not chord:
                continue
            if role in MELODIC_ROLES and dur >= SUSTAINED_BEATS and pc not in chord_pcs \
                    and any((pc - tone) % 12 == 1 for tone in chord_pcs):
                avoid.append(start)
            beat_in_bar = (start - next(s["start"] for s in reversed(project["sections"]) if s["start"] <= start + 1e-6)) % meter
            if role in MELODIC_ROLES and dur >= 0.5 and abs(beat_in_bar % 2) < 1e-6:
                strong_total += 1
                strong_fit += pc in chord_pcs or (pc - chord["root"]) % 12 == 2
            if role in ("bass", "sub") and abs(start - chord["start"]) < 0.26 and pc not in chord_pcs | {chord["bass"]}:
                bass_off.append(start)
        if outside:
            share = len(outside) / len(notes)
            issues.append(_issue("warn" if share > OUT_OF_KEY_SHARE else "info", "key.outside", track["name"],
                                 f"{len(outside)} of {len(notes)} notes ({share:.0%}) are outside {project['meta']['key']} "
                                 f"and outside the chord: {_examples(project, outside)}"))
        if avoid:
            issues.append(_issue("warn", "harmony.avoid_note", track["name"],
                                 f"{len(avoid)} sustained notes sit a semitone above a chord tone (they grind against the chord): "
                                 f"{_examples(project, avoid)}. Shorten them, move them off the beat, or change the note"))
        if strong_total >= 8 and strong_fit / strong_total < STRONG_BEAT_CHORD_SHARE:
            issues.append(_issue("warn", "harmony.strong_beats", track["name"],
                                 f"only {strong_fit}/{strong_total} notes on beats 1 and 3 are chord tones or ninths; "
                                 f"the melody will sound detached from the harmony"))
        if bass_off:
            issues.append(_issue("warn", "bass.off_chord", track["name"],
                                 f"bass plays a non-chord tone where the chord changes: {_examples(project, bass_off)}"))
        low, high = RANGES.get(role, (0, 127))
        stray = [s for s, _, p in notes if not low <= p <= high]
        if stray and role in RANGES:
            issues.append(_issue("warn", "range." + role, track["name"],
                                 f"{len(stray)} notes outside the usual {role} range "
                                 f"{theory.midi_to_name(low)}..{theory.midi_to_name(high)}: {_examples(project, stray)}"))
        if role in HARMONIC_ROLES:
            muddy = _low_clusters(notes)
            if muddy:
                issues.append(_issue("warn", "mud.low_voicing", track["name"],
                                     f"close intervals below {theory.midi_to_name(LOW_INTERVAL_LIMIT)} at {_examples(project, muddy)}; "
                                     f"raise the voicing (octave) or leave the low register to the bass"))
        if role in MELODIC_ROLES:
            limit = VOCAL_LEAP if role == "vocal" else 12
            leaps = [b[0] for a, b in zip(notes, notes[1:]) if abs(b[2] - a[2]) > limit and b[0] - (a[0] + a[1]) < 1.0]
            if leaps:
                issues.append(_issue("warn" if role == "vocal" else "info", "melody.leap", track["name"],
                                     f"leaps wider than {limit} semitones at {_examples(project, leaps)}"))
        if track.get("kind") == "vocal":
            short = [line["start"] + n[0] for line in track.get("lines", []) for n in line["notes"] if n[1] * spb < VOCAL_MIN_NOTE_S]
            if short:
                issues.append(_issue("warn", "vocal.short_note", track["name"],
                                     f"{len(short)} sung notes are shorter than {VOCAL_MIN_NOTE_S * 1000:.0f} ms and will smear: "
                                     f"{_examples(project, short)}"))
            lines = track.get("lines", [])
            for a, b in zip(lines, lines[1:]):
                if a["start"] + a["notes"][-1][0] + a["notes"][-1][1] > b["start"] + 1e-6:
                    issues.append(_issue("error", "vocal.overlap", track["name"],
                                         f"line {a['text']!r} is still sounding when {b['text']!r} starts ({_position(project, b['start'])})"))

    issues += _cross_track_clashes(project, pitched)
    issues += _structure(project)
    return issues


def _low_clusters(notes: list) -> list:
    found = []
    low = [(s, s + d, p) for s, d, p in notes if p < LOW_INTERVAL_LIMIT]
    for index, (start, end, pitch) in enumerate(low):
        for other_start, other_end, other in low[index + 1:]:
            if other_start >= end:
                break
            if 0 < abs(other - pitch) < 7:
                found.append(max(start, other_start))
                break
    return sorted(set(found))


def _cross_track_clashes(project: dict, pitched: list) -> list:
    """Sustained semitone rubs between different tracks: usually an accident of writing parts separately."""
    events = []
    harmonic = {track["name"] for track in pitched if track.get("role") in HARMONIC_ROLES}
    for track in pitched:
        events += [(s, s + d, p, track["name"]) for s, d, p in _pitched_notes(track) if d >= SUSTAINED_BEATS]
    events.sort()
    pairs = {}
    for index, (start, end, pitch, name) in enumerate(events):
        for other_start, other_end, other_pitch, other_name in events[index + 1:]:
            if other_start >= end:
                break
            if name in harmonic and other_name in harmonic:
                continue                                # two chord instruments share the chord's own inner semitones
            chord = _chord_at(project, other_start)
            if chord and {pitch % 12, other_pitch % 12} <= _chord_pcs(chord):
                continue                                # both are chord tones: the rub belongs to the chord itself
            if other_name != name and abs(other_pitch - pitch) in (1, 13) and min(end, other_end) - other_start >= 0.5:
                pairs.setdefault(tuple(sorted((name, other_name))), []).append(other_start)
    return [_issue("warn", "clash.semitone", " + ".join(names),
                   f"{len(beats)} sustained semitone clashes between these tracks: {_examples(project, sorted(beats))}")
            for names, beats in pairs.items()]


def _structure(project: dict) -> list:
    issues = []
    meta = project["meta"]
    seconds = meta["beats"] * 60.0 / meta["bpm"]
    energies = [s["energy"] for s in project["sections"]]
    if len(project["sections"]) >= 3 and max(energies) - min(energies) < 0.2:
        issues.append(_issue("warn", "structure.flat", "sections",
                             "all sections have nearly the same planned energy; a full song needs contrast (intro, build, peak, break)"))
    odd = [s["name"] for s in project["sections"] if s["bars"] % 2]
    if odd:
        issues.append(_issue("info", "structure.odd_length", "sections", f"sections with an odd number of bars: {odd}"))
    meter_beats = meta["meter"]
    last_bar = [n for t in project["tracks"] if t.get("role") != "fx" for n in t.get("notes", [])
                if n[0] >= meta["beats"] - meter_beats]
    planned = meta.get("ending") in ("hit", "fade") or (project.get("master") or {}).get("fade_out") \
        or any(a[0] == "volume" and a[2] >= meta["beats"] - 1e-6 for a in project.get("master_automation") or [])
    if len(last_bar) >= BUSY_LAST_BAR and not planned:
        issues.append(_issue("warn", "structure.no_ending", "song",
                             f"the last bar still plays {len(last_bar)} notes and nothing closes the song: it will stop dead. "
                             f"Add `ending: hit` (a closing downbeat that fades) or `ending: fade`, or write a closing section"))
    if seconds < 60:
        issues.append(_issue("info", "structure.short", "song", f"the song lasts {seconds:.0f} s; this is a sketch, not a full track"))
    meter = meta["meter"]
    for section in project["sections"]:
        a, b = section["start"], section["start"] + section["bars"] * meter
        centres = []
        for track in project["tracks"]:
            if track.get("kind") == "drums" or track.get("role") in ("fx", "bass", "sub"):
                continue
            pitches = [p for s, _, p in _pitched_notes(track) if a <= s < b]
            if pitches:
                centres.append((float(np.median(pitches)), track["name"]))
        crowded = [name for centre, name in centres if 55 <= centre <= 72]
        if len(crowded) > 4:
            issues.append(_issue("warn", "density.register", section["name"],
                                 f"{len(crowded)} parts are centred in the same octave span G3..C5 ({', '.join(crowded)}); "
                                 f"they will mask each other. Spread them over octaves or drop one"))
    return issues


def check_vocals(project: dict, models: str | None = None) -> list:
    """Lyric checks need the vocal engine's own pronunciation, so they live with the engine."""
    if not any(t.get("kind") == "vocal" for t in project["tracks"]):
        return []
    from . import vocal
    return vocal.lint_lyrics(project, models)


def format_report(project: dict, issues: list) -> str:
    meta = project["meta"]
    seconds = meta["beats"] * 60.0 / meta["bpm"]
    lines = [f"{meta['title']}: {meta['key']}, {meta['bpm']:g} bpm, {int(meta['beats'] / meta['meter'])} bars, "
             f"{int(seconds // 60)}:{int(seconds % 60):02d}", "sections:"]
    meter = meta["meter"]
    for section in project["sections"]:
        a, b = section["start"], section["start"] + section["bars"] * meter
        names = []
        for chord in project["chords"]:
            if a <= chord["start"] < b and (not names or names[-1] != chord["name"]):
                names.append(chord["name"])
        playing = [t["name"] for t in project["tracks"] if any(a <= n[0] < b for n in t["notes"]) or
                   any(a <= line["start"] < b for line in t.get("lines", []))]
        shown = " ".join(names[:8]) + (" ..." if len(names) > 8 else "")
        lines.append(f"  {section['name']:14s} {section['bars']:g} bars  energy {section['energy']:.2f}  chords: {shown or '-'}"
                     f"  | {', '.join(playing)}")
    for level in ("error", "warn", "info"):
        chosen = [i for i in issues if i["level"] == level]
        if chosen:
            lines.append(f"{level.upper()} ({len(chosen)}):")
            lines += [f"  [{i['code']}] {i['where']}: {i['message']}" for i in chosen]
    if not issues:
        lines.append("no issues found")
    return "\n".join(lines)
