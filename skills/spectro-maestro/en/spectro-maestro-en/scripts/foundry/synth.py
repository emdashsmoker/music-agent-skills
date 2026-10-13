# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Tonal synthesis engines. A patch is a plain dict; `render_notes` turns a note list into audio.

Engines
  sub    polyphonic subtractive voice: oscillator bank (with unison), noise, filter with envelope, amp ADSR
  fm     pairs of carrier and modulator sines with an index envelope (electric pianos, bells, FM basses)
  pluck  Karplus-Strong string (guitars, picked bass, harp-like plucks)
  organ  additive drawbars
  mono   one continuous voice with glide and per-note filter envelope (TB-303 lines, reese, legato leads)"""
from __future__ import annotations

import numpy as np

from . import dsp
from .dsp import SR
from .theory import midi_to_hz

VELOCITY_STEPS = 10             # timbre is rendered at this many velocity levels; loudness stays exact
DEFAULT_AMP = (0.005, 0.2, 0.7, 0.2)
MIN_CUTOFF, MAX_CUTOFF = 30.0, 18000.0
RES_Q_RANGE = 14.0              # resonance 0..1 maps to Q 0.7..14.7
MONO_BLOCK = 16                 # finer blocks: acid lines sweep a high-Q filter quickly


def _q_of(resonance: float) -> float:
    return 0.7071 + RES_Q_RANGE * float(np.clip(resonance, 0.0, 1.0)) ** 2


def _pan_gains(pan: float) -> tuple:
    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * np.pi / 4
    return float(np.cos(angle)), float(np.sin(angle))


def _osc_bank(spec: dict, freq, n: int, rng, width: float) -> np.ndarray:
    """One oscillator slot, possibly a unison stack spread across pitch and the stereo field."""
    voices = int(spec.get("voices", 1))
    spread = float(spec.get("spread", 0.0))
    base = 2.0 ** (spec.get("octave", 0) + spec.get("semi", 0) / 12.0 + spec.get("detune", 0.0) / 1200.0)
    wave = spec.get("wave", "saw")
    out = np.zeros((n, 2))
    offsets = np.linspace(-1.0, 1.0, voices) if voices > 1 else np.zeros(1)
    for index, offset in enumerate(offsets):
        # Outer voices sit further apart than inner ones, as in the hardware supersaw.
        cents = np.sign(offset) * abs(offset) ** 1.3 * spread
        f = freq * base * 2.0 ** (cents / 1200.0)
        pw = spec.get("pw", 0.5)
        if spec.get("pwm_depth"):
            pw = pw + spec["pwm_depth"] * np.sin(2 * np.pi * spec.get("pwm_rate", 0.5) * np.arange(n) / SR + index)
        if wave == "noise":
            voice = dsp.white_noise(n, rng)
        elif wave == "pulse" and not np.isscalar(pw):
            saw = dsp.osc("saw", f, n, SR, float(rng.uniform()))
            delay = np.arange(n) - pw * SR / np.maximum(f, 1.0)
            voice = saw - np.interp(delay, np.arange(n), saw)      # PWM as the difference of two saws
        else:
            voice = dsp.osc(wave, f, n, SR, float(rng.uniform()), pw)
        centre_boost = 1.0 if voices == 1 or abs(offset) > 1e-9 else 1.4
        left, right = _pan_gains(offset * width * (1 if index % 2 else -1) if voices > 1 else 0.0)
        out[:, 0] += voice * left * centre_boost
        out[:, 1] += voice * right * centre_boost
    return out * (spec.get("level", 1.0) / np.sqrt(voices))


def _pitch_curve(patch: dict, midi: float, n: int, rng) -> np.ndarray | float:
    freq = midi_to_hz(midi + patch.get("transpose", 0)) * 2.0 ** (rng.normal(0.0, patch.get("drift", 0.0)) / 1200.0)
    vibrato, bend = patch.get("vibrato"), patch.get("pitch_env")
    if not vibrato and not bend:
        return freq
    t = np.arange(n) / SR
    cents = np.zeros(n)
    if vibrato:
        onset = np.clip((t - vibrato.get("delay", 0.25)) / max(vibrato.get("fade", 0.3), 1e-3), 0.0, 1.0)
        cents += vibrato.get("depth", 10.0) * onset * np.sin(2 * np.pi * vibrato.get("rate", 5.5) * t)
    if bend:
        cents += 100.0 * bend.get("semis", 12.0) * np.exp(-t / max(bend.get("time", 0.03), 1e-4))
    return freq * 2.0 ** (cents / 1200.0)


def _apply_filter(x: np.ndarray, patch: dict, midi: float, velocity: float, gate_n: int) -> np.ndarray:
    flt = patch.get("filter")
    if not flt:
        return x
    n = len(x)
    octaves = flt.get("track", 0.0) * (midi - 60) / 12.0 + flt.get("vel", 0.0) * (velocity - 0.8) * 4.0
    cutoff = flt.get("cutoff", 2000.0) * 2.0 ** octaves
    curve = None
    if flt.get("env"):
        a, d, s, r = patch.get("fenv", (0.005, 0.25, 0.0, 0.2))
        curve = flt["env"] * dsp.adsr(n, gate_n, a, d, s, r)
    if flt.get("lfo_depth"):
        lfo = flt["lfo_depth"] * np.sin(2 * np.pi * flt.get("lfo_rate", 0.3) * np.arange(n) / SR)
        curve = lfo if curve is None else curve + lfo
    q = _q_of(flt.get("res", 0.1))
    poles = int(flt.get("poles", 4))
    kind = flt.get("type", "lp")
    if curve is None:
        return dsp.static_filter(x, kind, float(np.clip(cutoff, MIN_CUTOFF, MAX_CUTOFF)), q, 0.0, SR, poles)
    return dsp.tv_filter(x, kind, np.clip(cutoff * 2.0 ** curve, MIN_CUTOFF, MAX_CUTOFF), q, SR, poles)


def _drive(x: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return x
    gain = 1.0 + 10.0 * amount
    return np.tanh(x * gain) / np.tanh(gain)


def _voice_sub(patch: dict, midi: float, gate_n: int, n: int, velocity: float, rng) -> np.ndarray:
    freq = _pitch_curve(patch, midi, n, rng)
    width = float(patch.get("width", 0.0))
    mix = sum(_osc_bank(spec, freq, n, rng, width) for spec in patch.get("osc", [{"wave": "saw"}]))
    if patch.get("noise"):
        mix = mix + patch["noise"] * dsp.white_noise(n, rng)[:, None]
    if width <= 0:
        mix = mix[:, 0]
    mix = _apply_filter(mix * 0.5, patch, midi, velocity, gate_n)
    return _drive(mix, patch.get("drive", 0.0))


def _voice_fm(patch: dict, midi: float, gate_n: int, n: int, velocity: float, rng) -> np.ndarray:
    freq = _pitch_curve(patch, midi, n, rng)
    out = np.zeros(n)
    for op in patch.get("ops", [{"ratio": 1, "mod_ratio": 1, "index": 2.0}]):
        a, d, s, r = op.get("index_env", (0.001, 0.4, 0.2, 0.3))
        index = op.get("index", 2.0) * (0.5 + 0.5 * velocity * op.get("vel", 1.0)) * dsp.adsr(n, gate_n, a, d, s, r)
        detune = 2.0 ** (op.get("detune", 0.0) / 1200.0)
        modulator = np.sin(2 * np.pi * dsp.phase_of(freq * op.get("mod_ratio", 1.0) * detune, n))
        carrier_phase = dsp.phase_of(freq * op.get("ratio", 1.0) * detune, n)
        level = op.get("level", 1.0)
        if "decay" in op:
            level = level * dsp.exp_decay(n, op["decay"])
        out += level * np.sin(2 * np.pi * carrier_phase + index * modulator)
    return _drive(_apply_filter(out * 0.5, patch, midi, velocity, gate_n), patch.get("drive", 0.0))


def _voice_pluck(patch: dict, midi: float, gate_n: int, n: int, velocity: float, rng) -> np.ndarray:
    """Karplus-Strong: a burst of noise circulating in a delay line that loses highs on every pass."""
    freq = midi_to_hz(midi + patch.get("transpose", 0))
    period = max(2, int(round(SR / freq)))
    stretch = (SR / period) / freq            # the integer period is slightly off pitch; resample at the end
    need = int(n * stretch) + period + 8
    burst = dsp.white_noise(period, rng)
    brightness = float(np.clip(patch.get("pick", 0.6) * (0.6 + 0.5 * velocity), 0.05, 1.0))
    burst = dsp.static_filter(np.tile(burst, 3), "lp", 400.0 + 9000.0 * brightness)[-period:]
    burst -= burst.mean()
    loss = float(np.clip(patch.get("damp", 0.5), 0.0, 1.0))
    feedback = 10.0 ** (-3.0 * period / (SR * max(patch.get("decay", 2.0), 0.05)))      # -60 dB after `decay` s
    cycles = need // period + 1
    out = np.empty(cycles * period)
    current = burst
    for index in range(cycles):
        out[index * period:(index + 1) * period] = current
        shifted = np.concatenate([[current[-1]], current[:-1]])
        current = feedback * ((1.0 - loss * 0.5) * current + loss * 0.5 * shifted)
    out = np.interp(np.arange(n) * stretch, np.arange(len(out)), out)
    out /= np.max(np.abs(out)) + 1e-12
    body = float(patch.get("body", 0.0))
    if body > 0:                                         # a string's fundamental is stronger than a noise burst leaves it
        t = np.arange(n) / SR
        fundamental = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t)
        out = out + body * fundamental * dsp.exp_decay(n, patch.get("decay", 2.0))
    release = dsp.adsr(n, gate_n, 0.001, 0.01, 1.0, patch.get("release", 0.15))
    return _drive(_apply_filter(out * release, patch, midi, velocity, gate_n), patch.get("drive", 0.0))


def _voice_organ(patch: dict, midi: float, gate_n: int, n: int, velocity: float, rng) -> np.ndarray:
    freq = _pitch_curve(patch, midi, n, rng)
    out = sum(level * np.sin(2 * np.pi * dsp.phase_of(freq * ratio, n, SR, float(rng.uniform())))
              for ratio, level in patch.get("partials", [(1, 1.0), (2, 0.5), (3, 0.3)]))
    if patch.get("click"):
        click_n = min(n, int(0.01 * SR))
        out[:click_n] += patch["click"] * dsp.white_noise(click_n, rng) * np.linspace(1, 0, click_n)
    return _drive(_apply_filter(out * 0.4, patch, midi, velocity, gate_n), patch.get("drive", 0.0))


VOICES = {"sub": _voice_sub, "fm": _voice_fm, "pluck": _voice_pluck, "organ": _voice_organ}


def render_voice(patch: dict, midi: float, seconds: float, velocity: float, rng) -> np.ndarray:
    """One note of a polyphonic engine, release tail included. Mono or stereo depending on the patch."""
    a, d, s, r = patch.get("amp", DEFAULT_AMP)
    gate_n = max(1, int(seconds * SR))
    n = gate_n + int(r * SR) + 8
    body = VOICES[patch.get("engine", "sub")](patch, midi, gate_n, n, velocity, rng)
    env = dsp.adsr(n, gate_n, a, d, s, r)
    body = (body.T * env).T
    return dsp.fade_edges(body, SR, 0.001)


def render_poly(patch: dict, notes: list, seconds_per_beat: float, total_n: int, rng) -> np.ndarray:
    """Place every note of a polyphonic track. Identical notes are synthesised once and reused."""
    stereo = float(patch.get("width", 0.0)) > 0 and patch.get("engine", "sub") == "sub"
    out = np.zeros((total_n, 2) if stereo else total_n, dtype=np.float32)
    cache = {}
    curve = patch.get("vel_curve", 1.5)
    for note in notes:
        start, dur, midi, velocity = note[:4]
        level = max(1, round(velocity * VELOCITY_STEPS)) / VELOCITY_STEPS
        key = (midi, round(dur * seconds_per_beat, 4), level)
        if key not in cache:
            cache[key] = render_voice(patch, midi, key[1], level, rng).astype(np.float32)
        voice = cache[key]
        at = int(start * seconds_per_beat * SR)
        end = min(total_n, at + len(voice))
        if end > at:
            out[at:end] += voice[:end - at] * float((velocity / level) ** curve * level ** curve)
    return out


def render_mono(patch: dict, notes: list, seconds_per_beat: float, total_n: int, rng) -> np.ndarray:
    """One voice for the whole track. A note flagged 'slide' glides into the next one without retriggering
    the envelopes, which is what makes a 303 line speak. Accented notes open the filter further."""
    if not notes:
        return np.zeros(total_n, dtype=np.float32)
    glide = float(patch.get("glide", 0.06))
    a, d, s, r = patch.get("amp", (0.003, 0.2, 0.6, 0.02))
    flt = patch.get("filter", {})
    fenv_decay = float(patch.get("fenv_decay", 0.25))
    accent_at = float(patch.get("accent_at", 0.95))
    freq = np.zeros(total_n)
    amp = np.zeros(total_n)
    fenv = np.zeros(total_n)
    previous_hz, legato = None, False
    ordered = sorted(notes, key=lambda note: note[0])
    for index, note in enumerate(ordered):
        start, dur, midi, velocity = note[:4]
        flags = note[4] if len(note) > 4 else {}
        at = int(start * seconds_per_beat * SR)
        if at >= total_n:
            break
        next_at = int(ordered[index + 1][0] * seconds_per_beat * SR) if index + 1 < len(ordered) else total_n
        slide_out = bool(flags.get("slide"))
        gate_end = min(total_n, next_at if slide_out else at + max(1, int(dur * seconds_per_beat * SR)))
        tail_end = min(total_n, max(gate_end, next_at) if slide_out else min(next_at, gate_end + int(r * SR)))
        hz = midi_to_hz(midi + patch.get("transpose", 0))
        span = tail_end - at
        if span <= 0:
            continue
        if legato and previous_hz:
            t = np.arange(span) / SR
            freq[at:tail_end] = hz * (previous_hz / hz) ** np.exp(-t / max(glide / 4.0, 1e-4))
        else:
            freq[at:tail_end] = hz
        accent = velocity >= accent_at
        gain = velocity ** patch.get("vel_curve", 1.2) * (1.25 if accent else 1.0)
        if legato:
            amp[at:tail_end] = gain * max(s, 0.6)
            previous_fenv = fenv[at - 1] if at > 0 else 0.0
            fenv[at:tail_end] = previous_fenv * dsp.exp_decay(span, fenv_decay)
        else:
            amp[at:tail_end] = gain * dsp.adsr(span, gate_end - at, a, d, s, r)
            depth = 1.0 + (patch.get("accent", 0.5) if accent else 0.0)
            fenv[at:tail_end] = depth * dsp.exp_decay(span, fenv_decay * (0.6 if accent else 1.0))
        previous_hz, legato = hz, slide_out
    freq[freq <= 0] = 1.0
    active = amp > 0
    mix = np.zeros(total_n)
    for spec in patch.get("osc", [{"wave": "saw"}]):
        ratio = 2.0 ** (spec.get("octave", 0) + spec.get("semi", 0) / 12.0 + spec.get("detune", 0.0) / 1200.0)
        mix += spec.get("level", 1.0) * dsp.osc(spec.get("wave", "saw"), freq * ratio, total_n, SR,
                                                float(rng.uniform()), spec.get("pw", 0.5))
    mix *= active
    cutoff = flt.get("cutoff", 500.0) * 2.0 ** (flt.get("env", 3.0) * fenv)
    if flt.get("lfo_depth"):
        cutoff = cutoff * 2.0 ** (flt["lfo_depth"] * np.sin(2 * np.pi * flt.get("lfo_rate", 0.2) * np.arange(total_n) / SR))
    if flt.get("track"):
        cutoff = cutoff * (freq / 261.6) ** flt["track"]
    pre = float(patch.get("pre_drive", 0.0))
    if pre > 0:
        mix = np.tanh(mix * (1.0 + pre * 4.0))
    mix = dsp.tv_filter(mix * 0.5, flt.get("type", "lp"), np.clip(cutoff, MIN_CUTOFF, MAX_CUTOFF),
                        _q_of(flt.get("res", 0.7)), SR, int(flt.get("poles", 4)), MONO_BLOCK)
    mix = mix * dsp.one_pole_smooth(amp, 0.002)
    return _drive(mix, patch.get("drive", 0.0)).astype(np.float32)


def render_notes(patch: dict, notes: list, seconds_per_beat: float, total_n: int, rng) -> np.ndarray:
    if patch.get("engine") == "mono":
        return render_mono(patch, notes, seconds_per_beat, total_n, rng)
    return render_poly(patch, notes, seconds_per_beat, total_n, rng)
