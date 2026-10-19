# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Written words to DiffSinger phonemes in German, French, Spanish, Italian, Portuguese and Russian.
The same module as Spectro Maestro's foundry/g2p.py (same author, AGPL-3.0-or-later).

Voicebanks for these languages ship dictionaries with almost no words: they rely on OpenUtau's built-in G2P, which
looks a word up in a pronouncing dictionary and otherwise spells it out with a small ONNX model. This module ports
that route from OpenUtau (MIT licence, see THIRD_PARTY_NOTICES.md): G2pPack (dict.txt, then greedy decoding of
g2p.onnx) and DiffSingerG2pPhonemizer (the bank's own entries first; G2P symbols go through the bank dictionary's
replacements, else to '<lang>/<symbol>' when the bank has that symbol). The language packs are not shipped: each is
downloaded once from OpenUtau's repository at a pinned commit and checked against its SHA-256.

Departures from OpenUtau, each measured on its packs:
- The German Marzipan model reads a-z ä ö ü ß. The table in OpenUtau's C# class has an extra ë, which sent ö, ü
  and ß to the wrong letters: the model reproduced 47 of 150 dictionary words with umlauts that way (ß failed
  outright), and 131 with the table below.
- A word is looked up as written and in lower case in every dictionary before the model guesses: the packs'
  dictionaries are lower-case, and OpenUtau sent capitalised German nouns straight to the model.
- A word with an apostrophe or hyphen that no dictionary holds is read in parts (French l'amour, Italian
  dell'amore), and both apostrophe forms are tried (the French pack writes c’, the Italian one all'alba).
- A bank's generic dsdict.yaml lends its symbols but not its words: in multilingual banks it holds kana and pinyin,
  and a French "si" or "me" would otherwise be sung as Mandarin.
- A glide the pack writes as a consonant after a vowel (Spanish hoy: o I, Portuguese sem: e~ j~) stays in that
  vowel's syllable even where the bank maps it to a vowel symbol (Offglide). OpenUtau starts a note there and,
  when the word has no note left, adds it to the last one; the skills give one note per written syllable.
- Such a glide with no symbol in the bank is sung with the symbol of its vowel (Scheme.stand_ins): a bank whose
  Spanish dictionary lacks the semivowel I would otherwise stop at hoy, muy and rey.
"""
from __future__ import annotations

import hashlib
import os
import re
import zipfile
from dataclasses import dataclass

import numpy as np

OPENUTAU_COMMIT = "bc194b6fe4897427a73066390b286e11205fd10f"
PACK_URL = "https://raw.githubusercontent.com/stakira/OpenUtau/" + OPENUTAU_COMMIT + "/OpenUtau.Core/G2p/Data/{file}"
FIRST_SYMBOL = 4                # model indices 0-3 are reserved; letters and phonemes start at 4
STEP = 2                        # primes the decoder, and is its answer for "move to the next letter"
MAX_PHONEMES = 48               # OpenUtau's cap on the decoded length of one word
GENERIC_DICTIONARY = "dsdict.yaml"
APOSTROPHES = ("'", "’")


@dataclass(frozen=True)
class Scheme:
    """One of OpenUtau's DiffSinger phonemizers: its language pack and the bank dictionary it reads."""
    lang: str
    pack: str                   # file in OpenUtau.Core/G2p/Data
    sha256: str
    dictionary: str             # the bank dictionary this phonemizer reads
    letters: str                # model input symbols, from index 4
    symbols: tuple              # model output symbols, from index 4
    vowels: frozenset           # GetBaseG2pVowels of the phonemizer
    consonants: frozenset       # GetBaseG2pConsonants of the phonemizer
    lower_dictionary: bool = False    # Spanish pack: dict.txt words are matched lower-cased
    strip_stress: bool = False        # Italian pack: dict.txt and phones.txt symbols carry stress digits
    stand_ins: tuple = ()             # (glide, its vowel or glide): used when the bank has no symbol for the glide


def _scheme(lang, pack, sha256, dictionary, letters, symbols, vowels, consonants, **options) -> Scheme:
    return Scheme(lang, pack, sha256, dictionary, letters, tuple(symbols.split()), frozenset(vowels.split()),
                  frozenset(consonants.split()), **options)


