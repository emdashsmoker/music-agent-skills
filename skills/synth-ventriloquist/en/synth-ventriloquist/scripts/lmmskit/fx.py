# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Effect builders with musical units (dB, Hz, ms) on top of LMMS native and bundled LADSPA effects.

Each function appends one effect to an EffectChain and returns its <effect> element, so the
caller can automate a control afterwards (see control()). Only plugins shipped inside LMMS 1.2
on every platform are used, which keeps projects portable to a person's own LMMS install.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

from .project import EffectChain, Param

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "ladspa_catalog.json")
_catalog_cache: dict | None = None

EQ_PEAK_COUNT = 4
REVERB_ROOMS = {"small": 0, "medium": 1, "large": 2, "tunnel": 3, "large_smooth": 4, "experimental": 5}
DELAY_MODES = {"stereo": 0, "ping_pong": 1, "l_then_r": 2, "r_then_l": 3}
DELAY_MEDIA = {"plain": 0, "tape": 1, "old_tape": 2}


SATURATOR_FULL_DRIVE = 10.0           # drive value that maps to the plugin's maximum
OVERDRIVE_RANGE = (1.0, 3.0)          # the overdrive plugin's own drive scale

def catalog() -> dict:
    global _catalog_cache
    if _catalog_cache is None:
        with open(_CATALOG_PATH, encoding="utf-8") as handle:
            _catalog_cache = json.load(handle)
    return _catalog_cache


def db_to_gain(value_db: float) -> float:
    return 10 ** (value_db / 20.0)


def ladspa(chain: EffectChain, key: str, values: dict[str, float] | None = None, wet: float = 1.0) -> ET.Element:
    """Add a bundled LADSPA effect by 'file:Label' with controls addressed by port name.

    Every input port is written (catalog default unless given) because LMMS does not fall back to the
    plugin default for a port that is missing from the file.
    """
    entry = catalog().get(key)
    if entry is None:
        raise KeyError(f"LADSPA plugin '{key}' is not in the catalog; see references/effects.md for the list")
    unknown = set(values or {}) - set(entry["ports"])
    if unknown:
        raise KeyError(f"{key} has no port(s) {sorted(unknown)}; ports: {sorted(entry['ports'])}")
    ports = {}
    for name, (index, low, high, default) in entry["ports"].items():
        value = float((values or {}).get(name, default))
        if low is not None and high is not None:
            value = min(max(value, low), high)
        ports[index] = value
    file, label = key.split(":")
    return chain.add_ladspa(file, label, ports, len(ports), entry["channels"], wet=wet)


def control(effect: ET.Element, name: str) -> Param:
    """Automatable address of a control: the attribute name for native effects, the port name for LADSPA."""
    controls = EffectChain.controls(effect)
    if controls.tag != "ladspacontrols":
        return Param(controls, name)
    key = {a.get("name"): a.get("value") for a in effect.findall("key/attribute")}
    index = catalog()[f"{key['file']}:{key['plugin']}"]["ports"][name][0]
    return Param(controls.find(f"port0{index}"), "data")


# -- tone -----------------------------------------------------------------------------------------------
def eq(chain: EffectChain, *, highpass: float | None = None, lowpass: float | None = None,
       low_shelf: tuple[float, float] | None = None, high_shelf: tuple[float, float] | None = None,
       peaks: list[tuple[float, float, float]] | None = None, slope: int = 24, output_db: float = 0.0) -> ET.Element:
    """Parametric EQ. Shelves are (Hz, dB); peaks are up to four (Hz, dB, bandwidth in octaves). slope: 12/24/48 dB/oct."""
    peaks = peaks or []
    if len(peaks) > EQ_PEAK_COUNT:
        raise ValueError(f"the LMMS EQ has {EQ_PEAK_COUNT} peak bands; chain a second eq() for more")
    slope_index = {12: 0, 24: 1, 48: 2}[slope]
    values = {"Inputgain": 0, "Outputgain": output_db, "AnalyseIn": 0, "AnalyseOut": 0,
              "HPactive": highpass is not None, "HPfreq": highpass or 31, "HPres": 0.707, "HP": slope_index,
              "HP12": slope == 12, "HP24": slope == 24, "HP48": slope == 48,
              "LPactive": lowpass is not None, "LPfreq": lowpass or 18000, "LPres": 0.707, "LP": slope_index,
              "LP12": slope == 12, "LP24": slope == 24, "LP48": slope == 48,
              "Lowshelfactive": low_shelf is not None, "LowShelffreq": (low_shelf or (80, 0))[0],
              "Lowshelfgain": (low_shelf or (80, 0))[1], "LowShelfres": 1.4,
              "Highshelfactive": high_shelf is not None, "Highshelffreq": (high_shelf or (12000, 0))[0],
              "HighShelfgain": (high_shelf or (12000, 0))[1], "HighShelfres": 1.4}
    defaults = [120, 250, 2000, 4000]
    for band in range(EQ_PEAK_COUNT):
        freq, gain, width = peaks[band] if band < len(peaks) else (defaults[band], 0.0, 0.3)
        values.update({f"Peak{band + 1}active": band < len(peaks), f"Peak{band + 1}freq": freq,
                       f"Peak{band + 1}gain": gain, f"Peak{band + 1}bw": width})
    return chain.add_native("eq", values)


