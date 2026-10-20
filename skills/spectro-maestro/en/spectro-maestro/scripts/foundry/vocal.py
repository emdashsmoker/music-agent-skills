# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Vocal tracks: lyric lines with notes -> sung stems.

Engines
  kokoro, piper   a speech voice converted to singing (speech.py + singing.py)
  diffsinger      a singing voicebank supplied by the user (diffsinger.py)

The speech path adds three things on top of the conversion itself:
  - per-song timing calibration: the engines report phone times late, each line is measured against
    its own audio and lines without clear landmarks borrow the median of the others
  - sung endings: a speech voice lets the last word die away; such a line is spoken once more with a
    carrier word after it and the fully voiced last syllable is spliced in
  - layers: doubles and diatonic harmonies re-sung from the same lines"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re

import numpy as np
from scipy import signal

from . import mixprofile, phonetics, settings, singing, speech, theory
from .dsp import SR

VOCAL_VERSION = 25
DEFAULT_ENGINE = {"engine": "kokoro", "voice": "af_heart"}
SPOKEN_SYLLABLE_S = 0.21        # typical syllable length of the speech engines at speed 1
SPEED_RANGE = (0.7, 1.15)
MIN_LAG_LANDMARKS = 6           # fewer boundary observations than this do not pin the engine's lag down
# A word spoken after the line so that the line's last word is no longer sentence-final.
# It must start with a stop: the cut then falls in the stop's silence. Languages not listed are skipped.
CARRIER_WORDS = {"en": "but", "de": "doch", "es": "pero", "fr": "puis", "it": "poi", "pt": "pois", "nl": "dan"}
ENDING_MIN_PERIODICITY = 0.5    # the last vowel has died when its best instant is less periodic than this
ENDING_QUIET_DB = 9.0           # or when that instant is this far below the line's typical vowel
SPLICE_FADE_S = 0.008
CUT_ADVICE = ("its first {cut:g} s fall before the song starts and are cut (its opening consonants); start the line "
              "later or give the song a bar before it")
LINE_LEVEL_LIMIT_DB = 4.0
MIN_BREATH_BEATS = 0.5          # lyric lint: less room than this between two lines leaves no breath
FAST_SYLLABLE_S, FAST_SYLLABLE_COUNT = 0.2, 3    # lyric lint: this many notes this short make a line fast
REST_IN_WORD_S = 0.12           # lyric lint: a gap this long between two syllables of one word splits the word
# lyric lint: a note held this many beats, then a last syllable this fraction of it or shorter. The last word, usually the
# rhyme and the point of the line, is over before it is heard.
CLIP_HELD_BEATS, CLIP_RATIO = 2.0, 0.25
LAYER_DEFAULTS = {
    "double": {"gain_db": -9.0, "pan": 0.55, "detune": 7.0, "delay_ms": 14.0},
    "harmony": {"gain_db": -8.0, "pan": -0.35, "steps": 2},
}


VocalError = singing.VocalError


def _config(track: dict) -> dict:
    config = {**DEFAULT_ENGINE, "lang": None, "speed": None, "style": {}, "ending_fix": True, "level_lines": True}
    config.update(copy.deepcopy(track.get("vocal") or {}))
    return config


def _cache_dir(build_dir: str) -> str:
    return os.path.join(build_dir, "vocal_cache")


def _line_seconds(line: dict, spb: float) -> list:
    return [(offset * spb, dur * spb, midi, tie) for offset, dur, midi, tie in line["notes"]]


def _speed_for(notes: list, config: dict) -> float:
    """Speak slower for slow melodies and faster for quick ones, so less stretching is needed."""
    if config.get("speed"):
        return float(config["speed"])
    groups = singing.note_groups(notes)
    typical = float(np.median([g[1] - g[0] for g in groups]))
    return float(np.clip(SPOKEN_SYLLABLE_S / max(typical, 0.05), *SPEED_RANGE))


# ---------------------------------------------------------------- speech units with analysis

class LineSource:
    """Everything known about one spoken line: unit (aligned), WORLD analysis, syllables."""

    def __init__(self, unit, analysis: dict, frames: dict, key: str, lang: str | None = None):
        self.unit, self.analysis, self.frames, self.key = unit, analysis, frames, key
        self.syllables = phonetics.syllabify(unit.phones, lang)


