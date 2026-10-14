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


def check_part(rendered: dict, bpm: float, asr_model: str | None = None) -> list[dict]:
    """Recognition score for every different line of a rendered lead part, with lyric-craft hints for the weak ones.

    Repeats of a line (same words, same notes) are scored once. Backing parts sing the lead's words and are not
    scored. Craft hints are attached only to lines the recogniser stumbles on: a line that comes through clearly
    needs no rewriting, whatever the rules say.
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
        if key in seen:
            seen[key]["count"] += 1
            row["asr"] = seen[key]["asr"]
            continue
        # A following line can begin (with its opening consonant) before this one has ended: stop at its start,
        # or the recogniser hears the first sound of the next line as an extra word.
        following = next((start for start in starts if start > row["audio_start_s"]), row["audio_end_s"])
        piece = stem[int(row["audio_start_s"] * rate):int(min(row["audio_end_s"], following) * rate)]
        row["asr"] = asr.score_line(piece, rate, row["text"], asr_model, language=lang)
        seen[key] = {"row": row, "asr": row["asr"], "count": 1}
    for entry in seen.values():
        row, scored, report = entry["row"], entry["asr"], entry["row"]["report"]
        label = f"[{name}] line {row['index'] + 1} '{row['text']}'" + (f" (sung {entry['count']} times)" if entry["count"] > 1 else "")
        if scored["weak"]:
            hints = []
            if speech_voice:
                natural = theory.note(report["natural_pitch"]) if report.get("natural_pitch") else None
                hints = [f["message"].split(": ", 1)[-1] for f in
                         lyrics.lint_line(voice, line_tools.Line(row["text"], row["melody"]), bpm, natural_pitch=natural, role=row["kind"])]
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
        found.append(finding("info", "vocal_scores", f"[{name}] mean recognition score {np.mean(scores):.2f} over {len(scores)} different lines "
                             f"({flagged} flagged)", scores=scores))
    return found


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
