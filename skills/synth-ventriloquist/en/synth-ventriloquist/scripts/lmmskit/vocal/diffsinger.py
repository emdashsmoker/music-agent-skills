# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""DiffSinger voicebanks (OpenUtau layout) rendered directly with onnxruntime.

A voicebank is a folder the user supplies: dsconfig.yaml, phoneme and language tables, dictionaries,
speaker embeddings and ONNX models for duration, pitch, variance, acoustic features and the vocoder.
Nothing here downloads or names a voicebank; every bank comes with its own terms, which the user
must read and accept before it is used (describe() lists the licence files found in the folder).

Pipeline: words -> phonemes (bank dictionary, then a built-in English fallback) -> phoneme lengths
(duration model, then fitted so every vowel starts on its note) -> pitch curve (the bank's pitch
model) -> breathiness / voicing / tension (variance model) -> mel spectrogram (acoustic model) ->
waveform (vocoder).
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass

import numpy as np

from .phones import merge_tokens, to_arpabet
from .singing import LEGATO_GAP_S, OUTPUT_SR, Style, SungLine, SungNote, _finish

HEAD_SECONDS, TAIL_SECONDS = 0.5, 0.35
DEFAULT_STEPS = 20
SILENCE, BREATH = "SP", "AP"
VOWEL_TYPE = "vowel"
MIN_PHONE_FRAMES = 1
EDGE_GUARD_S = 0.03
MAX_CONSONANT_SHARE = 0.65                     # of a note: how much its closing consonants may take
LICENCE_PATTERNS = ("*readme*", "*license*", "*licence*", "*terms*", "*tos*", "*credit*", "character.txt")
ARPABET_FALLBACKS = {"ax": ["ah"], "dx": ["d", "t"], "q": ["cl", "gs"], "ll": ["l"], "mm": ["m"], "nn": ["n"]}
WEAK_VOWELS = ("er", "ax", "axr")
CHARACTER_LANGUAGES = ("ko", "ja", "zh")       # languages written without spaces: one written character per note


def _yaml(path: str) -> dict:
    import yaml
    with open(path, encoding="utf-8-sig") as handle:
        return yaml.safe_load(handle) or {}


def find_root(path: str) -> str:
    """Folder that holds the top-level dsconfig.yaml (the bank may sit one or two levels inside what was given)."""
    path = os.path.abspath(os.path.expanduser(path))
    candidates = [path] + sorted(glob.glob(os.path.join(path, "*")) + glob.glob(os.path.join(path, "*", "*")))
    for candidate in candidates:
        config = os.path.join(candidate, "dsconfig.yaml")
        if os.path.isdir(candidate) and os.path.exists(config) and "acoustic" in _yaml(config):
            return candidate
    raise FileNotFoundError(f"no DiffSinger voicebank (dsconfig.yaml with an 'acoustic' entry) under {path}")


@dataclass
class _Stage:
    folder: str
    config: dict
    phonemes: dict
    languages: dict
    speakers: dict[str, np.ndarray]