# Tables from OpenUtau.Core/G2p/<Language>G2p.cs and DiffSinger/Phonemizers/DiffSinger<Language>Phonemizer.cs.
SCHEMES = {
    "de": (
        _scheme("de", "g2p-de.zip", "632de5830101038765de92679a3fddfcc216c1ad068ff8df7220c1d44bf811ac", "dsdict-de.yaml",
                "23/abcdefghijklmnopqrstuvwxyzäëöüßêîôáéíúàèùę",
                "aa ae ah ao aw ax ay b cc ch d dh ee eh er ex f g hh ih iy jh k l m n ng oe ohh ooh oy p pf q r rr s sh "
                "t th ts ue uh uw v w x y yy z zh",
                "aa ae ah ao aw ax ay ee eh er ex ih iy oe ohh ooh oy ue uh uw yy",
                "b cc ch d dh f g hh jh k l m n ng p pf q r rr s sh t th ts v w x y z zh"),
        _scheme("de", "g2p-de-marzipan.zip", "a991a6aefb2de24e326d186c4dfae4bb7b8c871ae58d29fc379133acc642595c",
                "dsdict-de-marzipan.yaml", "abcdefghijklmnopqrstuvwxyzäöüß",
                "a er eh e ih i uh u oh o ueh ue oeh oe ex ei au eu w j p t k f s sh ch xh h pf ts tsh th m n ng b d g v "
                "z l r dsh zh rh rr rx dh q vf cl",
                "a er eh e ih i uh u oh o ueh ue oeh oe ex ei au eu",
                "j p t k f s sh ch xh h pf ts tsh th m n ng b d g v z l r dsh zh rh rr rx dh q vf cl"),
    ),
    "fr": (
        _scheme("fr", "g2p-fr-millefeuille.zip", "f5407ec5b57441b60a958224e668e7c44326ae34f1b233a13565be4c631bb42d",
                "dsdict-fr-millefeuille.yaml", "'-abcdefghijklmnopqrstuvwxyzéèêàâîôùûçœï()0123456789",
                "ah eh ae ee oe ih oh oo ou uh en in on uy y w f k p s sh t h b d g l m n r v z j ng q",
                "ah eh ae ee oe ih oh oo ou uh en in on",
                "y w f k p s sh t h b d g l m n r v z j ng q uy vf cl"),
    ),
    "es": (
        _scheme("es", "g2p-es.zip", "8ad48d9ca68a14c3ce684011c1a1f79db253dabc69878d75dcd208cbf2adad92", "dsdict-es.yaml",
                "'-abcdefghijklmnopqrstuvwxyzÁÉÍÓÚáãéëêíñóúü",
                "a b B ch d D e f g G gn i I k l ll m n o p r rr s t u U w x y Y z",
                "a e i o u",
                "b B ch d D f g G gn I k l ll m n p r rr s t U w x y Y z", lower_dictionary=True,
                stand_ins=(("I", "i"), ("U", "u"))),
    ),
    "it": (
        _scheme("it", "g2p-it.zip", "9571d89dbfdf5ac40abc67e4fc2fda3768ed00bb37b7f465c847cb6b6fde6017", "dsdict-it.yaml",
                "'abcdefghijklmnopqrstuvwxyzàèéìíòùú",
                "a b d dz dZZ e EE f g i j JJ k l LL m n nf ng o OO p r s SS t ts tSS u v w z",
                "a e EE i o OO u",
                "b d dz dZZ f g j JJ k l LL m n nf ng p r s SS t ts tSS v w z", strip_stress=True),
    ),
    "pt": (
        _scheme("pt", "g2p-pt.zip", "0b53a47165be26b1186bf30553289e4025d01e5e279f057d94ee0c71b1e8f217", "dsdict-pt.yaml",
                "-abcdefghijklmnopqrstuvwxyzàáâãçèéêíîóôõúûü",
                "E J L O R S X Z a a~ b d dZ e e~ f g i i~ j j~ k l m n o o~ p r s t tS u u~ v w w~ z",
                "E O a a~ e e~ i i~ o o~ u u~",
                "J L R S X Z b d dZ f g j j~ k l m n p r s t tS v w w~ z", stand_ins=(("j~", "j"), ("w~", "w"))),
    ),
    "ru": (
        _scheme("ru", "g2p-ru.zip", "79401a621546794c6a3db09a3870f6ab210b32019b66e60230c9cb4ab340da77", "dsdict-ru.yaml",
                "-абвгдежзийклмнопрстуфхцчшщъыьэюяё",
                "a aa ay b bb c ch d dd ee f ff g gg h hh i ii j ja je jo ju k kk l ll m mm n nn oo p pp r rr s sch sh "
                "ss t tt u uj uu v vv y yy z zh zz",
                "a aa ay ee i ii ja je jo ju oo u uj uu y yy",
                "b bb c ch d dd f ff g gg h hh j k kk l ll m mm n nn p pp r rr s sch sh ss t tt v vv z zh zz"),
    ),
}
LANGUAGES = frozenset(SCHEMES)
_packs: dict = {}


