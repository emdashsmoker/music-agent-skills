# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Phone classes and syllables for IPA phoneme strings (as written by espeak-ng).

Singing needs to know, for every syllable, which sounds come before the beat (onset consonants),
which sound is held on the note (the vowel nucleus) and which close it (coda).
"""
from __future__ import annotations

from dataclasses import dataclass, field

VOWELS = set("aɑɐɒæeəɚɛɜɝiɪᵻoɔuʊʌøœyɯɨɤʏɵʉɘɞɶᵊAIOWY")
# Vowel pairs sung as one syllable (first part held, second part a short glide at the end).
DIPHTHONGS = {"aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ", "əʊ", "eə", "ɪə", "ʊə", "ɛɪ", "ɑɪ", "ɔʊ"}
SINGLE_SYMBOL_DIPHTHONGS = set("AIOWY")           # misaki-style shorthands for eɪ aɪ oʊ aʊ ɔɪ
WEAK_NUCLEI = set("əɚᵊᵻ")                          # can fold into the previous vowel (fire: aɪ+ɚ sung as one)
STRESS_MARKS, LENGTH_MARK, NASAL_MARK = "ˈˌ", "ː", "̃"
# espeak marks a consonant that is a syllable (Czech krk, Brno) and a vowel that is not (Danish er, mor). Only languages
# other than English read them; English keeps the n̩ of button with the syllable before it, as its songs were written for.
SYLLABIC_MARK, NON_SYLLABIC_MARK = "̩", "̯"
# Outside English the melody gives the syllable count (fit_syllables): the lyrics are written one note per syllable of
# their language. A close vowel without stress after another vowel usually ends a diphthong (German Haus, Spanish hoy),
# so such vowels are joined first.
CLOSE_VOWELS = set("iyɨʉɯuɪʏʊ")
PLOSIVES = set("pbtdkɡgʔɾʈɖcɟq")
AFFRICATES = set("ʧʤʦʣʨʥꭧ")
FRICATIVES = set("fvθðszʃʒhxçɕʂʝɣχβɸʁ")
NASALS = set("mnŋɲɳɴ")
APPROXIMANTS = set("lɹwjɫɻɥʋʎɰrɽ")
VOICELESS = set("ptkʔfθsʃhxçɕʂʧʦʨχɸcqʈ")
PAUSES = set(" ,.;:!?—…\"()“”")
MODIFIERS = set("ʰʲᵝ")
# Voicing classes for singing (see voicing()): sonorants are always sung voiced, voiced obstruents only where the
# speech was voiced, everything else never. The flap ɾ counts as a sonorant: it is a brief voiced tap, not a burst.
SONORANTS = set("mnŋɲɳɱlɫɭʎɹrɾɻʀʁwjɥɰ")
VOICED_OBSTRUENTS = set("bdɡgvzʒðɟɖʝɣβʤʣʥ")
# Words that carry little stress in speech and blur when given a long or strong note.
WEAK_WORDS = {"a", "an", "the", "of", "in", "to", "at", "on", "for", "and", "or", "but", "is", "it", "its", "as", "by",
              "be", "am", "are", "was", "were", "that", "this", "with", "from", "so", "if", "than", "then", "some",
              "someone", "what", "when", "where", "will", "would", "could", "should", "can", "do", "does", "has", "have",
              "had", "i", "you", "he", "she", "we", "they", "me", "my", "your", "his", "her", "our", "their", "till", "may",
              "upon", "into", "onto", "about", "above", "across", "against", "along", "among", "around"}   # the last row opens on a reduced syllable
# Words whose syllable count differs between speakers and engines.
UNSTABLE_WORDS = {"fire", "fires", "hour", "hours", "every", "different", "tower", "towers", "wire", "wires", "factory",
                  "power", "flower", "flowers", "our", "desire", "higher", "liar", "prayer", "real", "really", "family",
                  "memory", "camera", "chocolate", "evening", "interesting", "poem", "being", "seeing", "quiet", "lion"}
# IPA (espeak en-us) to ARPAbet, used to feed singing voicebanks that are labelled in ARPAbet.
IPA_TO_ARPABET = {
    "ɑ": "aa", "æ": "ae", "ʌ": "ah", "ɐ": "ah", "ɔ": "ao", "ɒ": "aa", "aʊ": "aw", "ə": "ax", "ᵊ": "ax", "ɚ": "er", "ɜ": "er",
    "ɝ": "er", "aɪ": "ay", "ɛ": "eh", "e": "eh", "eɪ": "ey", "ɪ": "ih", "ᵻ": "ih", "i": "iy", "oʊ": "ow", "o": "ow", "ɔɪ": "oy",
    "ʊ": "uh", "u": "uw", "a": "aa", "əʊ": "ow",
    "b": "b", "ʧ": "ch", "tʃ": "ch", "d": "d", "ð": "dh", "ɾ": "dx", "f": "f", "ɡ": "g", "g": "g", "h": "hh", "ʤ": "jh",
    "dʒ": "jh", "k": "k", "l": "l", "ɫ": "l", "m": "m", "n": "n", "ŋ": "ng", "p": "p", "ɹ": "r", "r": "r", "s": "s",
    "ʃ": "sh", "t": "t", "θ": "th", "v": "v", "w": "w", "j": "y", "z": "z", "ʒ": "zh", "ʔ": "q",
}


def is_vowel(symbol: str) -> bool:
    return bool(symbol) and symbol[0] in VOWELS


def is_voiced(symbol: str) -> bool:
    return bool(symbol) and symbol[0] not in VOICELESS and symbol[0] not in PAUSES


def kind(symbol: str) -> str:
    """vowel, plosive, affricate, fricative, nasal, approximant, pause or other."""
    head = symbol[0] if symbol else " "
    for name, group in (("vowel", VOWELS), ("plosive", PLOSIVES), ("affricate", AFFRICATES), ("fricative", FRICATIVES),
                        ("nasal", NASALS), ("approximant", APPROXIMANTS), ("pause", PAUSES)):
        if head in group:
            return name
    return "other"


def voicing(symbol: str) -> str:
    """vowel, sonorant, voiced (obstruent), unvoiced or pause, judged by the first character."""
    head = symbol[0] if symbol else " "
    if head in PAUSES:
        return "pause"
    if head in VOWELS:
        return "vowel"
    if head in SONORANTS:
        return "sonorant"
    if head in VOICED_OBSTRUENTS:
        return "voiced"
    return "unvoiced"


@dataclass
class Phone:
    """One speech sound with its time span in seconds (marks such as stress and length are folded in)."""
    symbol: str
    start: float = 0.0
    end: float = 0.0
    word: int = 0
    stressed: bool = False

    @property
    def vowel(self) -> bool:
        return is_vowel(self.symbol)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Syllable:
    onset: list[Phone] = field(default_factory=list)
    nucleus: list[Phone] = field(default_factory=list)
    coda: list[Phone] = field(default_factory=list)
    word: int = 0

    @property
    def phones(self) -> list[Phone]:
        return self.onset + self.nucleus + self.coda

    @property
    def stressed(self) -> bool:
        return any(p.stressed for p in self.nucleus)

    @property
    def text(self) -> str:
        return "".join(p.symbol for p in self.phones)

    @property
    def diphthong(self) -> bool:
        joined = "".join(p.symbol.replace(LENGTH_MARK, "") for p in self.nucleus)
        return len(self.nucleus) > 1 or joined in SINGLE_SYMBOL_DIPHTHONGS or joined in DIPHTHONGS


def merge_tokens(symbols: list[str], starts: list[float], ends: list[float]) -> list[Phone]:
    """Fold stress, length and modifier marks into their sound and number the words.

    Input is one entry per phonemizer character with its time span; pauses (spaces, punctuation) separate words.
    """
    phones: list[Phone] = []
    word, pending_stress, carry_start = 0, False, None
    for symbol, start, end in zip(symbols, starts, ends):
        if symbol in STRESS_MARKS:
            pending_stress = pending_stress or symbol == "ˈ"
            carry_start = start if carry_start is None else carry_start          # the mark's time belongs to the next sound
            continue
        if symbol in PAUSES:
            if phones and phones[-1].symbol != " ":
                word += 1
            phones.append(Phone(" ", start if carry_start is None else carry_start, end, word))
            carry_start = None
            continue
        if (symbol == LENGTH_MARK or symbol == NASAL_MARK or symbol in MODIFIERS) and phones and phones[-1].symbol != " ":
            phones[-1].symbol += symbol if symbol == LENGTH_MARK else ""
            phones[-1].end = end
            continue
        phones.append(Phone(symbol, start if carry_start is None else carry_start, end, word, pending_stress and symbol[0] in VOWELS))
        if pending_stress and symbol[0] in VOWELS:
            pending_stress = False
        carry_start = None
    return phones


def language_key(lang: str | None) -> str:
    """The language part of a song or espeak language code: 'pt-br' and 'pt' -> 'pt'."""
    return (lang or "").lower().replace("_", "-").split("-")[0]


def is_english(lang: str | None) -> bool:
    """English, or no language given: the syllable rules the English songs were written for."""
    return language_key(lang) in ("", "en")


def _followed_by(sounds: list[Phone], index: int, mark: str) -> bool:
    return index + 1 < len(sounds) and sounds[index + 1].symbol == mark


def _nuclei_flags(sounds: list[Phone], english: bool) -> list[bool]:
    """Which sounds of a word can carry a syllable: vowels and, outside English, a consonant espeak marks syllabic."""
    return [sound.vowel or (not english and _followed_by(sounds, i, SYLLABIC_MARK)) for i, sound in enumerate(sounds)]


def _one_nucleus(sounds: list[Phone], index: int, english: bool) -> bool:
    """Whether the vowels at index and index + 1 make one syllable. English pairs them by DIPHTHONGS; other languages
    join only a vowel espeak marks non-syllabic and leave the rest to fit_syllables."""
    first, second = sounds[index], sounds[index + 1]
    if english:
        return first.symbol.replace(LENGTH_MARK, "") + second.symbol.replace(LENGTH_MARK, "") in DIPHTHONGS
    return _followed_by(sounds, index + 1, NON_SYLLABIC_MARK)


def syllabify(phones: list[Phone], lang: str | None = None) -> list[Syllable]:
    """Group sounds into syllables word by word: one vowel (or diphthong) each, consonants split around it.
    `lang` (en, de, pt-br ...) decides between the English rules and the ones every other language shares."""
    english = is_english(lang)
    syllables: list[Syllable] = []
    words: dict[int, list[Phone]] = {}
    for phone in phones:
        if phone.symbol != " ":
            words.setdefault(phone.word, []).append(phone)
    for word_index in sorted(words):
        sounds = words[word_index]
        nucleus = _nuclei_flags(sounds, english)
        nuclei: list[list[int]] = []
        i = 0
        while i < len(sounds):
            if nucleus[i]:
                if i + 1 < len(sounds) and nucleus[i + 1] and _one_nucleus(sounds, i, english):
                    nuclei.append([i, i + 1])
                    i += 2
                    continue
                nuclei.append([i])
            i += 1
        if not nuclei:                                   # a word without a vowel (e.g. "hmm"): attach to a neighbour
            if syllables:
                syllables[-1].coda += sounds
            else:
                syllables.append(Syllable(onset=sounds, word=word_index))
            continue
        word_syllables = []
        for n, nucleus in enumerate(nuclei):
            first = nuclei[n - 1][-1] + 1 if n else 0
            between = list(range(first, nucleus[0]))
            if n == 0:
                onset = between
            else:
                # One consonant between vowels opens the next syllable; a cluster gives its first sound to the previous one.
                keep = 0 if len(between) <= 1 else 1
                word_syllables[-1].coda += [sounds[k] for k in between[:keep]]
                onset = between[keep:]
            word_syllables.append(Syllable([sounds[k] for k in onset], [sounds[k] for k in nucleus], [], word_index))
        word_syllables[-1].coda += sounds[nuclei[-1][-1] + 1:]
        syllables += word_syllables
    if syllables and not syllables[0].nucleus and len(syllables) > 1:      # leading vowel-less word joins the next syllable
        syllables[1].onset = syllables[0].onset + syllables[1].onset
        syllables.pop(0)
    return syllables


def _join_rank(syllable: Syllable) -> int:
    """Which vowel contact fit_syllables joins first: a close vowel without stress, then any unstressed vowel, then the rest."""
    vowel = syllable.nucleus[0]
    if vowel.stressed:
        return 2
    return 0 if vowel.symbol[0] in CLOSE_VOWELS else 1


def fit_syllables(syllables: list[Syllable], wanted: int | None, lang: str | None = None) -> list[Syllable]:
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
        index = min(contacts, key=lambda i: (_join_rank(result[i]), i))
        previous, current = result[index - 1], result[index]
        result[index - 1] = Syllable(previous.onset, previous.nucleus + current.nucleus, current.coda, previous.word)
        result.pop(index)
    return result


def fold_weak_syllables(syllables: list[Syllable], wanted: int) -> list[Syllable]:
    """Reduce the syllable count to `wanted` by singing a weak vowel as the tail of the vowel before it.

    Covers words like fire, hour and tower (aɪ+ɚ), which engines count as two syllables and writers as one.
    Only vowel-vowel contacts inside one word are folded; returns the list unchanged if that is not enough.
    """
    result = list(syllables)
    while len(result) > wanted:
        for index in range(1, len(result)):
            previous, current = result[index - 1], result[index]
            contact = not previous.coda and not current.onset and previous.word == current.word
            if contact and current.nucleus and current.nucleus[0].symbol[0] in WEAK_NUCLEI:
                result[index - 1] = Syllable(previous.onset, previous.nucleus + current.nucleus, current.coda, previous.word)
                result.pop(index)
                break
        else:
            return list(syllables) if len(result) != wanted else result
    return result


def count_syllables(phoneme_text: str) -> int:
    symbols = list(phoneme_text)
    return len(syllabify(merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols))))


def to_arpabet(phones: list[Phone]) -> list[tuple[str, int, bool]]:
    """(ARPAbet symbol, word index, is vowel) per sound; diphthongs become one symbol."""
    result = []
    sounds = [p for p in phones if p.symbol != " "]
    i = 0
    while i < len(sounds):
        base = sounds[i].symbol.replace(LENGTH_MARK, "")
        pair = base + (sounds[i + 1].symbol.replace(LENGTH_MARK, "") if i + 1 < len(sounds) and sounds[i + 1].word == sounds[i].word else "")
        if pair in IPA_TO_ARPABET and len(pair) > len(base):
            result.append((IPA_TO_ARPABET[pair], sounds[i].word, is_vowel(pair)))
            i += 2
            continue
        if base in IPA_TO_ARPABET:
            result.append((IPA_TO_ARPABET[base], sounds[i].word, sounds[i].vowel))
        i += 1
    return result
