# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Speech backends for the TTS singing path: Kokoro and Piper.

A backend turns a lyric line into a spoken Unit: audio plus one timed Phone per sound. Engines
report phoneme durations on their own frame grid and those times run late against the audio by an
amount that differs per engine, voice and line, so the lag is measured on every line from the
audio itself (measure_lag) instead of being assumed.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass

import numpy as np

from .. import settings
from . import world
from .phones import PAUSES, Phone, is_voiced, merge_tokens, voicing

DEFAULT_SEED = 0
DOWNLOAD_TRIES = 3
ANALYSIS_FRAME_S = world.FRAME_S
LAG_SEARCH_S = 0.15
VOICING_ENERGY_FLOOR_DB = -45.0
# The lag is the shift at which the vowels the engine reported fall on periodic frames of the audio: the thing singing
# needs, since the held note is built from the middle of each reported vowel. Matching a voiced/unvoiced pattern
# instead (the earlier rule) was fooled by loud fricatives, which the pitch tracker voices: a line opening with
# "share" got the full 150 ms and the stretch landed on the "sh". A mild preference for the usual lag keeps a flat
# objective from wandering to the edge of the search.
PERIODIC_BAND_HZ = 4000.0              # periodicity is read from WORLD's aperiodicity below this
LAG_PRIOR_S = 0.04                     # the usual lag of the Kokoro voices
LAG_PRIOR_WEIGHT = 0.5                 # periodicity given up per second of distance from the prior
VOWEL_EDGE_SHARE = 0.2                 # of a vowel's span left out at each end when its periodicity is read
# After the lag, every phone boundary that predicts an audible event (the voice or a hiss switching on or off) is
# moved onto that event when it lies within SNAP_WINDOW_S, and the boundaries between are moved in proportion.
SNAP_WINDOW_S = 0.05
SIBILANT_HZ = 4000.0
SIBILANT_SHARE = 0.35                  # share of a frame's energy above SIBILANT_HZ that marks hiss
SILENCE_DB = -45.0
SIBILANT_LANDMARKS = set("sʃɕʂʧʦʨ")    # voiceless sibilants: their hiss starts and stops sharply
WORD_GAP = " "                         # the engines' timed space between words (see share_word_gaps)
TIMING_VERSION = 6                  # part of the unit cache key: units saved with an older lag rule are re-spoken
KOKORO_SAMPLE_RATE = 24000
KOKORO_FRAME_SAMPLES = 600                      # one duration unit of the timestamped model
KOKORO_REVISION = "dd4401a9add81ac692d20e240d22ec9dda82cc29"
KOKORO_BASE = f"https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped/resolve/{KOKORO_REVISION}"
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# Voices offered at planning time. licence notes are reminders; the model card of each voice is authoritative.
VOICES = {
    "kokoro:af_heart": {"engine": "kokoro", "gender": "female", "lang": "en-us", "note": "default female; Apache-2.0 model"},
    "kokoro:af_bella": {"engine": "kokoro", "gender": "female", "lang": "en-us", "note": "Apache-2.0 model"},
    "kokoro:af_nicole": {"engine": "kokoro", "gender": "female", "lang": "en-us", "note": "breathy; Apache-2.0 model"},
    "kokoro:bf_emma": {"engine": "kokoro", "gender": "female", "lang": "en-gb", "note": "British; Apache-2.0 model"},
    "kokoro:am_michael": {"engine": "kokoro", "gender": "male", "lang": "en-us", "note": "default male; Apache-2.0 model"},
    "kokoro:am_fenrir": {"engine": "kokoro", "gender": "male", "lang": "en-us", "note": "deep; Apache-2.0 model"},
    "kokoro:am_onyx": {"engine": "kokoro", "gender": "male", "lang": "en-us", "note": "dark; Apache-2.0 model"},
    "kokoro:bm_george": {"engine": "kokoro", "gender": "male", "lang": "en-gb", "note": "British; Apache-2.0 model"},
    "piper:en_US-ljspeech-high": {"engine": "piper", "gender": "female", "lang": "en-us", "note": "natural but slightly slurred; public-domain dataset"},
    "piper:en_US-kristin-medium": {"engine": "piper", "gender": "female", "lang": "en-us", "note": "clear, tends to clip syllables short"},
    "piper:en_US-lessac-medium": {"engine": "piper", "gender": "female", "lang": "en-us", "note": "clear and mature; Blizzard 2013 licence restricts use: read the model card first"},
    "piper:en_US-bryce-medium": {"engine": "piper", "gender": "male", "lang": "en-us", "note": "stable male"},
    "piper:en_US-libritts_r-medium": {"engine": "piper", "gender": "mixed", "lang": "en-us", "note": "clear, lo-fi and peaky; suits lo-fi tracks; CC BY 4.0 dataset"},
}
DEFAULT_VOICE = {"female": "kokoro:af_heart", "male": "kokoro:am_michael"}


