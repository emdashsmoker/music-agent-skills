# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Turn a spoken line into a sung one: place syllables on notes, hold the vowels, replace the pitch.

Method (WORLD analysis-synthesis):
  1. consonants keep their spoken length and sit before the beat; the vowel starts on the beat;
  2. the vowel is lengthened only in its steady middle, its transitions stay as spoken;
  3. pitch follows the notes through a second-order glide (slight overshoot, like a voice),
     with delayed vibrato on long notes and a small seeded drift;
  4. unvoiced consonants are copied from the recording instead of resynthesized, which keeps them crisp;
  5. syllable loudness is evened out, because speech swallows unstressed syllables and singing does not.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from . import world
from .phones import DIPHTHONGS, LENGTH_MARK, SINGLE_SYMBOL_DIPHTHONGS, VOICELESS, Phone, Syllable, fold_weak_syllables, syllabify
from .tts import Unit

FRAME_S = world.FRAME_S
OUTPUT_SR = 44100
LEGATO_GAP_S = 0.09                     # notes closer than this are sung without a break
MIN_VOWEL_S = 0.045
MIN_VOWEL_SHARE = 0.4                   # of the syllable's time slot
MIN_CONSONANT_SCALE = 0.5
LEAD_MARGIN_S = 0.02
VOWEL_HEAD_S, VOWEL_TAIL_S = 0.03, 0.04
GLIDE_TARGET_SHARE, GLIDE_MAX_S, GLIDE_MIN_S = 0.25, 0.14, 0.06
PITCH_ANTICIPATION_S = 0.03
GLIDE_OMEGA, GLIDE_DAMPING = 52.0, 0.72          # about 50 ms rise with a few percent overshoot
VIBRATO_MIN_NOTE_S, VIBRATO_DELAY_S, VIBRATO_RAMP_S = 0.45, 0.28, 0.25
VIBRATO_RATE_HZ, VIBRATO_BASE_CENTS, VIBRATO_EXTRA_CENTS = 5.6, 18.0, 16.0
DRIFT_CENTS, DRIFT_CUTOFF_HZ = 4.0, 6.0
SCOOP_SEMITONES = 0.9
RELEASE_DROP_CENTS, RELEASE_DROP_S = 25.0, 0.08
LEVEL_BOOST_LIMIT_DB, LEVEL_CUT_LIMIT_DB, LEVEL_STRENGTH = 9.0, -6.0, 0.7
SUSTAIN_EDGE_S, SUSTAIN_LIFT_LIMIT_DB = 0.03, 8.0
SPLICE_FADE_S = 0.005
PHRASE_FADE_IN_S, PHRASE_FADE_OUT_S = 0.008, 0.06
HIGHPASS_HZ = 70.0
FORMANT_SHIFT_THRESHOLD_ST, FORMANT_SHIFT_SHARE = 5.0, 0.0   # measured: moving formants with the pitch did not help
TARGET_PEAK = 0.7


@dataclass
class SungNote:
    start: float                        # seconds from the first note of the line
    duration: float
    pitch: float                        # MIDI note number


@dataclass
class Style:
    """Performance settings; the defaults suit pop and electronic vocals."""
    vibrato: float = 1.0                # 0 = straight tone, 2 = wide
    scoop: float = 0.6                  # how far phrase starts slide up into the note (0-1)
    drift: float = 1.0                  # random pitch wander
    evenness: float = LEVEL_STRENGTH    # 0 keeps speech dynamics, 1 makes every syllable equally loud
    seed: int = 0


@dataclass
class SungLine:
    audio: np.ndarray                   # mono, OUTPUT_SR
    lead_in: float                      # seconds of audio before the first note's beat
    layout: list[dict] = field(default_factory=list)       # per syllable: text, vowel span, pitches (for figures and checks)
    f0_target: np.ndarray | None = None
    notes: list[SungNote] = field(default_factory=list)


@dataclass
class _Segment:
    out_start: float
    out_end: float
    src_start: float
    src_end: float
    kind: str                           # 'consonant', 'vowel', 'glide', 'silence'
    syllable: int
    phone: Phone | None = None


def _duration(phones: list[Phone]) -> float:
    return sum(p.duration for p in phones)


