# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Kokoro singing from the inside: the model's own decoder is given the note lengths and the melody.

Kokoro first predicts how long each sound lasts, then a pitch curve and an energy curve, and only
then a decoder turns text + lengths + pitch + energy into audio. Here the model file is cut at those
three hand-over points (once, cached on disk). The lengths are replaced by the note plan, the pitch
curve by the melody and the energy curve by a held level, and the unchanged decoder synthesizes the
line. The voice sings at the written pitch in one pass, so there is no second vocoder, no stretching
of recorded vowels and no dying last word.
"""
from __future__ import annotations

import os

import numpy as np

from . import tts, world
from .phones import LENGTH_MARK, STRESS_MARKS, VOWELS, Phone, Syllable, fold_weak_syllables, merge_tokens, syllabify
from .singing import (FRAME_S, LEGATO_GAP_S, OUTPUT_SR, Style, SungLine, SungNote, _finish, _shape_phrases, _warp_envelope,
                      pitch_curve)

TOKEN_FRAME_S = tts.KOKORO_FRAME_SAMPLES / tts.KOKORO_SAMPLE_RATE      # 25 ms: unit of a sound's length
CURVE_STEPS_PER_FRAME = 2                                               # pitch and energy curves run at 12.5 ms
DURATION_TENSOR = "/encoder/Round_output_0"
PITCH_TENSOR = "/encoder/F0_proj/Conv_output_0"
ENERGY_TENSOR = "/encoder/N_proj/Conv_output_0"
LEAD_FRAMES, TAIL_FRAMES = 6, 4                 # quiet frames given to the start and end markers
MIN_VOWEL_FRAMES = 2
GLIDE_FRAMES = (3, 6)                           # frames for the second half of a diphthong (min, max)
GLIDE_SHARE = 0.22
SILENT_ENERGY = -9.0
REST_MIN_FRAMES = 3
HELD_ENERGY_PERCENTILE = 80
MAX_CONSONANT_SHARE = 0.6                       # of the room between two vowel onsets
CONSONANT_HEADROOM = 0.3
RAISE_FORMANT_SHARE = 0.15                      # formants follow a raised pitch by this share (in log frequency)
SILENCE_GUARD_FRAMES = 3
RANGE_PROBE_BELOW, RANGE_PROBE_ABOVE, RANGE_PROBE_SECONDS, RANGE_MIN_PERIODICITY = 9, 14, 1.2, 0.9
LEVEL_BOOST_DB, LEVEL_CUT_DB, CONSONANT_BOOST_DB, LEVEL_EXTRA = 18.0, -18.0, 6.0, 0.25
LEVEL_WINDOW_S, LEVEL_RAMP_S = 0.03, 0.015
CONSONANT_CEILING_DB = 1.0
ENERGY_SMOOTH_STEPS = 3


def _split_paths() -> tuple[str, str, str]:
    """Cut the timestamped Kokoro model into a prosody half and a decoder half (needs the `onnx` package once)."""
    folder = tts.cache_dir("kokoro")
    full = tts.fetch(f"{tts.KOKORO_BASE}/onnx/model.onnx", os.path.join(folder, "model.onnx"))
    prosody, decoder = os.path.join(folder, "prosody.onnx"), os.path.join(folder, "decoder.onnx")
    if not (os.path.exists(prosody) and os.path.exists(decoder)):
        from onnx.utils import extract_model
        extract_model(full, prosody + ".part", ["input_ids", "style", "speed", DURATION_TENSOR],
                      ["durations", PITCH_TENSOR, ENERGY_TENSOR], check_model=False)
        extract_model(full, decoder + ".part", ["input_ids", "style", DURATION_TENSOR, PITCH_TENSOR, ENERGY_TENSOR],
                      ["waveform"], check_model=False)
        os.replace(prosody + ".part", prosody)
        os.replace(decoder + ".part", decoder)
    return full, prosody, decoder


class NativeKokoro:
    """Holds the two model halves for one voice."""

    def __init__(self, voice: str, lang: str = "en-us"):
        import onnxruntime
        from kokoro_onnx.tokenizer import Tokenizer
        self.voice, self.lang, self.sr = voice, lang, tts.KOKORO_SAMPLE_RATE
        _, prosody, decoder = _split_paths()
        style = tts.fetch(f"{tts.KOKORO_BASE}/voices/{voice}.bin", os.path.join(tts.cache_dir("kokoro"), f"{voice}.bin"))
        self._styles = np.fromfile(style, dtype=np.float32).reshape(-1, 1, 256)
        self._tokenizer = Tokenizer()
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = max(1, os.cpu_count() or 2)
        self._prosody = onnxruntime.InferenceSession(prosody, options, providers=["CPUExecutionProvider"])
        self._decoder = onnxruntime.InferenceSession(decoder, options, providers=["CPUExecutionProvider"])

    @property
    def identity(self) -> str:
        return f"kokoro-native:{self.voice}:{tts.KOKORO_REVISION[:8]}"

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, self.lang)

    def tokens(self, text: str) -> tuple[list[str], np.ndarray, np.ndarray]:
        phonemes = self.phonemize(text)
        symbols = [s for s in phonemes if s in self._tokenizer.vocab]
        ids = self._tokenizer.tokenize("".join(symbols))
        return symbols, np.array([[0] + ids + [0]], dtype=np.int64), self._styles[len(ids)]

    def natural_frames(self, ids: np.ndarray, style: np.ndarray, speed: float) -> np.ndarray:
        """Spoken length of every token in frames, as the model would say the line."""
        ones = np.ones(ids.shape, dtype=np.float32)
        durations = self._prosody.run(["durations"], {"input_ids": ids, "style": style, "speed": np.array([speed], dtype=np.float32),
                                                      DURATION_TENSOR: ones})[0]
        return np.maximum(np.round(durations[0]), 1.0)

    def curves(self, ids, style, frames: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Pitch and energy the model predicts for the given lengths (energy is reused, pitch is replaced)."""
        _, pitch, energy = self._prosody.run(None, {"input_ids": ids, "style": style, "speed": np.array([1.0], dtype=np.float32),
                                                    DURATION_TENSOR: frames[None].astype(np.float32)})
        return pitch[0, 0], energy[0, 0]

    def decode(self, ids, style, frames: np.ndarray, pitch: np.ndarray, energy: np.ndarray) -> np.ndarray:
        waveform = self._decoder.run(None, {"input_ids": ids, "style": style, DURATION_TENSOR: frames[None].astype(np.float32),
                                            PITCH_TENSOR: pitch[None, None].astype(np.float32),
                                            ENERGY_TENSOR: energy[None, None].astype(np.float32)})[0]
        return waveform[0].astype(np.float64)


