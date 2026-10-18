# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Line-ending repair for speech voices.

A speech voice lets the last word of a sentence die away: quiet, breathy, often whispered. In a song
that word usually carries the longest note, and a whisper held for a second is hiss. The cure: speak
the line once more with a short carrier word after it, which keeps the real last word in full voice,
and splice only that last syllable onto the plain take. The carrier word itself is never sung.
"""
from __future__ import annotations

import numpy as np

from . import world
from .phones import Phone, syllabify
from .tts import Unit

VOICED_SHARE_MIN = 0.85          # the last vowel is "dying" when less than this share of it is voiced
QUIET_DB = 9.0                   # or when it is this far below the line's typical vowel
CARRIER_WORDS = {"en": "but"}    # starts with a stop so the cut is clean; languages not listed are skipped
SPLICE_FADE_S = 0.008
TAIL_S = 0.05
GAIN_LIMITS = (0.5, 2.0)


def _nucleus_span(syllable) -> tuple[float, float]:
    return syllable.nucleus[0].start, syllable.nucleus[-1].end


def _level_db(unit: Unit, span: tuple[float, float]) -> float:
    piece = unit.audio[int(span[0] * unit.sr):int(span[1] * unit.sr)]
    return 10 * np.log10(float(np.mean(piece ** 2)) + 1e-14) if len(piece) else -140.0


def ending_report(unit: Unit, f0: np.ndarray | None = None) -> dict:
    """Voiced share and relative level of the last vowel, and whether it counts as dying."""
    syllables = [s for s in syllabify(unit.phones) if s.nucleus]
    if not syllables:
        return {"dying": False, "voiced_share": 1.0, "level_vs_line_db": 0.0}
    f0 = world.quick_f0(unit.audio, unit.sr) if f0 is None else f0
    start, end = (int(t / world.FRAME_S) for t in _nucleus_span(syllables[-1]))
    frames = f0[start:max(end, start + 1)]
    voiced_share = float((frames > 0).mean()) if len(frames) else 0.0
    levels = [_level_db(unit, _nucleus_span(s)) for s in syllables]
    relative = levels[-1] - float(np.median(levels[:-1])) if len(levels) >= 3 else 0.0
    return {"dying": bool(voiced_share < VOICED_SHARE_MIN or relative < -QUIET_DB), "voiced_share": round(voiced_share, 3),
            "level_vs_line_db": round(float(relative), 1)}


def repair(backend, unit: Unit, speed: float, seed: int) -> Unit | None:
    """Unit with a fully voiced last syllable, or None when the repair does not apply or is not safe."""
    carrier = CARRIER_WORDS.get(str(getattr(backend, "lang", "") or "")[:2].lower())
    if not carrier:
        return None
    plain_text = backend.phonemize(unit.text)
    extended_text = backend.phonemize(f"{unit.text} {carrier}")
    if not (extended_text.startswith(plain_text) and len(extended_text) > len(plain_text)):
        return None                                   # the extra word changed how the line itself is pronounced
    donor = backend.synthesize(f"{unit.text} {carrier}", speed, seed)
    plain_syllables = [s for s in syllabify(unit.phones) if s.nucleus]
    donor_syllables = [s for s in syllabify(donor.phones) if s.nucleus]
    if len(donor_syllables) <= len(plain_syllables):
        return None
    last_plain, last_donor = plain_syllables[-1], donor_syllables[len(plain_syllables) - 1]
    if [p.symbol for p in last_plain.phones] != [p.symbol for p in last_donor.phones]:
        return None                                   # the two takes disagree about the last syllable
    cut, donor_cut, donor_end = last_plain.phones[0].start, last_donor.phones[0].start, last_donor.phones[-1].end
    sr = unit.sr
    head, tail = unit.audio[:int(cut * sr)], donor.audio[int(donor_cut * sr):int(donor_end * sr)]
    if len(plain_syllables) >= 2:                      # match loudness on the syllable before the splice
        before = np.sqrt(np.mean(unit.audio[slice(*(int(t * sr) for t in _nucleus_span(plain_syllables[-2])))] ** 2))
        donor_before = np.sqrt(np.mean(donor.audio[slice(*(int(t * sr) for t in _nucleus_span(donor_syllables[len(plain_syllables) - 2])))] ** 2))
        if before > 0 and donor_before > 0:
            tail = tail * float(np.clip(before / donor_before, *GAIN_LIMITS))
    fade = min(int(SPLICE_FADE_S * sr), len(head), len(tail))
    ramp = np.linspace(0.0, 1.0, fade) if fade else np.zeros(0)
    audio = np.concatenate([head[:len(head) - fade], head[len(head) - fade:] * (1 - ramp) + tail[:fade] * ramp, tail[fade:],
                            np.zeros(int(TAIL_S * sr))])
    shift = cut - fade / sr - donor_cut
    first_index = unit.phones.index(last_plain.phones[0])
    spliced = [Phone(p.symbol, p.start + shift, p.end + shift, last_plain.word, p.stressed) for p in last_donor.phones]
    return Unit(audio, sr, unit.phones[:first_index] + spliced, unit.text, unit.lag, snapped=unit.snapped)