def _raw_unit(backend, cache: speech.UnitCache, phones: str, speed: float) -> tuple:
    """(unit with the engine's own timings, frames, analysis, key), all cached on disk."""
    key = cache.key(backend, phones, speed, f"v{VOCAL_VERSION}")
    unit_path, analysis_path = cache.path(key, "raw"), cache.path(key, "world")
    if os.path.exists(unit_path) and os.path.exists(analysis_path):
        unit = speech.Unit.load(unit_path)
        data = np.load(analysis_path)
        frames = {name: data[name] for name in ("f0", "voiced", "level", "sibilant")}
        analysis = {"f0": data["f0_refined"], "sp": data["sp"].astype(np.float64), "ap": data["ap"].astype(np.float64),
                    "sr": unit.sr}
        return unit, frames, analysis, key
    unit = backend.synthesize(phones, speed)
    frames = speech.acoustic_frames(unit.audio, unit.sr)
    analysis = singing.analyse(unit.audio, unit.sr, frames["f0"])
    n = min(len(frames["f0"]), len(analysis["f0"]))
    analysis = {k: (v[:n] if k != "sr" else v) for k, v in analysis.items()}
    frames = {name: values[:n] for name, values in frames.items()}
    frames["voiced"] = analysis["f0"] > 0               # the analysis knows breath from voice; the pitch tracker alone does not
    unit.save(unit_path)
    np.savez(analysis_path, f0=frames["f0"], voiced=frames["voiced"], level=frames["level"], sibilant=frames["sibilant"],
             f0_refined=analysis["f0"], sp=analysis["sp"].astype(np.float32), ap=analysis["ap"].astype(np.float32))
    return unit, frames, analysis, key


def _aligned(backend, cache, phones: str, speed: float, fallback_lag: float | None) -> LineSource:
    unit, frames, analysis, key = _raw_unit(backend, cache, phones, speed)
    speech.align_unit(unit, frames, None if fallback_lag is None else fallback_lag / speed)
    source = LineSource(unit, analysis, frames, key, backend.lang)
    unit.info["vowel_edges_moved"] = singing.settle_vowels(unit.phones, source.syllables, analysis)
    return source


def song_lag(backend, cache, jobs: list) -> float | None:
    """How late the engine reports its sounds, measured over every line of the song, in seconds at speed 1.
    The lag is a fixed stretch of the engine's own timeline, so it grows as the engine speaks slower: every
    observation is multiplied by its line's speed here and divided by it again when it is applied.
    Hiss boundaries are the sharpest evidence; with too few of them voicing boundaries join in, and a song
    without either falls back on the best overall fit of each line."""
    hiss, every, fitted = [], [], []
    for phones, speed in jobs:
        unit, frames, _analysis, _key = _raw_unit(backend, cache, phones, speed)
        offsets = speech.landmark_offsets(unit.phones, frames)
        hiss += [o * speed for o in offsets["sibilant"]]
        every += [o * speed for o in offsets["sibilant"] + offsets["voicing"]]
        fitted.append(speech.measure_lag(unit.phones, frames)[0] * speed)
    for observations in (hiss, every):
        if len(observations) >= MIN_LAG_LANDMARKS:
            return float(np.median(observations))
    return float(np.median(fitted)) if fitted else None


# ---------------------------------------------------------------- sung endings

def ending_state(source: LineSource) -> dict:
    """Can the last vowel of the spoken line carry a held note? A speech voice often lets the final word fade to a
    whisper. The judgement is made at the instant that would be held: unvoiced there, hardly periodic, or much
    quieter than the same instant of the line's other vowels means the ending has died away."""
    unit, syllables = source.unit, source.syllables
    if not syllables:
        return {"dies": False}
    quality = [singing.hold_quality(unit.phones, s.nucleus, source.analysis) for s in syllables]
    last = quality[-1]
    drop = float(np.median([q["level_db"] for q in quality[:-1]]) - last["level_db"]) if len(quality) >= 3 else 0.0
    a, b = unit.phones[syllables[-1].nucleus[0]].start, unit.phones[syllables[-1].nucleus[-1]].end
    first = int(a / singing.FRAME_S)
    voiced = source.frames["voiced"][first:max(int(b / singing.FRAME_S), first + 1)]
    dies = (not last["voiced"]) or last["periodicity"] < ENDING_MIN_PERIODICITY or drop > ENDING_QUIET_DB
    return {"dies": bool(dies), "hold_periodicity": round(last["periodicity"], 2), "drop_db": round(drop, 1),
            "voiced_share": round(float(voiced.mean()) if len(voiced) else 0.0, 2)}


