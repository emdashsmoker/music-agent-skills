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
from .phones import (AFFRICATES, IPA_TO_ARPABET, LENGTH_MARK, NASALS, PLOSIVES, UNSTABLE_WORDS, VOWELS, WEAK_WORDS, Phone, Syllable,
                     fold_weak_syllables, merge_tokens, syllabify)
from .singing import OUTPUT_SR, Style

MIN_NOTE_S = 0.110                 # shorter notes smear consonants (a 16th at 140 bpm is 107 ms)
# Under about 200 ms a syllable starts to blur even on a singing voicebank (an eighth at 150 bpm is 200 ms), and a run of
# them reads as a rushed line. Same rule as spectro-maestro's lyrics.fast_syllables, counted per sung syllable here so a
# syllable bent over several short notes counts once.
FAST_SYLLABLE_S = 0.200
FAST_SYLLABLE_COUNT = 3
LONG_NOTE_BEATS = 2.0
# A line that builds up on a held note and then ends on a last syllable this fraction of it or shorter: the last word,
# usually the rhyme and the point of the line, is over before it is heard. Same rule as spectro-maestro's lyrics.clipped_line_end.
CLIP_RATIO = 0.25
STRONG_NOTE_BEATS = 1.0
SHORT_NOTE_BEATS = 0.5
CLUSTER_SIZE = 2
WEAK_RUN = 3
VOICE_RANGE_SEMITONES = 9          # comfortable distance of a melody from the voice's speaking pitch
CHORUS_MAX_SYLLABLES = 7
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
STRONG_BEAT_WEIGHT = 3             # downbeat or beat three (see METRIC_WEIGHTS)
EXPOSED_NOTE_S = 0.5               # a reduced or tiny vowel held this long is heard dying; shorter notes pass as in speech
PERIOD_SEARCH = 0.05
BEATS_PER_BAR = 4.0                # assumed when the caller does not know the song's meter
METRIC_WEIGHTS = ((4.0, 4), (2.0, 3), (1.0, 2), (0.5, 1))   # (beat grid, strength): downbeat, beat three, beats two and four, off-beats
GRID_TOLERANCE_BEATS = 1e-6


def _words(text: str) -> list[str]:
    return [w.strip(".,!?;:\"()").lower() for w in text.split() if w.strip(".,!?;:\"()")]


ARPABET_TO_IPA = {}
for _ipa, _arpabet in IPA_TO_ARPABET.items():            # the first IPA listed for a symbol is the one the rules read
    ARPABET_TO_IPA.setdefault(_arpabet, _ipa)


def _bank_symbol(symbol: str) -> str:
    """A voicebank's own phoneme (such as 'en/ah' or 'IY1') as the IPA symbol the lyric rules are written in."""
    bare = symbol.split("/")[-1].lower().rstrip("012")
    return ARPABET_TO_IPA.get(bare, bare)


def _voicebank_syllables(voice: str, text: str, lang: str) -> list[Syllable]:
    """Syllables of a line as a DiffSinger voicebank pronounces it, with IPA symbols so the same rules apply.
    Bank dictionaries carry no stress, so the stress rules stay quiet for these voices."""
    from . import diffsinger
    folder = voice.split(":", 1)[1].partition("#")[0]
    rows = diffsinger.voicebank(folder).syllables(text, lang)
    out = []
    for row in rows:
        make = lambda symbols: [Phone(_bank_symbol(s), 0.0, 0.0, row["word"], False) for s in symbols]
        out.append(Syllable(make(row["onset"]), make([row["vowel"]]) if row["vowel"] else [], make(row["coda"]), row["word"]))
    return out


def line_syllables(voice: str, text: str, wanted: int | None = None, lang: str = "en"):
    """Syllables of a line in `lang` as the engine pronounces it (folded toward `wanted` if given), without synthesizing."""
    if voice.startswith("diffsinger:"):
        syllables = _voicebank_syllables(voice, text, lang)
    else:
        phonemes = tts.backend(voice, lang).phonemize(text)
        symbols = list(phonemes)
        syllables = syllabify(merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols)))
    return fold_weak_syllables(syllables, wanted) if wanted is not None else syllables


