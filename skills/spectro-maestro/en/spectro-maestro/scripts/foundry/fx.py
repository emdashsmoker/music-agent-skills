# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Effects used as track inserts, send returns and on the master bus.

`apply_chain(x, [{"fx": "eq", ...}, ...], ctx)` runs a list of effect dicts in order.
Dynamics use vectorised detectors: release is a running maximum in the dB domain (exact for a
linear-in-dB release), so no per-sample loop is needed even on a fifteen minute mix."""
from __future__ import annotations

import numpy as np
from scipy import ndimage, signal

from . import dsp
from .dsp import SR

NOTE_VALUES = {"1/1": 4.0, "1/2": 2.0, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125}


class FxContext:
    """What an effect may need to know about the song."""
    def __init__(self, bpm: float, seed: int = 1):
        self.bpm = bpm
        self.seed = seed

    def beats_to_seconds(self, beats: float) -> float:
        return beats * 60.0 / self.bpm

    def time_of(self, value) -> float:
        """Seconds from 0.25 (seconds), '1/8' (note value), '1/8d' (dotted) or '1/8t' (triplet)."""
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value)
        scale = 1.5 if text.endswith("d") else 2.0 / 3.0 if text.endswith("t") else 1.0
        return self.beats_to_seconds(NOTE_VALUES[text.rstrip("dt")] * scale)


# ---------------------------------------------------------------- tone

def eq(x, bands, **_):
    """bands: [[kind, freq, gain_db, q], ...] with kind in peak / lowshelf / highshelf / hp / lp / notch."""
    for band in bands:
        kind, freq = band[0], float(band[1])
        gain = float(band[2]) if len(band) > 2 else 0.0
        q = float(band[3]) if len(band) > 3 else 0.7071
        x = dsp.static_filter(x, kind, freq, q, gain, SR, 4 if kind in ("hp", "lp") and len(band) > 4 else 2)
    return x


def hpf(x, freq=100.0, poles=2, **_):
    return dsp.static_filter(x, "hp", freq, 0.7071, 0.0, SR, poles)


def lpf(x, freq=8000.0, poles=2, **_):
    return dsp.static_filter(x, "lp", freq, 0.7071, 0.0, SR, poles)


def tilt(x, db_per_octave=0.0, pivot=1000.0, **_):
    """Gentle overall brightness change: opposite shelves around a pivot."""
    amount = db_per_octave * 3.0
    x = dsp.static_filter(x, "lowshelf", pivot / 3.0, 0.5, -amount)
    return dsp.static_filter(x, "highshelf", pivot * 3.0, 0.5, amount)


# ---------------------------------------------------------------- dynamics

def _release_follow(level_db: np.ndarray, release_s: float) -> np.ndarray:
    """Instant attack, then fall at a constant dB rate. Running-maximum identity, no loop."""
    slope = 60.0 / (max(release_s, 1e-3) * SR)          # dB per sample
    if len(level_db) <= FOLLOW_CHUNK:
        ramp = slope * np.arange(len(level_db))
        return np.maximum.accumulate(level_db + ramp) - ramp
    out = np.empty(len(level_db), dtype=np.float32)      # long curves: the same identity piece by piece
    ramp = slope * np.arange(FOLLOW_CHUNK)
    carried = -np.inf                                    # the envelope just before the piece, already one step decayed
    for start in range(0, len(level_db), FOLLOW_CHUNK):
        piece = level_db[start:start + FOLLOW_CHUNK].astype(np.float64)
        local = ramp[:len(piece)]
        lifted = piece + local
        lifted[0] = max(lifted[0], carried)
        follow = np.maximum.accumulate(lifted) - local
        out[start:start + len(piece)] = follow
        carried = follow[-1] - slope
    return out


FOLLOW_CHUNK = 1 << 20


def gain_reduction_db(x, threshold=-18.0, ratio=4.0, attack=0.01, release=0.15, knee=6.0, key=None) -> np.ndarray:
    """Per-sample gain change (<= 0 dB) of a feed-forward compressor. `key` replaces the detector signal."""
    detector = dsp.to_mono(np.abs(x if key is None else key)) if (x if key is None else key).ndim == 2 \
        else np.abs(x if key is None else key)
    level = dsp.lin_to_db(detector, 1e-6)
    level = dsp.one_pole_smooth(_release_follow(level, release), attack)
    over = level - threshold
    if knee > 0:
        over = np.where(over < -knee / 2, 0.0, np.where(over > knee / 2, over, (over + knee / 2) ** 2 / (2 * knee)))
    else:
        over = np.maximum(over, 0.0)
    return -over * (1.0 - 1.0 / ratio)


def comp(x, threshold=-18.0, ratio=4.0, attack=0.01, release=0.15, knee=6.0, makeup=0.0, mix=1.0, **_):
    reduction = gain_reduction_db(x, threshold, ratio, attack, release, knee)
    gain = dsp.db_to_lin(reduction + makeup)
    wet = (x.T * gain).T
    return wet if mix >= 1.0 else mix * wet + (1.0 - mix) * x


def gate(x, threshold=-40.0, release=0.08, **_):
    level = _release_follow(dsp.lin_to_db(dsp.to_mono(np.abs(x)), 1e-6), release)
    gain = dsp.one_pole_smooth((level > threshold).astype(float), 0.002)
    return (x.T * gain).T


def soft_clip(x, drive_db=0.0, **_):
    gain = float(dsp.db_to_lin(drive_db))
    return dsp.oversampled(x, lambda s: np.tanh(s * gain))


def limiter_reduction(peak: np.ndarray, ceiling_db: float = -1.0, lookahead: float = 0.005, release: float = 0.1) -> np.ndarray:
    """Gain reduction in dB (>= 0) that keeps a signal with this peak envelope under the ceiling."""
    window = max(1, int(lookahead * SR))
    needed = np.maximum(dsp.lin_to_db(peak, 1e-9) - ceiling_db, 0.0)
    held = ndimage.maximum_filter1d(needed, 2 * window + 1, mode="constant")    # see every peak one window early
    held = _release_follow(held, release * 4.0)
    return ndimage.uniform_filter1d(held, window, mode="nearest")               # ramp in over the look-ahead


def limiter(x, ceiling_db=-1.0, lookahead=0.005, release=0.1, **_):
    """Look-ahead limiter on inter-sample peaks. Returns (audio, gain change in dB per sample)."""
    reduction = limiter_reduction(dsp.peak_envelope(x), ceiling_db, lookahead, release)
    return (x.T * dsp.db_to_lin(-reduction)).T, -reduction


# ---------------------------------------------------------------- colour

def dist(x, drive=0.5, tone=6000.0, mix=1.0, kind="tanh", **_):
    gain = 1.0 + drive * 20.0
    shaper = {"tanh": lambda s: np.tanh(s * gain) / np.tanh(gain),
              "hard": lambda s: np.clip(s * gain, -1.0, 1.0),
              "fold": lambda s: np.sin(s * gain * np.pi / 2)}[kind]
    wet = dsp.static_filter(dsp.oversampled(x, shaper), "lp", tone)
    return mix * wet + (1.0 - mix) * x


def crush(x, bits=8, rate=11025.0, mix=1.0, **_):
    hold = max(1, int(round(SR / rate)))
    index = (np.arange(len(x)) // hold) * hold
    steps = 2.0 ** (bits - 1)
    wet = np.round(x[index] * steps) / steps
    return mix * wet + (1.0 - mix) * x


def chorus(x, rate=0.8, depth_ms=3.0, delay_ms=12.0, mix=0.5, voices=2, ctx=None, **_):
    """Modulated short delays, a different phase on each side: widens and thickens."""
    stereo = dsp.to_stereo(x).astype(float)
    n = len(stereo)
    position = np.arange(n, dtype=float)
    wet = np.zeros_like(stereo)
    for channel in range(2):
        for voice in range(voices):
            phase = 2 * np.pi * (voice / voices + channel * 0.25)
            delay = (delay_ms + depth_ms * np.sin(2 * np.pi * rate * (1 + 0.13 * voice) * position / SR + phase)) * SR / 1000
            wet[:, channel] += np.interp(position - delay, position, stereo[:, channel], left=0.0)
    return (1.0 - mix) * stereo + mix * wet / voices


def flanger(x, rate=0.25, depth_ms=2.0, delay_ms=2.5, feedback=0.5, mix=0.5, **_):
    stereo = dsp.to_stereo(x).astype(float)
    position = np.arange(len(stereo), dtype=float)
    wet = stereo.copy()
    for channel in range(2):
        delay = (delay_ms + depth_ms * np.sin(2 * np.pi * rate * position / SR + channel * 1.2)) * SR / 1000
        tap = stereo[:, channel]
        for order in range(3):                          # truncated feedback series
            tap = np.interp(position - delay, position, tap, left=0.0)
            wet[:, channel] += feedback ** order * tap
    return (1.0 - mix) * stereo + mix * wet * 0.5


def phaser(x, rate=0.3, low=400.0, high=3000.0, mix=0.5, **_):
    sweep = low * (high / low) ** (0.5 + 0.5 * np.sin(2 * np.pi * rate * np.arange(len(x)) / SR))
    wet = dsp.tv_filter(x, "notch", sweep, 1.5, SR, 2, 64)
    wet = dsp.tv_filter(wet, "notch", sweep * 2.7, 1.5, SR, 2, 64)
    return (1.0 - mix) * x + mix * wet


def tremolo(x, rate="1/8", depth=0.5, ctx=None, **_):
    seconds = ctx.time_of(rate) if ctx else 0.25
    lfo = 1.0 - depth * (0.5 + 0.5 * np.cos(2 * np.pi * np.arange(len(x)) / (seconds * SR)))
    return (x.T * lfo).T


def width(x, amount=1.0, mono_below=0.0, **_):
    """Scale the side signal; optionally fold everything below a frequency to mono (club-safe low end)."""
    stereo = dsp.to_stereo(x)
    kind = np.float32 if stereo.dtype == np.float32 else np.float64
    side = (stereo[:, 0] - stereo[:, 1]) * kind(0.5)
    if mono_below > 0:
        side = np.asarray(dsp.static_filter(side, "hp", mono_below, 0.7071, 0.0, SR, 4), dtype=kind)
    side *= kind(amount)
    out = np.empty(stereo.shape, dtype=kind)
    np.add(stereo[:, 0], stereo[:, 1], out=out[:, 0])
    out[:, 0] *= kind(0.5)                               # mid
    np.subtract(out[:, 0], side, out=out[:, 1])
    out[:, 0] += side
    return out


def lofi(x, wow=0.3, noise_db=-48.0, top=7000.0, ctx=None, **_):
    """Tape/VHS wear: slow pitch wobble, rolled-off top, hiss."""
    rng = np.random.default_rng((ctx.seed if ctx else 1) + 7919)
    position = np.arange(len(x), dtype=float)
    wobble = wow * 0.002 * SR * (np.sin(2 * np.pi * 0.6 * position / SR) + 0.4 * np.sin(2 * np.pi * 6.3 * position / SR))
    read = position - wobble - wobble.min()
    stereo = dsp.to_stereo(x).astype(float)
    wet = np.stack([np.interp(read, position, stereo[:, c], left=0.0) for c in range(2)], axis=1)
    wet = dsp.static_filter(wet, "lp", top, 0.7071, 0.0, SR, 4)
    hiss = dsp.static_filter(rng.standard_normal((len(x), 2)), "hp", 2000.0) * float(dsp.db_to_lin(noise_db))
    return wet + hiss


# ---------------------------------------------------------------- time

def delay(x, time="1/8d", feedback=0.4, mix=0.3, pingpong=True, damp=5000.0, lowcut=250.0, ctx=None, **_):
    """Feedback delay. Processed one delay-length chunk at a time, each chunk fed by the previous one."""
    seconds = ctx.time_of(time) if ctx else float(time)
    d = max(1, int(seconds * SR))
    dry = np.asarray(dsp.to_stereo(x), dtype=np.float32)
    n = len(dry)
    out = np.zeros((n, 2), dtype=np.float32)
    previous = np.zeros((d, 2))
    damp_sos = np.concatenate([dsp.sos_of("lp", damp), dsp.sos_of("hp", lowcut)])
    state = np.zeros((2, 2, 2))
    for start in range(0, n, d):
        chunk = np.zeros((d, 2))
        take = min(d, n - start)
        if pingpong:                                     # the input enters on the left, the echoes cross sides
            chunk[:take, 0] = dry[start:start + take].mean(axis=1)
        else:
            chunk[:take] = dry[start:start + take]
        fed, state = signal.sosfilt(damp_sos, previous[:, ::-1] if pingpong else previous, axis=0, zi=state)
        current = chunk + feedback * fed
        length = min(d, n - start - d)                   # what is written now is heard one delay time later
        if length > 0:
            out[start + d:start + d + length] = current[:length]
        previous = current
    if mix >= 1.0:
        return out
    out *= np.float32(mix)
    out += dry * np.float32(1.0 - mix)
    return out


def reverb_ir(decay=2.0, predelay=0.02, damp=6000.0, lowcut=200.0, size=1.0, seed=1) -> np.ndarray:
    """Synthetic stereo impulse response: sparse early reflections, then noise whose highs die first."""
    rng = np.random.default_rng(seed)
    n = int((decay * 1.2 + predelay) * SR)
    t = np.arange(n) / SR
    tail = rng.standard_normal((n, 2))
    bright = dsp.static_filter(tail, "hp", damp) * np.exp(-6.908 * t / (decay * 0.45))[:, None]
    dark = dsp.static_filter(tail, "lp", damp) * np.exp(-6.908 * t / decay)[:, None]
    tail = dsp.static_filter(bright + dark, "hp", lowcut, 0.7071, 0.0, SR, 4)
    build = np.clip(t / (0.03 * size), 0.0, 1.0)[:, None]          # diffuse onset instead of a click
    ir = tail * build
    for _ in range(int(8 * size)):
        at = int(rng.uniform(0.004, 0.06 * size) * SR)
        ir[at, int(rng.integers(2))] += rng.uniform(0.4, 1.0) * rng.choice([-1.0, 1.0]) * 4.0
    shift = int(predelay * SR)
    ir = np.concatenate([np.zeros((shift, 2)), ir])[:n]
    return ir / np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True))


REVERB_BLOCK = 1 << 20          # samples convolved at a time; keeps a long song from needing several full-length copies


def reverb(x, decay=2.0, predelay=0.02, damp=6000.0, lowcut=200.0, size=1.0, mix=0.25, ctx=None, **_):
    ir = reverb_ir(decay, predelay, damp, lowcut, size, (ctx.seed if ctx else 1) + 101)
    dry = np.asarray(dsp.to_stereo(x), dtype=np.float32)
    n = len(dry)
    wet = np.zeros((n, 2), dtype=np.float32)
    for start in range(0, n, REVERB_BLOCK):
        block = dry[start:start + REVERB_BLOCK]
        if not np.any(block):
            continue
        for c in range(2):
            piece = signal.oaconvolve(block[:, c].astype(np.float64), ir[:, c])
            end = min(n, start + len(piece))
            wet[start:end, c] += piece[:end - start]
    if mix >= 1.0:
        return wet
    wet *= np.float32(mix)
    wet += dry * np.float32(1.0 - mix)
    return wet


def gated_reverb(x, decay=1.2, hold=0.18, mix=0.5, ctx=None, **_):
    """The 80s snare: a big room chopped off abruptly."""
    wet = reverb(x, decay, 0.0, 9000.0, 300.0, 1.2, 1.0, ctx)
    key = dsp.to_mono(np.abs(dsp.to_stereo(x)))
    opened = ndimage.maximum_filter1d((key > 0.05 * key.max()).astype(float), int(hold * SR), origin=-int(hold * SR) // 2 + 1)
    return dsp.to_stereo(x) * (1.0 - mix * 0.3) + (wet.T * dsp.one_pole_smooth(opened, 0.004)).T * mix


def duck_shape(n: int, trigger_samples, attack=0.004, release=0.22, hold=0.02) -> np.ndarray:
    """How far the ducking is engaged at every sample (0 = not at all, 1 = fully): down at each trigger,
    back along a smooth curve. One shape serves every depth, so a mix keeps one array per release time."""
    span = int((attack + hold + release) * SR)
    t = np.arange(span) / SR
    shape = np.where(t < attack, t / attack, np.where(t < attack + hold, 1.0,
                     np.clip(1.0 - (t - attack - hold) / release, 0.0, 1.0) ** 2)).astype(np.float32)
    engaged = np.zeros(n, dtype=np.float32)
    for at in trigger_samples:
        at = int(at)
        if 0 <= at < n:
            end = min(n, at + span)
            np.maximum(engaged[at:end], shape[:end - at], out=engaged[at:end])
    return engaged


def apply_duck(x: np.ndarray, engaged: np.ndarray, depth_db: float) -> np.ndarray:
    """Volume ducking (the sidechain pump, driven by note positions instead of an audio detector), in place when
    `x` is single precision."""
    out = x if x.dtype == np.float32 and x.flags.writeable else np.array(x, dtype=np.float32)
    scale = np.float32(depth_db / 20.0)
    for start in range(0, len(out), DUCK_CHUNK):
        gain = np.power(np.float32(10.0), scale * engaged[start:start + DUCK_CHUNK])
        out[start:start + DUCK_CHUNK] *= gain if out.ndim == 1 else gain[:, None]
    return out


def duck_curve(n: int, trigger_samples, depth_db=-9.0, attack=0.004, release=0.22, hold=0.02) -> np.ndarray:
    """Gain curve of volume ducking for one depth."""
    return np.power(np.float32(10.0), np.float32(depth_db / 20.0) * duck_shape(n, trigger_samples, attack, release, hold))


DUCK_CHUNK = 1 << 20

EFFECTS = {"eq": eq, "hpf": hpf, "lpf": lpf, "tilt": tilt, "comp": comp, "gate": gate, "soft_clip": soft_clip,
           "dist": dist, "crush": crush, "chorus": chorus, "flanger": flanger, "phaser": phaser, "tremolo": tremolo,
           "width": width, "lofi": lofi, "delay": delay, "reverb": reverb, "gated_reverb": gated_reverb}


def apply_chain(x: np.ndarray, chain: list, ctx: FxContext) -> np.ndarray:
    for step in chain or []:
        params = dict(step)
        name = params.pop("fx", None)
        if name not in EFFECTS:
            raise ValueError(f"unknown effect {name!r}; known: {sorted(EFFECTS)}")
        x = EFFECTS[name](x, ctx=ctx, **params)
    return x
