# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""The ruler must find offsets it was given. A synthetic line: each syllable is a hiss followed by a harmonic tone,
with the tone starting a known time after the beat and, on one note, a known pitch error in the note's head.

Pass: every onset within ONSET_TOLERANCE_MS of the planted offset, head errors within HEAD_TOLERANCE_CENTS.
"""
import json
import os
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocal_timing  # noqa: E402

SR = 44100
BPM = 120.0
TEXT = "See saw sue"                         # three syllables, each opening on a voiceless s
MELODY = "A3/1 C4/1 E4/1 R/1"
FIRST_NOTE_S = 1.0
PLANTED_ONSET_MS = [20.0, -15.0, 0.0]
PLANTED_HEAD_CENTS = [0.0, 50.0, 0.0]
HISS_S = 0.08
TAIL_S = 0.05
ONSET_TOLERANCE_MS = 7.5                     # one and a half analysis frames
HEAD_TOLERANCE_CENTS = 10.0


def _tone(f0: np.ndarray) -> np.ndarray:
    phase = 2 * np.pi * np.cumsum(f0) / SR
    return sum((0.5 / k) * np.sin(k * phase) for k in range(1, 12))


def build(directory: str) -> str:
    rng = np.random.default_rng(1)
    audio = np.zeros(int(5.0 * SR))
    spans = []
    for index, (midi, onset_ms, head_cents) in enumerate(zip((57, 60, 64), PLANTED_ONSET_MS, PLANTED_HEAD_CENTS)):
        beat = FIRST_NOTE_S + index * 0.5
        voice_on = beat + onset_ms / 1000.0
        hiss_a, hiss_b = int((beat - HISS_S) * SR), int(voice_on * SR)
        audio[hiss_a:hiss_b] += 0.05 * rng.standard_normal(hiss_b - hiss_a)
        tone_a, tone_b = int(voice_on * SR), int((beat + 0.5 - TAIL_S) * SR)
        t = np.arange(tone_b - tone_a) / SR + (voice_on - beat)
        hz = 440.0 * 2 ** ((midi - 69) / 12) * np.where(t < vocal_timing.HEAD_S, 2 ** (head_cents / 1200), 1.0)
        audio[tone_a:tone_b] += 0.3 * _tone(hz)
        spans.append({"text": "s", "start_s": beat, "end_s": beat + 0.5 - TAIL_S, "pitches": [midi]})
    stem = os.path.join(directory, "stem.flac")
    sf.write(stem, audio, SR, subtype="PCM_16")
    row = {"text": TEXT, "melody": MELODY, "first_note_s": FIRST_NOTE_S, "audio_start_s": FIRST_NOTE_S - 0.2,
           "audio_end_s": FIRST_NOTE_S + 1.6, "report": {}, "syllables": spans}
    with open(os.path.join(directory, "vocals.json"), "w") as handle:
        json.dump({"bpm": BPM, "voice": "synthetic", "checkout": "-", "parts": [{"stem": stem, "lines": [row]}]}, handle)
    return directory


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        result = vocal_timing.measure(build(directory), use_asr=False)
    syllables = result["lines"][0]["syllables"]
    failures = []
    for syllable, onset_ms, head_cents in zip(syllables, PLANTED_ONSET_MS, PLANTED_HEAD_CENTS):
        found = syllable["onset_ms"]
        if syllable["onset_class"] != "voiceless" or found is None or abs(found - onset_ms) > ONSET_TOLERANCE_MS:
            failures.append(f"syllable {syllable['index']}: onset {found} ms (class {syllable['onset_class']}), planted {onset_ms}")
        head = syllable["head_cents"][0] if syllable["head_cents"] else None
        if head is None or abs(head - abs(head_cents)) > HEAD_TOLERANCE_CENTS:
            failures.append(f"syllable {syllable['index']}: head {head} cents, planted {head_cents}")
    print(json.dumps([{k: s[k] for k in ("onset_class", "onset_ms", "head_cents", "periodicity")} for s in syllables]))
    print("FAIL\n" + "\n".join(failures) if failures else "PASS")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
