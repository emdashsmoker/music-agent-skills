# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Audio measurement: loudness, peaks, spectral balance, stereo, envelopes.

Every number an agent needs to judge a mix without hearing it comes from here.
All functions take float arrays shaped (frames,) or (frames, channels).
"""
from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy import signal

SILENCE_DB = -120.0
ABSOLUTE_GATE_LUFS = -70.0
RELATIVE_GATE_LU = -10.0
MOMENTARY_SECONDS, SHORT_TERM_SECONDS = 0.4, 3.0
BLOCK_OVERLAP = 0.75
TRUE_PEAK_OVERSAMPLE = 4
CLIP_LEVEL = 0.999
CLIP_RUN = 3                                   # consecutive full-scale samples that count as clipping

# Analysis bands in Hz. Names are used across lint messages and figures.
BANDS = {"sub": (20, 60), "bass": (60, 250), "low_mid": (250, 500), "mid": (500, 2000),
         "high_mid": (2000, 6000), "air": (6000, 20000)}
VOCAL_BODY_BAND = (300, 3400)
CONSONANT_BAND = (1300, 5000)
KICK_BAND = (40, 120)


def load(path: str) -> tuple[np.ndarray, int]:
    data, rate = sf.read(path, dtype="float64", always_2d=True)
    return data, rate


def save(path: str, data: np.ndarray, rate: int, subtype: str = "PCM_16") -> str:
    sf.write(path, np.clip(data, -1.0, 1.0), rate, subtype=subtype)
    return path


def to_mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else x.mean(axis=1)


def db(value: float, floor: float = SILENCE_DB) -> float:
    return float(max(floor, 20.0 * np.log10(max(float(value), 1e-12))))


def power_db(value: float, floor: float = SILENCE_DB) -> float:
    return float(max(floor, 10.0 * np.log10(max(float(value), 1e-24))))


def rms_db(x: np.ndarray) -> float:
    return db(np.sqrt(np.mean(np.square(x)))) if len(x) else SILENCE_DB


# -- loudness (ITU-R BS.1770-4) ---------------------------------------------------------------------
ACTIVE_RANGE_LU = 30.0


def _k_weighting(rate: int):
    """Shelf + high-pass of BS.1770, re-derived for the given rate (coefficients in the spec are for 48 kHz)."""
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / rate)
    vh, vb = 10 ** (gain_db / 20), (10 ** (gain_db / 20)) ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf = ([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0],
             [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / rate)
    a0 = 1 + k / q + k * k
    highpass = ([1.0, -2.0, 1.0], [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    return shelf, highpass


def k_weighted(x: np.ndarray, rate: int) -> np.ndarray:
    shelf, highpass = _k_weighting(rate)
    # One contiguous 1-D array per channel: scipy filters those several times faster than a 2-D array.
    return np.stack([signal.lfilter(*highpass, signal.lfilter(*shelf, np.ascontiguousarray(x[:, c]))) for c in range(x.shape[1])], axis=1)


def _block_loudness(x: np.ndarray, rate: int, seconds: float) -> np.ndarray:
    """Loudness of overlapping blocks in LUFS (all channels summed with unit weight)."""
    y = k_weighted(x if x.ndim == 2 else x[:, None], rate)
    block, hop = int(seconds * rate), int(seconds * rate * (1 - BLOCK_OVERLAP))
    if len(y) < block:
        return np.array([])
    cumulative = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(y * y, axis=0)])
    starts = np.arange(0, len(y) - block + 1, hop)
    energy = (cumulative[starts + block] - cumulative[starts]).sum(axis=1) / block
    return -0.691 + 10 * np.log10(np.maximum(energy, 1e-24))


def integrated_lufs(x: np.ndarray, rate: int) -> float:
    blocks = _block_loudness(x, rate, MOMENTARY_SECONDS)
    blocks = blocks[blocks > ABSOLUTE_GATE_LUFS]
    if not len(blocks):
        return SILENCE_DB
    energy = 10 ** ((blocks + 0.691) / 10)
    threshold = -0.691 + 10 * np.log10(energy.mean()) + RELATIVE_GATE_LU
    gated = energy[blocks > threshold]
    return float(-0.691 + 10 * np.log10(gated.mean())) if len(gated) else SILENCE_DB


def short_term_lufs(x: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray]:
    """(times in seconds at block centres, loudness) with 3 s blocks: the song's energy curve."""
    values = _block_loudness(x, rate, SHORT_TERM_SECONDS)
    hop = SHORT_TERM_SECONDS * (1 - BLOCK_OVERLAP)
    return np.arange(len(values)) * hop + SHORT_TERM_SECONDS / 2, values


