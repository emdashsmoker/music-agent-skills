# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Speech recognition as a lyric-intelligibility probe.

A recogniser that cannot make out a sung line is evidence (not proof) that a listener will struggle
too. Scores find the weak lines; whether a line is acceptable is decided by listening."""
from __future__ import annotations

import difflib
import os
import re
import unicodedata

import numpy as np
from scipy import signal

from . import settings, speech

ASR_RATE = 16000
WHISPER_LANGUAGES = {"cmn": "zh", "nb": "no"}   # espeak's language names -> the recogniser's, where the two differ
_models = {}


def language_code(language: str | None) -> str | None:
    """The recogniser's code for a language given as a song code (zh) or an espeak name (cmn, en-gb)."""
    if not language:
        return None
    base = language.lower().split("-")[0]
    return WHISPER_LANGUAGES.get(base, base)


# The recogniser writes Japanese and Chinese in a script of its own choosing: kanji or katakana for kana lyrics,
# traditional characters for simplified ones. Counted letter by letter, a line that came through scored low ("谢谢你"
# heard as "謝謝你" scored 0.33), so lines in these languages are compared by sound: Chinese as espeak reads it,
# Japanese in hiragana, with kanji read by the pykakasi package when it is installed.
KATAKANA_TO_HIRAGANA = {code: code - 0x60 for code in range(0x30A1, 0x30F7)}
_readers: dict[str, object] = {}


def _reader(name: str):
    """A text reader loaded once: 'kakasi' (Japanese kanji to kana) or 'kokoro' (espeak through Kokoro's tokenizer);
    None when its package is missing."""
    if name not in _readers:
        try:
            if name == "kakasi":
                import pykakasi
                _readers[name] = pykakasi.kakasi()
            else:
                from kokoro_onnx.tokenizer import Tokenizer
                _readers[name] = Tokenizer()
        except ImportError:
            _readers[name] = None
    return _readers[name]


def comparable(text: str, language: str | None) -> str:
    """The form a line is scored in: Chinese as its sound, Japanese in hiragana, every other language as written."""
    code = language_code(language)
    if code == "zh" and _reader("kokoro") is not None:
        return _reader("kokoro").phonemize(text, "cmn").replace(" ", "")
    if code == "ja":
        reader = _reader("kakasi")
        text = "".join(item["hira"] for item in reader.convert(text)) if reader is not None else text
        return text.translate(KATAKANA_TO_HIRAGANA)
    return text


def model_for(model: str, language: str | None) -> str:
    """An English-only model (base.en) hears other languages as English: for them, its multilingual twin of the same size."""
    code = language_code(language)
    return model.removesuffix(".en") if model.endswith(".en") and code and code != "en" else model


def _model(name: str):
    if name not in _models:
        from faster_whisper import WhisperModel
        from .singing import VocalError
        root = os.path.join(speech.models_dir(), "whisper")
        try:
            _models[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(1, (os.cpu_count() or 2)),
                                         download_root=root, local_files_only=bool(settings.get("offline")))
        except Exception as error:                       # the model is fetched on first use; that needs the network
            raise VocalError(f"recognition model {name!r} could not be loaded ({type(error).__name__}: {error}). It is downloaded on "
                             f"first use into {root}; without network access, copy a faster-whisper model folder there or pass "
                             "its path as --asr-model") from error
    return _models[name]


STUCK_LETTER = re.compile(r"(.)\1{3,}")


def transcribe(audio: np.ndarray, sr: int, model: str | None = None, language: str | None = None) -> str:
    """Greedy-free, temperature-zero decoding of a mono array: the same audio always gives the same text."""
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    divisor = np.gcd(ASR_RATE, sr)
    mono = signal.resample_poly(mono, ASR_RATE // divisor, sr // divisor).astype(np.float32)
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    if peak < 1e-4:
        return ""
    segments, _ = _model(model or settings.get("asr_model")).transcribe(mono / peak * 0.9, beam_size=5, temperature=0.0, language=language,
                                           condition_on_previous_text=False, without_timestamps=True)
    heard = " ".join(segment.text.strip() for segment in segments)
    return STUCK_LETTER.sub(r"\1\1\1", heard)          # keep reports readable when a held note makes it stutter


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)           # a decomposed lyric (NFD Hangul) has two or three times the characters
    text = STUCK_LETTER.sub(r"\1", text.lower())     # a recogniser stuck on a held note repeats one letter
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)).strip()


def similarity(reference: str, heard: str, language: str | None = None) -> float:
    """Character-level match between the lyric and what was recognised, 0..1. Japanese and Chinese lines are
    compared in the form comparable() gives them."""
    a, b = normalise(comparable(reference, language)), normalise(comparable(heard, language))
    if not a.isascii():                 # outside Latin script, word spacing is a spelling convention the ear cannot hear
        a, b = a.replace(" ", ""), b.replace(" ", "")
    if not a:
        return 1.0 if not b else 0.0
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)