_singers: dict[str, NativeKokoro] = {}


def singer(voice: str) -> NativeKokoro:
    name = voice.split(":", 1)[-1]
    if name not in _singers:
        _singers[name] = NativeKokoro(name, tts.VOICES.get(f"kokoro:{name}", {}).get("lang", "en-us"))
    return _singers[name]


def _token_syllables(symbols: list[str], frames: np.ndarray, wanted: int):
    """Syllables whose phones remember which tokens they came from (start/end hold token indices)."""
    starts = [float(i) for i in range(len(symbols))]
    ends = [float(i + 1) for i in range(len(symbols))]
    phones = merge_tokens(symbols, starts, ends)
    return fold_weak_syllables(syllabify(phones), wanted), phones


def _token_range(phones: list[Phone]) -> list[int]:
    return [index for phone in phones for index in range(int(phone.start), int(phone.end))]


def plan_frames(symbols: list[str], natural: np.ndarray, groups: list[list[SungNote]]) -> tuple[np.ndarray, list[dict], float, list[Syllable]]:
    """Length in frames for every token so each vowel starts on its note. natural includes the two marker tokens.

    Per syllable the tokens run: [spaces] [opening consonants] [vowel] [closing consonants]. Consonants keep their
    spoken length, the vowel takes what is left of the note, and a rest becomes extra frames on the space before
    the next word. Returns (frames, layout, seconds from audio start to the first note's beat, syllables).
    """
    syllables, _ = _token_syllables(symbols, natural, len(groups))
    if len(syllables) != len(groups):
        spoken = " | ".join(s.text for s in syllabify(merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols))))
        raise ValueError(f"the line is spoken as {len(spoken.split(' | '))} syllables ({spoken}) but the melody has {len(groups)} "
                         "sung syllables. Add or remove notes, tie notes with '~', or reword the line.")
    frames = np.ones(len(symbols))
    onsets = [_token_range(s.onset) for s in syllables]
    nuclei = [_token_range(s.nucleus) for s in syllables]
    codas = [_token_range(s.coda) for s in syllables]
    for index in [k for group in onsets + codas for k in group]:
        frames[index] = natural[index + 1]                         # +1: natural[0] belongs to the start marker
    count = len(syllables)
    gaps = []                                                      # spaces and punctuation in front of each syllable
    for i in range(count):
        first = (onsets[i] or nuclei[i])[0]
        previous_last = (codas[i - 1] or nuclei[i - 1])[-1] if i else -1
        gaps.append(list(range(previous_last + 1, first)))

    def total(tokens):
        return int(sum(frames[k] for k in tokens))
    starts = [g[0].start for g in groups]
    lengths = [g[-1].start + g[-1].duration - g[0].start for g in groups]
    lead_frames = LEAD_FRAMES + len(gaps[0]) + total(onsets[0])
    planned = [lead_frames + int(round(start / TOKEN_FRAME_S)) for start in starts]     # frame where each vowel should begin
    layout, cursor = [], lead_frames
    for i in range(count):
        note_frames = int(round(lengths[i] / TOKEN_FRAME_S))
        rest, legato = 0, False
        if i + 1 < count:
            room = planned[i + 1] - cursor
            closing = codas[i] + onsets[i + 1]
            if total(closing) > MAX_CONSONANT_SHARE * room and closing:        # too many consonants for the slot: shorten them
                scale = MAX_CONSONANT_SHARE * room / total(closing)
                for k in closing:
                    frames[k] = max(1, int(round(frames[k] * scale)))
            lead_next = len(gaps[i + 1]) + total(onsets[i + 1])
            spare = room - total(codas[i]) - lead_next                           # frames left for the vowel (and a rest)
            sung = planned[i] + note_frames - cursor - total(codas[i])           # vowel length if the note ends as written
            legato = starts[i + 1] - (starts[i] + lengths[i]) < max(LEGATO_GAP_S, total(onsets[i + 1]) * TOKEN_FRAME_S)
            if legato or not gaps[i + 1] or spare - sung < REST_MIN_FRAMES:
                vowel = spare                                                    # no audible rest: hold the vowel through
            else:
                vowel, rest = sung, spare - sung
            vowel = max(MIN_VOWEL_FRAMES, vowel)
            if gaps[i + 1]:
                frames[gaps[i + 1][0]] = 1 + rest
        else:
            vowel = max(MIN_VOWEL_FRAMES, planned[i] + note_frames - cursor - total(codas[i]))
        _spread_vowel(frames, nuclei[i], symbols, vowel)
        vowel_start, vowel_end = cursor * TOKEN_FRAME_S, (cursor + total(nuclei[i])) * TOKEN_FRAME_S
        layout.append({"text": syllables[i].text, "vowel_start": vowel_start, "vowel_end": vowel_end,
                       "end": vowel_end + total(codas[i]) * TOKEN_FRAME_S, "legato": rest == 0 and i + 1 < count,
                       "pitches": [n.pitch for n in groups[i]], "squeezed": False, "rest_frames": rest,
                       "gap_tokens": gaps[i + 1] if i + 1 < count else []})
        if i + 1 < count:
            cursor += total(nuclei[i]) + total(codas[i]) + total(gaps[i + 1]) + total(onsets[i + 1])
    full = np.concatenate([[LEAD_FRAMES], frames, [TAIL_FRAMES]])
    return full, layout, lead_frames * TOKEN_FRAME_S, syllables


