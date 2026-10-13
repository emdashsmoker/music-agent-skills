# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Lyric craft checks for sung lines: what makes words carry on a melody, tested before any audio is mixed.

lint_line() reads a line and its melody and reports the patterns that measurably blur a TTS-sung
line (short notes, weak words on strong notes, stop-ended words on long notes ...).
compare() sings several wordings on the same notes and scores each, to choose between them.
The rules are starting points taken from measurements on English TTS voices; a line the user has
heard and approved stays as it is, whatever the lint or the score says.
"""
from __future__ import annotations

import numpy as np

from ..findings import finding
from . import asr, lines, tts
from .phones import PLOSIVES, AFFRICATES, NASALS, UNSTABLE_WORDS, VOWELS, WEAK_WORDS, fold_weak_syllables, merge_tokens, syllabify
from .singing import OUTPUT_SR, Style

MIN_NOTE_S = 0.110                 # shorter notes smear consonants (a 16th at 140 bpm is 107 ms)
LONG_NOTE_BEATS = 2.0
STRONG_NOTE_BEATS = 1.0
SHORT_NOTE_BEATS = 0.5
CLUSTER_SIZE = 2
WEAK_RUN = 3
VOICE_RANGE_SEMITONES = 9          # comfortable distance of a melody from the voice's speaking pitch
CHORUS_MAX_SYLLABLES = 7
PERIOD_SEARCH = 0.05


def _words(text: str) -> list[str]:
    return [w.strip(".,!?;:\"()").lower() for w in text.split() if w.strip(".,!?;:\"()")]


def line_syllables(voice: str, text: str, wanted: int | None = None):
    """Syllables of a line as the engine pronounces it (folded toward `wanted` if given), without synthesizing."""
    phonemes = tts.backend(voice).phonemize(text)
    symbols = list(phonemes)
    syllables = syllabify(merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols)))
    return fold_weak_syllables(syllables, wanted) if wanted is not None else syllables


def lint_line(voice: str, line: lines.Line, bpm: float, natural_pitch: float | None = None, role: str = "verse") -> list[dict]:
    """Findings for one line. natural_pitch (MIDI) enables the range check; role 'chorus' adds chorus rules."""
    found = []
    words = _words(line.text)
    groups, _, _ = lines.note_groups(line.melody, bpm)
    seconds_per_beat = 60.0 / bpm
    spoken = line_syllables(voice, line.text)
    syllables = fold_weak_syllables(spoken, len(groups))
    label = f"'{line.text}'"
    if len(syllables) != len(groups):
        per_word = {}
        for syllable in spoken:
            per_word[syllable.word] = per_word.get(syllable.word, 0) + 1
        table = ", ".join(f"{words[i] if i < len(words) else '?'}={count}" for i, count in sorted(per_word.items()))
        return [finding("error", "syllable_count", f"{label}: {len(spoken)} spoken syllables but {len(groups)} melody tokens ({table})")]
    if len(spoken) != len(syllables):
        found.append(finding("info", "folded_syllable", f"{label}: a weak second vowel is sung inside the note before it (fire, hour ...)"))
    for word in set(words) & UNSTABLE_WORDS:
        index = words.index(word)
        beats = [sum(n.duration for n in groups[i]) / seconds_per_beat for i, s in enumerate(syllables) if s.word == index]
        if not beats or max(beats) < LONG_NOTE_BEATS:
            found.append(finding("warn", "unstable_word", f"{label}: '{word}' has an unsteady syllable count; give it one note of {LONG_NOTE_BEATS:g}+ beats or choose another word"))
    durations = [sum(n.duration for n in group) for group in groups]
    beats = [d / seconds_per_beat for d in durations]
    weak = [words[s.word] in WEAK_WORDS if s.word < len(words) else False for s in syllables]
    for index, (syllable, seconds) in enumerate(zip(syllables, durations)):
        shortest = min(n.duration for n in groups[index])
        if shortest < MIN_NOTE_S:
            found.append(finding("warn", "note_too_short", f"{label}: '{syllable.text}' gets a {shortest * 1000:.0f} ms note; under {MIN_NOTE_S * 1000:.0f} ms consonants smear"))
        cluster = len(syllable.onset) >= CLUSTER_SIZE or len(syllable.coda) >= CLUSTER_SIZE
        if beats[index] <= SHORT_NOTE_BEATS and cluster:
            found.append(finding("warn", "cluster_on_short_note", f"{label}: '{syllable.text}' packs a consonant cluster into {beats[index]:g} beat"))
        ends_in_stop = bool(syllable.coda) and syllable.coda[-1].symbol[0] in PLOSIVES | AFFRICATES
        last_of_word = index + 1 == len(syllables) or syllables[index + 1].word != syllable.word
        if beats[index] >= LONG_NOTE_BEATS and ends_in_stop:
            found.append(finding("warn", "stop_on_long_note", f"{label}: '{syllable.text}' ends in a stop but holds {beats[index]:g} beats; an open vowel (day, go, you) sustains better"))
        if beats[index] >= LONG_NOTE_BEATS and weak[index] and last_of_word and index + 1 != len(syllables):
            found.append(finding("warn", "weak_word_on_long_note", f"{label}: weak word '{words[syllable.word]}' holds {beats[index]:g} beats"))
        if (index + 1 < len(syllables) and beats[index] >= STRONG_NOTE_BEATS and beats[index + 1] >= STRONG_NOTE_BEATS
                and ends_in_stop and syllables[index + 1].coda and syllables[index + 1].coda[-1].symbol[0] in PLOSIVES):
            found.append(finding("warn", "stop_words_in_a_row", f"{label}: two stop-ended syllables on notes of a beat or more ('{syllable.text}', '{syllables[index + 1].text}')"))
    if weak and weak[0]:
        found.append(finding("info", "weak_opening", f"{label}: opens on the weak word '{words[0]}'; recognisers and listeners catch a line better from a content word"))
    run = 0
    for index, flag in enumerate(weak):
        run = run + 1 if flag else 0
        if run == WEAK_RUN:
            found.append(finding("warn", "weak_words_in_a_row", f"{label}: {WEAK_RUN} weak-word syllables in a row ending at '{syllables[index].text}'"))
    for index in range(2, len(syllables)):
        if beats[index] >= LONG_NOTE_BEATS and weak[index - 1] and weak[index - 2] and beats[index - 1] <= SHORT_NOTE_BEATS and beats[index - 2] <= SHORT_NOTE_BEATS:
            found.append(finding("warn", "weak_pickup", f"{label}: two short weak words lead into the long note on '{syllables[index].text}'"))
    final = syllables[-1]
    if beats[-1] >= LONG_NOTE_BEATS and final.coda and final.coda[-1].symbol[0] in NASALS:
        found.append(finding("info", "nasal_line_end", f"{label}: the last long note closes on a nasal (second-best to an open vowel)"))
    if role == "chorus" and len(syllables) > CHORUS_MAX_SYLLABLES:
        found.append(finding("info", "chorus_density", f"{label}: {len(syllables)} syllables; chorus lines usually carry 5-{CHORUS_MAX_SYLLABLES} with a held last note"))
    if natural_pitch is not None:
        pitches = [n.pitch for g in groups for n in g]
        if max(pitches) - natural_pitch > VOICE_RANGE_SEMITONES + 5 or natural_pitch - min(pitches) > VOICE_RANGE_SEMITONES:
            found.append(finding("warn", "voice_range", f"{label}: melody spans MIDI {min(pitches)}-{max(pitches)}, far from this voice's speaking pitch ({natural_pitch:.0f}); transpose or pick another voice"))
    return found


def rhyme_vowel(voice: str, text: str) -> str:
    """Vowel sound that ends a line, for checking rhyme pairs."""
    syllables = line_syllables(voice, text)
    return "".join(p.symbol for p in syllables[-1].nucleus) if syllables and syllables[-1].nucleus else ""


def periodicity(audio: np.ndarray, sr: int, f0_hz: float, start: float, end: float) -> float:
    """How pitched a held note is: mean normalised autocorrelation at the note's period (1 = clean tone, 0 = noise).

    The period is searched a few percent around the written pitch in every window, so vibrato does not count as noise.
    """
    piece = audio[int(start * sr):int(end * sr)]
    centre = int(round(sr / f0_hz))
    window = 4 * centre
    lags = range(max(2, int(centre * (1 - PERIOD_SEARCH))), int(centre * (1 + PERIOD_SEARCH)) + 2)
    scores = []
    for offset in range(0, len(piece) - window - max(lags), window // 2):
        a = piece[offset:offset + window]
        best = 0.0
        for lag in lags:
            b = piece[offset + lag:offset + lag + window]
            denominator = np.sqrt(np.sum(a * a) * np.sum(b * b))
            if denominator > 1e-9:
                best = max(best, float(np.sum(a * b) / denominator))
        scores.append(best)
    return float(np.clip(np.mean(scores), 0.0, 1.0)) if scores else 0.0


def last_note_periodicity(sung) -> float:
    """Periodicity of the last held vowel of a sung line."""
    item, note = sung.layout[-1], sung.notes[-1]
    f0 = 440.0 * 2 ** ((note.pitch - 69) / 12)
    middle = item["vowel_start"] + 0.25 * (item["vowel_end"] - item["vowel_start"])
    return periodicity(sung.audio, OUTPUT_SR, f0, middle, item["vowel_end"] - 0.03)


def compare(voice: str, melody: str, texts: list[str], bpm: float, *, cache: str | None = None, style: Style | None = None,
            out_dir: str | None = None, asr_model: str | None = None, method: str = "auto", lang: str = "en", **options) -> list[dict]:
    """Sing each candidate wording on the same melody with any engine and score it.

    Candidates must have the melody's syllable count; one that does not is returned with an 'error' entry.
    """
    from . import engines
    results = []
    for index, text in enumerate(texts):
        try:
            sung, report = engines.render_line(voice, lines.Line(text, melody), bpm, cache=cache, style=style, method=method, lang=lang, **options)
        except (ValueError, KeyError) as error:
            results.append({"text": text, "error": str(error)})
            continue
        scored = asr.score_line(sung.audio, OUTPUT_SR, text, asr_model, language=lang)
        entry = {"text": text, "score": scored["score"], "heard": scored["heard"], "scores": scored["scores"],
                 "ending_repaired": bool((report.get("ending") or {}).get("repaired")),
                 "last_note_periodicity": round(last_note_periodicity(sung), 2)}
        if out_dir:
            entry["wav"] = lines.write_wav(f"{out_dir}/candidate_{index + 1}.wav", sung.audio)
        results.append(entry)
    return results
