# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Speech recognition as a lyric-intelligibility detector (faster-whisper).

The score says how much of a sung line a recogniser gets back. It finds weak lines; it does not
judge them. A recogniser hears the same audio differently with and without context, and a change
that raises the score can still sound less clear to a person, so listening decides.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np

from .. import settings

DEFAULT_MODEL = "base.en"                # larger models are slower; set asr_model or pass --asr-model for another
WEAK_LINE_SCORE = 0.85
PADDINGS_S = (0.0, 0.25, 0.5)             # silence added around a line for the first recognition passes
MORE_PADDINGS_S = tuple(i * 0.0625 for i in range(9) if i not in (0, 4, 8))   # the six extra passes when the first three disagree
STEADY_SPREAD = 0.1                       # first passes within this of each other need no extra passes
ASR_SAMPLE_RATE = 16000
WHISPER_LANGUAGES = {"cmn": "zh", "nb": "no"}   # espeak's language names -> the recogniser's, where the two differ
_models: dict[str, object] = {}


def _model(name: str):
    if name not in _models:
        from faster_whisper import WhisperModel
        _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _models[name]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)           # a decomposed lyric (NFD Hangul) has two or three times the characters
    return re.sub(r"\s+", " ", re.sub(r"[^\w' ]+", " ", text.lower())).strip()


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def match(expected: str, heard: str) -> float:
    """1.0 = every character recovered; 0 = nothing (1 - character error rate, floored at 0)."""
    expected, heard = normalize(expected), normalize(heard)
    if not expected:
        return 1.0
    return max(0.0, 1.0 - edit_distance(expected, heard) / len(expected))


def model_for(language: str | None, model: str | None = None) -> str:
    """`model`, else the setting asr_model, else base.en. An English-only model (.en) hears other languages as
    English, so lyrics in another language get its multilingual twin of the same size (base.en -> base)."""
    chosen = model or settings.get("asr_model") or DEFAULT_MODEL
    english = (language or "en").lower().startswith("en")
    return chosen if english or not chosen.endswith(".en") else chosen.removesuffix(".en")


def language_code(language: str | None) -> str | None:
    """The recogniser's code for a language given as a song code (zh) or an espeak name (cmn, en-gb)."""
    if not language:
        return None
    base = language.lower().split("-")[0]
    return WHISPER_LANGUAGES.get(base, base)


def transcribe(audio: np.ndarray, sr: int, model: str | None = None, language: str | None = "en", prompt: str | None = None) -> str:
    """Recognised text of a mono signal. Greedy settings with temperature 0 keep the result repeatable."""
    from scipy import signal
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    if sr != ASR_SAMPLE_RATE:
        divisor = np.gcd(ASR_SAMPLE_RATE, sr)
        mono = signal.resample_poly(mono, ASR_SAMPLE_RATE // divisor, sr // divisor)
    segments, _ = _model(model_for(language, model)).transcribe(mono.astype(np.float32), language=language_code(language), beam_size=5, temperature=0.0,
                                           condition_on_previous_text=False, initial_prompt=prompt, vad_filter=False)
    return " ".join(segment.text.strip() for segment in segments).strip()


def score_line(audio: np.ndarray, sr: int, expected: str, model: str | None = None, language: str | None = "en") -> dict:
    """Recognition score of one sung line: the second-best pass over a few amounts of leading and trailing silence.

    On a sung line of a few seconds the recogniser's answer flips with a few hundred milliseconds of padding, and on
    a line near the limit a change of one 16-bit step in the audio moved the median of three passes from 1.00 to
    0.56. Those failed passes are empty or invented transcripts, not a different hearing of the words, so one good
    pass is luck and two are evidence: the score is the second-best pass. Three passes decide when they agree
    within STEADY_SPREAD; otherwise six more paddings are tried first. 'scores' keeps every pass, sorted.
    """
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)

    def run(paddings) -> list[tuple[float, str]]:
        out = []
        for seconds in paddings:
            silence = np.zeros(int(seconds * sr))
            heard = transcribe(np.concatenate([silence, mono, silence]), sr, model, language)
            out.append((match(expected, heard), heard))
        return out
    passes = run(PADDINGS_S)
    if max(score for score, _ in passes) - min(score for score, _ in passes) > STEADY_SPREAD:
        passes += run(MORE_PADDINGS_S)
    passes.sort(key=lambda item: item[0])
    value, heard = passes[-2]
    return {"expected": expected, "heard": heard, "score": round(value, 2), "weak": value < WEAK_LINE_SCORE,
            "scores": [round(score, 2) for score, _ in passes]}
