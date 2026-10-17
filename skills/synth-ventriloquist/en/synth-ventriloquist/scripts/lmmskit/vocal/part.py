# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""A vocal part of a song: its lines, rendering to one audio stem, and the checks on the result.

Every line is sung on its own (and cached), then placed in a stem at its song position so that each
note's vowel starts on its beat. The stem is one audio file per part; LMMS plays it from bar 1.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

from .. import theory
from ..findings import finding
from . import asr, engines, lines as line_tools, lyrics
from .singing import OUTPUT_SR, Style

LINE_LOUDNESS_DB = -20.0                 # every line is brought to this RMS so the part needs little riding in the mix
TTS_ENGINES = ("kokoro", "piper")
PITCH_EDGE_HEAD_S, PITCH_EDGE_TAIL_S = 0.09, 0.04    # note edges left out of the pitch measurement: consonants and the glide live there
OFF_PITCH_CENTS = 25.0                   # a line whose median pitch error is above this is heard as out of tune
OFF_PITCH_LINE_SHARE = 0.5               # this share of the different lines off pitch (at least 2) means the melody sits badly for the voice
ROUGH_PERIODICITY = 0.6                  # a sung vowel less periodic than this is mostly breath or hiss
QUIET_DB = 8.0                           # a sung vowel this far under the line's typical vowel is swallowed
MIN_JUDGED_VOWEL_S = 0.06                # shorter vowels cannot be judged
CONSONANT_HEAVY_NOTE_S = 0.2             # on a note shorter than this, a vowel taking less than CONSONANT_HEAVY_VOWEL_SHARE of it
CONSONANT_HEAVY_VOWEL_SHARE = 0.5        # is mostly consonant by design: left out of the ROUGH check
VOWEL_EDGE_S = 0.01                      # trimmed from both ends of a vowel span before measuring it


@dataclass
class VocalPart:
    name: str
    voice: str
    role: str = "vocal"
    method: str = "auto"
    lang: str = "en"
    speed: float = 1.0
    style: Style = field(default_factory=Style)
    options: dict = field(default_factory=dict)        # engine options (DiffSinger: steps, gender, tension ...)
    lines: list[line_tools.Line] = field(default_factory=list)

    def line(self, start_beat: float, text: str, melody: str, harmony: int = 0, section: str = "", kind: str = "verse") -> "VocalPart":
        """Add a line. start_beat is the song position of the melody's first token; kind 'chorus' adds chorus lint."""
        self.lines.append(line_tools.Line(text, melody, start_beat, harmony, {"section": section, "kind": kind}))
        return self

    def derive(self, name: str, *, harmony: int = 0, seed: int | None = None, only_kind: str | None = None, role: str = "vocal_bg",
               voice: str | None = None) -> "VocalPart":
        """A second part from the same lines: a harmony (harmony=2 is a third above) or a double (other seed).

        only_kind='chorus' keeps the extra voice to chorus lines, which is the usual place for it.
        """
        style = Style(**{**vars(self.style), "seed": self.style.seed + 1 if seed is None else seed})
        part = VocalPart(name, voice or self.voice, role, self.method, self.lang, self.speed, style, dict(self.options))
        part.lines = [line_tools.Line(l.text, l.melody, l.start_beat, harmony, dict(l.meta)) for l in self.lines
                      if only_kind is None or l.meta.get("kind") == only_kind]
        return part


def _rms_db(audio: np.ndarray) -> float:
    loud = audio[np.abs(audio) > 1e-4]
    return 20 * np.log10(np.sqrt(np.mean(loud ** 2)) + 1e-12) if len(loud) else -120.0


