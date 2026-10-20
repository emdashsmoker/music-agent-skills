# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""IPA phone classes and syllable structure for sung text.

Works on the espeak-style IPA that Kokoro and Piper both speak, so one syllabifier serves every
language those engines cover. A syllable is: onset consonants, a vowel nucleus, coda consonants."""
from __future__ import annotations

from dataclasses import dataclass, field

VOWELS = set("aeiouyɑɐɒæəɚɛɜɝɪɨɔʊʌøœɯɤʉɵɘɞɶʏᵻᵊAIOWY")
SONORANTS = set("mnŋɲɳɱlɫɭʎɹrɾɻʀʁwjɥɰ")
VOICED_OBSTRUENTS = set("bdɡgvzʒðɟɖʝɣβʤʣʥ")
UNVOICED_OBSTRUENTS = set("ptkfsʃθhxçɸχħʔcqʧʦʨʈɕʂ")
SIBILANTS = set("sʃɕʂʧʦʨ")
PLOSIVES = set("ptkbdɡgʔcqʈɖ")
STRESS_MARKS = {"ˈ": 2, "ˌ": 1}
LENGTH_MARK = "ː"
SYLLABIC_MARK = "̩"
NASAL_MARK = "̃"
NON_SYLLABIC_MARK = "̯"
PAUSE = set(" ,.;:!?—…\"()“”^$_-'")
# Vowel pairs that form one nucleus in English. Any other English vowel-vowel sequence is two syllables (hiatus).
DIPHTHONGS = {"aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ", "əʊ", "eə", "ɪə", "iə", "ʊə", "ɛə", "ai", "au", "ei", "ou", "oi", "aɔ"}
# Outside English the melody gives the syllable count (fit_syllables): the lyrics are written one note per syllable of
# their language. A close vowel without stress after another vowel usually ends a diphthong (German Haus, Spanish hoy),
# so such vowels are joined first.
CLOSE_VOWELS = set("iyɨʉɯuɪʏʊ")
# Closing glide of a diphthong: kept short when the vowel is held, as singers do.
GLIDE_TARGETS = set("ɪʊiuəɐ")
VOCALISED_R = "ɐ"
OPEN_ENDING, NASAL_ENDING, STOP_ENDING = "open", "nasal", "stop"


def kind_of(symbol: str) -> str:
    """vowel / sonorant / voiced / unvoiced / pause, judged by the first character."""
    head = symbol[0]
    if head in PAUSE:
        return "pause"
    if head in VOWELS or SYLLABIC_MARK in symbol:
        return "vowel"
    if head in SONORANTS:
        return "sonorant"
    if head in VOICED_OBSTRUENTS:
        return "voiced"
    return "unvoiced"


@dataclass
class Phone:
    symbol: str
    start: float
    end: float
    kind: str
    stress: int = 0
    word: int = 0

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Syllable:
    onset: list = field(default_factory=list)     # indices into the phone list
    nucleus: list = field(default_factory=list)
    coda: list = field(default_factory=list)
    stress: int = 0
    word: int = 0

    @property
    def phones(self) -> list:
        return self.onset + self.nucleus + self.coda


def phones_from_tokens(symbols: list, durations: list) -> list:
    """Per-token symbols and durations (seconds) -> Phone list.
    Stress marks lend their time to the phone that follows, length marks to the phone before."""
    phones, pending_time, pending_stress, cursor, word = [], 0.0, 0, 0.0, 0
    for symbol, dur in zip(symbols, durations):
        if symbol in STRESS_MARKS:
            pending_time += dur
            pending_stress = STRESS_MARKS[symbol]
            continue
        if symbol in (LENGTH_MARK, SYLLABIC_MARK, NASAL_MARK) and phones and phones[-1].kind != "pause":
            phones[-1].symbol += symbol
            phones[-1].end += dur
            if symbol == SYLLABIC_MARK:
                phones[-1].kind = "vowel"
            cursor += dur
            continue
        kind = kind_of(symbol)
        if kind == "pause":
            word += 1
        phone = Phone(symbol, cursor, cursor + pending_time + dur, kind, 0, word)
        if kind == "vowel":
            phone.stress, pending_stress = pending_stress, 0
        phones.append(phone)
        cursor += pending_time + dur
        pending_time = 0.0
    return phones


def language_key(lang: str | None) -> str:
    """The language part of a song or espeak language code: 'pt-br' and 'pt' -> 'pt'."""
    return (lang or "").lower().replace("_", "-").split("-")[0]


def is_english(lang: str | None) -> bool:
    """English, or no language given: the syllable rules the English songs were written for."""
    return language_key(lang) in ("", "en")


def _joins(phones: list, first: int, second: int, english: bool) -> bool:
    """Whether the vowel at `second` belongs to the nucleus of the vowel just before it, at `first`."""
    a, b = phones[first], phones[second]
    if english:
        # English keeps the rule it was tuned with, unchanged: these pairs, and ɐ after a vowel sung as its glide.
        return ((a.symbol[-1] + b.symbol[0]) in DIPHTHONGS and LENGTH_MARK not in a.symbol) or b.symbol == VOCALISED_R
    # Other languages join only a vowel espeak marks non-syllabic and leave the rest to fit_syllables.
    return second + 1 < len(phones) and phones[second + 1].symbol == NON_SYLLABIC_MARK


def syllabify(phones: list, lang: str | None = None) -> list:
    """Group phones into syllables. Consonants between two vowels of one word open the next syllable;
    consonants before a pause close the syllable they follow. `lang` (en, de, pt-br ...) decides between the English
    rules and the ones every other language shares."""
    english = is_english(lang)
    syllables, current, pending = [], None, []
    previous_vowel = None
    for index, phone in enumerate(phones):
        if phone.kind == "pause":
            if current is not None:
                current.coda += pending
            elif pending and syllables:
                syllables[-1].coda += pending
            pending, current, previous_vowel = [], None, None
            continue
        if phone.kind == "vowel":
            adjacent = previous_vowel is not None and previous_vowel == index - 1 and len(current.nucleus) == 1
            joined = adjacent and _joins(phones, previous_vowel, index, english)
            if joined:
                current.nucleus.append(index)
                current.stress = max(current.stress, phone.stress)
            else:
                current = Syllable(onset=pending, nucleus=[index], stress=phone.stress, word=phone.word)
                syllables.append(current)
                pending = []
            previous_vowel = index
        else:
            pending.append(index)
    if pending and syllables:
        syllables[-1].coda += pending
    return syllables


def _join_rank(phones: list, syllable: Syllable) -> int:
    """Which vowel contact fit_syllables joins first: a close vowel without stress, then any unstressed vowel, then the rest."""
    vowel = phones[syllable.nucleus[0]]
    if vowel.stress == STRESS_MARKS["ˈ"]:
        return 2
    return 0 if vowel.symbol[0] in CLOSE_VOWELS else 1


def fit_syllables(phones: list, syllables: list, wanted: int | None, lang: str | None = None) -> list:
    """Outside English, join vowels that meet inside a word until there are `wanted` syllables: the melody, written one
    note per syllable of the lyrics' language, gives the count. English, and a list that cannot reach `wanted`, come
    back unchanged."""
    if wanted is None or is_english(lang):
        return syllables
    result = list(syllables)
    while len(result) > wanted:
        contacts = [i for i in range(1, len(result)) if result[i - 1].nucleus and result[i].nucleus and not result[i - 1].coda
                    and not result[i].onset and result[i - 1].word == result[i].word]
        if not contacts:
            return syllables
        index = min(contacts, key=lambda i: (_join_rank(phones, result[i]), i))
        previous, current = result[index - 1], result[index]
        result[index - 1] = Syllable(previous.onset, previous.nucleus + current.nucleus, current.coda,
                                     max(previous.stress, current.stress), previous.word)
        result.pop(index)
    return result


def ending_type(phones: list, syllable: Syllable) -> str:
    """How a syllable ends: open vowel, nasal/liquid, or a stop/fricative. Decides how well it holds a long note."""
    if not syllable.coda:
        return OPEN_ENDING
    last = phones[syllable.coda[-1]]
    return NASAL_ENDING if last.kind == "sonorant" else STOP_ENDING


def syllable_text(phones: list, syllable: Syllable) -> str:
    return "".join(phones[i].symbol for i in syllable.phones)


def unstable_count(phone_word: str) -> bool:
    """True when a word may be sung with one syllable more or fewer than counted:
    a diphthong or long vowel running straight into a schwa-like vowel (fire, hour, real)."""
    for a, b, c in zip(phone_word, phone_word[1:], phone_word[2:] + " "):
        if a + b in DIPHTHONGS and c in "ɚə":
            return True
    return any(x == LENGTH_MARK and y in "ɚə" for x, y in zip(phone_word, phone_word[1:]))
