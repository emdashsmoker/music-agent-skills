# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Sing with a DiffSinger voicebank the user supplies (the OpenUtau voicebank layout, ONNX models).

Nothing about any particular voicebank lives here. The user points to a folder, an archive or a
link; this module reads the voicebank's own configuration and dictionaries and runs its models
unmodified: duration, pitch, variance, acoustic, vocoder. The user is responsible for the terms
of the voicebank they choose; `inspect` lists the licence and readme files found so they can be read.

Pipeline per lyric line
  words -> phonemes (voicebank dictionary, then CMUdict for English, then espeak when available)
  phonemes -> notes (each vowel starts a note; consonants before it are sung ahead of the beat)
  duration model -> pitch model (or the built-in pitch curve) -> variance model -> acoustic model -> vocoder"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile

import numpy as np
import yaml

from . import singing, speech, theory
from .dsp import SR

ENGINE_SEED = speech.ENGINE_SEED
HEAD_FRAMES = TAIL_FRAMES = 8          # silence the models expect around a phrase
HEAD_CONSONANT_ROOM_S = 0.5            # time before the first note in which leading consonants may sit
REST_GAP_S = 0.12
CACHE_VERSION = 2
DEFAULTS = {"lang": "en", "speaker": None, "steps": 20, "pitch_steps": 10, "variance_steps": 10, "depth": 0.6,
            "deterministic": True,
            "pitch": "model", "expr": 1.0, "gender": 0.0, "velocity": 1.0, "tension": 0.0, "breathiness": 0.0,
            "voicing": 0.0}
LICENCE_PATTERNS = ("*licen*", "*terms*", "*readme*", "*README*", "character.txt", "*tos*", "*credit*")
ARPABET_VOWELS = {"aa", "ae", "ah", "ao", "aw", "ay", "eh", "er", "ey", "ih", "iy", "ow", "oy", "uh", "uw"}
IPA_TO_ARPABET = [("tʃ", "ch"), ("dʒ", "jh"), ("aɪ", "ay"), ("aʊ", "aw"), ("eɪ", "ey"), ("oʊ", "ow"), ("əʊ", "ow"),
                  ("ɔɪ", "oy"), ("ɑ", "aa"), ("æ", "ae"), ("ʌ", "ah"), ("ə", "ah"), ("ɐ", "ah"), ("ɔ", "ao"),
                  ("ɒ", "aa"), ("ɛ", "eh"), ("e", "eh"), ("ɜ", "er"), ("ɚ", "er"), ("ɝ", "er"), ("ɪ", "ih"),
                  ("ᵻ", "ih"), ("i", "iy"), ("ʊ", "uh"), ("u", "uw"), ("o", "ow"), ("a", "aa"),
                  ("b", "b"), ("d", "d"), ("f", "f"), ("ɡ", "g"), ("g", "g"), ("h", "hh"), ("k", "k"), ("l", "l"),
                  ("m", "m"), ("n", "n"), ("ŋ", "ng"), ("p", "p"), ("ɹ", "r"), ("r", "r"), ("s", "s"), ("ʃ", "sh"),
                  ("t", "t"), ("θ", "th"), ("v", "v"), ("w", "w"), ("j", "y"), ("z", "z"), ("ʒ", "zh"), ("ð", "dh"),
                  ("ɾ", "d")]


class DiffSingerError(singing.VocalError):
    pass


# ---------------------------------------------------------------- locating a voicebank

def resolve(reference: str) -> str:
    """Folder, .zip file, .zip URL or git URL -> folder that holds dsconfig.yaml.
    Archives and repositories are unpacked into the models directory under a name derived from the reference."""
    reference = os.path.expanduser(str(reference))
    if os.path.isdir(reference):
        return _find_root(reference)
    store = os.path.join(speech.models_dir(), "diffsinger")
    name = re.sub(r"[^\w.-]+", "_", os.path.splitext(os.path.basename(reference.rstrip("/")))[0])[-60:] or "voicebank"
    target = os.path.join(store, name + "_" + hashlib.sha1(reference.encode()).hexdigest()[:8])
    if not os.path.isdir(target):
        os.makedirs(store, exist_ok=True)
        if reference.startswith(("http://", "https://")) and not reference.lower().split("?")[0].endswith(".zip"):
            if not shutil.which("git"):
                raise DiffSingerError("git is needed to fetch a repository link")
            subprocess.run(["git", "clone", "--depth", "1", reference, target], check=True)
        else:
            archive = reference
            if reference.startswith(("http://", "https://")):
                archive = speech.fetch(reference, target + ".zip")
            if not os.path.isfile(archive):
                raise DiffSingerError(f"voicebank not found: {reference}")
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.namelist():           # refuse paths that would leave the target folder
                    if os.path.isabs(member) or ".." in member.split("/"):
                        raise DiffSingerError(f"unsafe path in archive: {member}")
                bundle.extractall(target)
    return _find_root(target)