def render_part(part: VocalPart, bpm: float, key: str | None, total_beats: float, out_path: str, cache: str | None = None) -> dict:
    """Sing every line and write the part's stem (FLAC, mono). Returns per-line placement and engine reports."""
    seconds_per_beat = 60.0 / bpm
    stem = np.zeros(int((total_beats * seconds_per_beat + 4.0) * OUTPUT_SR))
    rows = []
    for index, line in enumerate(part.lines):
        sung, report = engines.render_line(part.voice, line, bpm, key=key, style=part.style, speed=part.speed, cache=cache,
                                           method=part.method, lang=part.lang, **part.options)
        audio = sung.audio * 10 ** ((LINE_LOUDNESS_DB - _rms_db(sung.audio)) / 20)
        first_note = (line.start_beat + report["lead_rest_beats"]) * seconds_per_beat
        start = int(round((first_note - sung.lead_in) * OUTPUT_SR))
        if start < 0:                                    # a pickup before bar 1: drop what would fall before the song
            audio, start = audio[-start:], 0
        end = min(len(stem), start + len(audio))
        stem[start:end] += audio[:end - start]
        rows.append({"index": index, "text": line.text, "melody": line.melody, "harmony": line.harmony, "start_beat": line.start_beat,
                     "first_note_s": round(first_note, 3), "audio_start_s": round(start / OUTPUT_SR, 3),
                     "audio_end_s": round(end / OUTPUT_SR, 3), "section": line.meta.get("section", ""), "kind": line.meta.get("kind", "verse"),
                     "report": report,
                     "syllables": [{"text": item["text"], "start_s": round(start / OUTPUT_SR + item["vowel_start"], 3),
                                    "end_s": round(start / OUTPUT_SR + item["vowel_end"], 3), "pitches": item["pitches"]} for item in sung.layout]})
    peak = np.max(np.abs(stem))
    if peak > 0.98:
        stem *= 0.98 / peak
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    last = max((row["audio_end_s"] for row in rows), default=0.0)
    sf.write(out_path, stem[:int((last + 0.5) * OUTPUT_SR)], OUTPUT_SR, subtype="PCM_16")
    return {"part": part.name, "voice": part.voice, "role": part.role, "method": part.method, "lang": part.lang, "stem": out_path,
            "stem_seconds": round(last + 0.5, 2), "lines": rows}


def pitch_error_cents(piece: np.ndarray, rate: int, notes: list[tuple[float, float, int]], origin: float) -> float | None:
    """Median distance in cents between the sung pitch and the written notes, measured away from the note edges.
    Ported from Spectro Maestro's vocal_cli._pitch_error_cents (same author, AGPL-3.0-or-later).

    `notes` are (start_s, duration_s, midi) on the clock where `origin` is the time of the first sample of `piece`.
    None when no voiced frame falls inside a note.
    """
    from . import world
    f0, times = world.harvest_f0(piece, rate)
    times = times + origin
    errors = []
    for start, duration, midi in notes:
        inside = (times > start + PITCH_EDGE_HEAD_S) & (times < start + duration - PITCH_EDGE_TAIL_S) & (f0 > 0)
        if inside.any():
            errors += list(np.abs(1200 * np.log2(f0[inside] / _hz_of_midi(midi))))
    return round(float(np.median(errors)), 1) if errors else None


