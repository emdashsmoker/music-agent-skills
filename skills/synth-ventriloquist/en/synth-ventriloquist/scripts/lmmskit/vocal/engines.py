# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""One entry point for every singing engine: render_line(voice, line, ...) -> sung audio + report.

Voice ids
    kokoro:<voice>            Kokoro speech sung by stretching (method 'stretched', any pitch) or by the model's
                              own decoder (method 'held', clean only inside the voice's range)
    piper:<voice>             Piper speech, stretched
    diffsinger:<folder>       a DiffSinger voicebank the user supplied; '#<name>' picks a voice colour,
                              e.g. diffsinger:/path/to/bank#Soft
Rendered lines are cached on disk by content, so a song re-renders only the lines that changed.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np

from . import lines as line_tools
from . import tts
from .singing import OUTPUT_SR, Style, SungLine, SungNote

METHODS = ("auto", "stretched", "held")


def engine_of(voice: str) -> str:
    return voice.split(":", 1)[0]


def _cache_key(voice: str, line: line_tools.Line, bpm: float, key: str | None, style: Style, speed: float, options: dict) -> str:
    payload = [voice, line.text, line.melody, line.harmony, round(bpm, 4), key, vars(style), round(speed, 4), sorted(options.items()),
               tts.TIMING_VERSION]           # a new timing rule re-sings every cached line
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def _plain(value):
    """numpy scalars as plain Python numbers for JSON; anything else as text."""
    return value.item() if isinstance(value, np.generic) else str(value)


def _save(path: str, sung: SungLine, report: dict) -> None:
    np.savez_compressed(path, audio=sung.audio.astype(np.float32), lead_in=sung.lead_in, layout=json.dumps(sung.layout, default=_plain),
                        notes=np.array([[n.start, n.duration, n.pitch] for n in sung.notes]), report=json.dumps(report, default=_plain))


def _load(path: str) -> tuple[SungLine, dict]:
    data = np.load(path, allow_pickle=False)
    notes = [SungNote(float(a), float(b), float(c)) for a, b, c in data["notes"]]
    return SungLine(data["audio"].astype(np.float64), float(data["lead_in"]), json.loads(str(data["layout"])), None, notes), json.loads(str(data["report"]))


def render_line(voice: str, line: line_tools.Line, bpm: float, *, key: str | None = None, style: Style | None = None, speed: float = 1.0,
                cache: str | None = None, method: str = "auto", lang: str = "en", **options) -> tuple[SungLine, dict]:
    """Sing one line. options go to the engine.

    Speech voices: fix_ending=False switches the line-ending repair off.
    DiffSinger: steps, gender, velocity, tension, breathiness, expressiveness, own_pitch.
    """
    style = style or Style()
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    all_options = {"method": method, "lang": lang, **options}
    path = os.path.join(cache, "line_" + _cache_key(voice, line, bpm, key, style, speed, all_options) + ".npz") if cache else None
    if path and os.path.exists(path):
        return _load(path)
    melody = line_tools.harmonize(line.melody, key, line.harmony) if line.harmony and key else line.melody
    groups, lead_beats, _ = line_tools.note_groups(melody, bpm)
    engine = engine_of(voice)
    if engine == "diffsinger":
        from . import diffsinger
        folder, _, colour = voice.split(":", 1)[1].partition("#")
        sung, report = diffsinger.voicebank(folder).sing(line.text, groups, lang=lang, voice=colour or None, style=style, **options)
    elif engine == "kokoro" and method == "held":
        from . import kokoro_native
        sung, report = kokoro_native.sing_in_range(voice, line.text, groups, style, speed, lang)
    elif engine in ("kokoro", "piper"):
        sung, report = line_tools.sing_line(voice, line_tools.Line(line.text, melody), bpm, speed=speed, style=style, cache=cache,
                                            fix_ending=bool(options.get("fix_ending", True)), lang=lang)
        report["engine"] = f"{engine}-stretched"
    else:
        raise ValueError(f"unknown voice '{voice}'; use kokoro:<voice>, piper:<voice> or diffsinger:<folder>")
    report["lead_rest_beats"] = lead_beats
    if path:
        os.makedirs(cache, exist_ok=True)
        _save(path, sung, report)
    return sung, report


def describe_voice(voice: str) -> dict:
    """What an agent should tell the user about a voice before using it."""
    engine = engine_of(voice)
    if engine == "diffsinger":
        from . import diffsinger
        return diffsinger.voicebank(voice.split(":", 1)[1].partition("#")[0]).describe()
    info = dict(tts.VOICES.get(voice, {"engine": engine, "note": "not in the built-in list; check the model card"}))
    info["voice"] = voice
    return info