def assign(unit: Unit, groups: list[list[SungNote]]) -> list[Syllable]:
    """Syllables of the spoken line, folded to one per note group. Raises with a per-word table if counts differ."""
    syllables = fold_weak_syllables(syllabify(unit.phones), len(groups))
    if len(syllables) != len(groups):
        spoken = " | ".join(s.text for s in syllabify(unit.phones))
        raise ValueError(f"'{unit.text}' is spoken as {len(syllabify(unit.phones))} syllables ({spoken}) but the melody has "
                         f"{len(groups)} sung syllables. Add or remove notes, tie notes with '~', or reword the line.")
    return syllables


def _plan(syllables: list[Syllable], groups: list[list[SungNote]]) -> tuple[list[_Segment], float, list[dict]]:
    """Lay every sound of the line onto the output timeline."""
    onsets = [_duration(s.onset) for s in syllables]
    codas = [_duration(s.coda) for s in syllables]
    starts = [g[0].start for g in groups]
    ends = [g[-1].start + g[-1].duration for g in groups]
    count = len(syllables)
    # A rest shorter than the next syllable's opening consonants cannot be heard as a rest: sing through it.
    legato = [i + 1 < count and starts[i + 1] - ends[i] < max(LEGATO_GAP_S, onsets[i + 1]) for i in range(count)]
    scale_on, scale_co = [1.0] * count, [1.0] * count
    vowel_end = [0.0] * count
    for i in range(count):
        slot_end = starts[i + 1] if legato[i] else ends[i]
        following = onsets[i + 1] if legato[i] else 0.0
        room = slot_end - starts[i]
        need = max(MIN_VOWEL_S, MIN_VOWEL_SHARE * room)
        consonants = codas[i] + following
        if consonants > 0 and room - consonants < need:          # squeeze the consonants, never below half length
            factor = max(MIN_CONSONANT_SCALE, (room - need) / consonants)
            scale_co[i] = factor
            if legato[i]:
                scale_on[i + 1] = factor
            consonants *= factor
        vowel_end[i] = max(starts[i] + min(MIN_VOWEL_S, room * 0.5), slot_end - consonants)
    lead_in = onsets[0] * scale_on[0] + LEAD_MARGIN_S
    segments: list[_Segment] = []
    layout: list[dict] = []
    cursor = 0.0                                                   # output time already filled

    def place(phones, out_start, scale, index):
        position = out_start
        for phone in phones:
            length = phone.duration * scale
            segments.append(_Segment(position, position + length, phone.start, phone.end, "consonant", index, phone))
            position += length
        return position

    for i, syllable in enumerate(syllables):
        onset_start = lead_in + starts[i] - onsets[i] * scale_on[i]
        if onset_start > cursor + 1e-6:
            segments.append(_Segment(cursor, onset_start, 0.0, 0.0, "silence", i))
        place(syllable.onset, onset_start, scale_on[i], i)
        v0, v1 = lead_in + starts[i], lead_in + vowel_end[i]
        segments += _vowel_segments(syllable, v0, v1, i)
        cursor = place(syllable.coda, v1, scale_co[i], i)
        layout.append({"text": syllable.text, "vowel_start": v0, "vowel_end": v1, "end": cursor, "legato": legato[i],
                       "pitches": [n.pitch for n in groups[i]], "squeezed": min(scale_on[i], scale_co[i]) < 0.999})
    return segments, lead_in, layout


def _vowel_segments(syllable: Syllable, out_start: float, out_end: float, index: int) -> list[_Segment]:
    """Map the vowel onto its note: transitions at spoken speed, steady part stretched, diphthong glide at the end."""
    if not syllable.nucleus:
        return [_Segment(out_start, out_end, 0.0, 0.0, "silence", index)]
    src_start, src_end = syllable.nucleus[0].start, syllable.nucleus[-1].end
    src_length, out_length = src_end - src_start, out_end - out_start
    first = syllable.nucleus[0].symbol.replace(LENGTH_MARK, "")
    has_glide = len(syllable.nucleus) > 1 or first in SINGLE_SYMBOL_DIPHTHONGS or first in DIPHTHONGS
    if has_glide:
        # Hold the first vowel target, then move to the second sound only at the end of the note.
        split = syllable.nucleus[0].end if len(syllable.nucleus) > 1 else src_start + 0.6 * src_length
        glide_out = float(np.clip(GLIDE_TARGET_SHARE * out_length, GLIDE_MIN_S, GLIDE_MAX_S))
        glide_out = min(glide_out, 0.5 * out_length)
        return [_Segment(out_start, out_end - glide_out, src_start, split, "vowel", index, syllable.nucleus[0]),
                _Segment(out_end - glide_out, out_end, split, src_end, "glide", index, syllable.nucleus[-1])]
    head, tail = min(VOWEL_HEAD_S, 0.2 * src_length), min(VOWEL_TAIL_S, 0.25 * src_length)
    if out_length <= head + tail + FRAME_S:
        return [_Segment(out_start, out_end, src_start, src_end, "vowel", index, syllable.nucleus[0])]
    return [_Segment(out_start, out_start + head, src_start, src_start + head, "vowel", index, syllable.nucleus[0]),
            _Segment(out_start + head, out_end - tail, src_start + head, src_end - tail, "vowel", index, syllable.nucleus[0]),
            _Segment(out_end - tail, out_end, src_end - tail, src_end, "vowel", index, syllable.nucleus[0])]


