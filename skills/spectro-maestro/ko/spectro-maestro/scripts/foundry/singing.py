# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Turn a spoken line into a sung line.

The spoken audio is taken apart with the WORLD vocoder (pitch, spectral envelope, aperiodicity),
its timeline is re-laid so that every vowel starts on its note and is held for the note's length,
the pitch is replaced by a sung contour, and the result is put back together.

What makes the difference between 'pitch-corrected speech' and 'singing' is modelled explicitly:
  - vowels begin on the beat, the consonants before them are sung ahead of it
  - only the steady middle of a vowel is stretched; transitions and consonants keep their natural length
  - a diphthong holds its first vowel and glides late
  - pitch moves between notes in a smooth curve with a small overshoot, starts phrases from slightly below,
    adds delayed vibrato on held notes and a little random drift
  - unvoiced consonants are copied from the original recording so they stay crisp
  - syllables are evened out in level: speech swallows function words, singing does not"""
from __future__ import annotations

import numpy as np
from scipy import signal


class VocalError(ValueError):
    """A lyric line, a voice or a voicebank the composer must fix; reported without a traceback."""


FRAME_S = 0.005
PERIODIC_BAND_HZ = 4000.0
VOICED_MIN_PERIODICITY = 0.5    # below this a frame is breath or hiss, whatever the pitch tracker says
VOICED_LEVEL_RANGE_DB = 24.0    # frames this far under the loud frames are closures and pauses
SUSTAIN_REACH_S = 0.04          # how far past a vowel's reported edges the search for a voiced instant may go
VOWEL_BREATH_PERCENTILE = 75.0   # sung vowels are capped at this percentile of the take's voiced-vowel breathiness
MIN_FRAMES_FOR_BREATH_CAP = 20
RELEASE_SMOOTH_S = 0.06         # the fade of a phrase's last syllable is evened out over this long
RELEASE_FILL_DB, RELEASE_TRIM_DB = 4.0, 12.0     # how far a frame of that fade may be lifted into a dip or cut from a burst
SUSTAIN_MIN_FRAMES = 3          # fewer voiced frames than this inside a vowel means its reported position is off
F0_FLOOR, F0_CEIL = 60.0, 700.0
REST_GAP_S = 0.12               # a gap this long between notes is a rest: the syllable closes before it
MAX_CONSONANT_SHARE = 0.55      # consonants may take at most this share of the time between two vowel onsets
MIN_CONSONANT_SCALE = 0.4
HOLD_HALF_S = 0.012             # half-width of the stable slice of a vowel that is stretched into the held note
DIPHTHONG_HOLD_SHARE = 0.65     # the held instant of a diphthong lies in this first share of it
OPEN_BAND = (700.0, 4000.0)       # band whose share of energy tells an open vowel from a glide or nasal
SUSTAIN_LEVEL_WEIGHT, SUSTAIN_OPEN_WEIGHT, SUSTAIN_CHANGE_WEIGHT = 0.06, 0.0, 1.0   # chosen by recognition A/B
SUSTAIN_LATE_WEIGHT = 0.3
SUSTAIN_BRIGHT_WEIGHT = 0.04    # per dB below the vowel's brightest instant in BRIGHT_BAND
BRIGHT_BAND = (1000.0, 4000.0)    # where the upper formants sit; a nasal or glide transition is dull here
SPLICE_CONSONANTS = True
FADE_LIMIT_DB = 6.0             # a vowel's tail counts as faded once it is this far below its held level
MAX_EDGE_SHARE = 0.4            # a vowel's natural attack or release may take at most this share of its note
SPLICE_FADE_S = 0.004
LEVEL_EDGE_S = 0.02             # syllable level is measured this far inside the note
LEVEL_LIMIT_DB = 8.0
SILENCE_FLOOR = 1e-12

DEFAULT_STYLE = {
    "vibrato_depth": 28.0,      # cents, peak deviation on held notes
    "vibrato_rate": 5.6,        # Hz
    "vibrato_delay": 0.28,      # seconds before vibrato starts on a note
    "vibrato_min_note": 0.45,   # shorter notes get none
    "glide": 0.07,              # seconds, rise time between notes
    "overshoot": 0.82,          # damping of the pitch movement; below 1 overshoots a little
    "scoop": 0.6,               # semitones below the first note of a phrase
    "drift": 6.0,               # cents of slow random wander
    "fall": 0.35,               # semitones the pitch sags at the end of a phrase
    "level": 0.6,               # 0..1 how strongly syllable loudness is evened out
    "formant": 0.0,             # semitones of formant shift (positive = brighter, smaller voice)
    "breath": 0.0,              # 0..1 share of aspiration noise added to voiced frames
    "preparation": 0.12,        # share of an interval the pitch first moves the other way before a note change
    "ring": 3.0,                # dB of lift around 3 kHz on sung vowels (the 'ring' of a singing voice); consonants untouched
    "consonant_ceiling": -3.0,  # dB against the line's vowel level: louder t, s, k bursts are turned down to this
    "vowel_body": 0.0,          # 1 gives held ee vowels the body of the line's other vowels (at most 10 dB); 0 leaves them thin
}
RELEASE_MARGIN_DB = 1.0         # how far the end of a syllable may rise above the line's usual held-vowel level
CONSONANT_WINDOW_S = 0.01       # a burst is judged by its loudest stretch of this length
CONSONANT_CUT_LIMIT_DB = 6.0
PREPARATION_LIMIT = 0.4         # semitones
PREPARATION_WIDTH_S = 0.025
RING_HZ, RING_WIDTH_HZ = 3000.0, 700.0
RING_SMOOTH_S = 0.03
# Held "ee" vowels (he, she, we, see) come out thin. Measured on the dry lead stems of seven finished songs (1,655
# syllables, Kokoro voices): an ee syllable's 300-1300 Hz body sat 9 dB under the median body of its line while its
# energy above 1.3 kHz matched the body, so the word is quiet and sharp at once. The vowel has little body to begin
# with (first formant near 300 Hz, second above 2 kHz) and the stretch keeps it so; a singer opens the vowel toward
# "ih" on a held note to fill it. The fill does the equivalent on the spectral envelope: it raises the body band of ee
# frames toward the body level of the line's other vowels, and thins the breath noise above 2 kHz that makes the hiss.
VOWEL_FILL_SYMBOLS = {"i"}                # the ee vowel; the length mark is stripped before the test
VOWEL_FILL_MIN_S = 0.2                    # shorter vowels are mostly transition and are left alone
VOWEL_FILL_BODY_HZ = (300.0, 1300.0)      # the body band: the deficit is measured here and the fill covers it
VOWEL_FILL_FLAT_HZ = (400.0, 1100.0)      # the fill is flat here and ramps to nothing at the body band's edges
VOWEL_FILL_UNDER_DB = 3.0                 # the fill aims this far under the other vowels: ee is a lighter vowel by nature
VOWEL_FILL_LIMIT_DB = 10.0                # the deficit of a sung ee is about 10 dB on the envelope; more would remake the vowel
VOWEL_FILL_EDGE_S = 0.03                  # ramps at the vowel's ends so transitions keep their shape
VOWEL_FILL_BREATH_HZ = 2000.0             # breath noise above this is thinned on filled frames
VOWEL_FILL_BREATH_SHARE = 0.5             # share of that noise removed at strength 1


def analyse(audio: np.ndarray, sr: int, f0: np.ndarray | None = None) -> dict:
    """WORLD analysis at 5 ms frames."""
    import pyworld
    x = audio.astype(np.float64)
    if f0 is None:
        f0, times = pyworld.harvest(x, sr, f0_floor=F0_FLOOR, f0_ceil=F0_CEIL, frame_period=FRAME_S * 1000)
    else:
        times = np.arange(len(f0)) * FRAME_S
    f0 = pyworld.stonemask(x, f0.astype(np.float64), times, sr)
    fft_size = pyworld.get_cheaptrick_fft_size(sr, F0_FLOOR)
    sp = pyworld.cheaptrick(x, f0, times, sr, f0_floor=F0_FLOOR, fft_size=fft_size)
    ap = pyworld.d4c(x, f0, times, sr, fft_size=fft_size)
    return {"f0": np.where(truly_voiced(f0, sp, ap, sr), f0, 0.0), "sp": sp, "ap": ap, "sr": sr}


def periodicity(ap: np.ndarray, sr: int) -> np.ndarray:
    """Share of the energy below 4 kHz that is periodic, per frame (0 = noise, 1 = pure voice)."""
    bins = max(1, int(ap.shape[1] * PERIODIC_BAND_HZ / (0.5 * sr)))
    return 1.0 - ap[:, :bins].mean(axis=1)


def truly_voiced(f0: np.ndarray, sp: np.ndarray, ap: np.ndarray, sr: int) -> np.ndarray:
    """The pitch tracker reports a pitch through aspiration, hiss and even stop closures. A frame counts as voiced
    only when it is also periodic and not far below the loud frames of the take."""
    level = 10.0 * np.log10(sp.sum(axis=1) + 1e-12)
    loud = np.percentile(level, 90) if len(level) else 0.0
    return (f0 > 0) & (periodicity(ap, sr) >= VOICED_MIN_PERIODICITY) & (level >= loud - VOICED_LEVEL_RANGE_DB)


def note_groups(notes: list) -> list:
    """[(start, dur, midi, tie)] -> syllable groups [(start, end, [(start, end, midi), ...])]. A tie joins a note to the next."""
    groups, current = [], None
    for start, dur, midi, tie in notes:
        if current is None:
            current = [start, start + dur, []]
        current[2].append((start, start + dur, midi))
        current[1] = start + dur
        if not tie:
            groups.append(tuple(current))
            current = None
    if current is not None:
        groups.append(tuple(current))
    return groups


def pitch_curve(groups: list, n_frames: int, origin: float, style: dict, rng: np.random.Generator) -> np.ndarray:
    """Sung pitch in MIDI per frame. `origin` is the time of frame 0 relative to the line start (negative pre-roll)."""
    t = origin + np.arange(n_frames) * FRAME_S
    flat = [note for group in groups for note in group[2]]
    glide = max(style["glide"], 0.01)
    target = np.full(n_frames, float(flat[0][2]))
    for start, _end, midi in flat:
        target[t >= start - 0.45 * glide] = midi          # start moving early so the note is reached on time
    # Second-order response: the pitch 'swings' to each new note like a voice does.
    omega = 2.5 / glide                              # 10-90 % rise time of about `glide` seconds
    b, a = signal.bilinear([omega ** 2], [1.0, 2.0 * style["overshoot"] * omega, omega ** 2], fs=1.0 / FRAME_S)
    first = target[0] - style["scoop"]
    state = signal.lfilter_zi(b, a) * first
    curve, _ = signal.lfilter(b, a, target, zi=state)
    # Phrases that restart after a rest scoop again.
    for previous, group in zip(groups, groups[1:]):
        if group[0] - previous[1] >= REST_GAP_S:
            a0 = int((group[0] - origin) / FRAME_S)
            span = slice(max(0, a0 - int(0.03 / FRAME_S)), min(n_frames, a0 + int(0.15 / FRAME_S)))
            ramp = np.linspace(1.0, 0.0, span.stop - span.start) ** 2
            curve[span] -= style["scoop"] * ramp
    if style.get("preparation", 0.0) > 0:               # a voice dips before it rises and lifts before it falls
        for previous, note in zip(flat, flat[1:]):
            interval = note[2] - previous[2]
            if interval == 0 or note[0] - previous[1] >= REST_GAP_S:
                continue
            depth = -np.sign(interval) * min(style["preparation"] * abs(interval), PREPARATION_LIMIT)
            curve += depth * np.exp(-0.5 * ((t - (note[0] - 0.9 * glide)) / PREPARATION_WIDTH_S) ** 2)
    cents = np.zeros(n_frames)
    phase = 0.0
    for start, end, _notes in groups:
        for note_start, note_end, _midi in _notes:
            length = note_end - note_start
            if length < style["vibrato_min_note"] or style["vibrato_depth"] <= 0:
                continue
            a0, b0 = int((note_start - origin) / FRAME_S), min(n_frames, int((note_end - origin) / FRAME_S))
            if b0 <= a0:
                continue
            local = np.arange(b0 - a0) * FRAME_S
            delay = min(style["vibrato_delay"], 0.4 * length)
            depth = np.clip((local - delay) / 0.3, 0.0, 1.0) * np.clip((length - local) / 0.08, 0.0, 1.0)
            rate = style["vibrato_rate"] * (1.0 + 0.04 * rng.standard_normal())
            cents[a0:b0] += style["vibrato_depth"] * depth * np.sin(2 * np.pi * rate * local + phase)
            phase += 2 * np.pi * rate * length
    if style["drift"] > 0:
        wander = signal.lfilter(*signal.butter(2, 1.5, fs=1.0 / FRAME_S), rng.standard_normal(n_frames + 400))[400:]
        cents += style["drift"] * wander / (np.std(wander) + 1e-9)
    last_end = groups[-1][1]
    tail = np.clip((t - (last_end - 0.09)) / 0.09, 0.0, 1.0)
    return curve + cents / 100.0 - style["fall"] * tail ** 2


def layout(unit, syllables: list, groups: list, analysis: dict) -> tuple:
    """Where each source phone goes on the sung timeline.
    Returns (segments, pre_roll, closing_phrase, holds): segments are (target_start, target_end, source_start,
    source_end, phone_index); closing_phrase lists the syllables that end a phrase on a consonant and keep their
    spoken fade-out; holds is the held instant of every syllable."""
    phones = unit.phones
    if len(syllables) != len(groups):
        raise ValueError(f"{len(syllables)} syllables but {len(groups)} notes")
    holds = [sustain_point(phones, s.nucleus, analysis) for s in syllables]
    voiced_from = [min(voicing_onset(phones[s.nucleus[0]], analysis, hold), max(phones[s.nucleus[0]].start, hold - HOLD_HALF_S))
                   for s, hold in zip(syllables, holds)]

    def length(indices):
        return sum(phones[i].dur for i in indices)

    def before_beat(k):                                  # consonants plus any unvoiced start of the vowel itself
        return length(syllables[k].onset) + voiced_from[k] - phones[syllables[k].nucleus[0]].start

    def place(indices, cursor, scale):
        placed = []
        for i in indices:
            placed.append((cursor, cursor + phones[i].dur * scale, phones[i].start, phones[i].end, i))
            cursor += phones[i].dur * scale
        return placed, cursor

    segments, closing_phrase = [], []
    pre_roll = before_beat(0)
    onset_scale = 1.0
    for index, (syllable, group) in enumerate(zip(syllables, groups)):
        start, end = group[0], group[1]
        following = groups[index + 1][0] if index + 1 < len(groups) else None
        connected = following is not None and following - end < REST_GAP_S
        span = (following - start) if connected else (end - start)
        consonants = length(syllable.coda) + (before_beat(index + 1) if connected else 0.0)
        scale = 1.0 if consonants <= MAX_CONSONANT_SHARE * span else max(MIN_CONSONANT_SCALE, MAX_CONSONANT_SHARE * span / consonants)
        vowel_end = max((following if connected else end) - consonants * scale, start + 0.03)
        first = phones[syllable.nucleus[0]]
        lead = (voiced_from[index] - first.start) * onset_scale
        onset, _ = place(syllable.onset, start - lead - length(syllable.onset) * onset_scale, onset_scale)
        segments += onset
        if lead > 1e-4:
            segments.append((start - lead, start, first.start, voiced_from[index], syllable.nucleus[0]))
        nucleus_end = phones[syllable.nucleus[-1]].end
        if not connected and not syllable.coda:           # an open vowel before a rest: drop its spoken fade-out
            nucleus_end = strong_until(analysis, holds[index], nucleus_end)
        elif not connected:                               # a closed one keeps its glide (rain, voice) and its spoken fade
            closing_phrase.append(index)
        segments += _vowel_segments(phones, syllable.nucleus, start, vowel_end, voiced_from[index], holds[index], nucleus_end)
        coda, _ = place(syllable.coda, vowel_end, scale)
        segments += coda
        onset_scale = scale if connected else 1.0
    return segments, pre_roll, closing_phrase, holds


def sustain_point(phones: list, nucleus: list, analysis: dict, reach: tuple | None = None) -> float:
    """Time inside a vowel where it is most stable: strongly periodic, loud, away from the edges.
    This is the instant a held note is built from, so a breathy onset or a glide is never what gets stretched."""
    a, b = phones[nucleus[0]].start, phones[nucleus[-1]].end
    if len(nucleus) > 1:                                 # diphthong: hold the first vowel, not the glide
        b = a + DIPHTHONG_HOLD_SHARE * (b - a)
    margin = min(0.2 * (b - a), 0.03)
    low, high = int((a + margin) / FRAME_S), max(int((a + margin) / FRAME_S) + 1, int((b - margin) / FRAME_S))
    high = min(high, len(analysis["f0"]))
    if high <= low:
        return 0.5 * (a + b)
    if int((analysis["f0"][low:high] > 0).sum()) < SUSTAIN_MIN_FRAMES:
        # Engine timings are off by a few tens of milliseconds now and then: the reported vowel then covers the
        # aspiration before it or the closure after it. The voiced stretch is searched a little beyond the edges,
        # inside this syllable only.
        low = max(0, int((max(a - SUSTAIN_REACH_S, reach[0]) if reach else a) / FRAME_S))
        high = min(len(analysis["f0"]), max(low + 1, int((min(b + SUSTAIN_REACH_S, reach[1]) if reach else b) / FRAME_S)))
    nyquist = 0.5 * analysis["sr"]
    width = analysis["ap"].shape[1]
    bins = max(1, int(width * 4000.0 / nyquist))
    periodic = periodicity(analysis["ap"][low:high], analysis["sr"])
    power = analysis["sp"][low:high]
    level = 10.0 * np.log10(power.sum(axis=1) + 1e-12)
    open_a, open_b = int(width * OPEN_BAND[0] / nyquist), int(width * OPEN_BAND[1] / nyquist)
    openness = power[:, open_a:open_b].sum(axis=1) / (power.sum(axis=1) + 1e-12)     # vowels carry more here than w, r, l, m, n
    bright_a, bright_b = int(width * BRIGHT_BAND[0] / nyquist), int(width * BRIGHT_BAND[1] / nyquist)
    bright = 10.0 * np.log10(power[:, bright_a:bright_b].sum(axis=1) + 1e-12)
    voiced = analysis["f0"][low:high] > 0
    log_power = np.log(analysis["sp"][max(0, low - 1):high + 1, :bins * 2] + 1e-12)
    change = np.abs(np.diff(log_power, axis=0)).mean(axis=1)
    change = 0.5 * (change[:-1] + change[1:]) if len(change) == len(level) + 1 else np.resize(change, len(level))
    position = np.linspace(0.0, 1.0, len(level))          # the vowel's own colour is clearest before it leans into what follows
    score = (periodic + SUSTAIN_LEVEL_WEIGHT * (level - level.max()) + 0.5 * voiced
             + SUSTAIN_OPEN_WEIGHT * openness / (openness.max() + 1e-9)
             + SUSTAIN_BRIGHT_WEIGHT * (bright - bright.max())
             - SUSTAIN_CHANGE_WEIGHT * change / (change.max() + 1e-9) - SUSTAIN_LATE_WEIGHT * position)
    if voiced.any():                                     # an unvoiced instant is held only when the vowel has no voice at all
        score = np.where(voiced, score, -np.inf)
    return (low + int(np.argmax(score))) * FRAME_S


def syllable_reach(phones: list, syllable) -> tuple:
    """Time span of a syllable's vowel together with the voiced consonants that touch it: the region in which the
    vowel's voiced part can really lie when the reported boundaries are slightly off."""
    first, last = syllable.nucleus[0], syllable.nucleus[-1]
    start, end = phones[first].start, phones[last].end
    for index in reversed(syllable.onset):
        if index == first - 1 and phones[index].kind in ("sonorant", "unvoiced", "voiced"):
            start = phones[index].start + 0.5 * phones[index].dur    # a consonant's release may hide the vowel's start
        break
    for index in syllable.coda:
        if index == last + 1 and phones[index].kind == "sonorant":
            end = phones[index].start + 0.5 * phones[index].dur
        break
    return start, end