def _metric_weight(beat_in_bar: float) -> int:
    """How strong a position in the bar is: downbeat 4, beat three 3, other beats 2, off-beats 1, 16th places and finer 0."""
    for grid, weight in METRIC_WEIGHTS:
        if abs(beat_in_bar / grid - round(beat_in_bar / grid)) < GRID_TOLERANCE_BEATS:
            return weight
    return 0


def _stress_findings(label: str, words: list[str], syllables: list, weights: list[int], durations: list[float]) -> list[dict]:
    """A word whose stressed syllable sits on a weaker beat than one of its unstressed syllables (and on no longer note)
    is heard mis-accented; the stress comes from the engine's own pronunciation dictionary.
    Ported from Spectro Maestro's vocal.lint_lyrics stress rule (same author, AGPL-3.0-or-later)."""
    found = []
    by_word: dict[int, list[int]] = {}
    for index, syllable in enumerate(syllables):
        by_word.setdefault(syllable.word, []).append(index)
    for word, indices in by_word.items():
        for stressed in (i for i in indices if syllables[i].stressed):
            rival = next((i for i in indices if not syllables[i].stressed and weights[i] > weights[stressed]
                          and durations[i] >= durations[stressed]), None)
            if rival is not None:
                found.append(finding("warn", "stress_on_weak_beat", f"{label}: stressed syllable '{syllables[stressed].text}' of "
                                     f"'{words[word] if word < len(words) else '?'}' sits on a weaker beat than unstressed "
                                     f"'{syllables[rival].text}'; the word will sound mis-accented. Move the word so the stressed syllable "
                                     "lands on the stronger beat, or give it the longer note"))
    return found


def _bright_weight(syllable) -> int:
    """How many bright sounds a syllable carries at its edges, a cluster (st, sk, ts) counting as BRIGHT_CLUSTER_WEIGHT."""
    edges = sum(1 for p in syllable.onset + syllable.coda if p.symbol[0] in BRIGHT_CONSONANTS)
    return min(edges, BRIGHT_CLUSTER_WEIGHT)


def _is_bright(syllable) -> bool:
    return _bright_weight(syllable) > 0


def _bright_findings(label: str, syllables: list) -> list[dict]:
    """A line carried by t, k, p, s, z, sh: three bright sounds in five syllables (a cluster counts twice), or three syllables in a row."""
    weights = [_bright_weight(s) for s in syllables]
    flags = [w > 0 for w in weights]
    run, longest = 0, 0
    for flag in flags:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    crowded = len(flags) >= BRIGHT_MIN_SYLLABLES and sum(weights) >= BRIGHT_SHARE * len(flags)
    if not crowded and longest < BRIGHT_RUN:
        return []
    where = f"{sum(weights)} bright sounds over {len(flags)} syllables (st, sk, ts clusters count twice)" if crowded else f"{longest} syllables in a row"
    return [finding("warn", "bright_consonants", f"{label}: {where} on t, k, p, s, z or sh; the speech voices spit, hiss and peak there. Carry the line on voiced consonants (m, n, l, d, b, g, w, r) and keep those sounds to about one per word")]


