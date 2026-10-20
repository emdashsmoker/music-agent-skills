# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Vocal commands: list voices, check sung lines by recognition and pictures, compare lyric candidates."""
from __future__ import annotations

import copy
import json
import os
import unicodedata

WEAK_SCORE = 0.85
LINE_TAIL_S = 0.35
ROUGH_PERIODICITY = 0.6         # a sung vowel less periodic than this is mostly breath or hiss
QUIET_DB = 8.0                  # a sung vowel this far under the line's typical vowel is swallowed
MIN_VOWEL_S = 0.06              # shorter vowels cannot be judged
PITCH_SEARCH = 0.08             # the vowel's pitch is looked for this far around the written note
SPEECH_VOICES = [
    ("kokoro", "af_heart", "female, clear diction; the default"),
    ("kokoro", "am_michael", "male, clear diction"),
    ("piper", "en_US-ljspeech-medium", "female, natural, soft consonants; dataset: public domain"),
    ("piper", "en_US-bryce-medium", "male, steady; dataset: public domain"),
    ("piper", "en_US-kristin-medium", "female, crisp, syllables tend to detach; dataset: public domain"),
    ("piper", "en_US-lessac-medium", "female, mature tone; dataset licensed for research purposes only, "
                                     "tell the user before choosing it"),
    ("piper", "en_US-libritts_r-medium", "multi-speaker set, darker and lo-fi; dataset: CC BY 4.0, credit required"),
]


def _vocal_tracks(project: dict, wanted: str | None) -> list:
    tracks = [t for t in project["tracks"] if t.get("kind") == "vocal" and (not wanted or t["name"] == wanted)]
    if not tracks:
        raise SystemExit("ERROR: no vocal track" + (f" named {wanted!r}" if wanted else "") + " in this song")
    return tracks


def _pitch_error_cents(audio, notes: list, origin: float) -> float | None:
    """Median distance between the sung pitch and the written notes, away from note edges."""
    import numpy as np
    import pyworld
    from .dsp import SR
    f0, times = pyworld.harvest(audio.astype(np.float64), SR, f0_floor=60.0, f0_ceil=900.0, frame_period=5.0)
    times = times + origin
    errors = []
    for start, dur, midi, _tie in notes:
        inside = (times > start + 0.09) & (times < start + dur - 0.04) & (f0 > 0)
        if inside.any():
            errors += list(np.abs(1200 * np.log2(f0[inside] / (440.0 * 2 ** ((midi - 69) / 12)))))
    return round(float(np.median(errors)), 1) if errors else None


def _vowel_periodicity(piece, midi: float) -> float:
    """Median normalised autocorrelation at the note's pitch period (0 = noise, 1 = clean voice)."""
    import numpy as np
    from .dsp import SR
    period = SR / (440.0 * 2 ** ((midi - 69) / 12))
    frame, hop, values = int(0.03 * SR), int(0.01 * SR), []
    lags = range(int(period * (1 - PITCH_SEARCH)), int(period * (1 + PITCH_SEARCH)) + 2)
    for start in range(0, len(piece) - frame - lags[-1], hop):
        x = piece[start:start + frame]
        energy = float(np.sum(x * x))
        values.append(max(float(np.sum(x * piece[start + lag:start + lag + frame])) /
                          (np.sqrt(energy * float(np.sum(piece[start + lag:start + lag + frame] ** 2))) + 1e-12) for lag in lags))
    return float(np.median(values)) if values else 1.0


def rough_syllables(audio, line_start_s: float, notes: list, spans: list, labels: list) -> list:
    """Sung vowels that came out as noise or nearly silent: the faults a listener hears at once and a recogniser
    forgives. Returns [{'syllable', 'problem', 'periodicity', 'level_db'}]."""
    import numpy as np
    from .dsp import SR
    measured = []
    for span, label in zip(spans, labels):
        if not span or span[1] - span[0] < MIN_VOWEL_S:
            measured.append(None)
            continue
        a, b = int((line_start_s + span[0] + 0.01) * SR), int((line_start_s + span[1] - 0.01) * SR)
        piece = audio[max(a, 0):b].astype(np.float64)
        middle = 0.5 * (span[0] + span[1])
        midi = next((m for s, d, m, _ in notes if s <= middle < s + d), notes[-1][2])
        level = 10 * np.log10(float(np.mean(piece ** 2)) + 1e-12) if len(piece) else -120.0
        measured.append((label, _vowel_periodicity(piece, midi), level))
    levels = [m[2] for m in measured if m]
    typical = float(np.median(levels)) if levels else 0.0
    found = []
    for item in measured:
        if not item:
            continue
        label, periodic, level = item
        problem = "noise" if periodic < ROUGH_PERIODICITY else "quiet" if level < typical - QUIET_DB else None
        if problem:
            found.append({"syllable": label, "problem": problem, "periodicity": round(periodic, 2),
                          "level_db": round(level - typical, 1)})
    return found