def _spread_vowel(frames: np.ndarray, tokens: list[int], symbols: list[str], total: int) -> None:
    """Give a vowel its frames: marks stay one frame, a diphthong's second sound gets a short glide, the rest is held."""
    marks = [k for k in tokens if symbols[k] in STRESS_MARKS or symbols[k] == LENGTH_MARK]
    sounds = [k for k in tokens if k not in marks]
    for k in marks:
        frames[k] = 1
    budget = max(len(sounds), total - len(marks))
    if len(sounds) == 1:
        frames[sounds[0]] = budget
        return
    glide = int(np.clip(round(GLIDE_SHARE * budget), *GLIDE_FRAMES))
    glide = min(glide, budget - 1)
    per_tail = max(1, glide // (len(sounds) - 1))
    for k in sounds[1:]:
        frames[k] = per_tail
    frames[sounds[0]] = max(1, budget - per_tail * (len(sounds) - 1))


def level_vowels(audio: np.ndarray, sr: int, layout: list[dict], evenness: float) -> np.ndarray:
    """Ride the level so every held vowel sits with the line's strong vowels.

    The decoder renders a long steady vowel much quieter than a short spoken one, and its energy input
    hardly changes that, so the balance is set afterwards. Inside each vowel a slow level follower lifts
    quiet stretches to the line's reference and holds loud ones down; consonants between two vowels take
    the smaller lift of their neighbours and are held to just above the vowel level.
    """
    window = max(1, int(LEVEL_WINDOW_S * sr))
    power = np.convolve(audio ** 2, np.ones(window) / window, mode="same")
    level = 10 * np.log10(power + 1e-12)
    spans = [(int(item["vowel_start"] * sr), max(int(item["vowel_end"] * sr), int(item["vowel_start"] * sr) + 1)) for item in layout]
    reference = np.percentile([np.percentile(level[a:b], HELD_ENERGY_PERCENTILE) for a, b in spans], HELD_ENERGY_PERCENTILE)
    strength = min(1.0, evenness + LEVEL_EXTRA)
    curve = np.zeros(len(audio))
    cursor, previous = 0, 0.0
    for a, b in spans:
        b = min(b, len(audio))
        lift = np.clip((reference - level[a:b]) * strength, LEVEL_CUT_DB, LEVEL_BOOST_DB)
        typical = float(np.median(lift)) if len(lift) else 0.0
        curve[cursor:a] = min(previous, typical, CONSONANT_BOOST_DB)
        curve[a:b] = lift
        cursor, previous = b, typical
    curve[cursor:] = min(previous, CONSONANT_BOOST_DB)
    in_vowel = np.zeros(len(audio), dtype=bool)
    for a, b in spans:
        in_vowel[a:b] = True
    # Sibilants and bursts come out of the decoder far above the sung vowels: hold them to just over the vowel level.
    excess = np.maximum(0.0, level + curve - (reference + CONSONANT_CEILING_DB))
    curve = np.where(in_vowel, curve, curve - excess)
    ramp = max(1, int(LEVEL_RAMP_S * sr))
    curve = np.convolve(np.pad(curve, ramp // 2, mode="edge"), np.ones(ramp) / ramp, mode="valid")[:len(audio)]
    return audio * 10 ** (curve / 20)


def sing_in_range(voice: str, text: str, groups: list[list[SungNote]], style: Style | None = None, speed: float = 1.0) -> tuple[SungLine, dict]:
    """Sing a line with Kokoro's decoder, lowering it first when the melody goes above the voice's clean range.

    A lowered line is sung cleanly in range and then raised to the written key with a formant-preserving
    pitch shift (WORLD), which costs some naturalness; the report says by how many semitones.
    """
    limits = clean_range(voice)
    top = max(n.pitch for g in groups for n in g)
    lowered = int(max(0, np.ceil(top - limits["high"])))
    if lowered == 0:
        line, report = sing(voice, text, groups, style, speed)
        report["raised_semitones"] = 0
        return line, report
    shifted = [[SungNote(n.start, n.duration, n.pitch - lowered) for n in g] for g in groups]
    line, report = sing(voice, text, shifted, style, speed)
    f0, envelope, aperiodicity = world.analyze(line.audio, OUTPUT_SR)
    ratio = 2.0 ** (lowered / 12.0)
    raised = world.synthesize(f0 * ratio, _warp_envelope(envelope, ratio ** RAISE_FORMANT_SHARE), aperiodicity, OUTPUT_SR)[:len(line.audio)]
    peak = np.max(np.abs(raised))
    line.audio = raised * (np.max(np.abs(line.audio)) / peak) if peak > 0 else raised
    for item, group in zip(line.layout, groups):
        item["pitches"] = [n.pitch for n in group]
    line.notes = [n for g in groups for n in g]
    report["raised_semitones"] = lowered
    return line, report


def sing(voice: str, text: str, groups: list[list[SungNote]], style: Style | None = None, speed: float = 1.0) -> tuple[SungLine, dict]:
    """Sing a line with Kokoro's decoder at the written pitch. Returns the line and a report (decoder lag, natural pitch)."""
    style = style or Style()
    engine = singer(voice)
    symbols, ids, voice_style = engine.tokens(text)
    natural = engine.natural_frames(ids, voice_style, speed)
    frames, layout, lead_in, _ = plan_frames(symbols, natural, groups)
    # Energy: the model's prediction for stretched lengths sags and mutes the first sounds, so each token takes the
    # level it has in the spoken line; vowels are then lifted toward the line's strong vowels and held there.
    spoken_pitch, spoken_energy = engine.curves(ids, voice_style, natural)
    spoken_edges = np.concatenate([[0], np.cumsum(natural)]).astype(int) * CURVE_STEPS_PER_FRAME
    token_level = np.array([float(np.max(spoken_energy[spoken_edges[k]:spoken_edges[k + 1]])) for k in range(len(natural))])
    is_vowel_token = np.array([False] + [symbol[0] in VOWELS for symbol in symbols] + [False])
    held = float(np.percentile(token_level[is_vowel_token], HELD_ENERGY_PERCENTILE)) if is_vowel_token.any() else float(token_level.max())
    edges = np.concatenate([[0], np.cumsum(frames)]).astype(int) * CURVE_STEPS_PER_FRAME
    steps = int(edges[-1])
    step_s = TOKEN_FRAME_S / CURVE_STEPS_PER_FRAME
    energy = np.empty(steps)
    for k in range(len(frames)):
        level = token_level[k]
        if is_vowel_token[k]:
            level = level + (held - level) * style.evenness
        else:
            level = min(level, held - CONSONANT_HEADROOM)            # a consonant never outweighs the vowels around it
        energy[edges[k]:edges[k + 1]] = level
    for item in layout:                                              # stress and length marks belong to their vowel
        a, b = int(round(item["vowel_start"] / step_s)), int(round(item["vowel_end"] / step_s))
        energy[a:b] = np.max(energy[a:b]) if b > a else energy[a:b]
    # The decoder voices each sound a frame or two ahead of its token, so a silence must end early or it
    # swallows the consonant that follows it.
    guard = SILENCE_GUARD_FRAMES * CURVE_STEPS_PER_FRAME
    silent = np.zeros(steps, dtype=bool)
    silent[:max(0, edges[1] - guard)] = True
    silent[edges[-2]:] = True
    for item in layout:
        if item["rest_frames"] >= REST_MIN_FRAMES and item["gap_tokens"]:
            first = item["gap_tokens"][0] + 1                         # +1: token 0 is the start marker
            silent[edges[first]:max(edges[first], edges[first + 1] - guard)] = True
    energy = np.where(silent, SILENT_ENERGY, energy)
    kernel = np.ones(ENERGY_SMOOTH_STEPS) / ENERGY_SMOOTH_STEPS      # no sudden level steps: they click
    energy = np.convolve(np.pad(energy, ENERGY_SMOOTH_STEPS // 2, mode="edge"), kernel, mode="valid")[:steps]
    # Melody on the 5 ms grid of the shared pitch model, then resampled to the decoder's 12.5 ms steps.
    fine = pitch_curve(groups, lead_in, int(np.ceil(steps * step_s / FRAME_S)) + 1, style)
    target = np.interp(np.arange(steps) * step_s, np.arange(len(fine)) * FRAME_S, fine)
    pitch = np.where(silent, 0.0, target)
    predicted_pitch = spoken_pitch
    audio = engine.decode(ids, voice_style, frames, pitch, energy)
    # The decoder voices each sound a little before its frame; measure that on this line and move the beat reference.
    token_edges = np.concatenate([[0], np.cumsum(frames)]) * TOKEN_FRAME_S
    timed = merge_tokens(symbols, list(token_edges[1:-2]), list(token_edges[2:-1]))
    lag = tts.measure_lag(audio, engine.sr, timed)
    for item in layout:
        for key in ("vowel_start", "vowel_end", "end"):
            item[key] = max(0.0, item[key] - lag)
    audio = level_vowels(audio, engine.sr, layout, style.evenness)
    audio = _shape_phrases(audio, engine.sr, layout)
    line = SungLine(_finish(audio, engine.sr), max(0.0, lead_in - lag), layout, None, [n for g in groups for n in g])
    spoken = predicted_pitch[predicted_pitch > 60]
    report = {"text": text, "lag_ms": round(lag * 1000), "engine": "kokoro-native",
              "natural_pitch_hz": round(float(np.median(spoken)), 1) if len(spoken) else None}
    return line, report


def clean_range(voice: str, refresh: bool = False) -> dict:
    """Pitch range (MIDI) in which this voice's decoder holds a clean tone, found by trying it.

    A held 'la' is sung at rising pitches until the tone stops being periodic (the decoder falls back to its
    speaking register above a voice-specific ceiling). The result is cached per voice.
    """
    import json
    from .lyrics import periodicity
    name = voice.split(":", 1)[-1]
    path = os.path.join(tts.cache_dir("kokoro"), f"range_{name}.json")
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    engine = singer(voice)
    symbols, ids, voice_style = engine.tokens("la")
    spoken_pitch, _ = engine.curves(ids, voice_style, engine.natural_frames(ids, voice_style, 1.0))
    voiced = spoken_pitch[spoken_pitch > 60]
    centre = int(round(69 + 12 * np.log2(float(np.median(voiced)) / 440.0))) if len(voiced) else 55
    flat = Style(vibrato=0.0, scoop=0.0, drift=0.0)
    scores = {}
    for pitch in range(centre - RANGE_PROBE_BELOW, centre + RANGE_PROBE_ABOVE + 1):
        line, _ = sing(voice, "la", [[SungNote(0.0, RANGE_PROBE_SECONDS, pitch)]], flat)
        item = line.layout[0]
        hz = 440.0 * 2 ** ((pitch - 69) / 12)
        scores[pitch] = periodicity(line.audio, OUTPUT_SR, hz, item["vowel_start"] + 0.2, item["vowel_end"] - 0.1)
    clean = [pitch for pitch, score in scores.items() if score >= RANGE_MIN_PERIODICITY]
    # Keep the unbroken stretch of clean pitches around the speaking pitch.
    high = centre
    while high + 1 in clean:
        high += 1
    low = centre
    while low - 1 in clean:
        low -= 1
    result = {"voice": name, "speaking_pitch": centre, "low": low, "high": high,
              "periodicity": {str(k): round(v, 2) for k, v in scores.items()}}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    return result