def active_loudness(x: np.ndarray, rate: int, percentile: float = 90.0) -> float:
    """Loudness of a part while it plays: a high percentile of momentary loudness, so rests do not count.

    Blocks more than ACTIVE_RANGE_LU below the loudest one (rests, reverb tails) are left out. The gate is
    relative so that the result moves exactly with the fader: an absolute gate would drop quiet blocks as
    a part is turned down and shift the percentile.
    """
    blocks = _block_loudness(x, rate, MOMENTARY_SECONDS)
    blocks = blocks[blocks > ABSOLUTE_GATE_LUFS]
    if not len(blocks):
        return SILENCE_DB
    return float(np.percentile(blocks[blocks > blocks.max() - ACTIVE_RANGE_LU], percentile))


def peak_loudness(x: np.ndarray, rate: int) -> float:
    """Loudest 400 ms of a sound in LUFS; short one-shots are zero-padded so they still measure."""
    block = int(MOMENTARY_SECONDS * rate)
    if len(x) < block:
        x = np.concatenate([x, np.zeros((block - len(x),) + x.shape[1:])])
    blocks = _block_loudness(x, rate, MOMENTARY_SECONDS)
    return float(blocks.max()) if len(blocks) else SILENCE_DB


def loudness_range(x: np.ndarray, rate: int) -> float:
    """Spread between quiet and loud passages (10th to 95th percentile of short-term loudness), in LU."""
    _, values = short_term_lufs(x, rate)
    values = values[values > ABSOLUTE_GATE_LUFS]
    if len(values) < 2:
        return 0.0
    values = values[values > values.mean() - 20.0]
    return float(np.percentile(values, 95) - np.percentile(values, 10))


# -- peaks ----------------------------------------------------------------------------------------------
def sample_peak_db(x: np.ndarray) -> float:
    return db(np.max(np.abs(x))) if len(x) else SILENCE_DB


def true_peak_db(x: np.ndarray) -> float:
    if not len(x):
        return SILENCE_DB
    return db(np.max(np.abs(signal.resample_poly(x, TRUE_PEAK_OVERSAMPLE, 1, axis=0))))


def clipped_runs(x: np.ndarray) -> int:
    """Number of places where the signal sits at full scale for several samples in a row."""
    hot = (np.abs(to_mono(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)) >= CLIP_LEVEL).astype(int)
    if not hot.any():
        return 0
    edges = np.diff(np.concatenate([[0], hot, [0]]))
    lengths = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
    return int(np.sum(lengths >= CLIP_RUN))


def crest_db(x: np.ndarray) -> float:
    return sample_peak_db(x) - rms_db(x)


def dc_offset(x: np.ndarray) -> float:
    return float(np.max(np.abs(np.mean(x, axis=0)))) if len(x) else 0.0