@dataclass
class Unit:
    """One spoken line: mono audio and its sounds with corrected time spans."""
    audio: np.ndarray
    sr: int
    phones: list[Phone]
    text: str
    lag: float = 0.0                                # how late the engine's own timing ran, in seconds
    analysis: tuple | None = None                   # WORLD (f0, envelope, aperiodicity) of the audio, made with the lag
    snapped: int = 0                                # phone boundaries moved onto an audible event (snap_boundaries)

    @property
    def phoneme_text(self) -> str:
        return "".join(p.symbol for p in self.phones)


# -- model files ----------------------------------------------------------------------------------------
def cache_dir(*parts: str) -> str:
    base = settings.cache_dir()
    path = os.path.join(base, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def _download(url: str, temporary: str) -> None:
    with urllib.request.urlopen(url, timeout=600) as response, open(temporary, "wb") as handle:
        expected = int(response.headers.get("Content-Length") or 0)
        written = 0
        while chunk := response.read(1 << 20):
            handle.write(chunk)
            written += len(chunk)
    if expected and written != expected:          # a dropped connection ends the stream early without an error
        raise OSError(f"incomplete download: {written} of {expected} bytes")


def fetch(url: str, target: str) -> str:
    """Download once (three tries). Honours HTTPS_PROXY and the system CA bundle through urllib's defaults."""
    if os.path.exists(target) and os.path.getsize(target) > 0:
        return target
    temporary = target + ".part"
    for attempt in range(DOWNLOAD_TRIES):
        try:
            _download(url, temporary)
            break
        except Exception as error:
            if os.path.exists(temporary):
                os.remove(temporary)
            if attempt == DOWNLOAD_TRIES - 1:
                raise RuntimeError(f"could not download {url}: {error}. If this host is blocked, place the file at {target} by hand "
                                   "(see references/setup.md).") from error
    os.replace(temporary, target)
    return target


def _seed_everything(seed: int) -> None:
    """ONNX graphs draw their sampling noise from onnxruntime's global generator."""
    import onnxruntime
    onnxruntime.set_seed(seed)
    np.random.seed(seed)


# -- timing correction ------------------------------------------------------------------------------------
def voicing_track(audio: np.ndarray, sr: int, f0: np.ndarray | None = None) -> np.ndarray:
    """1 where a frame is voiced and audible, else 0, on the 5 ms analysis grid."""
    if f0 is None:
        f0 = world.quick_f0(audio, sr)
    hop = int(ANALYSIS_FRAME_S * sr)
    frames = min(len(f0), len(audio) // hop)
    energy = np.array([np.sqrt(np.mean(audio[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(frames)])
    loud = 20 * np.log10(energy / (energy.max() + 1e-12)) > VOICING_ENERGY_FLOOR_DB
    return ((f0[:frames] > 0) & loud).astype(float)


def vowel_periodicity(phones: list[Phone], periodic: np.ndarray, shift: float) -> float:
    """Mean periodicity of the middles of the vowels in `phones`, read `shift` seconds earlier than reported."""
    values = []
    for phone in phones:
        if not phone.vowel:
            continue
        first, last = int((phone.start - shift) / ANALYSIS_FRAME_S), int((phone.end - shift) / ANALYSIS_FRAME_S)
        edge = max(1, int((last - first) * VOWEL_EDGE_SHARE))
        low, high = max(0, first + edge), min(len(periodic), max(last - edge, first + edge + 1))
        if high > low:
            values.append(float(periodic[low:high].mean()))
    return float(np.mean(values)) if values else 0.0


def measure_lag_by_periodicity(phones: list[Phone], aperiodicity: np.ndarray, f0: np.ndarray, sr: int) -> float | None:
    """The lag that puts the reported vowels on the most periodic frames; None when the line has no voiced vowel."""
    bins = aperiodicity.shape[1]
    low = max(1, int(bins * PERIODIC_BAND_HZ / (sr / 2)))
    periodic = np.where(f0 > 0, 1 - aperiodicity[:, :low].mean(axis=1), 0.0)
    if not any(p.vowel for p in phones) or not (periodic > 0).any():
        return None
    shifts = np.arange(-LAG_SEARCH_S, LAG_SEARCH_S + 1e-9, ANALYSIS_FRAME_S)
    scores = [vowel_periodicity(phones, periodic, shift) - LAG_PRIOR_WEIGHT * abs(shift - LAG_PRIOR_S) for shift in shifts]
    return float(shifts[int(np.argmax(scores))])


def measure_lag(audio: np.ndarray, sr: int, phones: list[Phone], f0: np.ndarray | None = None) -> float:
    """Seconds by which the reported phone times trail the audio (positive = reported too late).

    Slides the voiced/unvoiced pattern predicted from the phone classes over the voicing measured in
    the audio and returns the shift with the best agreement.
    """
    measured = voicing_track(audio, sr, f0)
    predicted = np.zeros(len(measured))
    for phone in phones:
        if is_voiced(phone.symbol):
            predicted[int(phone.start / ANALYSIS_FRAME_S):int(phone.end / ANALYSIS_FRAME_S)] = 1.0
    if predicted.sum() == 0 or measured.sum() == 0:
        return 0.0
    span = int(LAG_SEARCH_S / ANALYSIS_FRAME_S)
    centred_measured, centred_predicted = measured - measured.mean(), predicted - predicted.mean()
    best_shift, best_score = 0, -np.inf
    for shift in range(-span, span + 1):                      # shift > 0: move predictions earlier
        moved = np.roll(centred_predicted, -shift)
        if shift > 0:
            moved[-shift:] = -predicted.mean()
        elif shift < 0:
            moved[:-shift] = -predicted.mean()
        score = float(np.dot(moved, centred_measured))
        if score > best_score:
            best_shift, best_score = shift, score
    return best_shift * ANALYSIS_FRAME_S


def apply_lag(phones: list[Phone], lag: float, total: float) -> list[Phone]:
    return [Phone(p.symbol, min(max(p.start - lag, 0.0), total), min(max(p.end - lag, 0.0), total), p.word, p.stressed) for p in phones]


def share_word_gaps(symbols: list[str], starts: list[float], ends: list[float], to_previous: float) -> tuple[list[float], list[float]]:
    """The time an engine reports for the space between two words is not silence: the neighbouring sounds run
    through it. Hand `to_previous` of it to the sound before and the rest to the sound after, and keep a zero-length
    word break. Real pauses (punctuation, the line's ends) are left alone. Works on the engine's tokens, before
    merge_tokens. Ported from Spectro Maestro's speech.share_word_gaps (same author, AGPL-3.0-or-later).

    Without it a timed gap gives two boundaries where the audio has one event, and snapping can hang the end of a
    word on the wrong one: "See the signal fires" was sung with the "the" taken from the end of "see"."""
    starts, ends = list(starts), list(ends)
    for i in range(1, len(symbols) - 1):
        if symbols[i] == WORD_GAP and symbols[i - 1] not in PAUSES and symbols[i + 1] not in PAUSES:
            cut = starts[i] + to_previous * (ends[i] - starts[i])
            ends[i - 1] = starts[i] = ends[i] = starts[i + 1] = cut
    return starts, ends


def acoustic_frames(audio: np.ndarray, sr: int, analysis: tuple) -> dict:
    """Frame-wise evidence on the 5 ms grid: truly voiced frames (world.truly_voiced) and hiss frames.
    Ported from Spectro Maestro's speech.acoustic_frames (same author, AGPL-3.0-or-later)."""
    from scipy import signal
    f0, envelope, aperiodicity = analysis
    hop = int(sr * ANALYSIS_FRAME_S)
    n = min(len(f0), len(audio) // hop)
    x = np.asarray(audio[:n * hop], dtype=np.float64)
    high = signal.sosfilt(signal.butter(4, SIBILANT_HZ, btype="highpass", fs=sr, output="sos"), x)
    power = np.mean(x.reshape(n, hop) ** 2, axis=1) + 1e-12
    high_power = np.mean(high.reshape(n, hop) ** 2, axis=1)
    level = 10.0 * np.log10(power)
    return {"voiced": world.truly_voiced(f0, envelope, aperiodicity, sr)[:n],
            "sibilant": (high_power / power > SIBILANT_SHARE) & (level > SILENCE_DB)}


def _transitions(flags: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(times where flags switch on, times where they switch off) in seconds."""
    change = np.diff(flags.astype(np.int8))
    return (np.nonzero(change == 1)[0] + 1) * ANALYSIS_FRAME_S, (np.nonzero(change == -1)[0] + 1) * ANALYSIS_FRAME_S


def _landmark(left: Phone, right: Phone, events: dict) -> np.ndarray | None:
    """The audible events the boundary between two phones predicts: hiss on or off, else voice on or off."""
    left_sib, right_sib = left.symbol[0] in SIBILANT_LANDMARKS, right.symbol[0] in SIBILANT_LANDMARKS
    left_kind, right_kind = voicing(left.symbol), voicing(right.symbol)
    left_voiced, right_voiced = left_kind in ("vowel", "sonorant"), right_kind in ("vowel", "sonorant")
    if left_sib != right_sib:
        return events["sibilant_on"] if right_sib else events["sibilant_off"]
    if left_kind in ("unvoiced", "pause") and right_voiced:
        return events["voiced_on"]
    if left_voiced and right_kind in ("unvoiced", "pause"):
        return events["voiced_off"]
    return None


def snap_boundaries(phones: list[Phone], frames: dict) -> int:
    """Move each phone boundary with an audible landmark to that landmark (at most SNAP_WINDOW_S away), in place, and
    move the boundaries between by interpolation. Returns how many were snapped.
    Ported from Spectro Maestro's speech._snap (same author, AGPL-3.0-or-later)."""
    events = dict(zip(("voiced_on", "voiced_off"), _transitions(frames["voiced"])))
    events.update(zip(("sibilant_on", "sibilant_off"), _transitions(frames["sibilant"])))
    anchors = [(0.0, 0.0)]
    timed = [p for p in phones if p.end - p.start > 1e-6]              # zero-length phones predict no event
    for left, right in zip(timed, timed[1:]):
        candidates = _landmark(left, right, events)
        if candidates is None or len(candidates) == 0:
            continue
        boundary = right.start
        nearest = float(candidates[np.argmin(np.abs(candidates - boundary))])
        if abs(nearest - boundary) <= SNAP_WINDOW_S and nearest > anchors[-1][1] + 1e-3 and boundary > anchors[-1][0] + 1e-3:
            anchors.append((boundary, nearest))
    total = phones[-1].end
    anchors.append((max(total, anchors[-1][0] + 1e-3), max(total, anchors[-1][1] + 1e-3)))
    predicted, actual = np.array(anchors).T
    for phone in phones:
        phone.start, phone.end = float(np.interp(phone.start, predicted, actual)), float(np.interp(phone.end, predicted, actual))
    return len(anchors) - 2


# -- backends ---------------------------------------------------------------------------------------------
class KokoroBackend:
    """Kokoro-82M (ONNX, timestamped export): natural English speech with per-phoneme durations."""
    engine = "kokoro"
    word_gap_to_previous = 0.5          # Spectro Maestro's measure on hiss landmarks: both neighbours spread into the gap

    def __init__(self, voice: str, lang: str = "en-us"):
        import onnxruntime
        from kokoro_onnx.tokenizer import Tokenizer
        self.voice, self.lang, self.sr = voice, lang, KOKORO_SAMPLE_RATE
        folder = cache_dir("kokoro")
        model = fetch(f"{KOKORO_BASE}/onnx/model.onnx", os.path.join(folder, "model.onnx"))
        style = fetch(f"{KOKORO_BASE}/voices/{voice}.bin", os.path.join(folder, f"{voice}.bin"))
        self._tokenizer = Tokenizer()
        self._styles = np.fromfile(style, dtype=np.float32).reshape(-1, 1, 256)
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = max(1, (os.cpu_count() or 2))
        self._session = onnxruntime.InferenceSession(model, options, providers=["CPUExecutionProvider"])

    @property
    def identity(self) -> str:
        return f"kokoro:{self.voice}:{KOKORO_REVISION[:8]}"

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, self.lang)

    def synthesize(self, text: str, speed: float = 1.0, seed: int = DEFAULT_SEED) -> Unit:
        phonemes = self.phonemize(text)
        ids = self._tokenizer.tokenize(phonemes)
        _seed_everything(seed)
        waveform, durations = self._session.run(None, {
            "input_ids": np.array([[0] + ids + [0]], dtype=np.int64), "style": self._styles[len(ids)],
            "speed": np.array([speed], dtype=np.float32)})
        audio = waveform[0].astype(np.float64)
        frames = np.maximum(np.round(durations[0]), 1.0)
        edges = np.concatenate([[0.0], np.cumsum(frames)]) * KOKORO_FRAME_SAMPLES / self.sr
        symbols = [s for s in phonemes if s in self._tokenizer.vocab]            # the tokenizer drops unknown symbols
        starts, ends = share_word_gaps(symbols, list(edges[1:-2]), list(edges[2:-1]), self.word_gap_to_previous)   # skip the pad tokens
        phones = merge_tokens(symbols, starts, ends)
        return _finish_unit(audio, self.sr, phones, text)


class PiperBackend:
    """Piper (VITS) voices. Durations come from the alignment output patched into the model at load time."""
    engine = "piper"
    word_gap_to_previous = 0.0          # Spectro Maestro's measure on hiss landmarks: the gap belongs to the sound that follows

    def __init__(self, voice: str, lang: str = "en-us"):
        from piper import PiperVoice
        self.voice, self.lang = voice, lang
        folder = cache_dir("piper")
        language, name, quality = voice.split("-")
        remote = f"{PIPER_BASE}/{language.split('_')[0]}/{language}/{name}/{quality}/{voice}.onnx"
        self._model = fetch(remote, os.path.join(folder, f"{voice}.onnx"))
        fetch(remote + ".json", os.path.join(folder, f"{voice}.onnx.json"))
        self._voice = PiperVoice.load(self._model)                 # used for phonemizing only
        self.sr = self._voice.config.sample_rate

    @property
    def identity(self) -> str:
        return f"piper:{self.voice}"

    def phonemize(self, text: str) -> str:
        return " ".join("".join(sentence) for sentence in self._voice.phonemize(text)).strip()

    def synthesize(self, text: str, speed: float = 1.0, seed: int = DEFAULT_SEED) -> Unit:
        from piper import PiperVoice, SynthesisConfig
        # onnxruntime fixes the random stream of a graph when the session is created, and every run advances
        # it. A fresh session per line is the only way the same line always gets the same sampling noise.
        _seed_everything(seed)
        voice = PiperVoice.load(self._model, include_alignments=True)
        config = SynthesisConfig(length_scale=1.0 / speed)
        pieces, symbols, starts, ends, cursor = [], [], [], [], 0.0
        for chunk in voice.synthesize(text, syn_config=config, include_alignments=True):
            pieces.append(chunk.audio_float_array.astype(np.float64))
            if not chunk.phoneme_alignments:
                raise RuntimeError(f"Piper voice {self.voice} returned no alignments; install the 'onnx' package")
            for item in chunk.phoneme_alignments:
                length = item.num_samples / chunk.sample_rate
                if item.phoneme not in ("^", "$", "_"):
                    symbols.append(item.phoneme)
                    starts.append(cursor)
                    ends.append(cursor + length)
                cursor += length
        audio = np.concatenate(pieces)
        starts, ends = share_word_gaps(symbols, starts, ends, self.word_gap_to_previous)
        return _finish_unit(audio, self.sr, merge_tokens(symbols, starts, ends), text)


def _finish_unit(audio: np.ndarray, sr: int, phones: list[Phone], text: str) -> Unit:
    total = len(audio) / sr
    analysis = world.analyze(audio, sr)
    f0, envelope, aperiodicity = analysis
    lag = measure_lag_by_periodicity(phones, aperiodicity, f0, sr)
    if lag is None:
        lag = measure_lag(audio, sr, phones, f0)
    timed = apply_lag(phones, lag, total)
    snapped = snap_boundaries(timed, acoustic_frames(audio, sr, analysis)) if timed else 0
    return Unit(audio, sr, timed, text, lag, analysis, snapped)


_backends: dict[str, object] = {}


def backend(voice: str, lang: str | None = None):
    """Backend for a voice id such as 'kokoro:af_heart' or 'piper:en_US-lessac-medium' (cached per process)."""
    if voice not in _backends:
        engine, _, name = voice.partition(":")
        language = lang or VOICES.get(voice, {}).get("lang", "en-us")
        if engine == "kokoro":
            _backends[voice] = KokoroBackend(name, language)
        elif engine == "piper":
            _backends[voice] = PiperBackend(name, language)
        else:
            raise ValueError(f"unknown TTS engine in voice id '{voice}'; use kokoro:<voice> or piper:<voice>")
    return _backends[voice]


# -- unit cache -------------------------------------------------------------------------------------------
def unit_key(identity: str, text: str, speed: float, seed: int) -> str:
    return hashlib.sha1(json.dumps([identity, text, round(speed, 4), seed, TIMING_VERSION]).encode("utf-8")).hexdigest()[:20]


def save_unit(path: str, unit: Unit) -> None:
    extra = {}
    if unit.analysis is not None:
        f0, envelope, aperiodicity = unit.analysis
        extra = {"f0": f0, "envelope": envelope.astype(np.float32), "aperiodicity": aperiodicity.astype(np.float32)}
    np.savez_compressed(path, audio=unit.audio.astype(np.float32), sr=unit.sr, lag=unit.lag, snapped=unit.snapped, text=unit.text,
                        symbols=np.array([p.symbol for p in unit.phones]), starts=np.array([p.start for p in unit.phones]),
                        ends=np.array([p.end for p in unit.phones]), words=np.array([p.word for p in unit.phones]),
                        stressed=np.array([p.stressed for p in unit.phones]), **extra)


def load_unit(path: str) -> Unit:
    data = np.load(path, allow_pickle=False)
    phones = [Phone(str(s), float(a), float(b), int(w), bool(x)) for s, a, b, w, x in
              zip(data["symbols"], data["starts"], data["ends"], data["words"], data["stressed"])]
    analysis = (data["f0"], data["envelope"].astype(np.float64), data["aperiodicity"].astype(np.float64)) if "f0" in data else None
    return Unit(data["audio"].astype(np.float64), int(data["sr"]), phones, str(data["text"]), float(data["lag"]), analysis,
                int(data["snapped"]) if "snapped" in data else 0)


def speak(voice: str, text: str, speed: float = 1.0, seed: int = DEFAULT_SEED, cache: str | None = None) -> Unit:
    """Synthesize a line (or read it from the cache folder)."""
    engine = backend(voice)
    if cache is None:
        return engine.synthesize(text, speed, seed)
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, unit_key(engine.identity, text, speed, seed) + ".npz")
    if os.path.exists(path):
        return load_unit(path)
    unit = engine.synthesize(text, speed, seed)
    save_unit(path, unit)
    return unit
