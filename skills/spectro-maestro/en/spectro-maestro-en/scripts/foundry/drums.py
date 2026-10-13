# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Synthesised drum machines and transition effects.

The classic machines are rebuilt from their published circuits rather than sampled: pitch-swept
sine kicks, tone-plus-noise snares, six detuned square oscillators for metallic hats (808),
bursts of filtered noise for claps. Each function returns one mono hit at full velocity."""
from __future__ import annotations

import numpy as np

from . import dsp
from .dsp import SR

METAL_RATIOS = (1.0, 1.4831, 1.8002, 2.5461, 2.6302, 3.8967)    # 808 cymbal oscillator bank, relative
METAL_BASE_HZ = 205.3


def _n(seconds: float) -> int:
    return int(seconds * SR)


def _decay(n: int, seconds: float) -> np.ndarray:
    """Envelope that falls by 30 dB over `seconds`: about how long a hit stays audible in a mix."""
    return np.exp(-3.454 * np.arange(n) / (max(seconds, 1e-4) * SR))


def _normalise(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    return x * (peak / (np.max(np.abs(x)) + 1e-12))


def _sweep(n: int, start_hz: float, end_hz: float, seconds: float, shape: float = 1.0) -> np.ndarray:
    """Exponential pitch fall from start to end, the core of every analogue kick and tom."""
    t = np.arange(n) / SR
    return end_hz + (start_hz - end_hz) * np.exp(-t / max(seconds, 1e-4) * shape)


def kick(p: dict, rng) -> np.ndarray:
    """Sine with a fast downward pitch sweep, a click, and optional overdrive."""
    n = _n(p.get("length", 1.8 * p.get("decay", 0.45)))
    freq = _sweep(n, p.get("start_hz", 240.0), p.get("tune_hz", 50.0), p.get("sweep", 0.035))
    body = np.sin(2 * np.pi * dsp.phase_of(freq, n)) * _decay(n, p.get("decay", 0.45))
    click_n = _n(0.004)
    click = np.zeros(n)
    click[:click_n] = dsp.white_noise(click_n, rng) * np.linspace(1, 0, click_n) ** 2
    click = dsp.static_filter(click, "hp", p.get("click_hz", 2500.0))
    out = body + p.get("click", 0.3) * click
    drive = p.get("drive", 0.0)
    if drive > 0:
        gain = 1.0 + drive * 12.0
        out = dsp.oversampled(out, lambda s: np.tanh(s * gain) if p.get("clip", "soft") == "soft"
                              else np.clip(s * gain, -1.0, 1.0))
        if p.get("tail_lp"):
            out = dsp.static_filter(out, "lp", p["tail_lp"])
    return _normalise(dsp.fade_edges(out, SR, 0.0005))


def snare(p: dict, rng) -> np.ndarray:
    """Two pitch-dropping tones for the shell plus band-limited noise for the snares."""
    n = _n(p.get("length", 1.8 * p.get("noise_decay", 0.2)))
    tone_hz = p.get("tune_hz", 185.0)
    shell = sum(np.sin(2 * np.pi * dsp.phase_of(_sweep(n, hz * 1.6, hz, 0.012), n)) * _decay(n, decay) * level
                for hz, decay, level in ((tone_hz, p.get("tone_decay", 0.12), 1.0), (tone_hz * 1.78, 0.07, 0.6)))
    noise = dsp.white_noise(n, rng)
    noise = dsp.static_filter(noise, "hp", p.get("noise_hp", 1200.0))
    noise = dsp.static_filter(noise, "lp", p.get("noise_lp", 9000.0))
    noise *= _decay(n, p.get("noise_decay", 0.2))
    out = p.get("tone", 0.6) * shell + p.get("snappy", 0.8) * noise
    if p.get("drive", 0.0) > 0:
        out = np.tanh(out * (1.0 + p["drive"] * 6.0))
    return _normalise(dsp.fade_edges(out, SR, 0.0005))


def clap(p: dict, rng) -> np.ndarray:
    """Several short noise bursts a few milliseconds apart, then a longer tail: many hands, one room."""
    n = _n(p.get("length", 1.8 * p.get("decay", 0.25) + 0.05))
    noise = dsp.static_filter(dsp.white_noise(n, rng), "bp", p.get("tone_hz", 1100.0), 1.4)
    noise = dsp.static_filter(noise, "hp", 500.0)
    env = np.zeros(n)
    spacing = p.get("spacing", 0.011)
    for index in range(int(p.get("bursts", 3))):
        start = _n(index * spacing)
        burst = _decay(n - start, 0.02)
        env[start:] = np.maximum(env[start:], burst * (0.7 + 0.1 * index))
    tail_start = _n(int(p.get("bursts", 3)) * spacing)
    env[tail_start:] = np.maximum(env[tail_start:], _decay(n - tail_start, p.get("decay", 0.25)))
    return _normalise(dsp.fade_edges(noise * env, SR, 0.0005))


def _metal(n: int, tune: float, rng) -> np.ndarray:
    return sum(dsp.osc("square", METAL_BASE_HZ * tune * ratio, n, SR, float(rng.uniform())) for ratio in METAL_RATIOS)


def hat(p: dict, rng) -> np.ndarray:
    """Metallic oscillator bank and noise through a high band; the decay decides closed or open."""
    n = _n(p.get("length", max(0.06, p.get("decay", 0.05) * 1.8)))
    metal = _metal(n, p.get("tune", 1.0), rng) / len(METAL_RATIOS)
    mix = p.get("metal", 0.6) * metal + (1.0 - p.get("metal", 0.6)) * dsp.white_noise(n, rng)
    mix = dsp.static_filter(mix, "bp", p.get("band_hz", 8500.0), 0.6)
    mix = dsp.static_filter(mix, "hp", p.get("hp_hz", 5000.0), 0.7071, 0.0, SR, 2)
    return _normalise(dsp.fade_edges(mix * _decay(n, p.get("decay", 0.05)), SR, 0.0003))


def cymbal(p: dict, rng) -> np.ndarray:
    """Crash or ride: the same metallic bank with a long tail whose top end fades first."""
    n = _n(p.get("length", 1.8 * p.get("decay", 1.6)))
    metal = _metal(n, p.get("tune", 1.3), rng) / len(METAL_RATIOS)
    mix = p.get("metal", 0.45) * metal + (1.0 - p.get("metal", 0.45)) * dsp.white_noise(n, rng)
    mix = dsp.static_filter(mix, "hp", p.get("hp_hz", 3500.0), 0.7071, 0.0, SR, 4)
    cutoff = 16000.0 * _decay(n, p.get("decay", 1.6) * 3.0) + 5000.0
    mix = dsp.tv_filter(mix, "lp", cutoff, 0.7071, SR, 2, 256)
    env = _decay(n, p.get("decay", 1.6))
    attack = _n(p.get("attack", 0.001))
    env[:attack] *= np.linspace(0.0, 1.0, attack)
    return _normalise(dsp.fade_edges(mix * env, SR, 0.002))


def tom(p: dict, rng) -> np.ndarray:
    n = _n(p.get("length", 1.8 * p.get("decay", 0.3)))
    hz = p.get("tune_hz", 110.0)
    body = np.sin(2 * np.pi * dsp.phase_of(_sweep(n, hz * 1.8, hz, 0.03), n)) * _decay(n, p.get("decay", 0.3))
    noise = dsp.static_filter(dsp.white_noise(n, rng), "lp", 2500.0) * _decay(n, 0.03)
    return _normalise(dsp.fade_edges(body + 0.15 * noise, SR, 0.0005))


def rim(p: dict, rng) -> np.ndarray:
    """Rimshot / clave: a few very short resonant pings."""
    n = _n(p.get("length", 0.12))
    out = sum(np.sin(2 * np.pi * hz * np.arange(n) / SR) * _decay(n, decay)
              for hz, decay in ((p.get("tune_hz", 1700.0), 0.03), (p.get("tune_hz", 1700.0) * 0.48, 0.02)))
    out += 0.3 * dsp.white_noise(n, rng) * _decay(n, 0.004)
    return _normalise(dsp.fade_edges(out, SR, 0.0003))


def cowbell(p: dict, rng) -> np.ndarray:
    """808 cowbell: two square oscillators a tritone-ish apart through a band-pass."""
    n = _n(p.get("length", 1.8 * p.get("decay", 0.3)))
    out = dsp.osc("square", 540.0 * p.get("tune", 1.0), n) + dsp.osc("square", 800.0 * p.get("tune", 1.0), n)
    out = dsp.static_filter(out, "bp", 2640.0 * p.get("tune", 1.0), 1.5)
    env = 0.7 * _decay(n, 0.04) + 0.3 * _decay(n, p.get("decay", 0.3))
    return _normalise(dsp.fade_edges(out * env, SR, 0.0003))


def shaker(p: dict, rng) -> np.ndarray:
    n = _n(p.get("length", 0.09))
    noise = dsp.static_filter(dsp.white_noise(n, rng), "hp", p.get("hp_hz", 5000.0), 0.7071, 0.0, SR, 4)
    attack = _n(0.012)
    env = _decay(n, p.get("decay", 0.06))
    env[:attack] *= np.linspace(0.0, 1.0, attack)
    return _normalise(noise * env)


def metal_hit(p: dict, rng) -> np.ndarray:
    """Industrial percussion: inharmonic ring-modulated partials through overdrive."""
    n = _n(p.get("length", 1.8 * p.get("decay", 0.35)))
    base = p.get("tune_hz", 320.0)
    partials = sum(np.sin(2 * np.pi * base * ratio * np.arange(n) / SR + rng.uniform(0, 6.28)) *
                   _decay(n, p.get("decay", 0.35) / (1 + 0.3 * i))
                   for i, ratio in enumerate((1.0, 2.76, 5.4, 8.93, 11.34)))
    noise = dsp.static_filter(dsp.white_noise(n, rng), "bp", base * 6, 2.0) * _decay(n, 0.05)
    return _normalise(dsp.fade_edges(np.tanh((partials / 3 + noise) * (1 + p.get("drive", 0.5) * 8)), SR, 0.0005))


# ---------------------------------------------------------------- transition effects (long, duration-driven)

def riser(p: dict, rng, seconds: float) -> np.ndarray:
    """Noise through a band-pass that climbs, plus a rising tone: tension before a section change."""
    n = _n(seconds)
    t = np.linspace(0.0, 1.0, n)
    cutoff = p.get("from_hz", 300.0) * (p.get("to_hz", 9000.0) / p.get("from_hz", 300.0)) ** t
    noise = dsp.tv_filter(dsp.white_noise(n, rng), "bp", cutoff, 2.5, SR, 2, 128)
    tone_hz = 110.0 * 2.0 ** (t * p.get("octaves", 2.0))
    tone = dsp.osc("saw", tone_hz, n) * 0.15 * p.get("tone", 1.0)
    return _normalise((noise + tone) * t ** p.get("curve", 2.0) * (1.0 - np.clip((t - 0.995) / 0.005, 0, 1)))


def downlifter(p: dict, rng, seconds: float) -> np.ndarray:
    n = _n(seconds)
    t = np.linspace(0.0, 1.0, n)
    cutoff = p.get("from_hz", 9000.0) * (p.get("to_hz", 200.0) / p.get("from_hz", 9000.0)) ** t
    noise = dsp.tv_filter(dsp.white_noise(n, rng), "bp", cutoff, 2.0, SR, 2, 128)
    return _normalise(dsp.fade_edges(noise * (1.0 - t) ** 1.5, SR, 0.002))


def noise_sweep(p: dict, rng, seconds: float) -> np.ndarray:
    n = _n(seconds)
    t = np.linspace(0.0, 1.0, n)
    cutoff = 400.0 * (30.0 ** t)
    noise = dsp.tv_filter(dsp.white_noise(n, rng), "lp", cutoff, 1.2, SR, 2, 128)
    return _normalise(dsp.fade_edges(noise * t ** 1.5, SR, 0.004))


def impact(p: dict, rng, seconds: float) -> np.ndarray:
    """Sub boom plus a burst of noise: marks the first beat of a big section."""
    n = _n(seconds)
    boom = np.sin(2 * np.pi * dsp.phase_of(_sweep(n, 120.0, 38.0, 0.12), n)) * dsp.exp_decay(n, min(seconds, 2.5))
    noise = dsp.static_filter(dsp.white_noise(n, rng), "lp", 5000.0) * dsp.exp_decay(n, min(seconds, 1.2))
    return _normalise(dsp.fade_edges(boom + 0.5 * noise, SR, 0.001))


def sub_drop(p: dict, rng, seconds: float) -> np.ndarray:
    n = _n(seconds)
    freq = _sweep(n, 90.0, 30.0, seconds / 3)
    return _normalise(dsp.fade_edges(np.sin(2 * np.pi * dsp.phase_of(freq, n)) * dsp.exp_decay(n, seconds), SR, 0.003))


def reverse_crash(p: dict, rng, seconds: float) -> np.ndarray:
    return cymbal({"length": seconds, "decay": seconds * 0.6, "tune": 1.3}, rng)[::-1].copy()


def crash_long(p: dict, rng, seconds: float) -> np.ndarray:
    return cymbal(p, rng)


HIT_ENGINES = {"kick": kick, "snare": snare, "clap": clap, "hat": hat, "cymbal": cymbal, "tom": tom, "rim": rim,
               "cowbell": cowbell, "shaker": shaker, "metal": metal_hit}
SWEEP_ENGINES = {"riser": riser, "downlifter": downlifter, "noise_sweep": noise_sweep, "impact": impact,
                 "sub_drop": sub_drop, "reverse_crash": reverse_crash, "crash": crash_long}