def settle_vowels(phones: list, syllables: list, analysis: dict) -> int:
    """Where a vowel's voiced part lies just outside its reported edges, move the edge it crosses so that the vowel
    contains it. Returns how many edges moved. Without this the held note is built from breath or from a closure."""
    def shift_edge(left: int, right: int, when: float) -> None:
        when = float(np.clip(when, phones[left].start + FRAME_S, phones[right].end - FRAME_S))
        phones[left].end = phones[right].start = when
        for between in range(left + 1, right):               # zero-length word breaks travel with the edge
            phones[between].start = phones[between].end = when

    def neighbour(index: int, step: int) -> int | None:
        index += step
        while 0 <= index < len(phones) and phones[index].dur <= 1e-6:
            index += step
        return index if 0 <= index < len(phones) and phones[index].kind != "pause" else None

    moved = 0
    for syllable in syllables:
        first, last = syllable.nucleus[0], syllable.nucleus[-1]
        hold = sustain_point(phones, syllable.nucleus, analysis, syllable_reach(phones, syllable))
        after, before = neighbour(last, 1), neighbour(first, -1)
        if hold + HOLD_HALF_S > phones[last].end and after is not None:
            shift_edge(last, after, hold + HOLD_HALF_S + FRAME_S)
            moved += 1
        elif hold - HOLD_HALF_S < phones[first].start and before is not None:
            shift_edge(before, first, hold - HOLD_HALF_S - FRAME_S)
            moved += 1
    return moved