def load_yaml(path: str) -> dict:
    """A bank file read as OpenUtau reads it (YAML 1.2): on, off, yes and no stay words, only true and false are
    booleans. PyYAML follows YAML 1.1 and turned the French and Portuguese nasal vowel 'on' into True, so the bank
    lost that vowel."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass
    Loader.yaml_implicit_resolvers = {first: [r for r in resolvers if r[0] != "tag:yaml.org,2002:bool"]
                                      for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()}
    Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
    with open(path, encoding="utf-8-sig") as handle:
        return yaml.load(handle, Loader=Loader) or {}


class Pack:
    """An OpenUtau language pack: pronouncing dictionary, symbol kinds and the spelling model (G2pPack)."""

    def __init__(self, scheme: Scheme, path: str):
        import onnxruntime as ort
        with zipfile.ZipFile(path) as archive:
            phones = archive.read("phones.txt").decode("utf-8").splitlines()
            entries = archive.read("dict.txt").decode("utf-8").splitlines()
            model = archive.read("g2p.onnx")

        def prep(symbol: str) -> str:
            return symbol.rstrip("0123456789") if scheme.strip_stress else symbol
        self.vowel = {prep(p[0]): p[1] == "vowel" for p in (line.split() for line in phones) if len(p) == 2}
        self.words = {}
        for line in entries:
            parts = line.strip().split("  ")
            if line.startswith(";;;") or len(parts) != 2:
                continue
            word = parts[0].lower() if scheme.lower_dictionary else parts[0]
            self.words[word] = [prep(s) for s in parts[1].split() if prep(s) in self.vowel]
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(model, options, providers=["CPUExecutionProvider"])
        self.index = {letter: i + FIRST_SYMBOL for i, letter in enumerate(scheme.letters)}
        self.symbols = scheme.symbols
        self.guesses: dict = {}

    def guess(self, word: str) -> list:
        """The model's phonemes for a word (G2pPack.Predict): greedy decoding, one letter position at a time."""
        if word not in self.guesses:
            letters = [self.index[c] for c in word.lower() if c in self.index]
            out, position = [STEP], 0
            while position < len(letters) and len(out) < MAX_PHONEMES:
                feed = {"src": np.array([letters], np.int32), "tgt": np.array([out], np.int32),
                        "t": np.array([position], np.int32)}
                token = int(self.session.run(None, feed)[0][0])
                if token == STEP:
                    position += 1
                else:
                    out.append(token)
            self.guesses[word] = [self.symbols[t - FIRST_SYMBOL] for t in out[1:] if t >= FIRST_SYMBOL]
        return list(self.guesses[word])


def pack(scheme: Scheme, folder: str, fetch) -> Pack:
    """The scheme's language pack, downloaded once into `folder` with `fetch(url, path)` and checked by SHA-256."""
    path = os.path.join(folder, scheme.pack)
    if path not in _packs:
        fetch(PACK_URL.format(file=scheme.pack), path)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        if digest != scheme.sha256:
            os.remove(path)
            raise ValueError(f"{scheme.pack} does not match the expected SHA-256 and was removed; download "
                             f"{PACK_URL.format(file=scheme.pack)} again or place a good copy at {path}")
        _packs[path] = Pack(scheme, path)
    return _packs[path]


def _mapping(scheme: Scheme, replacements: dict, tokens: set, use_lang_id: bool) -> dict:
    """Pack symbol -> bank symbol (DiffSingerG2pPhonemizer.LoadG2p): the dictionary's replacements, else the
    '<lang>/' form when the bank has it, else the bare symbol when the bank has that."""
    mapping = dict(replacements)
    for symbol in sorted(scheme.vowels | scheme.consonants):
        if symbol not in mapping:
            prefixed = f"{scheme.lang}/{symbol}"
            mapping[symbol] = prefixed if prefixed in tokens else symbol if symbol in tokens else \
                prefixed if use_lang_id else symbol
    for glide, stand_in in scheme.stand_ins:
        if mapping[glide] not in tokens and mapping.get(stand_in) in tokens:
            mapping[glide] = mapping[stand_in]
    return mapping