# -- spectrum -------------------------------------------------------------------------------------------
def spectrum(x: np.ndarray, rate: int, n_fft: int = 8192) -> tuple[np.ndarray, np.ndarray]:
    """Long-term average power spectrum of the mono sum: (frequencies, power)."""
    mono = to_mono(x)
    if len(mono) < n_fft:
        mono = np.pad(mono, (0, n_fft - len(mono)))
    return signal.welch(mono, rate, nperseg=n_fft, noverlap=n_fft // 2, scaling="spectrum", detrend=False)


def band_power(freqs: np.ndarray, power: np.ndarray, low: float, high: float) -> float:
    return float(power[(freqs >= low) & (freqs < high)].sum())


def band_levels(x: np.ndarray, rate: int, bands: dict | None = None) -> dict[str, float]:
    """Level of each band in dB relative to the full-band level (0 dB = all energy in that band)."""
    freqs, power = spectrum(x, rate)
    total = band_power(freqs, power, 20, rate / 2) or 1e-24
    return {name: power_db(band_power(freqs, power, low, high) / total) for name, (low, high) in (bands or BANDS).items()}


def band_rms_db(x: np.ndarray, rate: int, low: float, high: float) -> float:
    """Absolute level (dBFS) of one band."""
    freqs, power = spectrum(x, rate)
    return power_db(band_power(freqs, power, low, high))


def bandpass(x: np.ndarray, rate: int, low: float, high: float, order: int = 4) -> np.ndarray:
    high = min(high, rate / 2 * 0.99)
    sos = signal.butter(order, [low, high], btype="band", fs=rate, output="sos")
    return signal.sosfiltfilt(sos, x, axis=0)


def spectral_centroid(x: np.ndarray, rate: int) -> float:
    """Brightness in Hz: centre of mass of the magnitude spectrum (higher = brighter)."""
    freqs, power = spectrum(x, rate)
    keep = freqs >= 20
    magnitude = np.sqrt(power[keep])
    return float((freqs[keep] * magnitude).sum() / max(magnitude.sum(), 1e-12))


def spectral_rolloff(x: np.ndarray, rate: int, share: float = 0.85) -> float:
    """Frequency below which `share` of the energy lies."""
    freqs, power = spectrum(x, rate)
    keep = freqs >= 20
    cumulative = np.cumsum(power[keep])
    return float(freqs[keep][np.searchsorted(cumulative, share * cumulative[-1])])


def spectral_tilt(x: np.ndarray, rate: int) -> float:
    """Slope of the octave-band spectrum in dB per octave between 100 Hz and 10 kHz (pink noise = 0)."""
    freqs, power = spectrum(x, rate)
    centres = 100.0 * 2 ** np.arange(0, 7)
    levels = [power_db(band_power(freqs, power, c / 2 ** 0.5, c * 2 ** 0.5)) for c in centres]
    return float(np.polyfit(np.log2(centres), levels, 1)[0])


LOUD_WINDOW_S = 20.0                  # the densest passage: the drop or the last chorus
MID_RANGE_HZ, HIGH_RANGE_HZ = (354.0, 2828.0), (2828.0, 20000.0)          # the octaves around 0.5-2 kHz and around 4-16 kHz


def brightness_db(x: np.ndarray, rate: int) -> float:
    """Energy above 2.8 kHz against the energy of the three octaves below it, in dB.

    Pink noise reads 0. A spectrum that falls 4.5 dB per octave, the usual analyser reference for a finished
    mix, reads -4.5. Lower values are heard as dull or covered, higher ones as bright or harsh.
    """
    freqs, power = spectrum(x, rate)
    return power_db(band_power(freqs, power, *HIGH_RANGE_HZ) / max(band_power(freqs, power, *MID_RANGE_HZ), 1e-20))


def loudest_span(x: np.ndarray, rate: int, seconds: float = LOUD_WINDOW_S) -> tuple[int, int]:
    """Start and end sample of the stretch of `seconds` with the most energy (the drop or last chorus), in one-second steps."""
    size = int(seconds * rate)
    if len(x) <= size:
        return 0, len(x)
    power = np.cumsum(np.concatenate([[0.0], (x ** 2).mean(axis=1) if x.ndim == 2 else x ** 2]))
    starts = np.arange(0, len(x) - size, rate)
    best = int(starts[int(np.argmax(power[starts + size] - power[starts]))])
    return best, best + size


def loudest_window(x: np.ndarray, rate: int, seconds: float = LOUD_WINDOW_S) -> np.ndarray:
    start, end = loudest_span(x, rate, seconds)
    return x[start:end]


def shelf(x: np.ndarray, rate: int, hz: float, gain_db: float, high: bool) -> np.ndarray:
    """Second-order shelving filter (the common 'cookbook' form, slope 1). Used to predict what a shelf EQ will do."""
    a = 10 ** (gain_db / 40)
    w = 2 * np.pi * hz / rate
    cos, alpha, root = np.cos(w), np.sin(w) / 2 * np.sqrt(2.0), np.sqrt(a)
    sign = 1.0 if high else -1.0
    b = [a * ((a + 1) + sign * (a - 1) * cos + 2 * root * alpha), -sign * 2 * a * ((a - 1) + sign * (a + 1) * cos),
         a * ((a + 1) + sign * (a - 1) * cos - 2 * root * alpha)]
    den = [(a + 1) - sign * (a - 1) * cos + 2 * root * alpha, sign * 2 * ((a - 1) - sign * (a + 1) * cos),
           (a + 1) - sign * (a - 1) * cos - 2 * root * alpha]
    return signal.lfilter(np.array(b) / den[0], np.array(den) / den[0], x, axis=0)


# -- stereo ---------------------------------------------------------------------------------------------
def stereo_correlation(x: np.ndarray) -> float:
    """+1 mono, 0 unrelated, negative = cancels when summed to mono."""
    if x.ndim == 1 or x.shape[1] < 2:
        return 1.0
    left, right = x[:, 0], x[:, 1]
    denominator = np.sqrt(np.sum(left * left) * np.sum(right * right))
    return float(np.sum(left * right) / denominator) if denominator > 0 else 1.0


def stereo_width(x: np.ndarray) -> float:
    """Side energy over mid energy (0 = mono, 1 = as much side as mid)."""
    if x.ndim == 1 or x.shape[1] < 2:
        return 0.0
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    return float(np.sqrt(np.mean(side * side) / max(np.mean(mid * mid), 1e-24)))


# -- time domain ----------------------------------------------------------------------------------------
def envelope_db(x: np.ndarray, rate: int, window_seconds: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """RMS envelope in dB on a regular grid: (times, levels)."""
    mono = to_mono(x)
    hop = max(1, int(window_seconds * rate))
    frames = len(mono) // hop
    if frames == 0:
        return np.array([]), np.array([])
    levels = np.sqrt(np.mean(np.square(mono[:frames * hop].reshape(frames, hop)), axis=1))
    return np.arange(frames) * hop / rate, 20 * np.log10(np.maximum(levels, 1e-6))


def trim_silence(x: np.ndarray, rate: int, threshold_db: float = -60.0) -> tuple[int, int]:
    """First and last sample above the threshold."""
    loud = np.flatnonzero(np.max(np.abs(x if x.ndim == 2 else x[:, None]), axis=1) > 10 ** (threshold_db / 20))
    return (int(loud[0]), int(loud[-1]) + 1) if len(loud) else (0, 0)


def summary(x: np.ndarray, rate: int) -> dict:
    """One-call master report used by the analyze command."""
    start, end = trim_silence(x, rate)
    return {
        "duration_s": round(len(x) / rate, 2), "lufs_integrated": round(integrated_lufs(x, rate), 2),
        "loudness_range_lu": round(loudness_range(x, rate), 2), "true_peak_db": round(true_peak_db(x), 2),
        "sample_peak_db": round(sample_peak_db(x), 2), "crest_db": round(crest_db(x), 2), "clipped_runs": clipped_runs(x),
        "dc_offset": round(dc_offset(x), 5), "stereo_correlation": round(stereo_correlation(x), 3),
        "stereo_width": round(stereo_width(x), 3),
        "low_end_correlation": round(stereo_correlation(bandpass(x, rate, 30, 150)), 3) if x.ndim == 2 else 1.0,
        "centroid_hz": round(spectral_centroid(x, rate)), "tilt_db_per_octave": round(spectral_tilt(x, rate), 2),
        "loud_brightness_db": round(brightness_db(loudest_window(x, rate), rate), 1),
        "bands_db": {k: round(v, 1) for k, v in band_levels(x, rate).items()},
        "leading_silence_s": round(start / rate, 3), "trailing_silence_s": round((len(x) - end) / rate, 3),
    }