def hold_quality(phones: list, nucleus: list, analysis: dict) -> dict:
    """How well a vowel can carry a held note, judged at the instant that would be held:
    periodicity below 4 kHz (0..1), level in dB, and whether it is voiced there."""
    centre = sustain_point(phones, nucleus, analysis)
    i = min(int(centre / FRAME_S), len(analysis["f0"]) - 1)
    a, b = max(0, i - 2), min(len(analysis["f0"]), i + 3)
    bins = max(1, int(analysis["ap"].shape[1] * 4000.0 / (0.5 * analysis["sr"])))
    return {"periodicity": 1.0 - float(analysis["ap"][a:b, :bins].mean()),
            "level_db": 10.0 * np.log10(float(analysis["sp"][a:b].sum(axis=1).mean()) + 1e-12),
            "voiced": bool((analysis["f0"][a:b] > 0).mean() >= 0.5)}


def voicing_onset(first, analysis: dict, limit: float) -> float:
    """When the voice really starts inside a vowel. Breath, aspiration or a glottal gap before it
    belongs ahead of the beat, with the consonants."""
    a, b = int(first.start / FRAME_S), min(int(limit / FRAME_S), len(analysis["f0"]))
    voiced = np.nonzero(analysis["f0"][a:b] > 0)[0]
    return first.start if len(voiced) == 0 else first.start + float(voiced[0]) * FRAME_S