def lint_line(voice: str, line: lines.Line, bpm: float, natural_pitch: float | None = None, role: str = "verse",
              beats_per_bar: float = BEATS_PER_BAR, lang: str = "en") -> list[dict]:
    """Findings for one line sung in `lang`. natural_pitch (MIDI) enables the range check; role 'chorus' adds chorus rules.
    line.start_beat and beats_per_bar place the notes in their bars for the stress check."""
    found = []
    words = _words(line.text)
    groups, lead_beats, _ = lines.note_groups(line.melody, bpm)
    seconds_per_beat = 60.0 / bpm
    label = f"'{line.text}'"
    try:
        spoken = line_syllables(voice, line.text, lang=lang)
    except ValueError as error:                        # characters the voice's language cannot read (tts.espeak_phonemes)
        return [finding("error", "unreadable_text", f"{label}: {error}")]
    syllables = fold_weak_syllables(spoken, len(groups))
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
    quick = sum(1 for seconds in durations if seconds < FAST_SYLLABLE_S)
    if quick >= FAST_SYLLABLE_COUNT:
        found.append(finding("info", "fast_syllables", f"{label}: {quick} syllables are shorter than {FAST_SYLLABLE_S * 1000:.0f} ms; consonants "
                             "start to blur at this speed. If the line scores weak or sounds rushed, give it one syllable per beat"))
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
    weights = [_metric_weight((line.start_beat + lead_beats + group[0].start / seconds_per_beat) % beats_per_bar) for group in groups]
    found += _stress_findings(label, words, syllables, weights, durations)
    for index, syllable in enumerate(syllables):
        exposed = durations[index] >= EXPOSED_NOTE_S or (weights[index] >= STRONG_BEAT_WEIGHT and beats[index] >= SHORT_NOTE_BEATS)
        if not exposed or not syllable.nucleus:
            continue
        nucleus = syllable.nucleus[0].symbol.replace(LENGTH_MARK, "")
        where = "a strong beat" if weights[index] >= STRONG_BEAT_WEIGHT else f"{durations[index]:.2f} s"
        if nucleus in REDUCED_VOWELS and not syllable.diphthong and not (weak[index] and beats[index] >= LONG_NOTE_BEATS):
            found.append(finding("warn", "reduced_vowel_on_beat", f"{label}: '{syllable.text}' puts a reduced vowel (the a of about, the e of the) on {where}; the speech voices have almost no vowel there, so it sings as breath or a gap. Give it a short off-beat note and let a content word take the beat, or spell the strong form for the voice (too, thee, ay)"))
        if nucleus in SHORT_LAX_VOWELS and syllable.coda and syllable.coda[-1].symbol[0] in BRIGHT_CONSONANTS:
            found.append(finding("warn", "short_vowel_on_beat", f"{label}: '{syllable.text}' (it, its, sit) sits on {where}; its vowel lasts a few tens of milliseconds, so the note becomes the burst of its consonant. Give it a short off-beat note or a word with a long vowel"))
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
    found += _bright_findings(label, syllables)
    speech_voice = not voice.startswith("diffsinger:")       # a voicebank shapes its vowels; the thin held ee is a speech-voice fault
    for index, syllable in enumerate(syllables):
        if speech_voice and beats[index] >= LONG_NOTE_BEATS and syllable.nucleus and not syllable.diphthong and syllable.nucleus[0].symbol.replace(LENGTH_MARK, "") in EE_SYMBOLS:
            found.append(finding("info", "held_ee", f"{label}: '{syllable.text}' holds {beats[index]:g} beats on an ee vowel, which the speech voices sing thin and sharp; a word with ah, oh, oo or ay holds fuller, or fill it with Style(vowel_body=1)"))
    final = syllables[-1]
    held, tail = (round(beats[-2], 6), round(beats[-1], 6)) if len(syllables) >= 2 else (0.0, 0.0)   # rounded: seconds back to beats carry float error
    if held >= LONG_NOTE_BEATS and tail <= CLIP_RATIO * held:
        found.append(finding("warn", "clipped_line_end", f"{label}: '{syllables[-2].text}' holds {held:g} beats, then the line ends on "
                             f"'{final.text}' in {tail:g} beats; the last word is over before it is heard. Hold the last word itself, "
                             "or give it a beat or more and end on a rest"))
    if beats[-1] >= LONG_NOTE_BEATS and final.coda and final.coda[-1].symbol[0] in NASALS:
        found.append(finding("info", "nasal_line_end", f"{label}: the last long note closes on a nasal (second-best to an open vowel)"))
    if role == "chorus" and len(syllables) > CHORUS_MAX_SYLLABLES:
        found.append(finding("info", "chorus_density", f"{label}: {len(syllables)} syllables; chorus lines usually carry 5-{CHORUS_MAX_SYLLABLES} with a held last note"))
    if natural_pitch is not None:
        pitches = [n.pitch for g in groups for n in g]
        if max(pitches) - natural_pitch > VOICE_RANGE_SEMITONES + 5 or natural_pitch - min(pitches) > VOICE_RANGE_SEMITONES:
            found.append(finding("warn", "voice_range", f"{label}: melody spans MIDI {min(pitches)}-{max(pitches)}, far from this voice's speaking pitch ({natural_pitch:.0f}); transpose or pick another voice"))
    return found


def rhyme_vowel(voice: str, text: str, lang: str = "en") -> str:
    """Vowel sound that ends a line, for checking rhyme pairs."""
    syllables = line_syllables(voice, text, lang=lang)
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