def filter_sweep(chain: EffectChain, cutoff: float = 20000.0, resonance: float = 0.7, kind: str = "lowpass") -> ET.Element:
    """Channel filter meant to be automated: control(effect, 'cut1') in Hz."""
    kinds = {"lowpass": 0, "highpass": 1, "bandpass": 2, "notch": 4, "moog": 6, "lowpass24": 11}
    return chain.add_native("dualfilter", {"enabled1": 1, "filter1": kinds[kind], "cut1": cutoff, "res1": resonance,
                                           "gain1": 100, "mix": -1, "enabled2": 0, "filter2": 0, "cut2": 7000,
                                           "res2": 0.5, "gain2": 100})


def bass_boost(chain: EffectChain, freq: float = 100.0, gain: float = 1.5, ratio: float = 2.0) -> ET.Element:
    return chain.add_native("bassbooster", {"freq": freq, "gain": gain, "ratio": ratio})


def exciter(chain: EffectChain, amount: float = 1.0, scope_hz: float = 6000.0, harmonics: float = 8.0) -> ET.Element:
    """Adds synthetic highs above scope_hz: brightens a dull sound without raising hiss."""
    return ladspa(chain, "calf:Exciter", {"Input": 1, "Output": 1, "Amount": amount, "Scope": scope_hz, "Harmonics": harmonics,
                                          "Blend harmonics": 0})


# -- dynamics -------------------------------------------------------------------------------------------
def compressor(chain: EffectChain, *, threshold_db: float = -18.0, ratio: float = 3.0, attack_ms: float = 10.0,
               release_ms: float = 120.0, makeup_db: float = 0.0, knee_db: float = 6.0, peak_detect: bool = False) -> ET.Element:
    return ladspa(chain, "calf:Compressor", {
        "Bypass": 0, "Input": 1, "Threshold": db_to_gain(threshold_db), "Ratio": ratio, "Attack": attack_ms,
        "Release": release_ms, "Makeup Gain": db_to_gain(makeup_db), "Knee": db_to_gain(knee_db),
        "Detection": 1 if peak_detect else 0, "Stereo Link": 0})


def limiter(chain: EffectChain, *, ceiling_db: float = -1.0, input_gain_db: float = 0.0, release_s: float = 0.08) -> ET.Element:
    """Look-ahead brickwall limiter; the usual last effect on the master channel."""
    return ladspa(chain, "fast_lookahead_limiter_1913:fastLookaheadLimiter",
                  {"Input gain (dB)": input_gain_db, "Limit (dB)": ceiling_db, "Release time (s)": release_s})


def deesser(chain: EffectChain, *, threshold_db: float = -24.0, ratio: float = 3.0, split_hz: float = 6000.0) -> ET.Element:
    return ladspa(chain, "calf:Deesser", {"Bypass": 0, "Detection": 0, "Mode": 1, "Threshold": db_to_gain(threshold_db),
                                          "Ratio": ratio, "Laxity": 15, "Makeup": 1, "Split": split_hz, "Peak": split_hz,
                                          "Gain": 1, "Level": 1, "Peak Q": 1, "S/C-Listen": 0})


def gain(chain: EffectChain, volume_percent: float = 100.0, pan: float = 0.0) -> ET.Element:
    return chain.add_native("amplifier", {"volume": volume_percent, "pan": pan, "left": 100, "right": 100})


# -- space ----------------------------------------------------------------------------------------------
def reverb(chain: EffectChain, *, decay_s: float = 2.0, room: str = "large", damp_hz: float = 6000.0, predelay_ms: float = 15.0,
           low_cut: float = 250.0, high_cut: float = 9000.0, wet: float = 1.0, dry: float = 0.0, diffusion: float = 0.7) -> ET.Element:
    """Hall/plate reverb. Default is 100% wet for a send bus; set dry=1 and a small wet for an insert."""
    return ladspa(chain, "calf:Reverb", {"Decay time": decay_s, "High Frq Damp": damp_hz, "Room size": REVERB_ROOMS[room],
                                         "Diffusion": diffusion, "Wet Amount": wet, "Dry Amount": dry, "Pre Delay": predelay_ms,
                                         "Bass Cut": low_cut, "Treble Cut": high_cut})