def strong_until(analysis: dict, centre: float, end: float) -> float:
    """Last moment after the held instant at which the vowel is still voiced and within FADE_LIMIT_DB of its level there.
    A spoken vowel before a pause fades and goes breathy; that tail must not be what a sung note ends on."""
    a, b = int(centre / FRAME_S), min(int(end / FRAME_S), len(analysis["f0"]))
    if b <= a + 1:
        return end
    level = 10.0 * np.log10(analysis["sp"][a:b].sum(axis=1) + 1e-12)
    weak = (level < level[0] - FADE_LIMIT_DB) | (analysis["f0"][a:b] <= 0)
    faded = np.nonzero(weak)[0]
    return end if len(faded) == 0 else max(centre + HOLD_HALF_S, centre + float(faded[0]) * FRAME_S)


def _vowel_segments(phones: list, nucleus: list, start: float, end: float, source_start: float, centre: float,
                    source_end: float) -> list:
    """Hold a vowel over [start, end]: its attack and its release keep their natural length and the
    most stable instant in between is held for the rest. A diphthong therefore glides late."""
    index = nucleus[0]
    source, target = source_end - source_start, end - start
    if target <= source * 1.1 or source < 0.03:
        return [(start, end, source_start, source_end, index)]
    hold_a, hold_b = max(source_start, centre - HOLD_HALF_S), min(source_end, centre + HOLD_HALF_S)
    attack, release = hold_a - source_start, source_end - hold_b
    budget = MAX_EDGE_SHARE * target                     # long glides are compressed rather than eating the note
    attack_t, release_t = min(attack, budget), min(release, budget)
    return [(start, start + attack_t, source_start, hold_a, index),
            (start + attack_t, end - release_t, hold_a, hold_b, index),
            (end - release_t, end, hold_b, source_end, nucleus[-1])]


