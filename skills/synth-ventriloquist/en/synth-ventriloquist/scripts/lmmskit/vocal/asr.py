# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Speech recognition as a lyric-intelligibility detector (faster-whisper).

The score says how much of a sung line a recogniser gets back. It finds weak lines; it does not
judge them. A recogniser hears the same audio differently with and without context, and a change
that raises the score can still sound less clear to a person, so listening decides.
"""
from __future__ import annotations

import re

import numpy as np

DEFAULT_MODEL = "base.en"                # larger models are slower and rarely change which lines get flagged
MULTILINGUAL_MODEL = "base"
WEAK_LINE_SCORE = 0.85
PADDINGS_S = (0.0, 0.25, 0.5)             # silence added around a line for the repeated recognition passes
ASR_SAMPLE_RATE = 16000
_models: dict[str, object] = {}


def _model(name: str):
    if name not in _models:
        from faster_whisper import WhisperModel
        _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _models[name]


def normalize(text: str) -> str:
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


def model_for(language: str | None) -> str:
    """The small English-only model for English, the multilingual one of the same size otherwise."""
    return DEFAULT_MODEL if (language or "en").lower().startswith("en") else MULTILINGUAL_MODEL


def transcribe(audio: np.ndarray, sr: int, model: str | None = None, language: str | None = "en", prompt: str | None = None) -> str:
    """Recognised text of a mono signal. Greedy settings with temperature 0 keep the result repeatable."""
    from scipy import signal
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    if sr != ASR_SAMPLE_RATE:
        divisor = np.gcd(ASR_SAMPLE_RATE, sr)
        mono = signal.resample_poly(mono, ASR_SAMPLE_RATE // divisor, sr // divisor)
    segments, _ = _model(model or model_for(language)).transcribe(mono.astype(np.float32), language=language, beam_size=5, temperature=0.0,
                                           condition_on_previous_text=False, initial_prompt=prompt, vad_filter=False)
    return " ".join(segment.text.strip() for segment in segments).strip()


def score_line(audio: np.ndarray, sr: int, expected: str, model: str | None = None, language: str | None = "en") -> dict:
    """Recognition score of one sung line: the median over a few amounts of leading and trailing silence.

    A recogniser's answer on sung audio can flip with a few hundred milliseconds of padding, so a single pass
    raises false alarms; the median of three is steadier. 'scores' keeps all passes.
    """
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    passes = []
    for seconds in PADDINGS_S:
        silence = np.zeros(int(seconds * sr))
        heard = transcribe(np.concatenate([silence, mono, silence]), sr, model, language)
        passes.append((match(expected, heard), heard))
    passes.sort(key=lambda item: item[0])
    value, heard = passes[len(passes) // 2]
    return {"expected": expected, "heard": heard, "score": round(value, 2), "weak": value < WEAK_LINE_SCORE,
            "scores": [round(score, 2) for score, _ in passes]}