def with_sung_ending(backend, cache, source: LineSource, text: str, speed: float, fallback_lag) -> LineSource | None:
    """Splice the last syllable of 'text + carrier word' onto the plain take. None when it cannot be done safely."""
    carrier = CARRIER_WORDS.get(str(backend.lang or "")[:2].lower())
    if not carrier:
        return None
    phones = source.unit.text
    extended = backend.phonemize(f"{text.rstrip(' .,!?;:')} {carrier}")

    def bare(text_phones: str) -> str:                  # stress may move when a word follows; the sounds must not
        return "".join(c for c in text_phones.rstrip(" .,!?;:") if c not in phonetics.STRESS_MARKS)
    if not (bare(extended).startswith(bare(phones)) and len(bare(extended)) > len(bare(phones))):
        return None                                     # the extra word changed how the line itself is said
    donor = _aligned(backend, cache, extended, speed, fallback_lag)
    plain, count = source.unit, len(source.syllables)
    if len(donor.syllables) <= count:
        return None
    last_plain, last_donor = source.syllables[-1], donor.syllables[count - 1]
    plain_symbols = [plain.phones[i].symbol for i in last_plain.phones]
    donor_symbols = [donor.unit.phones[i].symbol for i in last_donor.phones]
    if plain_symbols != donor_symbols:
        return None
    sr = plain.sr
    first, donor_first, donor_last = last_plain.phones[0], last_donor.phones[0], last_donor.phones[-1]
    cut, donor_cut = plain.phones[first].start, donor.unit.phones[donor_first].start
    donor_end = donor.unit.phones[donor_last].end
    head = plain.audio[:int(cut * sr)].astype(np.float64)
    tail = donor.unit.audio[int(donor_cut * sr):int(donor_end * sr)].astype(np.float64)
    if count >= 2:                                      # same loudness as the plain take, judged on the syllable before
        def vowel_rms(unit, syllable):
            a, b = unit.phones[syllable.nucleus[0]].start, unit.phones[syllable.nucleus[-1]].end
            piece = unit.audio[int(a * sr):int(b * sr)].astype(np.float64)
            return float(np.sqrt(np.mean(piece ** 2))) if len(piece) else 0.0
        before, donor_before = vowel_rms(plain, source.syllables[-2]), vowel_rms(donor.unit, donor.syllables[count - 2])
        if before > 0 and donor_before > 0:
            tail = tail * float(np.clip(before / donor_before, 0.5, 2.0))
    fade = min(int(SPLICE_FADE_S * sr), len(head), len(tail))
    ramp = np.linspace(0.0, 1.0, fade) if fade else np.zeros(0)
    joined = np.concatenate([head[:len(head) - fade], head[len(head) - fade:] * (1 - ramp) + tail[:fade] * ramp,
                             tail[fade:], np.zeros(int(0.05 * sr))]).astype(np.float32)
    shift = cut - fade / sr - donor_cut
    phones_out = [copy.copy(p) for p in plain.phones[:first]]
    for index in range(donor_first, donor_last + 1):
        phone = copy.copy(donor.unit.phones[index])
        phone.start, phone.end = phone.start + shift, phone.end + shift
        phones_out.append(phone)
    phones_out.append(phonetics.Phone("$", phones_out[-1].end, len(joined) / sr, "pause", 0, phones_out[-1].word + 1))
    unit = speech.Unit(joined, sr, phones_out, phones, {**plain.info, "sung_ending": carrier})
    frames = speech.acoustic_frames(unit.audio, unit.sr)
    analysis = singing.analyse(unit.audio, unit.sr, frames["f0"])
    n = min(len(frames["f0"]), len(analysis["f0"]))
    analysis = {k: (v[:n] if k != "sr" else v) for k, v in analysis.items()}
    frames = {name: values[:n] for name, values in frames.items()}
    frames["voiced"] = analysis["f0"] > 0
    return LineSource(unit, analysis, frames, source.key + ".ending", backend.lang)


# ---------------------------------------------------------------- one line, one take

def line_source(backend, cache, line: dict, config: dict, speed: float, fallback_lag) -> tuple:
    """Spoken source of a lyric line, with its ending repaired when needed. Returns (source, diagnostics)."""
    phones = line.get("phonemes") or backend.phonemize(line["text"])
    source = _aligned(backend, cache, phones, speed, fallback_lag)
    state = ending_state(source)
    info = {"text": line["text"], "phones": phones, "speed": round(speed, 3), **source.unit.info,
            "ending": {**state, "fixed": False}}
    if config.get("ending_fix", True) and state["dies"] and "phonemes" not in line:
        fixed = with_sung_ending(backend, cache, source, line["text"], speed, fallback_lag)
        if fixed is not None:
            after = ending_state(fixed)
            info["ending"] = {**state, "fixed": True, "hold_periodicity_after": after.get("hold_periodicity"),
                              "drop_db_after": after.get("drop_db")}
            source = fixed
    voiced = source.analysis["f0"][source.analysis["f0"] > 0]
    info["source_median_midi"] = round(float(69 + 12 * np.log2(np.median(voiced) / 440.0)), 1) if len(voiced) else None
    info["syllables"] = [phonetics.syllable_text(source.unit.phones, s) for s in source.syllables]
    return source, info


def sing_line(source: LineSource, notes: list, style: dict, seed: int) -> tuple:
    groups = singing.note_groups(notes)
    if len(groups) != len(source.syllables):
        spelled = " | ".join(phonetics.syllable_text(source.unit.phones, s) for s in source.syllables)
        raise VocalError(f"{source.unit.text!r} is spoken in {len(source.syllables)} syllables ({spelled}) "
                         f"but the line has {len(groups)} notes. Add or remove notes, tie notes with ~ for one "
                         f"syllable on several notes, or respell the word.")
    return singing.sing(source.unit, source.analysis, source.syllables, notes, style, seed)