def _warp_frequency(sp: np.ndarray, semitones: float) -> np.ndarray:
    """Shift formants by resampling the spectral envelope along frequency."""
    if abs(semitones) < 1e-3:
        return sp
    ratio = 2.0 ** (semitones / 12.0)
    bins = np.arange(sp.shape[1])
    return np.stack([np.interp(bins / ratio, bins, frame, right=frame[-1]) for frame in sp])


def _flat_top_window(frequencies: np.ndarray, band: tuple, flat: tuple) -> np.ndarray:
    """1 inside `flat`, 0 outside `band`, half-cosine ramps between them on a log-frequency axis."""
    window = np.zeros(len(frequencies))
    ramp_in = (frequencies > band[0]) & (frequencies < flat[0])
    ramp_out = (frequencies > flat[1]) & (frequencies < band[1])
    window[(frequencies >= flat[0]) & (frequencies <= flat[1])] = 1.0
    window[ramp_in] = 0.5 - 0.5 * np.cos(np.pi * (np.log(frequencies[ramp_in]) - np.log(band[0])) / (np.log(flat[0]) - np.log(band[0])))
    window[ramp_out] = 0.5 + 0.5 * np.cos(np.pi * (np.log(frequencies[ramp_out]) - np.log(flat[1])) / (np.log(band[1]) - np.log(flat[1])))
    return window