def check_track(project: dict, track: dict, build: str, out_dir: str, plots_for: str, model: str) -> list:
    from . import asr, export, mixer, plots, singing, vocal
    from .dsp import SR
    n = mixer.total_samples(project, 2.0)
    spb = 60.0 / project["meta"]["bpm"]
    lead_only = {**track, "layers": []}              # doubles and harmonies are sung at render time; the check needs the lead
    name, audio, _settings = vocal.render_vocal_track(project, lead_only, n, build)[0]
    vocal_dir = os.path.join(out_dir, "vocals")
    export.write_audio(os.path.join(vocal_dir, f"{name}_dry.wav"), audio)
    with open(os.path.join(build, f"vocal_{name}.json"), encoding="utf-8") as handle:
        report = json.load(handle)
    language = (track.get("vocal") or {}).get("lang")
    model = asr.model_for(model, language)
    rows = []
    for index, (line, info) in enumerate(zip(track["lines"], report)):
        notes = [(o * spb, d * spb, m, t) for o, d, m, t in line["notes"]]
        start = line["start"] * spb
        pre = float(info.get("pre_roll_s", 0.1))
        a = max(0, int((start - pre - 0.03) * SR))
        b = min(len(audio), int((start + notes[-1][0] + notes[-1][1] + LINE_TAIL_S) * SR))
        if index + 1 < len(track["lines"]):             # stop before the next line's pick-up consonants
            following = track["lines"][index + 1]["start"] * spb - float(report[index + 1].get("pre_roll_s", 0.1)) - 0.03
            b = max(a + SR // 10, min(b, int(following * SR)))
        piece = audio[a:b]
        heard = asr.transcribe(piece, SR, model, asr.language_code(language) if not model.endswith(".en") else None)
        row = {"line": index + 1, "section": line["section"], "text": line["text"], "heard": heard,
               "score": asr.similarity(line["text"], heard),
               "pitch_error_cents": _pitch_error_cents(piece, notes, a / SR - start),
               "lag_ms": info.get("lag_ms"), "ending": info.get("ending"), "speed": info.get("speed"),
               "forced_voiced_frames": info.get("forced_voiced_frames"),
               "source_median_midi": info.get("source_median_midi"), "range": f"{info.get('lowest')}..{info.get('highest')}"}
        if info.get("cut_s"):
            row["cut_s"] = info["cut_s"]
        if info.get("vowel_spans"):
            row["rough"] = rough_syllables(audio, start, notes, info["vowel_spans"], info.get("syllables", []))
        rows.append(row)
        if plots_for == "all" or (plots_for == "weak" and (row["score"] < WEAK_SCORE or row.get("rough"))) \
                or plots_for == str(index + 1):
            labels = [(group[0], text) for group, text in zip(singing.note_groups(notes), info.get("syllables", []))]
            row["picture"] = plots.vocal_line(piece, SR, os.path.join(vocal_dir, f"{name}_line{index + 1:02d}.png"),
                                              a / SR - start, notes, labels)
            export.write_audio(os.path.join(vocal_dir, f"{name}_line{index + 1:02d}.wav"), piece)
    return rows


def cmd_voices(args) -> int:
    from . import speech
    print("speech engines sung through the built-in converter (models download on first use):")
    for engine, voice, note in SPEECH_VOICES:
        print(f"  engine: {engine:7s} voice: {voice:26s} {note}")
    print("  any other Kokoro voice id or Piper voice id (or a path to a Piper .onnx file) also works;")
    print("  usage terms differ per voice: read the voice's model card and tell the user before the first render")
    print("singing voicebanks: engine: diffsinger, voice: <folder of a voicebank the user supplied>")
    print(f"models directory: {speech.models_dir()}")
    return 0


def cmd_vocal_check(args) -> int:
    from . import songfile, vocal
    project = songfile.load(args.song, args.sections)
    out_dir = args.output or os.path.splitext(args.song)[0].removesuffix(".project") + "_out"
    build = os.path.join(out_dir, "build")
    os.makedirs(build, exist_ok=True)
    everything = {}
    try:
        for track in _vocal_tracks(project, args.track):
            rows = check_track(project, track, build, out_dir, args.plots, args.asr_model)
            everything[track["name"]] = rows
            scores = [r["score"] for r in rows]
            print(f"== {track['name']}: {len(rows)} lines, mean match {sum(scores) / len(scores):.2f}, "
                  f"{sum(s < WEAK_SCORE for s in scores)} below {WEAK_SCORE}, "
                  f"{sum(bool(r.get('rough')) for r in rows)} with rough syllables ==")
            for r in rows:
                ending = r.get("ending") or {}
                mark = "weak" if r["score"] < WEAK_SCORE else "ok  "
                fixed = "ending resung" if ending.get("fixed") else ("ending dies" if ending.get("dies") else "")
                rough = "  ROUGH: " + ", ".join(f"/{x['syllable']}/ {x['problem']}" for x in r["rough"]) if r.get("rough") else ""
                cut = "  CUT: " + vocal.CUT_ADVICE.format(cut=r["cut_s"]) if r.get("cut_s") else ""
                print(f"  {r['line']:2d} {mark} {r['score']:.2f}  pitch±{r['pitch_error_cents']}c  {r['text']!r} -> {r['heard']!r}  {fixed}{rough}{cut}")
            voices = [r["source_median_midi"] for r in rows if r["source_median_midi"]]
            if voices:
                from . import theory
                centre = sorted(voices)[len(voices) // 2]
                print(f"  voice speaks around {theory.midi_to_name(round(centre))}; lines span {rows[0]['range']} ...")
    except vocal.VocalError as error:
        print(f"ERROR: {error}")
        return 2
    with open(os.path.join(out_dir, "vocal_check.json"), "w", encoding="utf-8") as handle:
        json.dump(everything, handle, ensure_ascii=False, indent=1)
    print(f"dry vocal stems, line clips and pictures: {os.path.join(out_dir, 'vocals')}")
    print("scores and ROUGH marks point at lines to look at and listen to; they do not decide on their own")
    return 0


def cmd_vocal_try(args) -> int:
    """Sing alternative wordings on the notes of one line and compare how well each is recognised."""
    from . import asr, export, mixer, songfile, vocal
    from .dsp import SR
    project = songfile.load(args.song)
    track = _vocal_tracks(project, args.track)[0]
    line = track["lines"][args.line - 1]
    language = (track.get("vocal") or {}).get("lang")
    model = asr.model_for(args.asr_model, language)
    out_dir = args.output or os.path.splitext(args.song)[0].removesuffix(".project") + "_out"
    build = os.path.join(out_dir, "build")
    os.makedirs(os.path.join(out_dir, "vocals"), exist_ok=True)
    length = line["notes"][-1][0] + line["notes"][-1][1]
    print(f"line {args.line}: {line['text']!r} on {len(line['notes'])} notes")
    # Typed wordings arrive as the terminal sends them; a decomposed one (NFD) lost its accents (schön sung as schon).
    wordings = [unicodedata.normalize("NFC", text) for text in args.text or []]
    for number, text in enumerate([line["text"]] + wordings):
        trial = copy.deepcopy(project)
        trial["meta"]["beats"] = length + 8
        trial_track = copy.deepcopy(track)
        trial_track["lines"] = [{**line, "text": text, "start": 2.0}]
        trial_track["lines"][0].pop("phonemes", None)
        trial_track["layers"] = []
        trial_track["calibration_lines"] = track["lines"]
        n = mixer.total_samples(trial, 1.0)
        try:
            _name, audio, _ = vocal.render_vocal_track(trial, trial_track, n, build)[0]
        except vocal.VocalError as error:
            print(f"  {number}: {text!r}: {error}")
            continue
        heard = asr.transcribe(audio, SR, model, asr.language_code(language) if not model.endswith(".en") else None)
        path = export.write_audio(os.path.join(out_dir, "vocals", f"try_line{args.line}_{number}.wav"), audio)
        label = "current" if number == 0 else f"option {number}"
        print(f"  {label}: {asr.similarity(text, heard):.2f}  {text!r} -> {heard!r}  [{path}]")
    print("play the clips to the user before replacing a line they wrote or approved")
    return 0


def cmd_diffsinger_inspect(args) -> int:
    from . import diffsinger
    print(json.dumps(diffsinger.inspect(args.path), ensure_ascii=False, indent=1))
    return 0


def register(sub) -> None:
    p = sub.add_parser("voices", help="list vocal engines and voices")
    p.set_defaults(run=cmd_voices)

    p = sub.add_parser("vocal-check", help="sing the vocal tracks dry and test every line by speech recognition")
    p.add_argument("song")
    p.add_argument("-o", "--output")
    p.add_argument("--track")
    p.add_argument("--sections", help="only these sections")
    p.add_argument("--plots", default="weak", help="weak (default), all, none, or a line number")
    p.add_argument("--asr-model", help="faster-whisper model (setting asr_model, default base.en); an English-only model switches to its multilingual twin when the track's lang is not English")
    p.add_argument("--models", help="directory holding voice models")
    p.set_defaults(run=cmd_vocal_check)

    p = sub.add_parser("vocal-try", help="compare alternative wordings on the notes of one lyric line")
    p.add_argument("song")
    p.add_argument("--line", type=int, required=True, help="1-based line number within the vocal track")
    p.add_argument("--text", action="append", help="a candidate wording; repeat for several")
    p.add_argument("--track")
    p.add_argument("-o", "--output")
    p.add_argument("--asr-model", help="faster-whisper model (setting asr_model)")
    p.add_argument("--models", help="directory holding voice models")
    p.set_defaults(run=cmd_vocal_try)

    p = sub.add_parser("diffsinger-inspect", help="describe a DiffSinger voicebank folder the user supplied")
    p.add_argument("path")
    p.set_defaults(run=cmd_diffsinger_inspect)