def choose(lang: str, dictionaries: dict, tokens: set, use_lang_id: bool) -> tuple:
    """(scheme, dictionary file) for a bank: the phonemizer whose pack symbols the bank can sing most of, and on a tie
    the one whose own dictionary file the bank has. `dictionaries` maps the bank's dsdict file names to their
    replacements. Without the scheme's own file, dsdict-<lang>.yaml or another dsdict-<lang>-*.yaml stands in, then
    the generic dsdict.yaml (None when the bank has none of them)."""
    fallbacks = sorted(name for name in dictionaries if name == f"dsdict-{lang}.yaml" or name.startswith(f"dsdict-{lang}-"))
    fallbacks.sort(key=lambda name: name != f"dsdict-{lang}.yaml")
    best = None
    for scheme in SCHEMES[lang]:
        own = scheme.dictionary in dictionaries
        name = scheme.dictionary if own else next(iter(fallbacks), GENERIC_DICTIONARY if GENERIC_DICTIONARY in dictionaries else None)
        mapping = _mapping(scheme, dictionaries.get(name) or {}, tokens, use_lang_id)
        symbols = scheme.vowels | scheme.consonants
        coverage = sum(mapping[s] in tokens for s in symbols) / len(symbols)
        if best is None or (coverage, own) > best[0]:
            best = ((coverage, own), scheme, name)
    return best[1], best[2]


class Offglide(str):
    """A bank vowel symbol that closes the syllable before it instead of starting one (see the module notes)."""


class Route:
    """A bank's way from a written word to its own phonemes in one language (OpenUtau's DiffSingerG2pPhonemizer).
    The pack is loaded by `load_pack` on the first word the bank's own entries lack, so a bank whose dictionary
    holds every word of a song never downloads it."""

    def __init__(self, scheme: Scheme, load_pack, entries: dict, replacements: dict, tokens: set, use_lang_id: bool,
                 vowels: set):
        self.scheme, self.load_pack, self.entries = scheme, load_pack, entries
        self.mapping = _mapping(scheme, replacements, tokens, use_lang_id)
        self.vowels = vowels                            # bank symbols its dictionary types as vowels
        self._pack = None

    @property
    def pack(self) -> Pack:
        if self._pack is None:
            self._pack = self.load_pack()
        return self._pack

    def kinds(self) -> dict:
        """'vowel' or 'consonant' for every bank symbol the pack can produce, from the pack symbols it stands for
        (a vowel when any of them is: a glide's stand-in shares its vowel's symbol)."""
        kinds = {}
        for symbol in sorted(set(self.scheme.symbols) | self.scheme.vowels | self.scheme.consonants):
            target = self.mapping.get(symbol, symbol)
            if kinds.get(target) != "vowel":
                kinds[target] = "vowel" if symbol in self.scheme.vowels else "consonant"
        return kinds

    def phonemes(self, word: str) -> list | None:
        """The bank's phonemes for a written word, or None when it has no letters the pack reads."""
        for form in _forms(word):
            if form in self.entries:
                return list(self.entries[form])
        if not any(c.isalpha() for c in word):
            return None
        found = self._dictionary(word)
        if found is None and any(mark in word for mark in APOSTROPHES + ("-",)):
            parts = [self._dictionary(part) or self.pack.guess(part) for part in _parts(word)]
            found = [s for part in parts for s in part] if all(parts) else None
        if found is None:
            found = self.pack.guess(word)
        if not found:
            return None
        mapped = [self.mapping.get(s, s) for s in found]
        return [Offglide(m) if i and s not in self.scheme.vowels and m in self.vowels and found[i - 1] in self.scheme.vowels
                else m for i, (s, m) in enumerate(zip(found, mapped))]

    def _dictionary(self, word: str) -> list | None:
        for form in _forms(word):
            if form in self.pack.words:
                return list(self.pack.words[form])
        return None


def _forms(word: str) -> list:
    """The word as written and in lower case, each with both apostrophe forms."""
    forms = []
    for base in (word, word.lower()):
        for form in (base, base.replace("’", "'"), base.replace("'", "’")):
            if form not in forms:
                forms.append(form)
    return forms


def _parts(word: str) -> list:
    """l'amour -> l' + amour, peut-être -> peut + être: an apostrophe stays with the part before it."""
    parts, current = [], ""
    for c in word:
        if c == "-":
            parts.append(current)
            current = ""
        elif c in APOSTROPHES:
            parts.append(current + c)
            current = ""
        else:
            current += c
    return [part for part in parts + [current] if part.strip("'’")]