def _fill_vowel_body(sp: np.ndarray, ap: np.ndarray, unit, syllables: list, phone_of: np.ndarray, filled: np.ndarray,
                     sr: int, strength: float) -> None:
    """Give held ee vowels the body of the line's other vowels, in place (see VOWEL_FILL_* above).

    The deficit is each ee vowel's median body level against the median body level of the line's other vowels less
    VOWEL_FILL_UNDER_DB; the lift is that deficit times `strength`, capped, flat over the middle of the body band
    with cosine ramps to its edges, and ramped in time at the vowel's ends. Breath noise above 2 kHz is thinned on
    the same frames.
    """
    if strength <= 0:
        return
    bins = sp.shape[1]
    frequencies = np.arange(bins) * sr / (2 * (bins - 1))
    body = (frequencies >= VOWEL_FILL_BODY_HZ[0]) & (frequencies < VOWEL_FILL_BODY_HZ[1])
    level = 10 * np.log10(sp[:, body].sum(axis=1) + 1e-30)
    window = _flat_top_window(frequencies, VOWEL_FILL_BODY_HZ, VOWEL_FILL_FLAT_HZ)
    breath = frequencies >= VOWEL_FILL_BREATH_HZ
    spans = [np.nonzero(np.isin(phone_of, syllable.nucleus) & filled)[0] for syllable in syllables]
    is_ee = [bool(s.nucleus) and unit.phones[s.nucleus[0]].symbol.replace("ː", "") in VOWEL_FILL_SYMBOLS for s in syllables]
    others = np.concatenate([level[frames] for frames, ee in zip(spans, is_ee) if not ee and len(frames)] or [np.array([])])
    if not len(others):
        return
    reference = float(np.median(others))
    edge = int(VOWEL_FILL_EDGE_S / FRAME_S)
    for frames, ee in zip(spans, is_ee):
        if not ee or len(frames) * FRAME_S < VOWEL_FILL_MIN_S:
            continue
        lift = float(np.clip((reference - VOWEL_FILL_UNDER_DB - np.median(level[frames])) * strength, 0.0, VOWEL_FILL_LIMIT_DB))
        if lift <= 0:
            continue
        taper = np.ones(len(frames))
        taper[:edge] = np.linspace(0.0, 1.0, edge)
        taper[-edge:] = np.linspace(1.0, 0.0, edge)
        sp[frames] *= 10 ** (lift * taper[:, None] * window[None, :] / 10)
        ap[frames[:, None], np.nonzero(breath)[0][None, :]] *= 1 - VOWEL_FILL_BREATH_SHARE * strength * taper[:, None]


def _soften_consonants(audio: np.ndarray, unit, segments: list, origin: float, ceiling_db: float) -> int:
    """Speech puts some t, s and k bursts as loud as the vowels; on a sung line, with the vowels held and evened out,
    those stand out as harsh clicks and hiss. Each unvoiced consonant louder than the ceiling is turned down to it."""
    sr = unit.sr
    window, edge = int(CONSONANT_WINDOW_S * sr), int(SPLICE_FADE_S * sr)
    count = 0
    for target_start, target_end, _source_start, _source_end, index in segments:
        a, b = max(0, int((target_start - origin) * sr)), min(len(audio), int((target_end - origin) * sr))
        if unit.phones[index].kind != "unvoiced" or b - a < max(window, 2 * edge + 1):
            continue
        power = np.convolve(audio[a:b] ** 2, np.ones(window) / window, mode="valid")
        excess = 10 * np.log10(float(power.max()) + SILENCE_FLOOR) - ceiling_db
        if excess <= 0:
            continue
        cut = 10.0 ** (-min(excess, CONSONANT_CUT_LIMIT_DB) / 20.0)
        gain = np.full(b - a, cut)
        gain[:edge], gain[-edge:] = np.linspace(1.0, cut, edge), np.linspace(cut, 1.0, edge)
        audio[a:b] *= gain
        count += 1
    return count