def _glide(target: np.ndarray, resets: list[tuple[int, float]]) -> np.ndarray:
    """Second-order response to a stepwise pitch target (semitones). resets: (frame, starting value) at phrase starts."""
    steps_per_frame = 5
    dt = FRAME_S / steps_per_frame
    reset_at = dict(resets)
    value, velocity = target[0], 0.0
    result = np.empty_like(target)
    for frame, goal in enumerate(target):
        if frame in reset_at:
            value, velocity = reset_at[frame], 0.0
        for _ in range(steps_per_frame):
            acceleration = GLIDE_OMEGA ** 2 * (goal - value) - 2 * GLIDE_DAMPING * GLIDE_OMEGA * velocity
            velocity += acceleration * dt
            value += velocity * dt
        result[frame] = value
    return result


def pitch_curve(groups: list[list[SungNote]], lead_in: float, total_frames: int, style: Style) -> np.ndarray:
    """Target f0 in Hz for every output frame (never 0: voicing is decided elsewhere)."""
    rng = np.random.default_rng(style.seed)
    notes = [n for g in groups for n in g]
    target = np.full(total_frames, notes[0].pitch, dtype=float)
    resets = []
    previous_end = None
    for note in notes:
        start = int(max(0.0, lead_in + note.start - PITCH_ANTICIPATION_S) / FRAME_S)
        target[start:] = note.pitch
        if previous_end is None or note.start - previous_end > LEGATO_GAP_S:       # phrase start: slide up into the note
            resets.append((max(0, start - 2), note.pitch - SCOOP_SEMITONES * style.scoop))
        previous_end = note.start + note.duration
    curve = _glide(target, resets)
    for index, note in enumerate(notes):
        first, last = int((lead_in + note.start) / FRAME_S), min(total_frames, int((lead_in + note.start + note.duration) / FRAME_S))
        if last <= first:
            continue
        times = np.arange(last - first) * FRAME_S
        if note.duration >= VIBRATO_MIN_NOTE_S and style.vibrato > 0:
            delay = min(VIBRATO_DELAY_S, 0.4 * note.duration)
            depth = (VIBRATO_BASE_CENTS + VIBRATO_EXTRA_CENTS * min(1.0, (note.duration - VIBRATO_MIN_NOTE_S))) * style.vibrato
            rate = VIBRATO_RATE_HZ * (1.0 + rng.uniform(-0.05, 0.05))
            envelope = np.clip((times - delay) / VIBRATO_RAMP_S, 0.0, 1.0)
            curve[first:last] += depth / 100.0 * envelope * np.sin(2 * np.pi * rate * (times - delay))
        following = notes[index + 1].start if index + 1 < len(notes) else None
        if following is None or following - (note.start + note.duration) > LEGATO_GAP_S:   # phrase end: let the pitch sag
            tail = min(last - first, int(RELEASE_DROP_S / FRAME_S))
            curve[last - tail:last] -= RELEASE_DROP_CENTS / 100.0 * np.linspace(0.0, 1.0, tail)
    if style.drift > 0:
        noise = rng.standard_normal(total_frames + 200)
        b, a = signal.butter(2, DRIFT_CUTOFF_HZ, fs=1.0 / FRAME_S)
        wander = signal.lfilter(b, a, noise)[200:]
        curve += DRIFT_CENTS / 100.0 * style.drift * wander / (np.std(wander) + 1e-9)
    return 440.0 * 2.0 ** ((curve - 69.0) / 12.0)