def _to_mix_rate(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return audio
    divisor = np.gcd(SR, sr)
    return signal.resample_poly(audio, SR // divisor, sr // divisor).astype(np.float32)


def _voiced_rms_db(audio: np.ndarray) -> float:
    loud = audio[np.abs(audio) > 0.02 * (np.max(np.abs(audio)) + 1e-9)]
    return float(10 * np.log10(np.mean(loud.astype(np.float64) ** 2) + 1e-12)) if len(loud) else -80.0


def render_speech_lines(project: dict, track: dict, lines: list, n: int, build_dir: str, variant: dict | None = None) -> tuple:
    """All lines of a speech-engine vocal track as one mono stem. Returns (audio, per-line diagnostics)."""
    config = _config(track)
    variant = variant or {}
    backend = speech.backend_for(config["engine"], config["voice"], config.get("lang"))
    cache = speech.UnitCache(_cache_dir(build_dir))
    spb = 60.0 / project["meta"]["bpm"]
    style = {**config.get("style", {}), **variant.get("style", {})}
    jobs = []
    for line in lines:
        notes = _line_seconds(line, spb)
        jobs.append((line.get("phonemes") or backend.phonemize(line["text"]), _speed_for(notes, config), notes))
    calibration = [(phones, speed) for phones, speed, _ in jobs]
    for line in track.get("calibration_lines") or []:    # a trial of one line still uses the whole song's measurement
        calibration.append((line.get("phonemes") or backend.phonemize(line["text"]), _speed_for(_line_seconds(line, spb), config)))
    fallback = song_lag(backend, cache, calibration)
    out = np.zeros(n, dtype=np.float32)
    takes, report = [], []
    for index, (line, (phones, speed, notes)) in enumerate(zip(lines, jobs)):
        source, info = line_source(backend, cache, line, config, speed, fallback)
        seed = int(hashlib.sha1(f"{project['meta']['seed']}|{track['name']}|{index}|{variant.get('seed', 0)}".encode()).hexdigest()[:8], 16)
        shifted = [(s, d, m + variant.get("transpose", {}).get((index, k), 0) + variant.get("detune_semitones", 0.0), t)
                   for k, (s, d, m, t) in enumerate(notes)]
        audio, pre_roll, sung = sing_line(source, shifted, style, seed)
        spans = []                                       # where each syllable's vowel sounds, seconds from the line start
        for syllable in source.syllables:
            own = [seg for seg in sung["segments"] if seg[4] in syllable.nucleus]
            spans.append([round(min(seg[0] for seg in own), 3), round(max(seg[1] for seg in own), 3)] if own else None)
        info.update({"forced_voiced_frames": sung["forced_voiced_frames"], "spliced_consonants": sung["spliced_consonants"],
                     "vowel_spans": spans,
                     "start_s": round(line["start"] * spb, 3), "pre_roll_s": round(pre_roll, 3),
                     "lowest": theory.midi_to_name(min(m for _, _, m, _ in notes)),
                     "highest": theory.midi_to_name(max(m for _, _, m, _ in notes))})
        takes.append((line, _to_mix_rate(audio, source.unit.sr), pre_roll))
        report.append(info)
    levels = [_voiced_rms_db(audio) for _line, audio, _ in takes]
    typical = float(np.median(levels)) if levels else 0.0
    delay = variant.get("delay_ms", 0.0) / 1000.0
    for (line, audio, pre_roll), level, info in zip(takes, levels, report):
        if config.get("level_lines", True):
            audio = audio * 10.0 ** (float(np.clip(typical - level, -LINE_LEVEL_LIMIT_DB, LINE_LEVEL_LIMIT_DB)) / 20.0)
        at = int((line["start"] * spb - pre_roll + delay) * SR)
        if at < 0:                                   # sound before the song start cannot be played: it is cut
            cut = singing.audible_cut(audio, -at, SR)
            if cut > singing.AUDIBLE_CUT_S:
                info["cut_s"] = round(cut, 3)
            audio, at = audio[-at:], 0
        end = min(n, at + len(audio))
        if end > at:
            out[at:end] += audio[:end - at]
    return out, report


# ---------------------------------------------------------------- layers and the track

def _harmony_shifts(project: dict, lines: list, steps: int) -> dict:
    """Per-note semitone shifts for a diatonic harmony that lands on chord tones where the plain step would grind."""
    key = theory.parse_key(project["meta"]["key"])
    shifts = {}
    for index, line in enumerate(lines):
        section = next((s for s in reversed(project["sections"]) if s["start"] <= line["start"] + 1e-6), project["sections"][0])
        transpose = section.get("transpose", 0)
        for k, (offset, _dur, midi, _tie) in enumerate(line["notes"]):
            target = key.step(midi - transpose, steps) + transpose
            beat = line["start"] + offset
            chord = next((c for c in reversed(project["chords"]) if c["start"] <= beat + 1e-6 < c["start"] + c["dur"] + 1e-6), None)
            if chord:
                tones = {(chord["root"] + i) % 12 for i in chord["intervals"]}
                if target % 12 not in tones and any((target - tone) % 12 == 1 for tone in tones):
                    chord_obj = theory.Chord("", "", chord["root"], tuple(chord["intervals"]), chord["bass"])
                    target = theory.nearest_chord_tone(target, chord_obj, 1 if steps > 0 else -1)
            shifts[(index, k)] = target - midi
    return shifts


def _layer_lines(track: dict, layer: dict) -> list:
    wanted = layer.get("sections")
    return [line for line in track.get("lines", []) if not wanted or line["section"] in wanted]


def render_vocal_track(project: dict, track: dict, n: int, build_dir: str, profile: dict | None = None) -> list:
    """Stems of a vocal track: [(name, mono audio, mix overrides)]. The lead comes first, then its layers."""
    config = _config(track)
    lines = track.get("lines", [])
    if not lines:
        return []
    engine = config["engine"]
    cache_dir = _cache_dir(build_dir)
    os.makedirs(cache_dir, exist_ok=True)

    def render(name: str, chosen: list, variant: dict) -> np.ndarray:
        parts = [VOCAL_VERSION, config, chosen, variant.get("style"), variant.get("seed"),
                 sorted((str(k), v) for k, v in variant.get("transpose", {}).items()),
                 variant.get("delay_ms"), variant.get("detune_semitones"), project["meta"]["bpm"], project["meta"]["seed"]]
        model = speech.model_tag(engine)                 # another Kokoro revision sings another stem
        key = hashlib.sha1(json.dumps(parts + [model] if model else parts, sort_keys=True, default=str).encode()).hexdigest()[:20]
        path = os.path.join(cache_dir, f"stem_{key}.npy")
        report_path = os.path.join(build_dir, f"vocal_{name}.json")
        if os.path.exists(path) and os.path.exists(report_path):
            cached = np.load(path)                       # the same singing serves a vocal check and the full render
            return cached[:n] if len(cached) >= n else np.concatenate([cached, np.zeros(n - len(cached), dtype=cached.dtype)])
        if engine == "diffsinger":
            from . import diffsinger
            audio, report = diffsinger.render_lines(project, track, chosen, n, build_dir, variant)
        else:
            audio, report = render_speech_lines(project, track, chosen, n, build_dir, variant)
        np.save(path, audio)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=1)
        print(f"[vocal] {name}: {len(chosen)} lines sung with {engine}:{config['voice']}", flush=True)
        for index, info in enumerate(report):
            if info.get("cut_s"):
                print(f"[vocal] {name} line {index + 1} {info.get('text', '')!r}: {CUT_ADVICE.format(cut=info['cut_s'])}", flush=True)
        return audio

    lead_inserts = [] if (track.get("mix") or {}).get("dry") else copy.deepcopy(mixprofile.VOCAL_CHAIN)
    lead_inserts += copy.deepcopy((track.get("mix") or {}).get("inserts") or [])
    stems = [(track["name"], render(track["name"], lines, {}), {"inserts": lead_inserts})]
    backing = mixprofile.ROLE_DEFAULTS["backing"]
    for number, layer in enumerate(track.get("layers") or []):
        kind = layer.get("type", "double")
        if kind not in LAYER_DEFAULTS:
            raise VocalError(f"{track['name']}: unknown layer type {kind!r}; use double or harmony")
        settings = {**LAYER_DEFAULTS[kind], **layer}
        chosen = _layer_lines(track, layer)
        if not chosen:
            continue
        base = {**backing, "inserts": copy.deepcopy(lead_inserts), "gain_db": 0.0,
                "level": mixprofile.ROLE_DEFAULTS["vocal"]["level"] + float(settings["gain_db"])}
        if kind == "double":
            for side, sign in (("l", -1.0), ("r", 1.0)):
                variant = {"seed": number * 10 + (1 if sign < 0 else 2), "delay_ms": settings["delay_ms"] * (1.0 if sign > 0 else 0.6),
                           "style": {"formant": 0.12 * sign, "drift": 9.0}}
                variant["transpose"] = {}
                variant["detune_semitones"] = sign * settings["detune"] / 100.0
                audio = render(f"{track['name']}.double{number}{side}", chosen, variant)
                stems.append((f"{track['name']}.double{number}{side}", audio, {**base, "pan": sign * abs(settings["pan"])}))
        else:
            variant = {"seed": number * 10 + 5, "transpose": _harmony_shifts(project, chosen, int(settings["steps"])),
                       "style": {"vibrato_depth": 18.0}}
            stems.append((f"{track['name']}.harmony{number}", render(f"{track['name']}.harmony{number}", chosen, variant),
                          {**base, "pan": settings["pan"]}))
    return stems


# ---------------------------------------------------------------- lyric checks

def _metric_weight(beat_in_bar: float) -> int:
    """How strong a position in a 4/4 bar is: downbeat 4, beat three 3, other beats 2, off-beats 1, the rest 0."""
    for step, weight in ((4.0, 4), (2.0, 3), (1.0, 2), (0.5, 1)):
        if abs(beat_in_bar / step - round(beat_in_bar / step)) < 1e-6:
            return weight
    return 0


# Bright consonants spit, hiss and peak on the speech voices (see singing.py); a line built on them sounds spitty.
BRIGHT_CONSONANTS = set("tkpszʃʒʧʤ")
BRIGHT_SHARE = 0.6                 # bright sounds per syllable, in a line of BRIGHT_MIN_SYLLABLES or more (3 in 5)
BRIGHT_CLUSTER_WEIGHT = 2          # a cluster of two bright sounds (st, sk, ts, ks) counts this much: it spits the most
BRIGHT_MIN_SYLLABLES = 4
BRIGHT_RUN = 3                     # consecutive syllables on bright consonants
EE_SYMBOLS = {"i"}                 # the ee vowel: thin and sharp when held (the length mark is stripped first)
# Reduced vowels (the schwa of the, to, a, the first syllable of upon) and the tiny ɪ of it, its, sit: a spoken schwa lasts
# a few tens of milliseconds, so a note has almost nothing to hold. In a probe line a schwa held for half a second came out
# 18-22 dB under the line and 'the' sang as breath (periodicity 0.4); 'it' on a beat becomes the burst of its t.
REDUCED_VOWELS = set("əɐᵻɚ")
SHORT_LAX_VOWELS = {"ɪ"}
STRONG_BEAT_WEIGHT = 3             # downbeat or beat three (see _metric_weight)
EXPOSED_NOTE_S = 0.5               # a reduced or tiny vowel held this long is heard dying; shorter notes pass as in speech
WEAK_RUN = 3                       # weak function words in a row
# Function words that speech swallows (ported from synth-ventriloquist's lyric lint, same author); the last row opens on a reduced syllable.
WEAK_WORDS = {"a", "an", "the", "of", "in", "to", "at", "on", "for", "and", "or", "but", "is", "it", "its", "as", "by",
              "be", "am", "are", "was", "were", "that", "this", "with", "from", "so", "if", "than", "then", "some",
              "someone", "what", "when", "where", "will", "would", "could", "should", "can", "do", "does", "has", "have",
              "had", "i", "you", "he", "she", "we", "they", "me", "my", "your", "his", "her", "our", "their", "till", "may",
              "upon", "into", "onto", "about", "above", "across", "against", "along", "among", "around"}


def _bank_ipa(bank, line: dict, lang: str) -> str:
    """A DiffSinger line's phonemes as an IPA string, so the craft rules written for speech voices apply to it."""
    from . import diffsinger
    to_ipa = {}
    for ipa, arpabet in diffsinger.IPA_TO_ARPABET:
        to_ipa.setdefault(arpabet, ipa)
    words = diffsinger.line_words(bank, line, lang)
    return " ".join("".join(to_ipa.get(s.split("/")[-1].lower().rstrip("012"), s.split("/")[-1].lower()) for s in word) for word in words)


def _bright_weight(plist: list, syllable) -> int:
    """How many bright sounds a syllable carries at its edges, a cluster (st, sk, ts) counting as BRIGHT_CLUSTER_WEIGHT."""
    edges = sum(1 for i in syllable.onset + syllable.coda if plist[i].symbol[0] in BRIGHT_CONSONANTS)
    return min(edges, BRIGHT_CLUSTER_WEIGHT)


def lint_lyrics(project: dict, models: str | None = None) -> list:
    """Check every lyric line against the engine's own pronunciation, without synthesising audio."""
    settings.override("models_dir", models)
    issues = []
    spb = 60.0 / project["meta"]["bpm"]
    meter = project["meta"]["meter"]

    def issue(level, code, where, message):
        issues.append({"level": level, "code": code, "where": where, "message": message})

    for track in project["tracks"]:
        if track.get("kind") != "vocal":
            continue
        config = _config(track)
        lines = track.get("lines", [])
        for number, line in enumerate(lines):
            quick = sum(1 for note in line["notes"] if note[1] * spb < FAST_SYLLABLE_S)
            if quick >= FAST_SYLLABLE_COUNT:
                issue("info", "lyrics.fast_syllables", f"{track['name']} line {number + 1} {line['text']!r}",
                      f"{quick} notes are shorter than {FAST_SYLLABLE_S * 1000:.0f} ms; consonants start to blur at this speed. "
                      f"If the vocal check finds the line weak, give it one syllable per beat")
        for number, (line, following) in enumerate(zip(lines, lines[1:])):
            gap = following["start"] - (line["start"] + line["notes"][-1][0] + line["notes"][-1][1])
            if gap < MIN_BREATH_BEATS:
                issue("info", "lyrics.no_breath", f"{track['name']} line {number + 1} {line['text']!r}",
                      f"the next line starts {max(gap, 0):g} beats after this one ends; shorten the last note so the "
                      f"phrase can end and the next line's first consonants have room")
        backend = bank = None
        if config["engine"] == "diffsinger":
            # The bank's own lint checks pronunciation and syllable counts; the craft rules below then run on the
            # bank's phonemes rendered in IPA, since a voicebank blurs short syllables, spits on bright consonants and
            # swallows weak words much as a speech voice does. Bank dictionaries carry no stress, so the stress rule
            # stays quiet for them.
            from . import diffsinger
            issues += diffsinger.lint_lines(project, track)
            try:
                bank = diffsinger.voicebank(diffsinger._settings(track)["voice"])
            except Exception:
                continue
        else:
            try:
                backend = speech.backend_for(config["engine"], config["voice"], config.get("lang"))
            except Exception as error:                  # missing model or package: say what to do instead of crashing
                issue("error", "vocal.engine", track["name"], f"cannot load {config['engine']}:{config['voice']} ({error})")
                continue
        endings, low, high = [], 127, 0
        language = backend.lang if backend is not None else config.get("lang")
        for number, line in enumerate(track.get("lines", [])):
            where = f"{track['name']} line {number + 1} {line['text']!r}"
            if bank is not None:
                try:
                    phones = _bank_ipa(bank, line, config.get("lang") or "en")
                except Exception:
                    continue
            else:
                try:
                    phones = line.get("phonemes") or backend.phonemize(line["text"])
                except VocalError as error:             # characters the voice's language cannot read (speech.espeak_phonemes)
                    issue("error", "lyrics.unreadable", where, str(error))
                    continue
            symbols = ["^"] + list(phones) + ["$"]
            plist = phonetics.phones_from_tokens(symbols, [0.05] * len(symbols))
            syllables = phonetics.syllabify(plist, language)
            groups = singing.note_groups(_line_seconds(line, spb))
            if len(syllables) != len(groups):
                if backend is None:                     # the bank's own lint has reported it with the bank's spelling
                    continue
                words = []
                for word in line["text"].split():
                    alone = backend.phonemize(word)
                    wp = phonetics.phones_from_tokens(list(alone), [0.05] * len(alone))
                    words.append(f"{word}={len(phonetics.syllabify(wp, language))}")
                issue("error", "lyrics.syllables", where,
                      f"spoken in {len(syllables)} syllables but {len(groups)} notes. Per word: {' '.join(words)}. "
                      f"Syllables: {' | '.join(phonetics.syllable_text(plist, s) for s in syllables)}")
                continue
            for word in phones.split():
                if phonetics.unstable_count(word):
                    issue("info", "lyrics.unstable_word", where,
                          f"/{word}/ can be sung with one syllable more or fewer; give it one long note or respell it")
            section_start = next(s["start"] for s in reversed(project["sections"]) if s["start"] <= line["start"] + 1e-6)
            weights = [_metric_weight((line["start"] + g[0] / spb - section_start) % meter) for g in groups]
            lengths = [g[1] - g[0] for g in groups]
            by_word = {}
            for index, syllable in enumerate(syllables):
                by_word.setdefault(syllable.word, []).append(index)
            for indices in by_word.values():
                if len(indices) < 2:
                    continue
                stressed = [i for i in indices if syllables[i].stress == 2]
                for s in stressed:
                    rivals = [i for i in indices if i != s and syllables[i].stress == 0 and weights[i] > weights[s]
                              and lengths[i] >= lengths[s]]
                    if rivals:
                        issue("warn", "lyrics.stress", where,
                              f"stressed syllable /{phonetics.syllable_text(plist, syllables[s])}/ sits on a weaker beat than "
                              f"unstressed /{phonetics.syllable_text(plist, syllables[rivals[0]])}/; the word will sound mis-accented")
            for index in range(len(groups) - 1):
                if syllables[index].word == syllables[index + 1].word and groups[index + 1][0] - groups[index][1] >= REST_IN_WORD_S:
                    issue("warn", "lyrics.rest_in_word", where,
                          f"a rest falls inside a word, after /{phonetics.syllable_text(plist, syllables[index])}/; "
                          f"move the rest to a word boundary")
            last, last_len = syllables[-1], lengths[-1]
            kind = phonetics.ending_type(plist, last)
            endings.append(phonetics.syllable_text(plist, last)[len("".join(plist[i].symbol for i in last.onset)):])
            if last_len >= 2 * spb and kind == phonetics.STOP_ENDING:
                issue("warn", "lyrics.long_note_ending", where,
                      f"the last note is {last_len / spb:g} beats long but the word ends in a stop or fricative "
                      f"(/{phonetics.syllable_text(plist, last)}/); a word ending in an open vowel or a nasal holds better")
            # In beats, rounded: a length taken as end minus start misses an exact 2 beats by a float hair.
            held, tail = (round(lengths[-2] / spb, 6), round(last_len / spb, 6)) if len(lengths) >= 2 else (0.0, 0.0)
            if held >= CLIP_HELD_BEATS and tail <= CLIP_RATIO * held:
                issue("warn", "lyrics.clipped_line_end", where,
                      f"/{phonetics.syllable_text(plist, syllables[-2])}/ holds {held:g} beats, then the line ends on "
                      f"/{phonetics.syllable_text(plist, last)}/ in {tail:g} beats; the last word is over before it is heard. "
                      f"Hold the last word itself, or give it a beat or more and end on a rest")
            short = [g for g in groups if g[1] - g[0] < 0.11]
            if short:
                issue("warn", "lyrics.short_notes", where, f"{len(short)} notes shorter than 110 ms; syllables there will smear")
            weights = [_bright_weight(plist, s) for s in syllables]
            bright = [w > 0 for w in weights]
            longest, run = 0, 0
            for flag in bright:
                run = run + 1 if flag else 0
                longest = max(longest, run)
            crowded = len(bright) >= BRIGHT_MIN_SYLLABLES and sum(weights) >= BRIGHT_SHARE * len(bright)
            if crowded or longest >= BRIGHT_RUN:
                count = f"{sum(weights)} bright sounds over {len(bright)} syllables (st, sk, ts clusters count twice)" if crowded else f"{longest} syllables in a row"
                issue("warn", "lyrics.bright_consonants", where,
                      f"{count} on t, k, p, s, z or sh; the speech voices spit, hiss and peak there. Carry the line on "
                      f"voiced consonants (m, n, l, d, b, g, w, r) and keep those sounds to about one per word")
            text_words = re.findall(r"[a-z']+", line["text"].lower())
            aligned = len({s.word for s in syllables}) == len(text_words) and all(s.word < len(text_words) for s in syllables)
            weak = [aligned and text_words[s.word] in WEAK_WORDS for s in syllables]
            if weak and weak[0]:
                issue("info", "lyrics.weak_opening", where, f"opens on the weak word {text_words[0]!r}; recognisers and listeners catch a line better from a content word")
            run = 0
            for index, flag in enumerate(weak):
                run = run + 1 if flag else 0
                if run == WEAK_RUN:
                    issue("warn", "lyrics.weak_words_in_a_row", where, f"{WEAK_RUN} weak-word syllables in a row ending at /{phonetics.syllable_text(plist, syllables[index])}/")
            for index, syllable in enumerate(syllables):
                beats_held = lengths[index] / spb
                last_of_word = index + 1 == len(syllables) or syllables[index + 1].word != syllable.word
                if beats_held >= 2 and weak[index] and last_of_word and index + 1 != len(syllables):
                    issue("warn", "lyrics.weak_word_on_long_note", where, f"weak word {text_words[syllable.word]!r} holds {beats_held:g} beats")
                exposed = lengths[index] >= EXPOSED_NOTE_S or (weights[index] >= STRONG_BEAT_WEIGHT and beats_held >= 0.5)
                nucleus = plist[syllable.nucleus[0]].symbol.replace("ː", "") if len(syllable.nucleus) == 1 else ""
                spot = "a strong beat" if weights[index] >= STRONG_BEAT_WEIGHT else f"{lengths[index]:.2f} s"
                if exposed and nucleus in REDUCED_VOWELS and not (weak[index] and beats_held >= 2):
                    issue("warn", "lyrics.reduced_vowel_on_beat", where,
                          f"/{phonetics.syllable_text(plist, syllable)}/ puts a reduced vowel (the a of about, the e of the) on {spot}; the speech "
                          f"voices have almost no vowel there, so it sings as breath or a gap. Give it a short off-beat note and let a content word take the beat, or spell the strong form for the voice (too, thee, ay)")
                if exposed and nucleus in SHORT_LAX_VOWELS and syllable.coda and plist[syllable.coda[-1]].symbol[0] in BRIGHT_CONSONANTS:
                    issue("warn", "lyrics.short_vowel_on_beat", where,
                          f"/{phonetics.syllable_text(plist, syllable)}/ (it, its, sit) sits on {spot}; its vowel lasts a few tens of milliseconds, so the "
                          f"note becomes the burst of its consonant. Give it a short off-beat note or a word with a long vowel")
            for index, syllable in enumerate(syllables):     # a voicebank shapes its vowels; the thin held ee is a speech-voice fault
                if bank is None and lengths[index] >= 2 * spb and len(syllable.nucleus) == 1 and plist[syllable.nucleus[0]].symbol.replace("ː", "") in EE_SYMBOLS:
                    issue("info", "lyrics.held_ee", where,
                          f"/{phonetics.syllable_text(plist, syllable)}/ holds {lengths[index] / spb:g} beats on an ee vowel, which the speech voices "
                          f"sing thin and sharp; a word with ah, oh, oo or ay holds fuller, or fill it with style vowel_body: 1")
            pitches = [n[2] for n in line["notes"]]
            low, high = min(low, min(pitches)), max(high, max(pitches))
        if endings:
            issue("info", "lyrics.rhymes", track["name"], "line endings as sung: " + " / ".join(endings))
            issue("info", "vocal.range", track["name"],
                  f"melody spans {theory.midi_to_name(low)}..{theory.midi_to_name(high)}; after the first vocal render, "
                  f"vocal-check reports how far this is from the voice's own pitch")
    return issues
