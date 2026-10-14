# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Signal-processing primitives shared by the synths, the mixer and the analysers.
numpy and scipy only: no per-sample Python loops, time-varying filters run block-wise."""
from __future__ import annotations

import os

import numpy as np
from scipy import signal

SR = 44100
TV_BLOCK = 32                   # samples per coefficient update of a time-varying filter (0.7 ms)
LUFS_BLOCK_S, LUFS_HOP_S = 0.4, 0.1
LUFS_ABS_GATE, LUFS_REL_GATE = -70.0, -10.0
TRUE_PEAK_OVERSAMPLE = 4
STREAM_CHUNK = 1 << 16


def db_to_lin(db):
    """Single-precision curves stay single precision: a gain curve of a long mix is hundreds of megabytes in double."""
    db = np.asarray(db)
    if db.dtype != np.float32:
        db = db.astype(float)
    return 10.0 ** (db / 20.0)


def lin_to_db(lin, floor: float = 1e-12):
    return 20.0 * np.log10(np.maximum(np.abs(lin), floor))


def to_stereo(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def to_mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else x.mean(axis=1)


def fade_edges(x: np.ndarray, sr: int = SR, seconds: float = 0.003) -> np.ndarray:
    """Short fades so that a clipped start or end never clicks."""
    n = min(int(seconds * sr), len(x) // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n)
        x = x.copy()
        x[:n] = (x[:n].T * ramp).T
        x[-n:] = (x[-n:].T * ramp[::-1]).T
    return x


# ---------------------------------------------------------------- oscillators

def phase_of(freq, n: int, sr: int = SR, start: float = 0.0) -> np.ndarray:
    """Running phase in cycles for a constant or per-sample frequency."""
    if np.isscalar(freq):
        return start + np.arange(n) * (freq / sr)
    return start + np.concatenate([[0.0], np.cumsum(freq[:-1])]) / sr


def _poly_blep(t: np.ndarray, dt) -> np.ndarray:
    """Polynomial band-limited step residual: removes most aliasing of a naive discontinuity."""
    out = np.zeros_like(t)
    rising = t < dt
    x = t[rising] / (dt[rising] if not np.isscalar(dt) else dt)
    out[rising] = 2 * x - x * x - 1.0
    falling = t > 1.0 - dt
    x = (t[falling] - 1.0) / (dt[falling] if not np.isscalar(dt) else dt)
    out[falling] = x * x + 2 * x + 1.0
    return out


def osc(wave: str, freq, n: int, sr: int = SR, start: float = 0.0, pw=0.5) -> np.ndarray:
    """One oscillator. `freq` may be a scalar or a per-sample array; `start` is the phase in cycles."""
    phase = phase_of(freq, n, sr, start)
    t = phase % 1.0
    dt = (freq / sr) if np.isscalar(freq) else np.maximum(freq / sr, 1e-9)
    if wave == "sine":
        return np.sin(2 * np.pi * phase)
    if wave == "saw":
        return 2.0 * t - 1.0 - _poly_blep(t, dt)
    if wave in ("square", "pulse"):
        width = 0.5 if wave == "square" else pw
        shifted = (t + 1.0 - width) % 1.0
        return np.where(t < width, 1.0, -1.0) + _poly_blep(t, dt) - _poly_blep(shifted, dt)
    if wave == "tri":
        return 2.0 * np.abs(2.0 * t - 1.0) - 1.0
    raise ValueError(f"unknown waveform {wave!r}")


def white_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, n)


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """-3 dB/octave noise by shaping white noise in the frequency domain."""
    spectrum = np.fft.rfft(rng.standard_normal(n))
    scale = np.ones(len(spectrum))
    scale[1:] = 1.0 / np.sqrt(np.arange(1, len(spectrum)))
    out = np.fft.irfft(spectrum * scale, n)
    return out / (np.max(np.abs(out)) + 1e-12)


# ---------------------------------------------------------------- envelopes

def adsr(n: int, gate_n: int, attack: float, decay: float, sustain: float, release: float, sr: int = SR,
         curve: float = 4.0) -> np.ndarray:
    """Exponential-segment ADSR. `gate_n` samples of held note, release after it, total length n."""
    a, d, r = (max(1, int(x * sr)) for x in (attack, decay, release))
    gate_n = max(1, min(gate_n, n))
    env = np.empty(n)
    held = np.empty(gate_n)
    ramp = np.arange(min(a, gate_n)) / a
    held[:len(ramp)] = (1.0 - np.exp(-curve * ramp)) / (1.0 - np.exp(-curve))
    if gate_n > a:
        t = np.arange(gate_n - a) / d
        held[a:] = sustain + (1.0 - sustain) * np.exp(-curve * t)
    env[:gate_n] = held
    if n > gate_n:
        t = np.arange(n - gate_n) / r
        env[gate_n:] = held[-1] * np.exp(-curve * t) * np.clip(1.0 - (t - 1.0), 0.0, 1.0)
    return env


def exp_decay(n: int, seconds: float, sr: int = SR) -> np.ndarray:
    """Envelope that falls by 60 dB over `seconds`."""
    return np.exp(-6.908 * np.arange(n) / (max(seconds, 1e-4) * sr))


# ---------------------------------------------------------------- filters

def biquad(kind: str, freq, q=0.7071, gain_db=0.0, sr: int = SR) -> tuple:
    """RBJ cookbook biquad. freq/q/gain may be arrays; returns (b, a) with shape (..., 3), a0 normalised to 1."""
    freq = np.clip(np.asarray(freq, dtype=float), 10.0, sr * 0.49)
    w = 2 * np.pi * freq / sr
    cos, sin = np.cos(w), np.sin(w)
    q = np.maximum(np.asarray(q, dtype=float), 0.05)
    alpha = sin / (2 * q)
    amp = 10.0 ** (np.asarray(gain_db, dtype=float) / 40.0)
    one = np.ones_like(w * alpha * amp)
    if kind == "lp":
        b = [(1 - cos) / 2, 1 - cos, (1 - cos) / 2]; a = [1 + alpha, -2 * cos, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cos) / 2, -(1 + cos), (1 + cos) / 2]; a = [1 + alpha, -2 * cos, 1 - alpha]
    elif kind == "bp":
        b = [alpha, 0 * alpha, -alpha]; a = [1 + alpha, -2 * cos, 1 - alpha]
    elif kind == "notch":
        b = [one, -2 * cos, one]; a = [1 + alpha, -2 * cos, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * amp, -2 * cos, 1 - alpha * amp]; a = [1 + alpha / amp, -2 * cos, 1 - alpha / amp]
    elif kind in ("lowshelf", "highshelf"):
        sign = 1.0 if kind == "lowshelf" else -1.0
        root = 2 * np.sqrt(amp) * alpha
        b = [amp * ((amp + 1) - sign * (amp - 1) * cos + root), sign * 2 * amp * ((amp - 1) - sign * (amp + 1) * cos),
             amp * ((amp + 1) - sign * (amp - 1) * cos - root)]
        a = [(amp + 1) + sign * (amp - 1) * cos + root, -sign * 2 * ((amp - 1) + sign * (amp + 1) * cos),
             (amp + 1) + sign * (amp - 1) * cos - root]
    else:
        raise ValueError(f"unknown filter kind {kind!r}")
    b = np.stack(np.broadcast_arrays(*[x * one for x in b]), axis=-1)
    a = np.stack(np.broadcast_arrays(*[x * one for x in a]), axis=-1)
    return b / a[..., :1], a / a[..., :1]


def sos_of(kind: str, freq: float, q: float = 0.7071, gain_db: float = 0.0, sr: int = SR) -> np.ndarray:
    b, a = biquad(kind, freq, q, gain_db, sr)
    return np.concatenate([b, a])[None, :]


def sos_stream(sos: np.ndarray, x: np.ndarray, chunk: int = STREAM_CHUNK) -> np.ndarray:
    """sosfilt for long signals: double-precision filtering in cache-sized pieces, single-precision result.
    Avoids the several full-length float64 temporaries a one-shot call makes (the slow part on long mixes)."""
    if len(x) <= 2 * chunk:
        return signal.sosfilt(sos, x, axis=0)
    out = np.empty(x.shape, dtype=np.float32)
    state = np.zeros((len(sos), 2) + x.shape[1:])
    ringing = False
    for start in range(0, len(x), chunk):
        piece = x[start:start + chunk]
        if not ringing and not piece.any():              # silence in, silence out: most stems are mostly silent
            out[start:start + chunk] = 0.0
            continue
        out[start:start + chunk], state = signal.sosfilt(sos, piece, axis=0, zi=state)
        ringing = bool(np.abs(state).max() > 1e-9)
    return out


def static_filter(x: np.ndarray, kind: str, freq: float, q: float = 0.7071, gain_db: float = 0.0, sr: int = SR,
                  poles: int = 2) -> np.ndarray:
    sos = np.repeat(sos_of(kind, freq, q, gain_db, sr), max(1, poles // 2), axis=0)
    return sos_stream(sos, x)


_native = None                  # False once loading failed, the ctypes function once it succeeded


def _native_biquad():
    """Compiled block-biquad kernel, built on first use with the system C compiler.
    Without a compiler everything still works through scipy, only slower."""
    global _native
    if _native is not None:
        return _native or None
    import ctypes
    import hashlib
    import subprocess
    _native = False
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native", "tvfilter.c")
    from . import settings
    try:
        if str(settings.get("native")).lower() == "off" or not os.path.exists(source):
            return None
        compiler = settings.command("compiler", ("cc", "gcc", "clang"))
        if not compiler:
            return None
        with open(source, "rb") as handle:
            digest = hashlib.sha1(handle.read()).hexdigest()[:12]
        folder = os.path.join(settings.cache_dir(), "native")
        windows = os.name == "nt"
        library = os.path.join(folder, f"tvfilter-{digest}{'.dll' if windows else '.so'}")
        if not os.path.exists(library):
            os.makedirs(folder, exist_ok=True)
            flags = ["-O2", "-shared"] + ([] if windows else ["-fPIC"])
            subprocess.run(compiler + flags + [source, "-o", library + ".tmp"], check=True, capture_output=True)
            os.replace(library + ".tmp", library)
        function = ctypes.CDLL(library).tv_biquad
        pointer = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
        function.argtypes = [pointer, pointer, ctypes.c_long, ctypes.c_int, pointer, pointer, ctypes.c_long, ctypes.c_long]
        function.restype = None
        _native = function
    except Exception:                                    # any trouble with the compiler or the library: use the slower path
        return None
    return _native


def _block_biquad(x: np.ndarray, b: np.ndarray, a: np.ndarray, block: int) -> np.ndarray:
    """One biquad whose coefficients change every `block` samples; state carries across blocks."""
    native = _native_biquad()
    if native is not None:
        source = np.ascontiguousarray(x, dtype=np.float64)
        out = np.empty_like(source)
        native(source, out, len(source), source.shape[1] if source.ndim == 2 else 1, np.ascontiguousarray(b, dtype=np.float64),
               np.ascontiguousarray(a, dtype=np.float64), len(b), block)
        return out
    out = np.empty_like(x, dtype=np.float64)
    state = np.zeros((2, x.shape[1])) if x.ndim == 2 else np.zeros(2)
    for i in range(len(b)):
        start = i * block
        out[start:start + block], state = signal.lfilter(b[i], a[i], x[start:start + block], axis=0, zi=state)
    return out


def tv_filter(x: np.ndarray, kind: str, freq: np.ndarray, q=0.7071, sr: int = SR, poles: int = 2,
              block: int = TV_BLOCK) -> np.ndarray:
    """Filter whose cutoff (and optionally q) follows a per-sample curve.
    Coefficients update once per block and the filter state carries across blocks."""
    n = len(x)
    freq = np.asarray(freq)
    if freq.ndim == 0 or np.ptp(freq) < 1e-6 * float(np.mean(freq)) and np.isscalar(q):
        return static_filter(x, kind, float(np.mean(freq)), float(np.mean(q)), 0.0, sr, poles)
    starts = np.arange(0, n, block)
    centers = np.minimum(starts + block // 2, n - 1)
    q_curve = q if np.isscalar(q) else np.asarray(q)[centers]
    b, a = biquad(kind, freq[centers], q_curve, 0.0, sr)
    out = np.asarray(x, dtype=np.float64)
    for _ in range(max(1, poles // 2)):
        out = _block_biquad(out, b, a, block)
    return out.astype(np.float32)


def one_pole_smooth(x: np.ndarray, seconds: float, sr: int = SR) -> np.ndarray:
    if seconds <= 0 or len(x) == 0:
        return x
    k = np.exp(-1.0 / (seconds * sr))
    state = np.asarray(x[0] * k, dtype=float)[None]
    if len(x) <= 2 * STREAM_CHUNK:
        return signal.lfilter([1 - k], [1, -k], x, axis=0, zi=state)[0]
    out = np.empty(x.shape, dtype=np.float32)           # long curves: filtered in pieces, kept in single precision
    for start in range(0, len(x), STREAM_CHUNK):
        out[start:start + STREAM_CHUNK], state = signal.lfilter([1 - k], [1, -k], x[start:start + STREAM_CHUNK], axis=0, zi=state)
    return out


def chunked(x: np.ndarray, function, size: int = SR * 12, context: int = 1024) -> np.ndarray:
    """Apply a short-memory function piece by piece so long mixes do not need several times their size in RAM."""
    if len(x) <= size + 2 * context:
        return function(x)[:len(x)]
    out = np.empty_like(x)
    for start in range(0, len(x), size):
        a, b = max(0, start - context), min(len(x), start + size + context)
        take = min(size, len(x) - start)
        out[start:start + take] = function(x[a:b])[start - a:start - a + take]
    return out


def oversampled(x: np.ndarray, function, factor: int = 4) -> np.ndarray:
    """Run a nonlinearity at a higher rate so its harmonics do not fold back as aliasing."""
    def run(part):
        up = signal.resample_poly(part, factor, 1, axis=0)
        return signal.resample_poly(function(up), 1, factor, axis=0)[:len(part)]
    return chunked(x, run)


def peak_envelope(x: np.ndarray, factor: int = TRUE_PEAK_OVERSAMPLE) -> np.ndarray:
    """Largest inter-sample magnitude around each sample (all channels): what a true-peak meter sees."""
    def run(part):
        up = np.abs(signal.resample_poly(part, factor, 1, axis=0))
        if up.ndim == 2:
            up = up.max(axis=1)
        return up[:len(part) * factor].reshape(len(part), factor).max(axis=1)
    mono_shape = np.empty(len(x), dtype=np.float32)
    if len(x) <= SR * 14:
        return run(x)
    for start in range(0, len(x), SR * 12):
        a, b = max(0, start - 1024), min(len(x), start + SR * 12 + 1024)
        take = min(SR * 12, len(x) - start)
        mono_shape[start:start + take] = run(x[a:b])[start - a:start - a + take]
    return mono_shape


# ---------------------------------------------------------------- loudness

def _k_weighting(sr: int) -> np.ndarray:
    """BS.1770 pre-filter: high shelf (+4 dB above ~1.7 kHz) followed by a ~38 Hz high-pass."""
    shelf = sos_of("highshelf", 1681.97, 0.7071, 3.99984, sr)
    high = sos_of("hp", 38.1355, 0.5003, 0.0, sr)
    return np.concatenate([shelf, high])


def block_loudness(x: np.ndarray, sr: int = SR, block_s: float = LUFS_BLOCK_S, hop_s: float = LUFS_HOP_S) -> np.ndarray:
    """K-weighted loudness (LUFS) of overlapping blocks. Mono counts as one channel.
    The signal is filtered and squared piece by piece; only the per-hop energies are kept."""
    hop, per_block = int(hop_s * sr), max(1, int(round(block_s / hop_s)))
    sos = _k_weighting(sr)
    channels = x.shape[1] if x.ndim == 2 else 1
    state = np.zeros((len(sos), 2, channels))
    hops = np.zeros(len(x) // hop + 1)
    step = hop * max(1, STREAM_CHUNK // hop)
    ringing = False
    for start in range(0, len(x), step):
        piece = x[start:start + step].reshape(-1, channels)
        if not ringing and not piece.any():
            continue
        weighted, state = signal.sosfilt(sos, piece, axis=0, zi=state)
        ringing = bool(np.abs(state).max() > 1e-9)
        energy = np.sum(weighted * weighted, axis=1)
        full = len(energy) // hop
        first = start // hop
        if full:
            hops[first:first + full] = energy[:full * hop].reshape(full, hop).sum(axis=1)
        if len(energy) > full * hop:
            hops[first + full] = energy[full * hop:].sum()
    total = np.concatenate([[0.0], np.cumsum(hops)])
    count = max(1, len(x) // hop - per_block + 1)
    mean_square = (total[per_block:per_block + count] - total[:count]) / (per_block * hop)
    return -0.691 + 10.0 * np.log10(np.maximum(mean_square, 1e-12))


def lufs_of_blocks(blocks: np.ndarray) -> float:
    """Gated integrated loudness (ITU-R BS.1770-4) from 400 ms block loudness values."""
    power = 10.0 ** ((blocks + 0.691) / 10.0)
    keep = blocks > LUFS_ABS_GATE
    if not keep.any():
        return -70.0
    relative = -0.691 + 10.0 * np.log10(power[keep].mean()) + LUFS_REL_GATE
    keep &= blocks > relative
    return float(-0.691 + 10.0 * np.log10(power[keep].mean())) if keep.any() else -70.0


def loud_part_of_blocks(blocks: np.ndarray, percentile: float = 95.0) -> float:
    active = blocks[blocks > LUFS_ABS_GATE]
    return float(np.percentile(active, percentile)) if len(active) else -70.0


def integrated_lufs(x: np.ndarray, sr: int = SR) -> float:
    return lufs_of_blocks(block_loudness(x, sr))


def loud_part_lufs(x: np.ndarray, sr: int = SR, percentile: float = 95.0) -> float:
    """Loudness of the loud moments of a stem. Unlike the integrated value this does not sink when
    the part plays rarely, so sparse hits and sustained pads can share one balance scale."""
    return loud_part_of_blocks(block_loudness(x, sr), percentile)


def true_peak_db(x: np.ndarray) -> float:
    return float(lin_to_db(np.max(peak_envelope(x)) if len(x) else 0.0))