class Voicebank:
    def __init__(self, path: str):
        import onnxruntime
        self.root = find_root(path)
        self._ort = onnxruntime
        self._sessions: dict[str, object] = {}
        self.acoustic = self._stage(self.root)
        self.duration = self._stage(os.path.join(self.root, "dsdur"))
        self.pitch = self._stage(os.path.join(self.root, "dspitch")) if os.path.exists(os.path.join(self.root, "dspitch", "dsconfig.yaml")) else None
        self.variance = self._stage(os.path.join(self.root, "dsvariance")) if os.path.exists(os.path.join(self.root, "dsvariance", "dsconfig.yaml")) else None
        self.vocoder_folder, self.vocoder_config = self._find_vocoder()
        self.sample_rate = int(self.acoustic.config.get("sample_rate", 44100))
        self.hop = int(self.acoustic.config.get("hop_size", 512))
        self.frame_s = self.hop / self.sample_rate
        self._dictionaries: dict[str, tuple[dict, dict]] = {}

    # -- loading ----------------------------------------------------------------------------------
    def _stage(self, folder: str) -> _Stage:
        config = _yaml(os.path.join(folder, "dsconfig.yaml"))

        def resolve(name):
            return os.path.normpath(os.path.join(folder, name))
        phoneme_file = resolve(config.get("phonemes", "phonemes.json"))
        if phoneme_file.endswith(".json"):
            with open(phoneme_file, encoding="utf-8") as handle:
                phonemes = json.load(handle)
        else:                                       # older banks: one phoneme per line, index = line number
            with open(phoneme_file, encoding="utf-8") as handle:
                phonemes = {line.strip(): index for index, line in enumerate(handle) if line.strip()}
        languages = {}
        if config.get("use_lang_id") and config.get("languages"):
            with open(resolve(config["languages"]), encoding="utf-8") as handle:
                languages = json.load(handle)
        speakers = {}
        for entry in config.get("speakers", []):
            file = resolve(entry if entry.endswith(".emb") else entry + ".emb")
            speakers[os.path.basename(entry).removesuffix(".emb")] = np.fromfile(file, dtype=np.float32)
        return _Stage(folder, config, phonemes, languages, speakers)

    def _find_vocoder(self) -> tuple[str, dict]:
        name = str(self.acoustic.config.get("vocoder", "dsvocoder"))
        for folder in (os.path.join(self.root, name), os.path.join(self.root, "dsvocoder")):
            if os.path.exists(os.path.join(folder, "vocoder.yaml")):
                return folder, _yaml(os.path.join(folder, "vocoder.yaml"))
        raise FileNotFoundError(f"the voicebank names vocoder '{name}' but ships no vocoder.yaml; place the vocoder under "
                                f"{os.path.join(self.root, 'dsvocoder')} (see the bank's own instructions)")

    def _session(self, stage: _Stage | None, key: str, path: str | None = None, seed: int | None = None):
        """ONNX session. Models without sampling noise are created once and kept.

        The pitch, variance and acoustic models draw diffusion noise from a random stream that onnxruntime fixes
        when a session is created and advances on every run. Passing a seed builds a fresh session, so a line
        rendered again (alone or inside a long song) gets the same noise and therefore the same audio.
        """
        file = path or os.path.normpath(os.path.join(stage.folder, stage.config[key]))
        if seed is None and file in self._sessions:
            return self._sessions[file]
        options = self._ort.SessionOptions()
        options.intra_op_num_threads = max(1, os.cpu_count() or 2)
        options.log_severity_level = 3
        if seed is not None:
            self._ort.set_seed(seed)
            return self._ort.InferenceSession(file, options, providers=["CPUExecutionProvider"])
        self._sessions[file] = self._ort.InferenceSession(file, options, providers=["CPUExecutionProvider"])
        return self._sessions[file]

    # -- description ------------------------------------------------------------------------------
    def describe(self) -> dict:
        """What the bank offers and which documents state its terms (to be read with the user before use)."""
        documents = []
        for pattern in LICENCE_PATTERNS:
            for path in glob.glob(os.path.join(self.root, "**", pattern), recursive=True):
                if os.path.isfile(path) and path.lower().endswith((".txt", ".md", ".yaml", ".pdf", ".html")) and "dsdict" not in path:
                    documents.append(os.path.relpath(path, self.root))
        character = {}
        if os.path.exists(os.path.join(self.root, "character.yaml")):
            character = _yaml(os.path.join(self.root, "character.yaml"))
        return {"root": self.root, "name": character.get("name") or os.path.basename(self.root),
                "languages": sorted(self.acoustic.languages) or ["(single language)"],
                "voices": sorted(self.acoustic.speakers) or ["(default)"], "sample_rate": self.sample_rate,
                "has_pitch_model": self.pitch is not None, "has_variance_model": self.variance is not None,
                "vocoder": self.vocoder_config.get("name"), "phoneme_count": len(self.acoustic.phonemes),
                "terms_documents": sorted(set(documents))}

    # -- words to phonemes ------------------------------------------------------------------------
    def _dictionary(self, lang: str) -> tuple[dict, dict]:
        """(word -> phonemes, phoneme -> type) from dsdict-<lang>.yaml, else the bank's generic dsdict.yaml."""
        if lang not in self._dictionaries:
            entries, kinds = {}, {}
            for name in (f"dsdict-{lang}.yaml", "dsdict.yaml"):
                matches = glob.glob(os.path.join(self.duration.folder, name)) or glob.glob(os.path.join(self.duration.folder, f"dsdict-{lang}*.yaml"))
                if not matches:
                    continue
                document = _yaml(matches[0])
                for entry in document.get("entries") or []:
                    entries.setdefault(str(entry["grapheme"]).lower(), [str(p) for p in entry["phonemes"]])
                for symbol in document.get("symbols") or []:
                    kinds.setdefault(str(symbol["symbol"]), symbol.get("type", ""))
                if entries:
                    break
            self._dictionaries[lang] = (entries, kinds)
        return self._dictionaries[lang]

    def _known(self, phoneme: str, lang: str) -> str | None:
        table = self.acoustic.phonemes
        for candidate in (f"{lang}/{phoneme}", phoneme):
            if candidate in table:
                return candidate
        return None

    def _fallback_english(self, word: str) -> list[str] | None:
        """Pronounce an out-of-dictionary English word with espeak and translate to the bank's ARPAbet symbols."""
        from kokoro_onnx.tokenizer import Tokenizer
        if not hasattr(self, "_g2p"):
            self._g2p = Tokenizer()
        ipa = self._g2p.phonemize(word, "en-us")
        symbols = list(ipa)
        result = []
        for arpabet, _, _ in to_arpabet(merge_tokens(symbols, [0.0] * len(symbols), [0.0] * len(symbols))):
            match = next((self._known(option, "en") for option in [arpabet] + ARPABET_FALLBACKS.get(arpabet, []) if self._known(option, "en")), None)
            if match is None:
                return None
            result.append(match)
        return result or None

    def phonemize(self, text: str, lang: str = "en") -> list[list[str]]:
        """Phonemes per word. Languages written without spaces are looked up one written character at a time."""
        entries, _ = self._dictionary(lang)
        words = re.findall(r"[^\s,.!?;:\"()]+", text.lower())
        result = []
        for word in words:
            if word in entries:
                result.append([self._known(p.split("/")[-1], lang) or p for p in entries[word]])
                continue
            if lang in CHARACTER_LANGUAGES and all(character in entries for character in word):
                result += [[self._known(p.split("/")[-1], lang) or p for p in entries[character]] for character in word]
                continue
            fallback = self._fallback_english(word) if lang == "en" else None
            if fallback is None:
                raise KeyError(f"the voicebank's {lang} dictionary has no entry for '{word}'; respell it or choose another word")
            result.append(fallback)
        return result

    def is_vowel(self, phoneme: str, lang: str) -> bool:
        _, kinds = self._dictionary(lang)
        return kinds.get(phoneme, kinds.get(phoneme.split("/")[-1], "")) == VOWEL_TYPE

    def syllables(self, text: str, lang: str = "en", wanted: int | None = None) -> list[dict]:
        """One entry per sung syllable: {'onset': [...], 'vowel': str, 'coda': [...], 'word': index}.

        With `wanted`, a weak vowel that directly follows another vowel in the same word (fire, hour, tower) is
        folded into the note before it until the count matches.
        """
        result = self._split_syllables(text, lang)
        while wanted is not None and len(result) > wanted:
            for index in range(1, len(result)):
                previous, current = result[index - 1], result[index]
                weak = (current["vowel"] or "").split("/")[-1] in WEAK_VOWELS
                if weak and not current["onset"] and not previous["coda"] and previous["word"] == current["word"]:
                    previous["coda"] = [current["vowel"]] + current["coda"]
                    result.pop(index)
                    break
            else:
                break
        return result

    def _split_syllables(self, text: str, lang: str) -> list[dict]:
        result = []
        for word_index, phonemes in enumerate(self.phonemize(text, lang)):
            vowels = [i for i, p in enumerate(phonemes) if self.is_vowel(p, lang)]
            if not vowels:                               # vowel-less word: hang it on the neighbouring syllable
                if result:
                    result[-1]["coda"] += phonemes
                else:
                    result.append({"onset": phonemes, "vowel": None, "coda": [], "word": word_index})
                continue
            for n, position in enumerate(vowels):
                start = vowels[n - 1] + 1 if n else 0
                between = phonemes[start:position]
                if n and len(between) > 1:               # a cluster gives its first consonant to the previous syllable
                    result[-1]["coda"].append(between[0])
                    between = between[1:]
                onset = between
                if result and result[-1]["vowel"] is None:
                    onset = result.pop()["onset"] + onset
                result.append({"onset": onset, "vowel": phonemes[position], "coda": [], "word": word_index})
            result[-1]["coda"] += phonemes[vowels[-1] + 1:]
        return result

    # -- rendering --------------------------------------------------------------------------------
    def _ids(self, stage: _Stage, phonemes: list[str], lang: str) -> tuple[np.ndarray, np.ndarray]:
        tokens = np.array([[stage.phonemes[p] for p in phonemes]], dtype=np.int64)
        languages = np.array([[stage.languages.get(p.split("/")[0], stage.languages.get(lang, 0)) if "/" in p else 0 for p in phonemes]], dtype=np.int64)
        return tokens, languages

    def _speaker(self, stage: _Stage, voice: str | None, length: int) -> np.ndarray | None:
        if not stage.speakers:
            return None
        name = voice if voice in stage.speakers else next(iter(stage.speakers))
        return np.repeat(stage.speakers[name][None, None, :], length, axis=1).astype(np.float32)

    def _run(self, session, feed: dict) -> list[np.ndarray]:
        wanted = {i.name for i in session.get_inputs()}
        return session.run(None, {k: v for k, v in feed.items() if k in wanted and v is not None})

    def sing(self, text: str, groups: list[list[SungNote]], *, lang: str = "en", voice: str | None = None, style: Style | None = None,
             steps: int = DEFAULT_STEPS, gender: float = 0.0, velocity: float = 1.0, tension: float = 0.0, breathiness: float = 0.0,
             expressiveness: float = 1.0, own_pitch: bool = True) -> tuple[SungLine, dict]:
        """Render one line. own_pitch=True uses the bank's pitch model; False draws the curve with singing.pitch_curve.

        voice picks a speaker/colour embedding by name. gender (-1..1), velocity (0.5..2), tension and breathiness
        offsets map to the usual OpenUtau expressions. Returns the line and a small report.
        """
        style = style or Style()
        colours = sorted(self.acoustic.speakers)
        if voice and voice not in colours:
            raise ValueError(f"this voicebank has no voice colour '{voice}'; it offers {colours or 'a single voice'}")
        syllables = self.syllables(text, lang, len(groups))
        if len(syllables) != len(groups):
            spoken = " | ".join(" ".join(s["onset"] + [s["vowel"] or ""] + s["coda"]) for s in syllables)
            raise ValueError(f"'{text}' has {len(syllables)} sung syllables in this voicebank ({spoken}) but the melody has "
                             f"{len(groups)}. Add or remove notes, tie notes with '~', or reword the line.")
        phonemes, word_div, word_frames, phone_note, notes, vowel_positions = self._layout(syllables, groups)
        frames_total = int(sum(word_frames))
        tokens, languages = self._ids(self.duration, phonemes, lang)
        word_div_array = np.array([word_div], dtype=np.int64)
        word_dur_array = np.array([word_frames], dtype=np.int64)
        note_midi = np.array([n["midi"] for n in notes], dtype=np.float32)
        ph_midi = np.array([[int(round(note_midi[phone_note[i]])) for i in range(len(phonemes))]], dtype=np.int64)
        linguistic = self._session(self.duration, "linguistic")
        encoder_out, x_masks = self._run(linguistic, {"tokens": tokens, "languages": languages, "word_div": word_div_array, "word_dur": word_dur_array})
        predicted = self._run(self._session(self.duration, "dur"), {
            "encoder_out": encoder_out, "x_masks": x_masks, "ph_midi": ph_midi,
            "spk_embed": self._speaker(self.duration, voice, len(phonemes))})[0][0]
        ph_dur = self._fit_durations(np.maximum(predicted, MIN_PHONE_FRAMES), word_div, word_frames)
        ph_dur_array = ph_dur[None].astype(np.int64)

        note_dur = np.array([[n["frames"] for n in notes]], dtype=np.int64)
        note_rest = np.array([[n["rest"] for n in notes]], dtype=bool)
        base_pitch = np.repeat(note_midi, note_dur[0]).astype(np.float32)[None]
        if own_pitch and self.pitch is not None:
            tokens_p, languages_p = self._ids(self.pitch, phonemes, lang)
            encoder_p = self._run(self._session(self.pitch, "linguistic"), {"tokens": tokens_p, "languages": languages_p, "ph_dur": ph_dur_array})[0]
            pitch = self._run(self._session(self.pitch, "pitch", seed=style.seed), {
                "encoder_out": encoder_p, "ph_dur": ph_dur_array, "note_midi": note_midi[None], "note_rest": note_rest, "note_dur": note_dur,
                "pitch": base_pitch, "expr": np.full((1, frames_total), expressiveness, dtype=np.float32),
                "retake": np.ones((1, frames_total), dtype=bool), "spk_embed": self._speaker(self.pitch, voice, frames_total),
                "steps": np.array(steps, dtype=np.int64), "speedup": np.array(max(1, 1000 // max(steps, 1)), dtype=np.int64)})[0]
        else:
            from .singing import FRAME_S, pitch_curve
            fine = pitch_curve(groups, HEAD_SECONDS, int(frames_total * self.frame_s / FRAME_S) + 2, style)
            hz = np.interp(np.arange(frames_total) * self.frame_s, np.arange(len(fine)) * FRAME_S, fine)
            pitch = (69 + 12 * np.log2(hz / 440.0)).astype(np.float32)[None]
        f0 = (440.0 * 2.0 ** ((pitch - 69.0) / 12.0)).astype(np.float32)

        zeros = np.zeros((1, frames_total), dtype=np.float32)
        curves = {"breathiness": zeros, "voicing": zeros, "tension": zeros, "energy": zeros}
        if self.variance is not None:
            tokens_v, languages_v = self._ids(self.variance, phonemes, lang)
            session = self._session(self.variance, "variance", seed=style.seed)
            names = [o.name.removesuffix("_pred") for o in session.get_outputs()]
            encoder_v = self._run(self._session(self.variance, "linguistic"), {"tokens": tokens_v, "languages": languages_v, "ph_dur": ph_dur_array})[0]
            outputs = self._run(session, {
                "encoder_out": encoder_v, "ph_dur": ph_dur_array, "pitch": pitch.astype(np.float32), **{name: zeros for name in names},
                "retake": np.ones((1, frames_total, len(names)), dtype=bool), "spk_embed": self._speaker(self.variance, voice, frames_total),
                "steps": np.array(steps, dtype=np.int64), "speedup": np.array(max(1, 1000 // max(steps, 1)), dtype=np.int64)})
            curves.update(dict(zip(names, outputs)))
        tokens_a, languages_a = self._ids(self.acoustic, phonemes, lang)
        acoustic = self._session(self.acoustic, "acoustic", seed=style.seed)
        mel = self._run(acoustic, {
            "tokens": tokens_a, "languages": languages_a, "durations": ph_dur_array, "f0": f0,
            "breathiness": (curves["breathiness"] + breathiness).astype(np.float32), "voicing": curves["voicing"].astype(np.float32),
            "tension": (curves["tension"] + tension).astype(np.float32), "energy": curves["energy"].astype(np.float32),
            "gender": np.full((1, frames_total), gender, dtype=np.float32), "velocity": np.full((1, frames_total), velocity, dtype=np.float32),
            "spk_embed": self._speaker(self.acoustic, voice, frames_total), "steps": np.array(steps, dtype=np.int64),
            "speedup": np.array(max(1, 1000 // max(steps, 1)), dtype=np.int64),
            "depth": np.array(float(self.acoustic.config.get("max_depth", 0.6)), dtype=np.float32)})[0]
        vocoder = self._session(None, "", os.path.join(self.vocoder_folder, self.vocoder_config["model"]))
        audio = self._run(vocoder, {"mel": mel.astype(np.float32), "f0": f0})[0][0].astype(np.float64)

        edges = np.concatenate([[0], np.cumsum(ph_dur)]) * self.frame_s
        layout = []
        for syllable, group, position in zip(syllables, groups, vowel_positions):
            coda_end = position + 1 + len(syllable["coda"])
            layout.append({"text": " ".join(syllable["onset"] + [syllable["vowel"]] + syllable["coda"]), "vowel_start": float(edges[position]),
                           "vowel_end": float(edges[position + 1]), "end": float(edges[coda_end]), "legato": True,
                           "pitches": [n.pitch for n in group], "squeezed": False})
        # Models sometimes leave a faint blip in the padding before the first and after the last sound: clear it.
        first_sound = float(edges[1]) - EDGE_GUARD_S
        last_sound = float(edges[len(phonemes) - 1]) + EDGE_GUARD_S if phonemes[-1] == SILENCE else float(edges[-1])
        audio[:max(0, int(first_sound * self.sample_rate))] = 0.0
        audio[int(last_sound * self.sample_rate):] = 0.0
        line = SungLine(_finish(audio, self.sample_rate), HEAD_SECONDS, layout, f0[0], [n for g in groups for n in g])
        report = {"text": text, "engine": "diffsinger", "phonemes": " ".join(phonemes), "frames": frames_total, "steps": steps,
                  "voice": voice or next(iter(self.acoustic.speakers), None)}
        return line, report

    def _layout(self, syllables: list[dict], groups: list[list[SungNote]]):
        """Phonemes grouped the way the models expect: a 'word' starts at a vowel and runs up to the next vowel.

        Returns (phonemes, phonemes per word, frames per word, note index per phoneme, notes, index of each syllable's vowel).
        Notes are {'midi', 'frames', 'rest'} and cover the same frames as the words.
        """
        def frames_of(seconds: float) -> int:
            return int(round(seconds / self.frame_s))
        head = frames_of(HEAD_SECONDS)
        phonemes, word_div, word_frames, phone_note, notes = [SILENCE] + list(syllables[0]["onset"]), [], [], [], []
        word_div.append(len(phonemes))
        word_frames.append(head)
        notes.append({"midi": groups[0][0].pitch, "frames": head, "rest": True})
        phone_note += [0] * len(phonemes)
        vowel_positions = []
        position = head                                               # frame where the current vowel starts
        for index, (syllable, group) in enumerate(zip(syllables, groups)):
            start = group[0].start
            end = group[-1].start + group[-1].duration
            is_last = index + 1 == len(syllables)
            next_start = None if is_last else groups[index + 1][0].start
            next_onset = [] if is_last else syllables[index + 1]["onset"]
            rest_after = is_last or next_start - end > LEGATO_GAP_S
            first_note = len(notes)
            cursor = position
            for n, note in enumerate(group):                          # one note entry per pitch (slurs share the syllable)
                note_end = head + frames_of(note.start + note.duration) if n + 1 < len(group) or rest_after else head + frames_of(next_start)
                note_end = max(note_end, cursor + 1)
                notes.append({"midi": note.pitch, "frames": note_end - cursor, "rest": False})
                cursor = note_end
            word = [syllable["vowel"]] + list(syllable["coda"]) + ([] if rest_after else list(next_onset))
            vowel_positions.append(len(phonemes))
            phonemes += word
            phone_note += [first_note] * len(word)
            word_div.append(len(word))
            word_frames.append(cursor - position)
            position = cursor
            if rest_after:
                length = (frames_of(TAIL_SECONDS) if is_last else head + frames_of(next_start) - position)
                length = max(length, 2)
                word = [SILENCE] + list(next_onset)
                phonemes += word
                phone_note += [len(notes)] * len(word)
                word_div.append(len(word))
                word_frames.append(length)
                notes.append({"midi": group[-1].pitch if is_last else groups[index + 1][0].pitch, "frames": length, "rest": True})
                position += length
        return phonemes, word_div, word_frames, phone_note, notes, vowel_positions

    @staticmethod
    def _fit_durations(predicted: np.ndarray, word_div: list[int], word_frames: list[int]) -> np.ndarray:
        """Scale the predicted phoneme lengths inside each word so the word fills its frames exactly.

        The first phoneme of a word (its vowel, or a silence) absorbs the rounding and keeps at least a third of the
        word, so closing consonants cannot crowd out a short note.
        """
        result = np.zeros(len(predicted), dtype=np.int64)
        cursor = 0
        for count, frames in zip(word_div, word_frames):
            piece = predicted[cursor:cursor + count].astype(float)
            if count == 1:
                result[cursor] = frames
            else:
                tail = piece[1:]
                room = max(count - 1, int(frames * MAX_CONSONANT_SHARE))
                scale = min(1.0, room / max(tail.sum(), 1e-6))
                fitted = np.maximum(MIN_PHONE_FRAMES, np.round(tail * scale)).astype(np.int64)
                while fitted.sum() > max(frames - 1, count - 1) and fitted.max() > 1:
                    fitted[np.argmax(fitted)] -= 1
                result[cursor + 1:cursor + count] = fitted
                result[cursor] = max(1, frames - fitted.sum())
            cursor += count
        return result


_banks: dict[str, Voicebank] = {}


def voicebank(path: str) -> Voicebank:
    key = os.path.abspath(os.path.expanduser(path))
    if key not in _banks:
        _banks[key] = Voicebank(path)
    return _banks[key]
