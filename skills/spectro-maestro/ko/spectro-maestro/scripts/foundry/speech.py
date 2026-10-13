# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Speech engines used as singing-voice sources: Kokoro and Piper.

Each backend turns a line of text into a `Unit`: audio plus the time span of every phone.
The engines report phone times late and unevenly, so `align_unit` measures the real positions
from the audio itself (voicing, sibilance, silence) and moves the boundaries there.
Models are fetched from their public hosts on first use and kept in the models directory."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field

import numpy as np

from . import phonetics, settings
from .phonetics import Phone

ENGINE_SEED = 20240229          # fixed seed for every stochastic model op: same text, same audio
KOKORO_REPO = "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped/resolve/main"
KOKORO_SR, KOKORO_FRAME = 24000, 600
PIPER_REPO = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
ANALYSIS_FRAME_S = 0.005
LAG_SEARCH_MS = (-160, 60)
SNAP_WINDOW_S = 0.05            # how far a boundary may move to meet the acoustic event it predicts
SIBILANT_SHARE = 0.35           # share of energy above 4 kHz that marks a sibilant frame
SILENCE_DB = -45.0
KOKORO_LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "p": "pt-br",
               "j": "ja", "z": "cmn"}


def models_dir() -> str:
    return settings.models_dir()


def fetch(url: str, path: str) -> str:
    """Download once. Partial downloads never leave a file with the final name.
    Without network access the error names the file, so it can be put in place by hand."""
    from .singing import VocalError
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    by_hand = f"To provide it by hand, download {url} elsewhere and save it as {path}"
    if settings.get("offline"):
        raise VocalError(f"a model file is missing and downloads are switched off (setting 'offline'). {by_hand}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"[models] downloading {url} -> {path}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": settings.APP})
    try:
        with urllib.request.urlopen(request, timeout=settings.get("download_timeout_s")) as response, open(path + ".part", "wb") as handle:
            while True:
                block = response.read(1 << 20)
                if not block:
                    break
                handle.write(block)
    except OSError as error:                             # no network, blocked host, proxy refusal, time-out
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        raise VocalError(f"download failed ({error}). {by_hand}") from error
    os.replace(path + ".part", path)
    return path


def _session(path: str):
    import onnxruntime as ort
    ort.set_seed(ENGINE_SEED)
    options = ort.SessionOptions()
    options.log_severity_level = 3
    return ort.InferenceSession(path, options, providers=["CPUExecutionProvider"])


@dataclass
class Unit:
    """One spoken line: audio and the timed phones in it."""
    audio: np.ndarray
    sr: int
    phones: list
    text: str = ""
    info: dict = field(default_factory=dict)

    def save(self, path: str) -> None:
        np.savez(path, audio=self.audio, sr=self.sr, text=self.text, info=json.dumps(self.info),
                 symbols=np.array([p.symbol for p in self.phones]), starts=[p.start for p in self.phones],
                 ends=[p.end for p in self.phones], kinds=np.array([p.kind for p in self.phones]),
                 stress=[p.stress for p in self.phones], words=[p.word for p in self.phones])

    @staticmethod
    def load(path: str) -> "Unit":
        data = np.load(path, allow_pickle=False)
        phones = [Phone(str(s), float(a), float(b), str(k), int(st), int(w)) for s, a, b, k, st, w in
                  zip(data["symbols"], data["starts"], data["ends"], data["kinds"], data["stress"], data["words"])]
        return Unit(data["audio"], int(data["sr"]), phones, str(data["text"]), json.loads(str(data["info"])))


def share_word_gaps(phones: list, to_previous: float) -> list:
    """The time an engine reports for the space between two words is not silence: the neighbouring sounds
    run through it. Hand `to_previous` of it to the sound before and the rest to the sound after, and keep
    a zero-length word break. Real pauses (punctuation, the line's ends) are left alone."""
    for before, gap, after in zip(phones, phones[1:], phones[2:]):
        if gap.symbol == " " and before.kind != "pause" and after.kind != "pause":
            cut = gap.start + to_previous * (gap.end - gap.start)
            before.end = gap.start = gap.end = after.start = cut
    return phones


class KokoroBackend:
    """Kokoro-82M (Apache-2.0) through its ONNX export that also returns per-token durations."""
    engine = "kokoro"
    WORD_GAP_TO_PREVIOUS = 0.5      # measured on sibilant landmarks: both neighbours spread into the gap

    def __init__(self, voice: str = "af_heart", lang: str | None = None):
        root = os.path.join(models_dir(), "kokoro")
        self.voice = voice
        self.lang = lang or KOKORO_LANG.get(voice[0], "en-us")
        self.sr = KOKORO_SR
        self.session = _session(fetch(f"{KOKORO_REPO}/onnx/model.onnx", os.path.join(root, "onnx", "model.onnx")))
        style_path = fetch(f"{KOKORO_REPO}/voices/{voice}.bin", os.path.join(root, "voices", f"{voice}.bin"))
        self.styles = np.fromfile(style_path, dtype=np.float32).reshape(-1, 1, 256)
        from kokoro_onnx.tokenizer import Tokenizer
        self.tokenizer = Tokenizer()

    def phonemize(self, text: str) -> str:
        return self.tokenizer.phonemize(text, self.lang)

    def synthesize(self, phones: str, speed: float = 1.0) -> Unit:
        ids = self.tokenizer.tokenize(phones)
        if not ids:
            raise ValueError(f"nothing to say in {phones!r}")
        audio, durations = self.session.run(None, {
            "input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
            "style": self.styles[min(len(ids), len(self.styles) - 1)],
            "speed": np.array([speed], dtype=np.float32)})
        audio = audio.squeeze().astype(np.float32)
        frames = np.maximum(np.round(durations.squeeze()), 1.0)           # the model rounds the same way
        seconds = frames * (len(audio) / self.sr) / frames.sum()
        kept = [c for c in phones if c in self.tokenizer.vocab] if hasattr(self.tokenizer, "vocab") else list(phones)
        symbols = ["^"] + kept[:len(ids)] + ["$"]
        timed = share_word_gaps(phonetics.phones_from_tokens(symbols, list(seconds)), self.WORD_GAP_TO_PREVIOUS)
        return Unit(audio, self.sr, timed, phones, {"speed": speed})


class PiperBackend:
    """Piper VITS voices. Phone durations come from the model's own duration tensor, exposed as an extra output."""
    engine = "piper"
    WORD_GAP_TO_PREVIOUS = 0.0      # measured on sibilant landmarks: the gap belongs to the sound that follows

    def __init__(self, voice: str = "en_US-lessac-medium", lang: str | None = None):
        self.voice = voice
        model, config = self._files(voice)
        with open(config, encoding="utf-8") as handle:
            self.config = json.load(handle)
        self.lang = lang or self.config.get("espeak", {}).get("voice", "en-us")
        self.sr = int(self.config["audio"]["sample_rate"])
        self.hop = int(self.config["audio"].get("hop_length", 256))
        from piper import PiperVoice
        self.model_path = self._aligned(model)
        self.piper = PiperVoice.load(self.model_path, config_path=config)

    @staticmethod
    def _files(voice: str) -> tuple:
        if os.path.isfile(voice):                           # a model file the user supplied
            return voice, voice + ".json"
        if voice.count("-") != 2:
            from .singing import VocalError
            raise VocalError(f"Piper voice {voice!r}: expected a name like en_US-ljspeech-medium (see `studio.py voices`) "
                             "or the path of an .onnx voice file")
        locale, name, quality = voice.split("-")
        root = os.path.join(models_dir(), "piper")
        base = f"{PIPER_REPO}/{locale.split('_')[0]}/{locale}/{name}/{quality}/{voice}"
        return (fetch(base + ".onnx", os.path.join(root, voice + ".onnx")),
                fetch(base + ".onnx.json", os.path.join(root, voice + ".onnx.json")))

    @staticmethod
    def _aligned(model_path: str) -> str:
        """Copy of the model whose per-phone duration tensor (the single Ceil node) is a graph output."""
        target = model_path[:-5] + ".aligned.onnx" if not model_path.endswith(".aligned.onnx") else model_path
        if not os.path.exists(target):
            import onnx
            model = onnx.load(model_path)
            names = {out for node in model.graph.node if node.op_type == "Ceil" for out in node.output}
            if len(names) != 1:
                raise RuntimeError(f"cannot find the duration tensor in {model_path} (Ceil outputs: {sorted(names)})")
            info = onnx.helper.ValueInfoProto()
            info.name = names.pop()
            model.graph.output.append(info)
            onnx.save(model, target)
        return target

    def phonemize(self, text: str) -> str:
        return " ".join("".join(sentence) for sentence in self.piper.phonemize(text)).strip()

    def synthesize(self, phones: str, speed: float = 1.0) -> Unit:
        from piper import SynthesisConfig
        symbols = list(phones)
        ids = self.piper.phonemes_to_ids(symbols)
        # The model samples noise from a generator that lives in the session and cannot be reset,
        # so a fresh seeded session per line is the only way to get the same audio every time.
        self.piper.session = _session(self.model_path)
        config = SynthesisConfig(length_scale=self.config["inference"].get("length_scale", 1.0) / speed)
        audio, samples = self.piper.phoneme_ids_to_audio(ids, config, include_alignments=True)
        if samples is None:
            raise RuntimeError("this Piper voice returned no alignments")
        audio = np.asarray(audio, dtype=np.float32)
        id_map = self.config["phoneme_id_map"]
        pad, bos, eos = id_map["_"][0], id_map["^"][0], id_map["$"][0]
        seconds, labels, cursor = [], [], iter(symbols)
        for token, count in zip(ids, samples):
            if token == pad and labels:
                seconds[-1] += count / self.sr              # the blank after a phone belongs to that phone
            elif token == bos:
                labels.append("^"); seconds.append(count / self.sr)
            elif token == eos:
                labels.append("$"); seconds.append(count / self.sr)
            elif token != pad:
                labels.append(next(cursor, "?")); seconds.append(count / self.sr)
        scale = (len(audio) / self.sr) / max(sum(seconds), 1e-9)
        timed = share_word_gaps(phonetics.phones_from_tokens(labels, [s * scale for s in seconds]), self.WORD_GAP_TO_PREVIOUS)
        return Unit(audio, self.sr, timed, phones, {"speed": speed})


BACKENDS = {"kokoro": KokoroBackend, "piper": PiperBackend}
_loaded = {}


def backend_for(engine: str, voice: str, lang: str | None = None):
    key = (engine, voice, lang)
    if key not in _loaded:
        if engine not in BACKENDS:
            raise KeyError(f"unknown speech engine {engine!r}; use one of {sorted(BACKENDS)}")
        _loaded[key] = BACKENDS[engine](voice, lang)
    return _loaded[key]


# ---------------------------------------------------------------- measuring where the phones really are

def acoustic_frames(audio: np.ndarray, sr: int) -> dict:
    """Frame-wise evidence at 5 ms: f0 (0 = unvoiced), sibilance flag, level in dB."""
    import pyworld
    from scipy import signal
    x = audio.astype(np.float64)
    f0, _ = pyworld.harvest(x, sr, f0_floor=60.0, f0_ceil=700.0, frame_period=ANALYSIS_FRAME_S * 1000)
    hop = int(sr * ANALYSIS_FRAME_S)
    n = min(len(f0), len(x) // hop)
    high = signal.sosfilt(signal.butter(4, 4000.0, btype="highpass", fs=sr, output="sos"), x)
    power = np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12
    high_power = np.mean(high[:n * hop].reshape(n, hop) ** 2, axis=1)
    level = 10.0 * np.log10(power)
    return {"f0": f0[:n], "voiced": f0[:n] > 0, "level": level,
            "sibilant": (high_power / power > SIBILANT_SHARE) & (level > SILENCE_DB)}


def _expected(phones: list, n: int, shift_frames: int) -> tuple:
    """Predicted voicing (1 voiced, 0 unvoiced, -1 unknown) and sibilance per frame for a given shift."""
    voiced = np.full(n, -1, dtype=np.int8)
    sibilant = np.zeros(n, dtype=bool)
    for phone in phones:
        a = int(round(phone.start / ANALYSIS_FRAME_S)) + shift_frames
        b = int(round(phone.end / ANALYSIS_FRAME_S)) + shift_frames
        a, b = max(0, a), min(n, b)
        if b <= a:
            continue
        if phone.kind in ("vowel", "sonorant"):
            voiced[a:b] = 1
        elif phone.kind in ("unvoiced", "pause"):
            voiced[a:b] = 0
        if phone.symbol[0] in phonetics.SIBILANTS:
            sibilant[a:b] = True
    return voiced, sibilant


def _agreement(phones: list, frames: dict, shift_frames: int) -> float:
    """How well the shifted prediction matches the audio (0..1). The last syllable is left out:
    a speech voice often whispers it, which would drag the estimate."""
    n = len(frames["voiced"])
    voiced, sibilant = _expected(phones, n, shift_frames)
    vowels = [p for p in phones if p.kind == "vowel"]
    if len(vowels) >= 3:
        cut = max(0, int(round(vowels[-1].start / ANALYSIS_FRAME_S)) + shift_frames)
        voiced[cut:] = -1
        sibilant[cut:] = False
    known = voiced >= 0
    if not known.any():
        return 0.0
    score = float(np.mean(voiced[known] == frames["voiced"][known]))
    if sibilant.any():                                   # sibilants are sharp landmarks; unpredicted hiss is ignored
        score = (2.0 * score + float(np.mean(frames["sibilant"][sibilant]))) / 3.0
    return score


def measure_lag(phones: list, frames: dict) -> tuple:
    """Time shift (seconds) that best lays the predicted phones over the audio, with how decisive it is."""
    low, high = (int(ms / 1000 / ANALYSIS_FRAME_S) for ms in LAG_SEARCH_MS)
    shifts = np.arange(low, high + 1)
    scores = np.array([_agreement(phones, frames, int(s)) for s in shifts])
    best = int(np.argmax(scores))
    decisive = float(scores[best] - np.median(scores))
    return float(shifts[best] * ANALYSIS_FRAME_S), float(scores[best]), decisive


def landmark_offsets(phones: list, frames: dict) -> dict:
    """Direct observations of the lag: for every phone boundary where hiss or voicing should switch, the distance
    (seconds) to the nearest such switch in the audio. Hiss switches are sharp, voicing switches are blurrier."""
    voiced_on, voiced_off = _transitions(frames["voiced"])
    sib_on, sib_off = _transitions(frames["sibilant"])
    found = {"sibilant": [], "voicing": []}
    timed = [p for p in phones if p.end - p.start > 1e-6]
    reach = max(abs(ms) for ms in LAG_SEARCH_MS) / 1000.0
    for left, right in zip(timed[1:], timed[2:-1]):          # the line's own edges are padding, not events
        left_sib, right_sib = left.symbol[0] in phonetics.SIBILANTS, right.symbol[0] in phonetics.SIBILANTS
        left_voiced, right_voiced = left.kind in ("vowel", "sonorant"), right.kind in ("vowel", "sonorant")
        if left_sib != right_sib:
            name, candidates = "sibilant", (sib_on if right_sib else sib_off)
        elif left.kind in ("unvoiced", "pause") and right_voiced:
            name, candidates = "voicing", voiced_on
        elif left_voiced and right.kind in ("unvoiced", "pause"):
            name, candidates = "voicing", voiced_off
        else:
            continue
        if len(candidates):
            offset = float(candidates[np.argmin(np.abs(candidates - right.start))] - right.start)
            if abs(offset) <= reach:
                found[name].append(offset)
    return found


def _transitions(flags: np.ndarray) -> tuple:
    change = np.diff(flags.astype(np.int8))
    return (np.nonzero(change == 1)[0] + 1) * ANALYSIS_FRAME_S, (np.nonzero(change == -1)[0] + 1) * ANALYSIS_FRAME_S


def _snap(phones: list, frames: dict) -> int:
    """Move each boundary with an audible landmark (voicing or sibilance switching on or off) to that
    landmark, then shift the boundaries in between by interpolation. Returns how many were snapped."""
    voiced_on, voiced_off = _transitions(frames["voiced"])
    sib_on, sib_off = _transitions(frames["sibilant"])
    anchors = [(0.0, 0.0)]
    timed = [p for p in phones if p.end - p.start > 1e-6]      # zero-length word breaks predict no event
    for left, right in zip(timed, timed[1:]):
        boundary = right.start
        left_voiced, right_voiced = left.kind in ("vowel", "sonorant"), right.kind in ("vowel", "sonorant")
        left_sib, right_sib = left.symbol[0] in phonetics.SIBILANTS, right.symbol[0] in phonetics.SIBILANTS
        left_open = left.kind in ("unvoiced", "pause")
        right_open = right.kind in ("unvoiced", "pause")
        if left_sib != right_sib:
            candidates = sib_on if right_sib else sib_off
        elif left_open and right_voiced:
            candidates = voiced_on
        elif left_voiced and right_open:
            candidates = voiced_off
        else:
            continue
        if len(candidates) == 0:
            continue
        nearest = candidates[np.argmin(np.abs(candidates - boundary))]
        if abs(nearest - boundary) <= SNAP_WINDOW_S and nearest > anchors[-1][1] + 1e-3 and boundary > anchors[-1][0] + 1e-3:
            anchors.append((boundary, float(nearest)))
    total = phones[-1].end
    anchors.append((max(total, anchors[-1][0] + 1e-3), max(total, anchors[-1][1] + 1e-3)))
    predicted, actual = np.array(anchors).T
    for phone in phones:
        phone.start, phone.end = float(np.interp(phone.start, predicted, actual)), float(np.interp(phone.end, predicted, actual))
    return len(anchors) - 2


def align_unit(unit: Unit, frames: dict | None = None, fallback_lag: float | None = None) -> Unit:
    """Correct the unit's phone times in place from the audio. Records what was measured in unit.info."""
    frames = frames or acoustic_frames(unit.audio, unit.sr)
    lag, score, decisive = measure_lag(unit.phones, frames)
    # An engine's lag is a property of the engine, so the song's typical value is the better estimate; one line's
    # own measurement swings by tens of milliseconds whenever the line has few unvoiced sounds to hold on to.
    used = lag if fallback_lag is None else fallback_lag
    total = len(unit.audio) / unit.sr
    for phone in unit.phones:
        phone.start = float(np.clip(phone.start + used, 0.0, total))
        phone.end = float(np.clip(phone.end + used, 0.0, total))
    unit.phones[0].start, unit.phones[-1].end = 0.0, total
    snapped = _snap(unit.phones, frames)
    unit.info.update({"lag_ms": round(used * 1000), "lag_measured_ms": round(lag * 1000), "lag_decisive": round(decisive, 3),
                      "agreement": round(_agreement(unit.phones, frames, 0), 3), "snapped": snapped})
    return unit


class UnitCache:
    """Spoken lines and their analyses on disk, keyed by engine, voice, phones and speed."""

    def __init__(self, directory: str):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    def key(backend, phones: str, speed: float, tag: str = "") -> str:
        text = json.dumps([backend.engine, backend.voice, backend.lang, phones, round(speed, 3), tag])
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]

    def path(self, key: str, suffix: str) -> str:
        return os.path.join(self.dir, f"{key}.{suffix}.npz")