def delay(chain: EffectChain, bpm: float, *, left_16ths: int = 3, right_16ths: int = 4, feedback: float = 0.35,
          mode: str = "ping_pong", medium: str = "tape", wet: float = 1.0, dry: float = 0.0) -> ET.Element:
    """Tempo-synced stereo delay. Times are in 16th notes (3 = dotted 8th). Default 100% wet for a send bus."""
    return ladspa(chain, "calf:VintageDelay", {"Tempo": bpm, "Subdivide": 4, "Time L": left_16ths, "Time R": right_16ths,
                                               "Feedback": feedback, "Amount": wet, "Mix mode": DELAY_MODES[mode],
                                               "Medium": DELAY_MEDIA[medium], "Dry Amount": dry, "Stereo Width": 1})


# -- modulation and colour ------------------------------------------------------------------------------
def chorus(chain: EffectChain, *, rate_hz: float = 0.5, depth_ms: float = 3.0, delay_ms: float = 5.0, voices: int = 3,
           wet: float = 0.6, dry: float = 1.0) -> ET.Element:
    return ladspa(chain, "calf:MultiChorus", {"Min delay": delay_ms, "Mod depth": depth_ms, "Modulation rate": rate_hz,
                                              "Stereo phase": 180, "Voices": voices, "Inter-voice phase": 64, "Amount": wet,
                                              "Dry Amount": dry, "Center Frq 1": 100, "Center Frq 2": 5000, "Q": 0.125,
                                              "Overlap": 0.75})


def phaser(chain: EffectChain, *, rate_hz: float = 0.25, depth: float = 4000.0, centre_hz: float = 1000.0,
           feedback: float = 0.25, stages: int = 6, wet: float = 1.0) -> ET.Element:
    return ladspa(chain, "calf:Phaser", {"Center Freq": centre_hz, "Mod depth": depth, "Mod rate": rate_hz, "Feedback": feedback,
                                         "# Stages": stages, "Stereo phase": 180, "Reset": 0, "Amount": wet, "Dry Amount": 1})


def flanger(chain: EffectChain, *, rate_hz: float = 0.2, depth_ms: float = 0.5, delay_ms: float = 0.5, feedback: float = 0.5,
            wet: float = 1.0) -> ET.Element:
    return ladspa(chain, "calf:Flanger", {"Min delay": delay_ms, "Mod depth": depth_ms, "Mod rate": rate_hz, "Feedback": feedback,
                                          "Stereo phase": 90, "Reset": 0, "Amount": wet, "Dry Amount": 1})


def saturator(chain: EffectChain, *, drive: float = 3.0, character: float = 0.5) -> ET.Element:
    """Valve-style saturation. drive 0-10 sets how hard the signal is pushed, character 0-1 goes from soft to edgy.

    Adds harmonics and density: bass, drums, gritty leads. (swh Valve saturation. Two better-known saturators,
    Calf Saturator and TAP TubeWarmth, start up differently from run to run on a busy machine, so the same
    project did not always render the same file with them.)
    """
    return ladspa(chain, "valve_1209:valve", {"Distortion level": min(max(drive, 0.0) / SATURATOR_FULL_DRIVE, 1.0), "Distortion character": character})


def distortion(chain: EffectChain, *, drive: float = 5.0) -> ET.Element:
    """Overdrive, harder than saturator. drive 1 (clean) to 10 (full). (swh Fast overdrive.)"""
    low, high = OVERDRIVE_RANGE
    return ladspa(chain, "foverdrive_1196:foverdrive", {"Drive level": low + (high - low) * (min(max(drive, 1.0), 10.0) - 1.0) / 9.0})


def bitcrush(chain: EffectChain, *, rate_hz: float = 11025.0, levels: int = 64, in_gain_db: float = 0.0, out_gain_db: float = 0.0) -> ET.Element:
    return chain.add_native("bitcrush", {"ingain": in_gain_db, "innoise": 0, "outgain": out_gain_db, "outclip": 0,
                                         "rate": rate_hz, "stereodiff": 0, "levels": levels, "rateon": 1, "depthon": 1})


def stereo_width(chain: EffectChain, width: float = 20.0) -> ET.Element:
    """Haas-style widener (delays one side by `width` samples). Check mono compatibility after using it."""
    return chain.add_native("stereoenhancer", {"width": width})


def mono(chain: EffectChain) -> ET.Element:
    """Collapse a channel to mono: for sub bass and kick."""
    return chain.add_native("stereomatrix", {"l-l": 0.5, "l-r": 0.5, "r-l": 0.5, "r-r": 0.5})
