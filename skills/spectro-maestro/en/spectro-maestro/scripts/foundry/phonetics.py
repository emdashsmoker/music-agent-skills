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
# Vowel pairs that form one nucleus. Any other vowel-vowel sequence is two syllables (hiatus).
DIPHTHONGS = {"aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ", "əʊ", "eə", "ɪə", "iə", "ʊə", "ɛə", "ai", "au", "ei", "ou", "oi", "aɔ"}
# The pairs of languages whose espeak output has diphthongs English lacks (German neu, Dutch uit, Portuguese não).
# Each set is that language's whole list, since a pair can be one syllable in one language and two in another.
# Only the languages listed use these sets and the rules that go with them (_joins); English and every other
# language keep DIPHTHONGS and the rules they had. A length mark on the first vowel is part of the pair
# (Norwegian jeg).
_NORWEGIAN = DIPHTHONGS | {"øy", "ɛːɪ"}
LANGUAGE_DIPHTHONGS = {
    "de": DIPHTHONGS | {"ɔø"},
    "da": DIPHTHONGS,                                                              # er, mor: the ɐ̯ is not a syllable
    "pl": DIPHTHONGS,                                                              # nauka: a-u is two syllables
    "nl": (DIPHTHONGS - {"iə"}) | {"ʌʊ", "œy", "ɛi", "ɛɪ", "eʊ"},                  # België: i and ə are two syllables
    "fr": DIPHTHONGS | {"yi"},
    "es": DIPHTHONGS | {"oɪ", "eʊ"},
    "it": DIPHTHONGS | {"ɔi", "ɛi", "eʊ", "ʊɔ"},
    "pt": DIPHTHONGS | {"ɐʊ", "ɐy", "ɐɪ", "oɪ", "uɪ", "eʊ", "ɛʊ"},
    "ro": DIPHTHONGS | {"ea", "ɔa", "oa"},
    "fi": DIPHTHONGS | {"yø", "uo", "ie", "æi", "øi", "yi", "ui", "ey", "æy", "øy", "iu", "eu"},
    "et": DIPHTHONGS | {"aa", "ee", "ii", "oo", "uu", "ææ", "øø", "yy", "ɤɤ"},   # espeak doubles a long vowel: saab, keel
    "lv": DIPHTHONGS | {"ie", "ui", "uo"},
    "lt": DIPHTHONGS | {"ie", "ui", "uo", "ee"},                                  # espeak writes ė as ee
    "sk": DIPHTHONGS | {"uo", "ia", "ie", "iu"},
    "cs": DIPHTHONGS | {"eu"},
    "is": DIPHTHONGS | {"øy"},
    "no": _NORWEGIAN, "nb": _NORWEGIAN, "nn": _NORWEGIAN,
}
# In those languages a pair whose second vowel carries the stress is two syllables (Spanish país, Italian paura),
# except these, where espeak writes a glide as a vowel before the stressed one (French nuit, Italian cuore, Slovak piatok).
RISING_DIPHTHONGS = {"fr": {"yi"}, "it": {"ʊɔ"}, "sk": {"ia", "ie", "iu"}}
FULL_VOWEL_A = {"pt"}                       # ɐ is a vowel of its own there (rua, lua), not a vocalised r
SYLLABIC_R = {"hr", "sr", "bs"}            # espeak writes the r of srce and prst without a syllabic mark
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
    """The key of the per-language tables for a song or espeak language code: 'pt-br' and 'pt' -> 'pt'."""
    return (lang or "").lower().replace("_", "-").split("-")[0]


def _syllabic_r(phones: list) -> set:
    """Indices of r sounds with no vowel on either side: the nucleus of srce, prst and Hrvatska."""
    def vowel_at(i: int) -> bool:
        return 0 <= i < len(phones) and phones[i].kind == "vowel"
    return {i for i, phone in enumerate(phones) if phone.symbol[0] == "r" and not vowel_at(i - 1) and not vowel_at(i + 1)}


def _joins(phones: list, first: int, second: int, key: str) -> bool:
    """Whether the vowel at `second` belongs to the nucleus of the vowel just before it, at `first`."""
    a, b = phones[first], phones[second]
    if key not in LANGUAGE_DIPHTHONGS:
        # English and the languages without a table of their own keep the rule they were tuned with, unchanged.
        # German 'durch', 'vier': the r is a glide, not a syllable.
        return ((a.symbol[-1] + b.symbol[0]) in DIPHTHONGS and LENGTH_MARK not in a.symbol) or b.symbol == VOCALISED_R
    pair = a.symbol.replace(NASAL_MARK, "") + b.symbol[0]
    return ((pair in LANGUAGE_DIPHTHONGS[key] and not b.stress) or pair in RISING_DIPHTHONGS.get(key, set())
            or (second + 1 < len(phones) and phones[second + 1].symbol == NON_SYLLABIC_MARK)
            or (b.symbol == VOCALISED_R and key not in FULL_VOWEL_A))


def syllabify(phones: list, lang: str | None = None) -> list:
    """Group phones into syllables. Consonants between two vowels of one word open the next syllable;
    consonants before a pause close the syllable they follow. `lang` (en, de, pt-br ...) picks the vowel pairs."""
    key = language_key(lang)
    syllabic_r = _syllabic_r(phones) if key in SYLLABIC_R else set()
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
        if phone.kind == "vowel" or index in syllabic_r:
            adjacent = previous_vowel is not None and previous_vowel == index - 1 and len(current.nucleus) == 1
            joined = adjacent and _joins(phones, previous_vowel, index, key)
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