def _warp_envelope(envelope: np.ndarray, ratio: float) -> np.ndarray:
    """Shift formants by `ratio` (>1 = up) by resampling each envelope frame along frequency."""
    bins = envelope.shape[1]
    positions = np.arange(bins) / ratio
    low = np.clip(np.floor(positions).astype(int), 0, bins - 1)
    high = np.clip(low + 1, 0, bins - 1)
    weight = np.clip(positions - low, 0.0, 1.0)
    return envelope[:, low] * (1 - weight) + envelope[:, high] * weight


def sing(unit: Unit, groups: list[list[SungNote]], style: Style | None = None, analysis=None) -> SungLine:
    """Sing a spoken line. groups holds one list of notes per sung syllable (several notes = a slur)."""
    style = style or Style()
    syllables = assign(unit, groups)
    f0, envelope, aperiodicity = analysis if analysis is not None else world.analyze(unit.audio, unit.sr)
    segments, lead_in, layout = _plan(syllables, groups)
    total = segments[-1].out_end + PHRASE_FADE_OUT_S
    frames = int(np.ceil(total / FRAME_S))
    source_frames = len(f0)
    source_index = np.zeros(frames)
    region = np.zeros(frames, dtype=int)                 # 0 silence, 1 consonant, 2 vowel (held or glide)
    owner = np.full(frames, -1)
    for segment in segments:
        first, last = int(round(segment.out_start / FRAME_S)), min(frames, int(round(segment.out_end / FRAME_S)))
        if last <= first or segment.kind == "silence":
            continue
        ramp = (np.arange(first, last) - first + 0.5) / (last - first)
        source_index[first:last] = (segment.src_start + ramp * (segment.src_end - segment.src_start)) / FRAME_S
        region[first:last] = 1 if segment.kind == "consonant" else 2
        owner[first:last] = segment.syllable
    low = np.clip(np.floor(source_index).astype(int), 0, source_frames - 1)
    high = np.clip(low + 1, 0, source_frames - 1)
    weight = (source_index - low)[:, None]
    sung_envelope = np.exp(np.log(envelope[low]) * (1 - weight) + np.log(envelope[high]) * weight)
    sung_aperiodicity = aperiodicity[low] * (1 - weight) + aperiodicity[high] * weight
    source_voiced = f0[np.clip(np.round(source_index).astype(int), 0, source_frames - 1)] > 0

    # Loudness: bring each syllable's vowel toward the level of the line's stronger vowels.
    energy = envelope.sum(axis=1)
    vowel_levels = []
    for syllable in syllables:
        a, b = int(syllable.nucleus[0].start / FRAME_S), max(int(syllable.nucleus[-1].end / FRAME_S), int(syllable.nucleus[0].start / FRAME_S) + 1)
        vowel_levels.append(10 * np.log10(np.mean(energy[a:b]) + 1e-20))
    reference = np.percentile(vowel_levels, 75)
    gains_db = [float(np.clip((reference - level) * style.evenness, LEVEL_CUT_LIMIT_DB, LEVEL_BOOST_LIMIT_DB)) for level in vowel_levels]
    centres = [(item["vowel_start"] + item["vowel_end"]) / 2 / FRAME_S for item in layout]
    gain_curve = np.interp(np.arange(frames), centres, gains_db) if len(centres) > 1 else np.full(frames, gains_db[0])
    sung_envelope *= (10 ** (gain_curve / 10))[:, None]
    sung_envelope *= (10 ** (_sustain_gain_db(sung_envelope, layout, style.evenness) / 10))[:, None]

    target = pitch_curve(groups, lead_in, frames, style)
    voiced_source = f0[f0 > 0]
    if len(voiced_source):
        shift = 12 * np.log2(np.median(target[region == 2]) / np.median(voiced_source)) if (region == 2).any() else 0.0
        if abs(shift) > FORMANT_SHIFT_THRESHOLD_ST:      # far from the speaking pitch: move the formants a little the same way
            sung_envelope = _warp_envelope(sung_envelope, 2 ** (shift * FORMANT_SHIFT_SHARE / 12))
    voiced = (region == 2) | ((region == 1) & source_voiced)
    sung_f0 = np.where(voiced, target, 0.0)
    silent = region == 0
    sung_envelope[silent] = 1e-12
    audio = world.synthesize(sung_f0, sung_envelope, sung_aperiodicity, unit.sr)[:int(total * unit.sr)]
    audio = _restore_consonants(audio, unit, segments, gain_curve)
    audio = _shape_phrases(audio, unit.sr, layout)
    audio = _finish(audio, unit.sr)
    return SungLine(audio, lead_in, layout, np.where(voiced, target, 0.0), [n for g in groups for n in g])