def _find_root(folder: str) -> str:
    hits = sorted(glob.glob(os.path.join(glob.escape(folder), "**", "dsconfig.yaml"), recursive=True), key=len)
    for hit in hits:
        with open(hit, encoding="utf-8-sig") as handle:
            if "acoustic" in (yaml.safe_load(handle) or {}):
                return os.path.dirname(hit)
    raise DiffSingerError(f"no DiffSinger voicebank (dsconfig.yaml with an 'acoustic' entry) under {folder}")


def _read_yaml(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as handle:
        return yaml.safe_load(handle) or {}


def _read_phonemes(path: str) -> dict:
    if path.endswith(".json"):
        with open(path, encoding="utf-8-sig") as handle:
            return json.load(handle)
    with open(path, encoding="utf-8-sig") as handle:
        return {line.strip(): index for index, line in enumerate(handle) if line.strip()}


class Stage:
    """One model folder of a voicebank (root, dsdur, dspitch, dsvariance) with its own config and token table."""

    def __init__(self, folder: str):
        self.folder = folder
        self.config = _read_yaml(os.path.join(folder, "dsconfig.yaml"))
        self.tokens = _read_phonemes(self.path(self.config["phonemes"]))
        self.languages = {}
        if self.config.get("use_lang_id") and self.config.get("languages"):
            with open(self.path(self.config["languages"]), encoding="utf-8-sig") as handle:
                self.languages = json.load(handle)
        self.frame_s = self.config.get("hop_size", 512) / self.config.get("sample_rate", 44100)
        self.seed_offset = 0
        self._sessions = {}
        self._embeds = {}

    def path(self, relative: str) -> str:
        return os.path.normpath(os.path.join(self.folder, relative))

    def forget(self, keys: tuple) -> None:
        for key in keys:
            self._sessions.pop(key, None)

    def session(self, key: str):
        if key not in self._sessions:
            import onnxruntime as ort
            ort.set_seed(ENGINE_SEED + self.seed_offset)
            options = ort.SessionOptions()
            options.log_severity_level = 3
            self._sessions[key] = ort.InferenceSession(self.path(self.config[key]), options, providers=["CPUExecutionProvider"])
        return self._sessions[key]

    def run(self, key: str, feeds: dict) -> list:
        """Run a model, passing only the inputs it declares and fixing scalar ranks to what it expects."""
        session = self.session(key)
        chosen = {}
        for item in session.get_inputs():
            if item.name not in feeds:
                raise DiffSingerError(f"{os.path.basename(self.folder)}/{self.config[key]} needs input {item.name!r}, "
                                      f"which this runner does not provide")
            value = feeds[item.name]
            if isinstance(value, np.ndarray) and value.size == 1 and item.name in ("steps", "depth", "speedup"):
                value = value.reshape([1] * len(item.shape))
            chosen[item.name] = value
        return session.run(None, chosen)

    def token_ids(self, symbols: list) -> np.ndarray:
        missing = [s for s in symbols if s not in self.tokens]
        if missing:
            raise DiffSingerError(f"phonemes {sorted(set(missing))} are not in {os.path.basename(self.folder)}'s phoneme table")
        return np.array([[self.tokens[s] for s in symbols]], dtype=np.int64)

    def language_ids(self, symbols: list) -> np.ndarray:
        return np.array([[self.languages.get(s.split("/")[0], 0) if "/" in s else 0 for s in symbols]], dtype=np.int64)

    def speakers(self) -> list:
        return [os.path.basename(s) for s in self.config.get("speakers") or []]

    def embed(self, mix: dict) -> np.ndarray | None:
        """Speaker embedding for a mix {name: weight}; None when the model has no speakers."""
        entries = self.config.get("speakers") or []
        if not entries:
            return None
        table = {os.path.basename(entry): entry for entry in entries}
        total = np.zeros(int(self.config.get("hidden_size", 256)), dtype=np.float32)
        used = False
        for name, weight in mix.items():
            match = next((k for k in table if k.lower() == str(name).lower()), None)
            if match is None:
                raise DiffSingerError(f"speaker {name!r} not found; available: {sorted(table)}")
            if match not in self._embeds:
                self._embeds[match] = np.fromfile(self.path(table[match] + ".emb"), dtype=np.float32)
            if not used:
                total = np.zeros_like(self._embeds[match])
            total += float(weight) * self._embeds[match]
            used = True
        return total

    def steps_feed(self, steps: int) -> dict:
        if self.config.get("use_continuous_acceleration"):
            return {"steps": np.array(int(steps), dtype=np.int64)}
        speedup = max(1, 1000 // int(steps))
        while 1000 % speedup and speedup > 1:
            speedup -= 1
        return {"speedup": np.array(speedup, dtype=np.int64)}


class Voicebank:
    def __init__(self, reference: str):
        self.root = resolve(reference)
        self.acoustic = Stage(self.root)
        self.stages = {name: Stage(os.path.join(self.root, name)) for name in ("dsdur", "dspitch", "dsvariance")
                       if os.path.exists(os.path.join(self.root, name, "dsconfig.yaml"))}
        if "dsdur" not in self.stages:
            raise DiffSingerError("this voicebank has no duration model (dsdur); phoneme timing cannot be predicted")
        vocoder_dir = next((d for d in (os.path.join(self.root, str(self.acoustic.config.get("vocoder", ""))),
                                        os.path.join(self.root, "dsvocoder"))
                            if os.path.exists(os.path.join(d, "vocoder.yaml"))), None)
        if vocoder_dir is None:
            raise DiffSingerError("no vocoder found in the voicebank (expected dsvocoder/vocoder.yaml)")
        self.vocoder_config = _read_yaml(os.path.join(vocoder_dir, "vocoder.yaml"))
        self.vocoder_path = os.path.join(vocoder_dir, self.vocoder_config["model"])
        self._vocoder = None
        self.seed_offset = 0
        self._dictionaries = {}

    def reseed(self, seed: int) -> None:
        """Start every sampling model from a known random state.
        The models draw their diffusion noise from a generator that lives inside the session and cannot be reset,
        so the sessions that sample are rebuilt for each phrase. A phrase then sounds the same whatever was
        rendered before it; a different seed gives a different take (used for doubles)."""
        for stage, keys in ((self.acoustic, ("acoustic",)), (self.stages.get("dspitch"), ("pitch",)),
                            (self.stages.get("dsvariance"), ("variance",))):
            if stage is not None:
                stage.seed_offset = int(seed)
                stage.forget(keys)
        self.seed_offset = int(seed)
        self._vocoder = None

    def vocoder(self):
        if self._vocoder is None:
            import onnxruntime as ort
            ort.set_seed(ENGINE_SEED + self.seed_offset)
            options = ort.SessionOptions()
            options.log_severity_level = 3
            self._vocoder = ort.InferenceSession(self.vocoder_path, options, providers=["CPUExecutionProvider"])
        return self._vocoder

    def dictionary(self, lang: str) -> dict:
        """{'entries': {grapheme: [phonemes]}, 'types': {symbol: type}} from dsdict-<lang>.yaml or dsdict.yaml."""
        if lang not in self._dictionaries:
            folder = self.stages["dsdur"].folder
            path = next((p for p in (os.path.join(folder, f"dsdict-{lang}.yaml"), os.path.join(folder, "dsdict.yaml"))
                         if os.path.exists(p)), None)
            if path is None:
                raise DiffSingerError(f"the voicebank has no dictionary for language {lang!r}")
            data = _read_yaml(path)
            entries = {str(e["grapheme"]): [str(p) for p in e["phonemes"]] for e in data.get("entries") or []}
            types = {str(s["symbol"]): str(s["type"]) for s in data.get("symbols") or []}
            replacements = {str(r["from"]): str(r["to"]) for r in data.get("replacements") or []}
            self._dictionaries[lang] = {"entries": entries, "types": types, "replacements": replacements,
                                        "longest": max((len(g) for g in entries), default=1)}
        return self._dictionaries[lang]


_banks = {}


def voicebank(reference: str) -> Voicebank:
    if reference not in _banks:
        _banks[reference] = Voicebank(reference)
    return _banks[reference]


def inspect(reference: str) -> dict:
    """What a voicebank offers, and which of its files state the terms of use."""
    bank = voicebank(reference)
    folder = bank.stages["dsdur"].folder
    documents = sorted({os.path.relpath(p, bank.root) for pattern in LICENCE_PATTERNS
                        for p in glob.glob(os.path.join(glob.escape(bank.root), pattern))})
    acoustic = bank.acoustic.config
    return {"root": bank.root, "speakers": bank.acoustic.speakers(),
            "languages": sorted(bank.acoustic.languages) or ["(single language)"],
            "dictionaries": sorted(os.path.basename(p) for p in glob.glob(os.path.join(glob.escape(folder), "dsdict*.yaml"))),
            "models": {"duration": True, "pitch": "dspitch" in bank.stages, "variance": "dsvariance" in bank.stages},
            "sample_rate": acoustic.get("sample_rate"), "controls": [k[4:-6] for k, v in acoustic.items()
                                                                      if k.startswith("use_") and k.endswith("_embed") and v],
            "read_these_for_terms_of_use": documents,
            "note": "Read the listed files (and the voicebank's download page) and tell the user the usage terms before rendering."}


# ---------------------------------------------------------------- text to phonemes

_cmudict = None


def _english_fallback(word: str) -> list | None:
    """ARPAbet (lower case, no stress) for an English word outside the voicebank dictionary."""
    global _cmudict
    if _cmudict is None:
        try:
            import cmudict
            _cmudict = cmudict.dict()
        except ImportError:
            _cmudict = {}
    hit = _cmudict.get(word.lower())
    if hit:
        return [re.sub(r"\d", "", p).lower() for p in hit[0]]
    try:
        from kokoro_onnx.tokenizer import Tokenizer
        ipa = Tokenizer().phonemize(word, "en-us")
    except Exception:
        return None
    out, index = [], 0
    ipa = "".join(c for c in ipa if c not in "ˈˌː ")
    while index < len(ipa):
        for source, target in IPA_TO_ARPABET:
            if ipa.startswith(source, index):
                out.append(target)
                index += len(source)
                break
        else:
            index += 1
    return out or None


def word_phonemes(bank: Voicebank, word: str, lang: str) -> list:
    """Phonemes of one written word in the voicebank's own symbols."""
    book = bank.dictionary(lang)
    tokens = bank.stages["dsdur"].tokens
    clean = word.strip(" \t.,!?;:\"()[]…—").replace("’", "'")
    if not clean:
        return []
    for candidate in (clean, clean.lower()):
        if candidate in book["entries"]:
            return list(book["entries"][candidate])
    if lang == "en":
        arpabet = _english_fallback(clean)
        if arpabet:
            out = []
            for phoneme in arpabet:
                mapped = book["replacements"].get(phoneme) or (f"{lang}/{phoneme}" if f"{lang}/{phoneme}" in tokens else phoneme)
                if mapped not in tokens:
                    raise DiffSingerError(f"word {word!r}: phoneme {phoneme!r} has no match in this voicebank")
                out.append(mapped)
            return out
    # Scripts without spaces between syllables (kana, hangul, hanzi): longest dictionary match from the left.
    out, index = [], 0
    while index < len(clean):
        for size in range(min(book["longest"], len(clean) - index), 0, -1):
            piece = clean[index:index + size]
            if piece in book["entries"]:
                out += book["entries"][piece]
                index += size
                break
        else:
            raise DiffSingerError(f"cannot pronounce {word!r} (stuck at {clean[index:]!r}) with the voicebank's {lang} "
                                  f"dictionary. Give the line a 'phonemes' entry in the voicebank's own symbols.")
    return out


def line_words(bank: Voicebank, line: dict, lang: str) -> list:
    """[[phonemes of word 1], ...]. A line may carry 'phonemes': 'en/hh en/ah | en/l en/ow' to override."""
    if line.get("phonemes"):
        return [chunk.split() for chunk in str(line["phonemes"]).split("|") if chunk.strip()]
    return [p for p in (word_phonemes(bank, word, lang) for word in re.split(r"[\s\-]+", line["text"])) if p]


def _is_vowel(bank: Voicebank, lang: str, symbol: str) -> bool:
    kind = bank.dictionary(lang)["types"].get(symbol)
    if kind is None:
        return symbol.split("/")[-1] in ARPABET_VOWELS
    return kind == "vowel"


def _is_glide(bank: Voicebank, lang: str, symbol: str) -> bool:
    return bank.dictionary(lang)["types"].get(symbol) in ("semivowel", "liquid")


def syllable_groups(bank: Voicebank, words: list, lang: str) -> tuple:
    """Split the phonemes of a line into note-sized groups: [[head consonants], [syllable 1], [syllable 2], ...].
    A group starts at a vowel (or at a glide between a consonant and a vowel) and runs to the next start, so it
    ends with the consonants that lead into the next syllable. `word_cut[k]` is where, inside group k, the next
    word begins (None when the group ends inside a word or at the end of the line)."""
    groups, word_cut = [[]], [None]
    for symbols in words:
        vowel = [_is_vowel(bank, lang, s) for s in symbols]
        glide = [_is_glide(bank, lang, s) for s in symbols]
        starts = [False] * len(symbols)
        if not any(vowel):
            starts[0] = True
        for i, flag in enumerate(vowel):
            if flag:
                if i >= 2 and glide[i - 1] and not vowel[i - 2]:
                    starts[i - 1] = True
                else:
                    starts[i] = True
        if not starts[0]:
            word_cut[-1] = len(groups[-1])
        for symbol, start in zip(symbols, starts):
            if start:
                groups.append([])
                word_cut.append(None)
            groups[-1].append(symbol)
    return groups, word_cut


# ---------------------------------------------------------------- one phrase through the models

def _frames(seconds: float, frame_s: float) -> int:
    return int(round(seconds / frame_s))


def _per_frame(values, durations: np.ndarray) -> np.ndarray:
    return np.repeat(np.asarray(values), durations, axis=0)


DEPTH_STEP_SCALE = 1000                 # older exports count shallow-diffusion depth in steps out of 1000


def _depth_feed(acoustic: Stage, settings: dict) -> dict:
    """The acoustic model's shallow-diffusion depth and sampling acceleration in the units its export declares.
    Recent exports take the depth as a fraction (float, max_depth <= 1) next to the usual steps or speedup feed.
    Older ones take an int64 step count out of 1000: the speedup is then chosen so that the requested number of
    sampling steps is taken within that depth, and the depth is rounded down to a multiple of it (as OpenUtau does)."""
    inputs = {item.name: item.type for item in acoustic.session("acoustic").get_inputs()}
    if "depth" not in inputs:
        return acoustic.steps_feed(settings["steps"])
    max_depth = float(acoustic.config.get("max_depth", 1.0))
    if "int" not in inputs["depth"]:
        return {"depth": np.array(min(float(settings["depth"]), max_depth), dtype=np.float32),
                **acoustic.steps_feed(settings["steps"])}
    depth_steps = min(int(round(float(settings["depth"]) * DEPTH_STEP_SCALE)), int(max_depth))
    speedup = max(1, depth_steps // int(settings["steps"]))
    return {"depth": np.array(max(speedup, depth_steps // speedup * speedup), dtype=np.int64),
            "speedup": np.array(speedup, dtype=np.int64)}


def sing_phrase(bank: Voicebank, groups: list, word_cut: list, notes: list, settings: dict, lang: str) -> tuple:
    """Render one phrase. `groups` and `word_cut` come from syllable_groups, `notes` are (start_s, dur_s, midi, tie)
    relative to the phrase start. Returns (audio, seconds of audio before the phrase start, sample rate, info)."""
    note_groups = singing.note_groups(notes)
    if len(note_groups) != len(groups) - 1:
        raise DiffSingerError(f"{len(groups) - 1} syllables but {len(note_groups)} notes")
    if settings.get("deterministic", True):
        bank.reseed(int(settings.get("seed", 0)))
    dur_stage = bank.stages["dsdur"]
    frame_s = bank.acoustic.frame_s
    mix = settings["speaker"] if isinstance(settings["speaker"], dict) else \
        {settings["speaker"] or (bank.acoustic.speakers() or [None])[0]: 1.0}

    # --- lay the groups on the timeline; a rest inside the phrase becomes a silence group that also
    # holds the consonants leading into the next note
    plan = [{"at": -HEAD_CONSONANT_ROOM_S, "symbols": ["SP"] + groups[0], "midi": note_groups[0][2][0][2], "rest": True}]
    for index, (group, note) in enumerate(zip(groups[1:], note_groups)):
        following = note_groups[index + 1] if index + 1 < len(note_groups) else None
        rest_after = following is not None and following[0] - note[1] >= REST_GAP_S
        cut = word_cut[index + 1] if rest_after and word_cut[index + 1] is not None else len(group)
        plan.append({"at": note[0], "symbols": group[:cut], "midi": note[2][0][2], "rest": False})
        if rest_after:
            plan.append({"at": note[1], "symbols": ["SP"] + group[cut:], "midi": following[2][0][2], "rest": True})
    end = note_groups[-1][1]
    symbols = [s for item in plan for s in item["symbols"]]
    word_div = np.array([[len(item["symbols"]) for item in plan]], dtype=np.int64)
    edges = [item["at"] for item in plan] + [end]
    word_dur = np.array([[max(1, _frames(b, frame_s) - _frames(a, frame_s)) for a, b in zip(edges, edges[1:])]], dtype=np.int64)
    feeds = {"tokens": dur_stage.token_ids(symbols), "languages": dur_stage.language_ids(symbols),
             "word_div": word_div, "word_dur": word_dur}
    encoder_out, masks = dur_stage.run("linguistic", feeds)
    ph_midi = np.array([[int(round(item["midi"])) for item in plan for _ in item["symbols"]]], dtype=np.int64)
    feeds = {"encoder_out": encoder_out, "x_masks": masks, "ph_midi": ph_midi}
    embed = dur_stage.embed(mix)
    if embed is not None:
        feeds["spk_embed"] = np.tile(embed, (1, len(symbols), 1)).astype(np.float32)
    predicted = np.maximum(dur_stage.run("dur", feeds)[0].squeeze(0).astype(np.float64), 0.5) * frame_s

    # --- fit the predicted durations into the note grid: silence absorbs the slack before consonants,
    # sung groups are stretched to reach the next group exactly
    starts, cursor = [], 0
    for item, a, b in zip(plan, edges, edges[1:]):
        count = len(item["symbols"])
        own = predicted[cursor:cursor + count]
        if item["rest"]:
            consonants = own[1:]
            room = (b - a) * 0.9
            scale = min(1.0, room / consonants.sum()) if consonants.sum() > 0 else 1.0
            offsets = b - np.cumsum((consonants * scale)[::-1])[::-1]
            starts += [a] + list(offsets)
        else:
            scale = (b - a) / own.sum()
            starts += list(a + np.concatenate([[0.0], np.cumsum(own * scale)[:-1]]))
        cursor += count
    bounds = np.array(starts + [end])
    origin = bounds[0] - HEAD_FRAMES * frame_s
    all_symbols = ["SP"] + symbols + ["SP"]
    frame_edges = np.concatenate([[0], np.round((bounds - origin) / frame_s).astype(int)])
    frame_edges = np.maximum.accumulate(frame_edges)
    durations = np.diff(np.concatenate([frame_edges, [frame_edges[-1] + TAIL_FRAMES]]))
    # the leading silence symbol of the plan merges with the padding silence
    durations = np.concatenate([[durations[0] + durations[1]], durations[2:]])
    all_symbols = all_symbols[1:]
    durations = np.maximum(durations, 1).astype(np.int64)
    n_frames = int(durations.sum())
    times = origin + np.arange(n_frames) * frame_s

    # --- pitch
    flat_notes = [(s, e, m) for group in note_groups for (s, e, m) in group[2]]
    pitch_stage = bank.stages.get("dspitch")
    if settings["pitch"] == "model" and pitch_stage is not None:
        midi = _predict_pitch(pitch_stage, bank, all_symbols, durations, flat_notes, note_groups, origin, n_frames, mix,
                              settings, lang)
    else:
        style = {**singing.DEFAULT_STYLE, **settings.get("style", {})}
        scale = singing.FRAME_S / frame_s
        fine = singing.pitch_curve(note_groups, int(np.ceil(n_frames / scale)) + 2, origin, style,
                                   np.random.default_rng(settings.get("seed", 1)))
        midi = np.interp(times, origin + np.arange(len(fine)) * singing.FRAME_S, fine)
    midi = midi + settings.get("_shift", 0.0)
    f0 = (440.0 * 2.0 ** ((midi - 69.0) / 12.0)).astype(np.float32)[None, :]

    # --- variance curves the acoustic model wants
    acoustic = bank.acoustic
    wanted = [name for name in ("energy", "breathiness", "voicing", "tension") if acoustic.config.get(f"use_{name}_embed")]
    curves = {}
    variance_stage = bank.stages.get("dsvariance")
    if wanted:
        if variance_stage is None:
            raise DiffSingerError("the acoustic model needs variance curves but the voicebank has no dsvariance model")
        curves = _predict_variance(variance_stage, all_symbols, durations, midi, mix, settings)
    feeds = {"tokens": acoustic.token_ids(all_symbols), "languages": acoustic.language_ids(all_symbols),
             "durations": durations[None, :], "f0": f0,
             "gender": np.full((1, n_frames), float(settings["gender"]), dtype=np.float32),
             "velocity": np.full((1, n_frames), float(settings["velocity"]), dtype=np.float32),
             **_depth_feed(acoustic, settings)}
    offsets = {"breathiness": settings["breathiness"], "voicing": settings["voicing"], "tension": settings["tension"]}
    for name in wanted:
        low, high = (-10.0, 10.0) if name == "tension" else (-96.0, 0.0)
        feeds[name] = np.clip(curves[name] + float(offsets.get(name, 0.0)), low, high).astype(np.float32)[None, :]
    embed = acoustic.embed(mix)
    if embed is not None:
        feeds["spk_embed"] = np.tile(embed, (1, n_frames, 1)).astype(np.float32)
    mel = acoustic.run("acoustic", feeds)[0]
    if str(bank.vocoder_config.get("mel_base", "10")) != str(acoustic.config.get("mel_base", "10")):
        mel = mel * (2.302585 if str(bank.vocoder_config.get("mel_base")) == "e" else 0.4342945)
    audio = bank.vocoder().run(None, {"mel": mel.astype(np.float32), "f0": f0})[0].squeeze()
    rate = int(bank.vocoder_config.get("sample_rate", 44100))
    # how far the first consonants reach ahead of the phrase start (the padding silence before them does not count)
    lead = max(0.0, -float(bounds[1])) if groups[0] else 0.0
    info = {"symbols": all_symbols, "bounds_s": [round(float(b), 3) for b in bounds], "frames": n_frames, "lead_s": lead}
    return audio.astype(np.float32), -origin, rate, info


def _predict_pitch(stage: Stage, bank: Voicebank, symbols: list, durations: np.ndarray, flat_notes: list,
                   note_groups: list, origin: float, n_frames: int, mix: dict, settings: dict, lang: str) -> np.ndarray:
    frame_s = stage.frame_s
    feeds = {"tokens": stage.token_ids(symbols), "languages": stage.language_ids(symbols), "ph_dur": durations[None, :]}
    encoder_out = stage.run("linguistic", feeds)[0]
    # note sequence with rests: head padding, gaps between notes, tail padding
    midi, rest, seconds = [flat_notes[0][2]], [True], [flat_notes[0][0] - origin]
    cursor = flat_notes[0][0]
    for start, end, pitch in flat_notes:
        if start - cursor > 1e-6:
            midi.append(pitch); rest.append(True); seconds.append(start - cursor)
        midi.append(pitch); rest.append(False); seconds.append(end - start)
        cursor = end
    midi.append(flat_notes[-1][2]); rest.append(True); seconds.append(TAIL_FRAMES * frame_s)
    edges = np.round(np.cumsum([0.0] + seconds) / frame_s).astype(int)
    note_dur = np.maximum(np.diff(edges), 0)
    note_dur[-1] += n_frames - int(note_dur.sum())
    if note_dur[-1] < 0:
        raise DiffSingerError("note and phoneme timelines disagree in length")
    feeds = {"encoder_out": encoder_out, "ph_dur": durations[None, :],
             "note_midi": np.array([midi], dtype=np.float32), "note_rest": np.array([rest], dtype=bool),
             "note_dur": note_dur[None, :].astype(np.int64),
             "pitch": np.full((1, n_frames), 60.0, dtype=np.float32), "retake": np.ones((1, n_frames), dtype=bool),
             "expr": np.full((1, n_frames), float(settings["expr"]), dtype=np.float32),
             **stage.steps_feed(settings["pitch_steps"])}
    embed = stage.embed(mix)
    if embed is not None:
        feeds["spk_embed"] = np.tile(embed, (1, n_frames, 1)).astype(np.float32)
    return stage.run("pitch", feeds)[0].squeeze(0).astype(np.float64)


def _predict_variance(stage: Stage, symbols: list, durations: np.ndarray, midi: np.ndarray, mix: dict, settings: dict) -> dict:
    n_frames = int(durations.sum())
    feeds = {"tokens": stage.token_ids(symbols), "languages": stage.language_ids(symbols), "ph_dur": durations[None, :]}
    encoder_out = stage.run("linguistic", feeds)[0]
    names = [name for name in ("energy", "breathiness", "voicing", "tension") if stage.config.get(f"predict_{name}")]
    feeds = {"encoder_out": encoder_out, "ph_dur": durations[None, :], "pitch": midi.astype(np.float32)[None, :],
             "retake": np.ones((1, n_frames, len(names)), dtype=bool), **stage.steps_feed(settings["variance_steps"])}
    for name in names:
        feeds[name] = np.zeros((1, n_frames), dtype=np.float32)
    embed = stage.embed(mix)
    if embed is not None:
        feeds["spk_embed"] = np.tile(embed, (1, n_frames, 1)).astype(np.float32)
    session = stage.session("variance")
    outputs = stage.run("variance", feeds)
    return {out.name.replace("_pred", ""): value.squeeze(0) for out, value in zip(session.get_outputs(), outputs)}


# ---------------------------------------------------------------- track level

def _settings(track: dict) -> dict:
    config = dict(track.get("vocal") or {})
    if not config.get("voice"):
        raise DiffSingerError(f"{track['name']}: engine diffsinger needs 'voice': a voicebank folder, archive or link "
                              f"supplied by the user")
    settings = {**DEFAULTS, **{k: v for k, v in config.items() if k in DEFAULTS or k == "style"}}
    settings["voice"] = config["voice"]
    return settings


def render_lines(project: dict, track: dict, lines: list, n: int, build_dir: str, variant: dict | None = None) -> tuple:
    """All lines of a DiffSinger vocal track as one mono stem at the mix rate. Returns (audio, per-line diagnostics)."""
    from scipy import signal
    variant = variant or {}
    settings = _settings(track)
    bank = voicebank(settings["voice"])
    lang = settings["lang"]
    spb = 60.0 / project["meta"]["bpm"]
    cache_dir = os.path.join(build_dir, "vocal_cache")
    os.makedirs(cache_dir, exist_ok=True)
    out = np.zeros(n, dtype=np.float32)
    report = []
    for index, line in enumerate(lines):
        notes = [(o * spb, d * spb, m + variant.get("transpose", {}).get((index, k), 0), t)
                 for k, (o, d, m, t) in enumerate(line["notes"])]
        words = line_words(bank, line, lang)
        groups, word_cut = syllable_groups(bank, words, lang)
        if len(groups) - 1 != len(singing.note_groups(notes)):
            raise DiffSingerError(f"{line['text']!r} is sung in {len(groups) - 1} syllables ({_spelled(groups)}) but the line has "
                                  f"{len(singing.note_groups(notes))} notes")
        seed = variant.get("seed", 0)
        key = hashlib.sha1(json.dumps([CACHE_VERSION, bank.root, settings, groups, notes, seed, variant.get("style")], sort_keys=True,
                                      default=str).encode()).hexdigest()[:20]
        path = os.path.join(cache_dir, f"ds_{key}.npz")
        if os.path.exists(path):
            data = np.load(path)
            audio, pre_roll, rate, lead = data["audio"], float(data["pre_roll"]), int(data["rate"]), float(data["lead"])
        else:
            local = {**settings, "seed": seed, "_shift": variant.get("detune_semitones", 0.0)}
            if variant.get("style"):                   # a double is another take: other noise, slightly other timbre
                local["style"] = {**local.get("style", {}), **variant["style"]}
                local["gender"] = float(local["gender"]) + 0.5 * float(variant["style"].get("formant", 0.0))
            audio, pre_roll, rate, info = sing_phrase(bank, groups, word_cut, notes, local, lang)
            lead = info["lead_s"]
            np.savez(path, audio=audio, pre_roll=pre_roll, rate=rate, lead=lead)
        if rate != SR:
            divisor = np.gcd(SR, rate)
            audio = signal.resample_poly(audio, SR // divisor, rate // divisor).astype(np.float32)
        at = int((line["start"] * spb - pre_roll + variant.get("delay_ms", 0.0) / 1000.0) * SR)
        if at < 0:
            audio, at = audio[-at:], 0
        stop = min(n, at + len(audio))
        if stop > at:
            out[at:stop] += audio[:stop - at]
        pitches = [m for _, _, m, _ in notes]
        report.append({"text": line["text"], "phones": " ".join(s for g in groups for s in g),
                       "syllables": [" ".join(x.split("/")[-1] for x in g) for g in groups[1:]], "start_s": round(line["start"] * spb, 3),
                       "pre_roll_s": round(lead + 0.02, 3), "lowest": theory.midi_to_name(min(pitches)),
                       "highest": theory.midi_to_name(max(pitches))})
    return out, report


def _spelled(groups: list) -> str:
    """Syllables for messages. Each group starts at its vowel; the consonants that open the next syllable close it."""
    bare = [" ".join(symbol.split("/")[-1] for symbol in group) for group in groups]
    return (f"({bare[0]}) " if bare[0] else "") + " | ".join(bare[1:]) + "  [each group starts at its vowel]"


def lint_lines(project: dict, track: dict) -> list:
    issues = []

    def issue(level, code, where, message):
        issues.append({"level": level, "code": code, "where": where, "message": message})

    try:
        settings = _settings(track)
        bank = voicebank(settings["voice"])
    except (DiffSingerError, OSError) as error:
        issue("error", "vocal.engine", track["name"], str(error))
        return issues
    lang = settings["lang"]
    spb = 60.0 / project["meta"]["bpm"]
    for number, line in enumerate(track.get("lines", [])):
        where = f"{track['name']} line {number + 1} {line['text']!r}"
        try:
            groups, _cuts = syllable_groups(bank, line_words(bank, line, lang), lang)
        except DiffSingerError as error:
            issue("error", "lyrics.pronunciation", where, str(error))
            continue
        count = len(singing.note_groups([(o * spb, d * spb, m, t) for o, d, m, t in line["notes"]]))
        if len(groups) - 1 != count:
            issue("error", "lyrics.syllables", where,
                  f"sung in {len(groups) - 1} syllables but {count} notes. Syllables: {_spelled(groups)}")
    return issues