def sing(unit, analysis: dict, syllables: list, notes: list, style: dict | None = None, seed: int = 1) -> tuple:
    """Sung audio for one line. Returns (audio at unit.sr, pre_roll_seconds, info).
    `notes` are (start_s, dur_s, midi, tie) relative to the line start; the audio begins `pre_roll` before it."""
    import pyworld
    style = {**DEFAULT_STYLE, **(style or {})}
    rng = np.random.default_rng(seed)
    groups = note_groups(notes)
    segments, pre_roll, closing_phrase, holds = layout(unit, syllables, groups, analysis)
    origin = -pre_roll - 0.01
    total = max(seg[1] for seg in segments) - origin + 0.08
    n = int(np.ceil(total / FRAME_S))
    t = origin + np.arange(n) * FRAME_S
    source_frame = np.full(n, np.nan)
    phone_of = np.full(n, -1)
    for target_start, target_end, source_start, source_end, index in segments:
        a, b = int(np.ceil((target_start - origin) / FRAME_S)), int(np.ceil((target_end - origin) / FRAME_S))
        b = min(b, n)
        if b <= a:
            continue
        along = (t[a:b] - target_start) / max(target_end - target_start, 1e-6)
        source_frame[a:b] = (source_start + along * (source_end - source_start)) / FRAME_S
        phone_of[a:b] = index
    f0_source, sp_source, ap_source = analysis["f0"], analysis["sp"], analysis["ap"]
    last = len(f0_source) - 1
    filled = ~np.isnan(source_frame)
    position = np.clip(np.where(filled, source_frame, 0.0), 0, last)
    low = np.floor(position).astype(int)
    high = np.minimum(low + 1, last)
    weight = (position - low)[:, None]
    sp = (1.0 - weight) * sp_source[low] + weight * sp_source[high]
    ap = (1.0 - weight) * ap_source[low] + weight * ap_source[high]
    source_voiced = f0_source[np.round(position).astype(int)] > 0

    kinds = np.array([unit.phones[i].kind if i >= 0 else "pause" for i in phone_of])
    must_voice = np.isin(kinds, ("vowel", "sonorant")) & filled
    may_voice = (kinds == "voiced") & filled & source_voiced
    voiced = must_voice | may_voice
    forced = must_voice & ~source_voiced
    if forced.any() and (source_voiced & must_voice).any():
        # A devoiced vowel has pure-noise aperiodicity; borrow the periodicity of the voiced vowels.
        reference = np.median(ap[source_voiced & must_voice], axis=0)
        ap[forced] = np.minimum(ap[forced], reference)
    held_levels = [float(sp_source[min(int(hold / FRAME_S), last)].sum()) for hold in holds]
    typical = float(np.median(held_levels))
    for syllable, hold, held in zip(syllables, holds, held_levels):
        # Where the reported vowel sits a little early, the real vowel arrives after the held instant and the
        # syllable would end on a punch. What follows the held instant may not be louder than the line's usual
        # vowel level (or than this vowel's own held level, when that is higher).
        closing = list(syllable.nucleus) + [i for i in syllable.coda if unit.phones[i].kind == "sonorant"]
        tail = np.isin(phone_of, closing) & (position > hold / FRAME_S)
        if tail.any():
            limit = max(held, typical) * 10.0 ** (RELEASE_MARGIN_DB / 10.0)
            sp[tail] *= np.minimum(1.0, limit / np.maximum(sp[tail].sum(axis=1), 1e-20))[:, None]
    for index in closing_phrase:
        # Speech ends a phrase in a creak: the last vowel and an l, n, m or r after it die away in irregular bursts.
        # Sung on a steady pitch those bursts are heard as a tremble, so the end of the phrase follows the smoothed
        # level of the spoken fade and never rises again.
        syllable = syllables[index]
        closing = list(syllable.nucleus) + [i for i in syllable.coda if unit.phones[i].kind == "sonorant"]
        tail = np.nonzero(np.isin(phone_of, closing) & (position > holds[index] / FRAME_S))[0]
        width = max(1, int(RELEASE_SMOOTH_S / FRAME_S))
        if RELEASE_SMOOTH_S > 0 and len(tail) > width:
            level = 10.0 * np.log10(np.maximum(sp[tail].sum(axis=1), 1e-20))
            padded = np.concatenate([np.full(width, level[0]), level, np.full(width, level[-1])])
            smooth = np.convolve(padded, np.ones(width) / width, mode="same")[width:-width]
            steady = np.minimum.accumulate(smooth)
            sp[tail] *= 10.0 ** (np.clip(steady - level, -RELEASE_TRIM_DB, RELEASE_FILL_DB) / 10.0)[:, None]
    sung_vowels = (kinds == "vowel") & filled
    clean = sung_vowels & source_voiced
    if clean.sum() >= MIN_FRAMES_FOR_BREATH_CAP:
        # Speech lets breath ride on short vowels after p, t, k and h; held on a note that breath is heard as hiss.
        # No sung vowel may be breathier than the take's ordinary voiced vowels.
        ceiling = np.percentile(ap[clean], VOWEL_BREATH_PERCENTILE, axis=0)
        ap[sung_vowels] = np.minimum(ap[sung_vowels], ceiling)
    if style["breath"] > 0:
        ap = np.clip(ap + style["breath"] * (1.0 - ap), 0.0, 1.0)
    _fill_vowel_body(sp, ap, unit, syllables, phone_of, filled, unit.sr, style.get("vowel_body", 0.0))
    sp = _warp_frequency(sp, style["formant"])
    if style.get("ring", 0.0) > 0:
        hz = np.arange(sp.shape[1]) * (0.5 * unit.sr / (sp.shape[1] - 1))
        bell = np.exp(-0.5 * ((hz - RING_HZ) / RING_WIDTH_HZ) ** 2)
        width = max(1, int(RING_SMOOTH_S / FRAME_S))
        amount = np.convolve((kinds == "vowel").astype(float), np.ones(width) / width, mode="same")
        sp = sp * 10.0 ** (style["ring"] * amount[:, None] * bell[None, :] / 10.0)
    sp[~filled] = SILENCE_FLOOR
    midi = pitch_curve(groups, n, origin, style, rng)
    f0 = np.where(voiced, 440.0 * 2.0 ** ((midi - 69.0) / 12.0), 0.0)
    audio = pyworld.synthesize(f0, np.ascontiguousarray(sp), np.ascontiguousarray(np.clip(ap, 0.0, 1.0)), unit.sr,
                               FRAME_S * 1000)

    # --- crisp consonants: unvoiced obstruents at natural speed are copied from the recording
    sr = unit.sr
    fade = int(SPLICE_FADE_S * sr)
    spliced = 0
    for target_start, target_end, source_start, source_end, index in segments:
        phone = unit.phones[index]
        natural = abs((target_end - target_start) - (source_end - source_start)) < 0.004
        if not SPLICE_CONSONANTS or phone.kind != "unvoiced" or not natural:
            continue
        a = int((target_start - origin) * sr)
        piece = unit.audio[int(source_start * sr):int(source_end * sr)].astype(np.float64)
        if len(piece) <= 2 * fade or a < 0 or a + len(piece) > len(audio):
            continue
        ramp = np.ones(len(piece))
        ramp[:fade], ramp[-fade:] = np.linspace(0, 1, fade), np.linspace(1, 0, fade)
        audio[a:a + len(piece)] = audio[a:a + len(piece)] * (1.0 - ramp) + piece * ramp
        spliced += 1

    # --- even out syllable loudness and close the phrase. Levels are measured on what was actually sung:
    # the held slice of a vowel can be louder or quieter than the spoken vowel was on average.
    gains_t, gains, levels = [], [], []
    for group in groups:
        a = int((group[0] - origin + LEVEL_EDGE_S) * sr)
        b = max(a + int(0.02 * sr), int((group[1] - origin - LEVEL_EDGE_S) * sr))
        piece = audio[max(a, 0):min(b, len(audio))]
        levels.append(10 * np.log10(float(np.mean(piece ** 2)) + 1e-12) if len(piece) else -80.0)
    median = float(np.median(levels))
    for group, level in zip(groups, levels):
        gains_t.append(0.5 * (group[0] + group[1]))
        gains.append(float(np.clip((median - level) * style["level"], -LEVEL_LIMIT_DB, LEVEL_LIMIT_DB)))
    sample_t = origin + np.arange(len(audio)) / sr
    audio = audio * 10.0 ** (np.interp(sample_t, gains_t, gains) / 20.0)
    softened = _soften_consonants(audio, unit, segments, origin, median + style["consonant_ceiling"])
    for group, following in zip(groups, groups[1:] + [None]):
        if following is None or following[0] - group[1] >= REST_GAP_S:      # release before a rest
            end = group[1]
            fall = np.clip((end + 0.06 - sample_t) / 0.08, 0.0, 1.0)
            window = (sample_t > end - 0.02) & (sample_t < end + 0.2)
            audio[window] *= fall[window]
    info = {"frames": n, "forced_voiced_frames": int(forced.sum()), "spliced_consonants": spliced, "level_gains_db": gains,
            "softened_consonants": softened,
            "f0_midi": midi, "voiced": voiced, "origin": origin, "segments": segments}
    return audio.astype(np.float32), -origin, info