def _sustain_gain_db(sung_envelope: np.ndarray, layout: list[dict], strength: float) -> np.ndarray:
    """Gain per frame that keeps a held vowel from fading the way a spoken vowel does.

    Inside each vowel the quieter frames are raised toward the vowel's own strong level; the first and
    last moments are left alone so attacks and releases keep their shape.
    """
    gain = np.zeros(len(sung_envelope))
    level = 10 * np.log10(sung_envelope.sum(axis=1) + 1e-30)
    edge = int(SUSTAIN_EDGE_S / FRAME_S)
    for item in layout:
        first, last = int(item["vowel_start"] / FRAME_S), min(len(gain), int(item["vowel_end"] / FRAME_S))
        if last - first < 4 * edge:
            continue
        reference = np.percentile(level[first:last], 80)
        lift = np.clip((reference - level[first:last]) * strength, 0.0, SUSTAIN_LIFT_LIMIT_DB)
        taper = np.ones(last - first)
        taper[:edge] = np.linspace(0.0, 1.0, edge)
        taper[-edge:] = np.linspace(1.0, 0.0, edge)
        gain[first:last] = lift * taper
    return gain


def _restore_consonants(audio: np.ndarray, unit: Unit, segments: list[_Segment], gain_curve: np.ndarray) -> np.ndarray:
    """Copy unvoiced consonants straight from the recording where they kept their spoken length."""
    sr = unit.sr
    fade = int(SPLICE_FADE_S * sr)
    result = audio.copy()
    for segment in segments:
        if segment.kind != "consonant" or segment.phone is None or segment.phone.symbol[0] not in VOICELESS:
            continue
        out_length, src_length = segment.out_end - segment.out_start, segment.src_end - segment.src_start
        if abs(out_length - src_length) > 0.002 or src_length < 2 * SPLICE_FADE_S:
            continue
        a, b = int(segment.out_start * sr), int(segment.out_start * sr) + int(src_length * sr)
        s0 = int(segment.src_start * sr)
        if b > len(result) or s0 + (b - a) > len(unit.audio):
            continue
        piece = unit.audio[s0:s0 + (b - a)] * 10 ** (gain_curve[min(len(gain_curve) - 1, int(segment.out_start / FRAME_S))] / 20)
        window = np.ones(b - a)
        window[:fade] = np.linspace(0.0, 1.0, fade)
        window[-fade:] = np.linspace(1.0, 0.0, fade)
        result[a:b] = result[a:b] * (1 - window) + piece * window
    return result


def _shape_phrases(audio: np.ndarray, sr: int, layout: list[dict]) -> np.ndarray:
    """Soft start for the line and a short fade wherever a held vowel ends into a rest without a closing consonant."""
    result = audio.copy()
    fade_in = int(PHRASE_FADE_IN_S * sr)
    result[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    for item in layout:
        open_ending = not item["legato"] and abs(item["end"] - item["vowel_end"]) < 1e-6
        if open_ending:
            end = min(len(result), int(item["end"] * sr))
            start = max(0, end - int(PHRASE_FADE_OUT_S * sr))
            result[start:end] *= np.linspace(1.0, 0.0, end - start) ** 1.5
            result[end:min(len(result), end + int(PHRASE_FADE_OUT_S * sr))] = 0.0
    return result


def _finish(audio: np.ndarray, sr: int) -> np.ndarray:
    """Remove rumble, convert to the project rate and set a consistent peak."""
    sos = signal.butter(2, HIGHPASS_HZ, btype="high", fs=sr, output="sos")
    cleaned = signal.sosfiltfilt(sos, audio)
    if sr != OUTPUT_SR:
        divisor = np.gcd(OUTPUT_SR, sr)
        cleaned = signal.resample_poly(cleaned, OUTPUT_SR // divisor, sr // divisor)
    peak = np.max(np.abs(cleaned))
    return cleaned * (TARGET_PEAK / peak) if peak > 0 else cleaned


def natural_pitch(unit: Unit, analysis=None) -> float:
    """Median speaking pitch of the voice as a MIDI note number: melodies near it sound most natural."""
    f0 = (analysis[0] if analysis is not None else world.quick_f0(unit.audio, unit.sr))
    voiced = f0[f0 > 0]
    return float(69 + 12 * np.log2(np.median(voiced) / 440.0)) if len(voiced) else 60.0