def _hz_of_midi(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _note_under(middle: float, notes: list[tuple[float, float, int]]) -> tuple[float, float, int]:
    return next((note for note in notes if note[0] <= middle < note[0] + note[1]), notes[-1])


def rough_syllables(stem: np.ndarray, rate: int, syllables: list[dict], notes: list[tuple[float, float, int]]) -> list[dict]:
    """Sung vowels that came out as noise or nearly silent: the faults a listener hears at once and a recogniser forgives.
    Ported from Spectro Maestro's vocal_cli.rough_syllables (same author, AGPL-3.0-or-later).

    `syllables` are the rendered line's rows ({text, start_s, end_s} of the vowel on the stem's clock) and `notes`
    its melody on the same clock. A vowel that is too short to judge, or that is mostly consonant by design on a
    short note, is not reported. Returns [{syllable, problem ('noise' or 'quiet'), periodicity, level_db}].
    """
    measured = []
    for item in syllables:
        vowel_s = item["end_s"] - item["start_s"]
        middle = 0.5 * (item["start_s"] + item["end_s"])
        _start, duration, midi = _note_under(middle, notes)
        consonant_heavy = duration < CONSONANT_HEAVY_NOTE_S and vowel_s < CONSONANT_HEAVY_VOWEL_SHARE * duration
        if vowel_s < MIN_JUDGED_VOWEL_S or consonant_heavy:
            continue
        a, b = item["start_s"] + VOWEL_EDGE_S, item["end_s"] - VOWEL_EDGE_S
        piece = stem[int(a * rate):int(b * rate)]
        level = 10 * np.log10(float(np.mean(piece ** 2)) + 1e-12) if len(piece) else -120.0
        measured.append((item["text"], lyrics.periodicity(stem, rate, _hz_of_midi(midi), a, b), level))
    typical = float(np.median([level for _, _, level in measured])) if measured else 0.0
    found = []
    for text, periodic, level in measured:
        problem = "noise" if periodic < ROUGH_PERIODICITY else "quiet" if level < typical - QUIET_DB else None
        if problem:
            found.append({"syllable": text, "problem": problem, "periodicity": round(periodic, 2), "level_db": round(float(level - typical), 1)})
    return found


def check_part(rendered: dict, bpm: float, asr_model: str | None = None, figure_dir: str | None = None,
               beats_per_bar: float = lyrics.BEATS_PER_BAR) -> list[dict]:
    """Recognition score, pitch error, rough syllables and a dying ending for every different line of a rendered lead part,
    with lyric-craft hints for the weak ones.

    Repeats of a line (same words, same notes) are scored once. Backing parts sing the lead's words and are not
    scored. Craft hints are attached only to lines the recogniser stumbles on: a line that comes through clearly
    needs no rewriting, whatever the rules say. With figure_dir, every weak or rough line gets a vocal_line
    figure there (spectrogram with syllable marks over the sung pitch on the written notes).
    """
    name, voice, lang = rendered["part"], rendered["voice"], rendered.get("lang", "en")
    if rendered.get("role", "vocal") != "vocal":
        return []
    found = []
    stem, rate = sf.read(rendered["stem"])
    speech_voice = engines.engine_of(voice) in TTS_ENGINES
    seen: dict[tuple[str, str], dict] = {}
    starts = sorted(row["audio_start_s"] for row in rendered["lines"])
    for row in rendered["lines"]:
        key = (row["text"].lower(), row["melody"])
        if key in seen:                                   # a repeat carries the first take's measurements
            seen[key]["count"] += 1
            for field_name in ("asr", "pitch_error_cents", "rough"):
                row[field_name] = seen[key]["row"][field_name]
            continue
        # A following line can begin (with its opening consonant) before this one has ended: stop at its start,
        # or the recogniser hears the first sound of the next line as an extra word.
        following = next((start for start in starts if start > row["audio_start_s"]), row["audio_end_s"])
        piece = stem[int(row["audio_start_s"] * rate):int(min(row["audio_end_s"], following) * rate)]
        row["asr"] = asr.score_line(piece, rate, row["text"], asr_model, language=lang)
        notes = line_tools.melody_in_seconds(row["melody"], bpm, row["first_note_s"])
        row["pitch_error_cents"] = pitch_error_cents(piece, rate, notes, row["audio_start_s"])
        row["rough"] = rough_syllables(stem, rate, row["syllables"], notes)
        seen[key] = {"row": row, "asr": row["asr"], "count": 1, "piece": piece, "notes": notes}
    for entry in seen.values():
        row, scored, report = entry["row"], entry["asr"], entry["row"]["report"]
        label = f"[{name}] line {row['index'] + 1} '{row['text']}'" + (f" (sung {entry['count']} times)" if entry["count"] > 1 else "")
        if row["rough"]:
            listed = ", ".join(f"'{r['syllable']}' ({r['problem']}, periodicity {r['periodicity']}, {r['level_db']:+g} dB)" for r in row["rough"])
            found.append(finding("warn", "rough_syllables", f"{label}: sung vowels came out as noise or nearly silent: {listed}. Look at the "
                                 "line's figure; if the vowel shows a smudge instead of stripes, lengthen its note, choose a word with fewer "
                                 "consonants around it, or try another voice", line=row["index"], rough=row["rough"]))
        ending = report.get("ending") or {}
        state = ending.get("after", ending)                 # the state after the repair when one was made
        if state.get("dying"):
            found.append(finding("warn", "ending_dies", f"{label}: the last vowel still dies away"
                                 + (" after the line-ending repair" if ending.get("repaired") else " and the line-ending repair could not be applied")
                                 + f" ({state.get('voiced_share', 0.0) * 100:.0f}% voiced, {state.get('level_vs_line_db', 0.0):+.1f} dB against the line's vowels). "
                                 "Its held note will be heard as breath or hiss: end the line on an open vowel or diphthong, give the last word a "
                                 "shorter note, or try another voice", line=row["index"], ending=state))
        if figure_dir and (scored["weak"] or row["rough"] or state.get("dying")):
            from .. import visual
            os.makedirs(figure_dir, exist_ok=True)
            labels = [(item["start_s"], item["text"]) for item in row["syllables"]]
            row["figure"] = visual.vocal_line(entry["piece"], rate, os.path.join(figure_dir, f"{name.replace(' ', '_')}_line{row['index'] + 1:02d}.png"),
                                              row["audio_start_s"], entry["notes"], labels, title=label)
        if scored["weak"]:
            hints = []
            if speech_voice:
                natural = theory.note(report["natural_pitch"]) if report.get("natural_pitch") else None
                hints = [f["message"].split(": ", 1)[-1] for f in
                         lyrics.lint_line(voice, line_tools.Line(row["text"], row["melody"], row["start_beat"]), bpm, natural_pitch=natural,
                                          role=row["kind"], beats_per_bar=beats_per_bar)]
            found.append(finding("warn", "weak_line", f"{label} is recognised as '{scored['heard']}' (score {scored['score']}). Listen to the line; "
                                 "if it really is unclear, compare other wordings on the same notes or change the notes"
                                 + (". Possible causes: " + "; ".join(hints) if hints else ""), line=row["index"], score=scored["score"], hints=hints))
        ending = report.get("ending")
        if ending and ending.get("dying") and not ending.get("repaired"):
            found.append(finding("info", "soft_ending", f"{label}: the last vowel fades in the spoken take and could not be repaired"))
        if report.get("raised_semitones"):
            found.append(finding("info", "raised", f"{label} was sung {report['raised_semitones']} semitones lower and raised afterwards (melody above the voice's clean range)"))
    scores = [entry["asr"]["score"] for entry in seen.values()]
    if scores:
        flagged = sum(1 for entry in seen.values() if entry["asr"]["weak"])
        table = [f"line {e['row']['index'] + 1:2d} score {e['asr']['score']:.2f} pitch error {_cents_text(e['row']['pitch_error_cents'])}"
                 f" rough {', '.join(r['syllable'] for r in e['row']['rough']) or '-'}  '{e['row']['text']}'" for e in seen.values()]
        found.append(finding("info", "vocal_scores", f"[{name}] mean recognition score {np.mean(scores):.2f} over {len(scores)} different lines "
                             f"({flagged} flagged)", scores=scores, table=table))
        off_pitch = [e["row"] for e in seen.values() if (e["row"]["pitch_error_cents"] or 0.0) > OFF_PITCH_CENTS]
        if len(off_pitch) >= max(2, int(np.ceil(OFF_PITCH_LINE_SHARE * len(scores)))):
            found.append(finding("warn", "off_pitch_lines", f"[{name}] {len(off_pitch)} of {len(scores)} different lines sit more than "
                                 f"{OFF_PITCH_CENTS:g} cents from their notes (lines {', '.join(str(r['index'] + 1) for r in off_pitch)}); "
                                 "the melody is outside the range this voice holds cleanly: transpose the part toward its natural pitch "
                                 "or choose another voice", lines=[r["index"] for r in off_pitch]))
    return found


def _cents_text(cents: float | None) -> str:
    return f"{cents:5.1f}c" if cents is not None else "   - "


def save_report(path: str, rendered: list[dict]) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rendered, handle, indent=1, ensure_ascii=False, default=float)
    return path


def lyric_sheet(parts: list[dict], title: str = "") -> str:
    """Plain-text lyrics of the lead parts with section headings and time stamps."""
    lines_out = [title, ""] if title else []
    seen_section = None
    lead = [row for part in parts if part["role"] == "vocal" for row in part["lines"]]
    for row in sorted(lead, key=lambda r: r["first_note_s"]):
        if row["section"] and row["section"] != seen_section:
            lines_out += ["", f"[{row['section']}]"]
            seen_section = row["section"]
        minutes, seconds = divmod(int(row["first_note_s"]), 60)
        lines_out.append(f"{minutes}:{seconds:02d}  {row['text']}")
    return "\n".join(lines_out).strip() + "\n"
