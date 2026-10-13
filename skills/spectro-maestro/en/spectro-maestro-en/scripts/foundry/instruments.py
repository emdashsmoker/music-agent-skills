# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Instrument library: every name a track may put in `inst`.

Three kinds
  drum    one-shot hits from drums.HIT_ENGINES (pitch shifts the tuning)
  sweep   duration-driven transition effects from drums.SWEEP_ENGINES
  synth   tonal patches for synth.render_notes

A track may also give a dict: {base: lead_supersaw, filter: {cutoff: 3000}} overrides the named patch,
and song-level `patches:` defines new names the same way."""
from __future__ import annotations

import copy

import numpy as np

from . import drums, fx, synth
from .dsp import SR

DRUMS = {
    # --- kicks
    "kick_909": ("kick", dict(start_hz=230, tune_hz=52, sweep=0.030, decay=0.42, click=0.35, drive=0.15)),
    "kick_808": ("kick", dict(start_hz=130, tune_hz=46, sweep=0.020, decay=1.1, click=0.10)),
    "kick_house": ("kick", dict(start_hz=220, tune_hz=55, sweep=0.028, decay=0.30, click=0.40, drive=0.20)),
    "kick_techno": ("kick", dict(start_hz=200, tune_hz=48, sweep=0.035, decay=0.50, click=0.30, drive=0.40)),
    "kick_trance": ("kick", dict(start_hz=300, tune_hz=50, sweep=0.025, decay=0.36, click=0.50, drive=0.20)),
    "kick_psy": ("kick", dict(start_hz=420, tune_hz=48, sweep=0.018, decay=0.20, click=0.25, drive=0.10)),
    "kick_gabber": ("kick", dict(start_hz=320, tune_hz=58, sweep=0.070, decay=0.55, click=0.30, drive=1.0,
                                 clip="hard", tail_lp=5000)),
    "kick_hardstyle": ("kick", dict(start_hz=280, tune_hz=52, sweep=0.080, decay=0.60, click=0.45, drive=0.85,
                                    tail_lp=6000)),
    "kick_dnb": ("kick", dict(start_hz=260, tune_hz=62, sweep=0.020, decay=0.22, click=0.50, drive=0.25)),
    "kick_linn": ("kick", dict(start_hz=180, tune_hz=60, sweep=0.020, decay=0.25, click=0.40)),
    "kick_lofi": ("kick", dict(start_hz=160, tune_hz=55, sweep=0.030, decay=0.30, click=0.15, drive=0.10)),
    "kick_industrial": ("kick", dict(start_hz=260, tune_hz=50, sweep=0.040, decay=0.40, click=0.50, drive=0.80,
                                     clip="hard", tail_lp=7000)),
    "kick_break": ("kick", dict(start_hz=170, tune_hz=64, sweep=0.022, decay=0.20, click=0.60, click_hz=1500,
                                drive=0.15)),
    # --- snares and claps
    "snare_909": ("snare", dict(tune_hz=185, tone=0.6, snappy=0.8, noise_decay=0.20)),
    "snare_808": ("snare", dict(tune_hz=170, tone=0.8, snappy=0.55, noise_decay=0.16, noise_hp=1500)),
    "snare_linn": ("snare", dict(tune_hz=200, tone=0.7, snappy=0.8, noise_decay=0.22, noise_lp=7500)),
    "snare_dnb": ("snare", dict(tune_hz=215, tone=0.8, snappy=0.9, noise_decay=0.16, noise_hp=1800, drive=0.3,
                                length=0.3)),
    "snare_trap": ("snare", dict(tune_hz=235, tone=0.5, snappy=1.0, noise_decay=0.14, noise_hp=2500)),
    "snare_break": ("snare", dict(tune_hz=205, tone=0.9, snappy=0.7, noise_decay=0.18, noise_hp=900, noise_lp=7000,
                                  drive=0.2)),
    "snare_industrial": ("snare", dict(tune_hz=160, tone=0.5, snappy=1.0, noise_decay=0.35, noise_hp=700, drive=0.8,
                                       length=0.5)),
    "snare_lofi": ("snare", dict(tune_hz=190, tone=0.6, snappy=0.6, noise_decay=0.15, noise_lp=5000)),
    "snare_roll": ("snare", dict(tune_hz=200, tone=0.5, snappy=0.9, noise_decay=0.12)),
    "clap_909": ("clap", dict(tone_hz=1100, bursts=3, decay=0.25)),
    "clap_808": ("clap", dict(tone_hz=1000, bursts=4, decay=0.18, spacing=0.009)),
    "clap_big": ("clap", dict(tone_hz=1200, bursts=4, decay=0.45)),
    "snap": ("clap", dict(tone_hz=2200, bursts=1, decay=0.06)),
    # --- hats and cymbals
    "hat_closed_909": ("hat", dict(decay=0.045, band_hz=7500, metal=0.5)),
    "hat_open_909": ("hat", dict(decay=0.35, band_hz=7500, metal=0.5)),
    "hat_closed_808": ("hat", dict(decay=0.040, band_hz=8500, metal=0.85, hp_hz=6000)),
    "hat_open_808": ("hat", dict(decay=0.30, band_hz=8500, metal=0.85, hp_hz=6000)),
    "hat_closed_lofi": ("hat", dict(decay=0.05, band_hz=6500, metal=0.4, hp_hz=4500)),
    "hat_pedal": ("hat", dict(decay=0.09, band_hz=8000, metal=0.5)),
    "ride_909": ("cymbal", dict(decay=0.9, tune=1.7, hp_hz=5500, metal=0.7)),
    "crash_909": ("cymbal", dict(decay=1.6, tune=1.3, hp_hz=3500)),
    "splash": ("cymbal", dict(decay=0.6, tune=1.9, hp_hz=5000)),
    # --- percussion
    "tom_low": ("tom", dict(tune_hz=85, decay=0.35)),
    "tom_mid": ("tom", dict(tune_hz=125, decay=0.30)),
    "tom_high": ("tom", dict(tune_hz=175, decay=0.25)),
    "conga": ("tom", dict(tune_hz=260, decay=0.14)),
    "timpani": ("tom", dict(tune_hz=95, decay=1.2)),
    "rim_808": ("rim", dict(tune_hz=1700)),
    "clave": ("rim", dict(tune_hz=2500)),
    "cowbell_808": ("cowbell", dict()),
    "shaker": ("shaker", dict()),
    "tambourine": ("hat", dict(decay=0.12, band_hz=7500, metal=0.7, hp_hz=5000)),
    "metal_hit": ("metal", dict(tune_hz=320, decay=0.35, drive=0.5)),
    "anvil": ("metal", dict(tune_hz=780, decay=0.5, drive=0.3)),
}

SWEEPS = {
    "riser": ("riser", dict()),
    "noise_sweep": ("noise_sweep", dict()),
    "downlifter": ("downlifter", dict()),
    "impact": ("impact", dict()),
    "sub_drop": ("sub_drop", dict()),
    "reverse_crash": ("reverse_crash", dict()),
    "crash": ("crash", dict(decay=1.6, tune=1.3, hp_hz=3500)),
}

_SUPERSAW = [dict(wave="saw", voices=7, spread=28, level=1.0), dict(wave="saw", voices=5, spread=18, octave=-1, level=0.5)]

PATCHES = {
    # ------------------------------------------------ bass
    "bass_303": dict(engine="mono", osc=[dict(wave="saw")], filter=dict(cutoff=320, res=0.78, env=3.2, poles=4),
                     fenv_decay=0.22, accent=0.6, glide=0.06, amp=(0.002, 0.25, 0.75, 0.015), drive=0.25),
    "bass_303_square": dict(engine="mono", osc=[dict(wave="square")], filter=dict(cutoff=280, res=0.8, env=3.4, poles=4),
                            fenv_decay=0.2, accent=0.6, glide=0.06, amp=(0.002, 0.25, 0.75, 0.015), drive=0.25),
    "bass_sub": dict(engine="sub", osc=[dict(wave="sine"), dict(wave="tri", level=0.15)],
                     amp=(0.004, 0.1, 0.9, 0.06)),
    "bass_808": dict(engine="sub", osc=[dict(wave="sine")], pitch_env=dict(semis=7, time=0.025),
                     amp=(0.002, 1.2, 0.0, 0.25), drive=0.35),
    "bass_reese": dict(engine="mono", osc=[dict(wave="saw", detune=-18), dict(wave="saw", detune=18),
                                           dict(wave="sine", octave=-1, level=0.7)],
                       filter=dict(cutoff=450, res=0.25, env=0.6, poles=4, lfo_rate=0.17, lfo_depth=0.9),
                       fenv_decay=0.6, glide=0.08, amp=(0.006, 0.3, 0.9, 0.05), drive=0.2),
    "bass_moog": dict(engine="sub", osc=[dict(wave="saw"), dict(wave="square", octave=-1, level=0.6)],
                      filter=dict(cutoff=260, res=0.3, env=2.6, poles=4, vel=0.3), fenv=(0.002, 0.18, 0.15, 0.1),
                      amp=(0.003, 0.25, 0.7, 0.08), drive=0.15),
    "bass_fm": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=1, index=3.2, index_env=(0.001, 0.12, 0.15, 0.1)),
                                      dict(ratio=1, mod_ratio=2, index=1.2, index_env=(0.001, 0.06, 0.0, 0.05),
                                           level=0.4)],
                    amp=(0.002, 0.2, 0.6, 0.06)),
    "bass_offbeat": dict(engine="sub", osc=[dict(wave="saw"), dict(wave="saw", detune=9, level=0.7),
                                            dict(wave="sine", octave=-1, level=0.6)],
                         filter=dict(cutoff=380, res=0.2, env=2.0, poles=4), fenv=(0.002, 0.16, 0.2, 0.08),
                         amp=(0.003, 0.2, 0.75, 0.05)),
    "bass_rolling": dict(engine="sub", osc=[dict(wave="saw")], filter=dict(cutoff=240, res=0.35, env=2.8, poles=4),
                         fenv=(0.001, 0.07, 0.0, 0.03), amp=(0.001, 0.09, 0.3, 0.02), drive=0.2),
    "bass_pluck": dict(engine="sub", osc=[dict(wave="square", level=0.7), dict(wave="sine", octave=-1)],
                       filter=dict(cutoff=300, res=0.15, env=2.4, poles=2), fenv=(0.001, 0.12, 0.0, 0.08),
                       amp=(0.002, 0.3, 0.3, 0.1)),
    "bass_organ": dict(engine="organ", partials=[(1, 1.0), (2, 0.6), (3, 0.25)], click=0.15,
                       amp=(0.003, 0.2, 0.8, 0.06)),
    "bass_picked": dict(engine="pluck", decay=1.4, damp=0.95, pick=0.3, body=1.2, drive=0.3, release=0.07,
                        filter=dict(cutoff=1500, res=0.15, poles=2), amp=(0.001, 0.1, 1.0, 0.07)),
    "bass_wobble": dict(engine="mono", osc=[dict(wave="saw"), dict(wave="square", detune=7, level=0.8),
                                            dict(wave="sine", octave=-1, level=0.8)],
                        filter=dict(cutoff=700, res=0.45, env=0.0, poles=4, lfo_rate="1/8t", lfo_depth=2.2),
                        glide=0.04, amp=(0.005, 0.2, 1.0, 0.04), drive=0.45),
    "bass_hoover": dict(engine="sub", osc=[dict(wave="pulse", pw=0.3, pwm_rate=1.7, pwm_depth=0.2, voices=3, spread=30),
                                           dict(wave="saw", octave=-1, level=0.8)],
                        pitch_env=dict(semis=-5, time=0.08), filter=dict(cutoff=1800, res=0.2, poles=2),
                        amp=(0.01, 0.2, 0.9, 0.1), width=0.5, fx=[dict(fx="chorus", mix=0.4)]),
    "bass_saw_dist": dict(engine="sub", osc=[dict(wave="saw"), dict(wave="square", octave=-1, level=0.5)],
                          filter=dict(cutoff=900, res=0.2, env=1.2, poles=4), fenv=(0.002, 0.15, 0.3, 0.05),
                          amp=(0.002, 0.15, 0.85, 0.05), drive=0.8),
    # ------------------------------------------------ leads
    "lead_supersaw": dict(engine="sub", osc=_SUPERSAW, width=0.9,
                          filter=dict(cutoff=7500, res=0.05, poles=2, track=0.3),
                          amp=(0.008, 0.3, 0.85, 0.35)),
    "lead_saw": dict(engine="sub", osc=[dict(wave="saw"), dict(wave="saw", detune=11, level=0.7)],
                     filter=dict(cutoff=3200, res=0.2, env=1.0, poles=4, track=0.5), fenv=(0.005, 0.3, 0.4, 0.2),
                     amp=(0.006, 0.2, 0.8, 0.2), vibrato=dict(rate=5.6, depth=14, delay=0.25)),
    "lead_square": dict(engine="sub", osc=[dict(wave="pulse", pw=0.5, pwm_rate=0.7, pwm_depth=0.12)],
                        filter=dict(cutoff=4200, res=0.1, poles=2, track=0.5),
                        amp=(0.004, 0.15, 0.8, 0.15), vibrato=dict(rate=5.8, depth=12, delay=0.2)),
    "lead_chip": dict(engine="sub", osc=[dict(wave="pulse", pw=0.25)], amp=(0.001, 0.05, 0.85, 0.03)),
    "lead_sine": dict(engine="mono", osc=[dict(wave="sine"), dict(wave="tri", level=0.2)],
                      filter=dict(cutoff=6000, res=0.0, env=0.0, poles=2), glide=0.12,
                      amp=(0.01, 0.2, 0.9, 0.08)),
    "lead_acid": dict(engine="mono", osc=[dict(wave="saw")], filter=dict(cutoff=600, res=0.82, env=3.0, poles=4),
                      fenv_decay=0.18, accent=0.7, glide=0.05, amp=(0.002, 0.2, 0.75, 0.015), drive=0.35),
    "lead_psy": dict(engine="mono", osc=[dict(wave="saw"), dict(wave="square", detune=5, level=0.6)],
                     filter=dict(cutoff=700, res=0.7, env=3.2, poles=4), fenv_decay=0.09, glide=0.03,
                     amp=(0.001, 0.12, 0.5, 0.02), drive=0.3),
    "lead_hoover": dict(engine="sub", osc=[dict(wave="pulse", pw=0.35, pwm_rate=2.1, pwm_depth=0.25, voices=5, spread=45),
                                           dict(wave="saw", octave=-1, voices=3, spread=30, level=0.8)],
                        pitch_env=dict(semis=-7, time=0.12), width=0.8, filter=dict(cutoff=5000, res=0.1, poles=2),
                        amp=(0.01, 0.3, 0.9, 0.2), fx=[dict(fx="chorus", mix=0.5, depth_ms=4.0)]),
    "lead_guitar": dict(engine="pluck", decay=2.2, damp=0.35, pick=0.7, drive=0.12, release=0.25,
                        filter=dict(cutoff=4200, res=0.05, poles=2), amp=(0.001, 0.1, 1.0, 0.25),
                        fx=[dict(fx="chorus", rate=0.6, depth_ms=3.5, mix=0.45)]),
    "lead_guitar_dist": dict(engine="pluck", decay=3.0, damp=0.3, pick=0.8, drive=0.9, release=0.2,
                             filter=dict(cutoff=3600, res=0.1, poles=2), amp=(0.001, 0.1, 1.0, 0.2)),
    "lead_fm_bell": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=3.5, index=2.4, index_env=(0.001, 0.8, 0.0, 0.5)),
                                           dict(ratio=2, mod_ratio=7.0, index=1.0, index_env=(0.001, 0.3, 0.0, 0.3),
                                                level=0.35)],
                         amp=(0.002, 1.4, 0.0, 0.9)),
    # ------------------------------------------------ plucks and arps
    "pluck_saw": dict(engine="sub", osc=[dict(wave="saw", voices=3, spread=14), dict(wave="saw", octave=1, level=0.3)],
                      width=0.6, filter=dict(cutoff=500, res=0.15, env=4.0, poles=4, track=0.4, vel=0.3),
                      fenv=(0.001, 0.16, 0.0, 0.15), amp=(0.002, 0.3, 0.0, 0.2)),
    "pluck_supersaw": dict(engine="sub", osc=_SUPERSAW, width=0.9,
                           filter=dict(cutoff=600, res=0.1, env=4.2, poles=4, track=0.4),
                           fenv=(0.001, 0.2, 0.05, 0.2), amp=(0.002, 0.35, 0.1, 0.25)),
    "pluck_square": dict(engine="sub", osc=[dict(wave="square"), dict(wave="square", octave=1, level=0.25)],
                         filter=dict(cutoff=700, res=0.2, env=3.2, poles=2, track=0.4), fenv=(0.001, 0.12, 0.0, 0.1),
                         amp=(0.001, 0.22, 0.0, 0.12)),
    "pluck_fm": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=4, index=1.6, index_env=(0.001, 0.08, 0.0, 0.06))],
                     amp=(0.001, 0.4, 0.0, 0.25)),
    "pluck_string": dict(engine="pluck", decay=1.8, damp=0.3, pick=0.8, amp=(0.001, 0.1, 1.0, 0.4)),
    "arp_pulse": dict(engine="sub", osc=[dict(wave="pulse", pw=0.3), dict(wave="saw", detune=8, level=0.4)],
                      filter=dict(cutoff=1400, res=0.3, env=2.2, poles=4, track=0.4), fenv=(0.001, 0.1, 0.1, 0.08),
                      amp=(0.001, 0.14, 0.2, 0.08)),
    # ------------------------------------------------ pads and chords
    "pad_warm": dict(engine="sub", osc=[dict(wave="saw", voices=3, spread=16), dict(wave="saw", octave=-1, level=0.5)],
                     width=0.8, filter=dict(cutoff=1100, res=0.1, poles=4, track=0.3, lfo_rate=0.11, lfo_depth=0.25),
                     amp=(0.5, 0.5, 0.85, 0.9)),
    "pad_supersaw": dict(engine="sub", osc=_SUPERSAW, width=1.0,
                         filter=dict(cutoff=3800, res=0.05, poles=2, track=0.3), amp=(0.25, 0.4, 0.9, 0.8)),
    "pad_strings": dict(engine="sub", osc=[dict(wave="saw", voices=4, spread=20), dict(wave="saw", octave=1, level=0.35,
                                                                                         voices=3, spread=14)],
                        width=0.9, filter=dict(cutoff=2600, res=0.05, poles=2, track=0.3), amp=(0.18, 0.3, 0.9, 0.5),
                        fx=[dict(fx="chorus", rate=0.6, depth_ms=4.0, mix=0.5, voices=3)]),
    "pad_pwm": dict(engine="sub", osc=[dict(wave="pulse", pw=0.5, pwm_rate=0.4, pwm_depth=0.3),
                                       dict(wave="saw", octave=-1, level=0.4)],
                    filter=dict(cutoff=1600, res=0.15, poles=4, track=0.3), amp=(0.3, 0.4, 0.85, 0.7),
                    fx=[dict(fx="chorus", rate=0.5, depth_ms=3.5, mix=0.5)]),
    "pad_dark": dict(engine="sub", osc=[dict(wave="saw", voices=2, spread=10), dict(wave="square", octave=-1, level=0.6)],
                     width=0.6, filter=dict(cutoff=420, res=0.35, poles=4, lfo_rate=0.07, lfo_depth=0.6),
                     amp=(0.8, 0.6, 0.9, 1.2)),
    "pad_glass": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=2, index=1.2, index_env=(0.4, 1.0, 0.5, 0.8)),
                                        dict(ratio=2, mod_ratio=5, index=0.5, level=0.25)],
                      amp=(0.35, 0.6, 0.8, 1.0), fx=[dict(fx="chorus", mix=0.4)]),
    "pad_choir": dict(engine="sub", osc=[dict(wave="saw", voices=5, spread=22), dict(wave="noise", level=0.06)],
                      width=0.9, filter=dict(type="bp", cutoff=900, res=0.3, poles=2, track=0.2),
                      amp=(0.35, 0.4, 0.9, 0.8), vibrato=dict(rate=5.0, depth=8, delay=0.4),
                      fx=[dict(fx="eq", bands=[["peak", 2800, 4, 2.0]])]),
    "chord_stab": dict(engine="sub", osc=[dict(wave="saw", voices=3, spread=15)], width=0.7,
                       filter=dict(cutoff=900, res=0.2, env=3.0, poles=4), fenv=(0.001, 0.14, 0.1, 0.12),
                       amp=(0.002, 0.2, 0.3, 0.15)),
    "chord_supersaw": dict(engine="sub", osc=_SUPERSAW, width=1.0,
                           filter=dict(cutoff=6000, res=0.05, poles=2, track=0.3), amp=(0.004, 0.2, 0.8, 0.18)),
    "chord_rave": dict(engine="sub", osc=[dict(wave="saw", voices=5, spread=35), dict(wave="pulse", pw=0.3, level=0.6)],
                       width=0.8, filter=dict(cutoff=2400, res=0.3, env=1.5, poles=2), fenv=(0.001, 0.2, 0.2, 0.1),
                       amp=(0.002, 0.25, 0.5, 0.12), drive=0.2),
    "keys_piano": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=1, index=1.6, index_env=(0.001, 0.5, 0.05, 0.3)),
                                         dict(ratio=1, mod_ratio=3, index=0.9, index_env=(0.001, 0.12, 0.0, 0.1),
                                              level=0.5, detune=3),
                                         dict(ratio=2, mod_ratio=2, index=0.6, index_env=(0.001, 0.25, 0.0, 0.2),
                                              level=0.25, detune=-3)],
                       amp=(0.002, 1.8, 0.0, 0.35), filter=dict(cutoff=5200, res=0.0, poles=2, track=0.5, vel=0.4)),
    "keys_ep": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=1, index=1.1, index_env=(0.001, 0.9, 0.2, 0.4)),
                                      dict(ratio=1, mod_ratio=14, index=0.5, index_env=(0.001, 0.07, 0.0, 0.05),
                                           level=0.35)],
                    amp=(0.002, 1.6, 0.25, 0.4), fx=[dict(fx="tremolo", rate="1/4", depth=0.2)]),
    "keys_organ": dict(engine="organ", partials=[(0.5, 0.6), (1, 1.0), (1.5, 0.5), (2, 0.6), (3, 0.3), (4, 0.2)],
                       click=0.2, amp=(0.003, 0.05, 1.0, 0.05)),
    "brass_synth": dict(engine="sub", osc=[dict(wave="saw", voices=2, spread=10), dict(wave="saw", detune=-7, level=0.7)],
                        width=0.5, filter=dict(cutoff=700, res=0.15, env=2.6, poles=4, track=0.4, vel=0.3),
                        fenv=(0.05, 0.3, 0.55, 0.15), amp=(0.02, 0.2, 0.85, 0.15)),
    "strings_orch": dict(engine="sub", osc=[dict(wave="saw", voices=6, spread=14)], width=0.9,
                         filter=dict(cutoff=3200, res=0.0, poles=2, track=0.4), amp=(0.12, 0.3, 0.9, 0.4),
                         vibrato=dict(rate=5.4, depth=9, delay=0.3),
                         fx=[dict(fx="eq", bands=[["hp", 120], ["peak", 2500, -2, 1.0]])]),
    "bell_tubular": dict(engine="fm", ops=[dict(ratio=1, mod_ratio=3.53, index=2.0, index_env=(0.001, 1.5, 0.0, 1.0)),
                                           dict(ratio=2.76, mod_ratio=1, index=0.6, level=0.3, decay=1.2)],
                         amp=(0.001, 2.5, 0.0, 1.5)),
    "drone": dict(engine="sub", osc=[dict(wave="saw", voices=3, spread=8), dict(wave="sine", octave=-1)],
                  width=0.7, filter=dict(cutoff=300, res=0.4, poles=4, lfo_rate=0.05, lfo_depth=1.2),
                  amp=(2.0, 1.0, 1.0, 3.0)),
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else copy.deepcopy(value)
    return out


def drum_names() -> set:
    return set(DRUMS) | set(SWEEPS)


def all_names() -> dict:
    return {"drum": sorted(DRUMS), "sweep": sorted(SWEEPS), "synth": sorted(PATCHES)}


def resolve(inst, custom: dict | None = None) -> dict:
    """Instrument reference -> {'kind', 'engine', 'params'|'patch', 'name'}. Raises KeyError with the valid names."""
    custom = custom or {}
    override = {}
    if isinstance(inst, dict):
        if "base" not in inst:                            # a complete patch written in place
            return {"kind": "synth", "name": "inline", "patch": copy.deepcopy(inst)}
        override = {k: v for k, v in inst.items() if k != "base"}
        inst = inst.get("base")
    if inst in custom:
        inner = custom[inst]
        others = {k: v for k, v in custom.items() if k != inst}
        resolved = resolve(inner, others) if "base" in inner else {"kind": "synth", "patch": copy.deepcopy(inner)}
        field = "patch" if resolved["kind"] == "synth" else "params"
        resolved[field] = _merge(resolved[field], override)
        resolved["name"] = inst
        return resolved
    if inst in DRUMS or inst in SWEEPS:
        engine, params = (DRUMS if inst in DRUMS else SWEEPS)[inst]
        return {"kind": "drum" if inst in DRUMS else "sweep", "name": inst, "engine": engine,
                "params": _merge(params, override)}
    if inst in PATCHES:
        return {"kind": "synth", "name": inst, "patch": _merge(PATCHES[inst], override)}
    raise KeyError(f"unknown instrument {inst!r}. Run the 'instruments' command for the list.")


def _sync_rates(patch: dict, ctx: fx.FxContext) -> dict:
    """Turn tempo-synced LFO rates such as '1/8t' into Hz."""
    flt = patch.get("filter")
    if flt and isinstance(flt.get("lfo_rate"), str):
        patch = copy.deepcopy(patch)
        patch["filter"]["lfo_rate"] = 1.0 / ctx.time_of(flt["lfo_rate"])
    return patch


def _place_hits(hit_of, notes: list, seconds_per_beat: float, total_n: int, chokes: np.ndarray | None) -> np.ndarray:
    out = np.zeros(total_n, dtype=np.float32)
    for start, dur, midi, velocity, *_ in notes:
        hit = hit_of(midi, dur * seconds_per_beat)
        at = int(start * seconds_per_beat * SR)
        end = min(total_n, at + len(hit))
        if chokes is not None:
            later = chokes[chokes > at + 64]
            if len(later) and later[0] < end:                  # a closed hat cuts the ringing open hat
                end = int(later[0]) + 220
                hit = hit[:end - at].copy()
                hit[-220:] *= np.linspace(1.0, 0.0, 220)
        if end > at:
            out[at:end] += hit[:end - at] * velocity ** 1.5
    return out


def render_track(resolved: dict, notes: list, ctx: fx.FxContext, total_n: int, seed: int,
                 chokes: np.ndarray | None = None) -> np.ndarray:
    """Raw audio of one track before mixing (patch-level effects included)."""
    rng = np.random.default_rng(seed)
    seconds_per_beat = 60.0 / ctx.bpm
    if resolved["kind"] == "drum":
        engine, params, cache = drums.HIT_ENGINES[resolved["engine"]], resolved["params"], {}

        def hit_of(midi, seconds):
            if midi not in cache:
                tuned = dict(params)
                ratio = 2.0 ** ((midi - 60) / 12.0)
                for key in ("tune_hz", "start_hz"):
                    if key in tuned:
                        tuned[key] = tuned[key] * ratio
                if "tune" in tuned or resolved["engine"] in ("hat", "cymbal", "cowbell"):
                    tuned["tune"] = tuned.get("tune", 1.0) * ratio
                cache[midi] = engine(tuned, np.random.default_rng(seed + int(midi))).astype(np.float32)
            return cache[midi]
        return _place_hits(hit_of, notes, seconds_per_beat, total_n, chokes)
    if resolved["kind"] == "sweep":
        engine, params = drums.SWEEP_ENGINES[resolved["engine"]], resolved["params"]
        return _place_hits(lambda midi, seconds: engine(params, rng, max(seconds, 0.05)).astype(np.float32),
                           notes, seconds_per_beat, total_n, None)
    patch = _sync_rates(resolved["patch"], ctx)
    audio = synth.render_notes(patch, notes, seconds_per_beat, total_n, rng)
    if patch.get("fx"):
        audio = fx.apply_chain(audio, patch["fx"], ctx).astype(np.float32)
    return audio
