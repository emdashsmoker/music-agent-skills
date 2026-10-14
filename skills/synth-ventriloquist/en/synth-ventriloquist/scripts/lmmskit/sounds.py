# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Sound library: named patches built from LMMS's own instruments and factory samples.

A patch is plain data (plugin, settings, envelopes, filter, insert effects, mix role), so an
agent can copy one, change a few numbers and audition the result. Everything here loads in a
stock LMMS 1.2 on any platform: no soundfonts, no VSTs, no downloads.

Naming: drums are '<machine>_<piece>' (909_kick, 808_snare, linn_clap); synths are '<character>_<role>'.
"""
from __future__ import annotations

import copy
import filecmp
import os
import shutil

from . import fx, kit
from .project import DEFAULT_BASENOTE, MIDI_MINUS_LMMS_KEY, Project, Track

SINE, TRIANGLE, SAW, SQUARE, MOOG_SAW, EXPONENTIAL, NOISE, USER_WAVE = range(8)
MOD_PM, MOD_AM, MOD_MIX, MOD_SYNC, MOD_FM = range(5)
FILTER_LP, FILTER_HP, FILTER_BP, FILTER_NOTCH, FILTER_MOOG, FILTER_LP_X2, FILTER_LP24 = 0, 1, 2, 4, 6, 7, 11
DRUM_PITCH = 60                                   # drum patches play their natural sound at C4
DRUM_BASENOTE = DRUM_PITCH - MIDI_MINUS_LMMS_KEY
LFO_SECONDS_AT_KNOB_ONE = 20.0                    # LMMS: LFO period = 20 s * lspd
KIT_FOLDER = "kit"                                # where kit files live inside a project's samples folder
KIT_GATE_MARGIN = 0.02


def osc3(waves, vols, coarse=(0, 0, 0), fine=((0, 0), (0, 0), (0, 0)), pan=(0, 0, 0), spread=(0, 0, 0),
         phase=(0, 0, 0), mod=(MOD_MIX, MOD_MIX)) -> dict:
    """TripleOscillator settings. fine is (left cents, right cents) per oscillator; spread is stereo phase detune."""
    attrs = {"modalgo1": mod[0], "modalgo2": mod[1], "modalgo3": MOD_MIX}
    for i in range(3):
        attrs.update({f"wavetype{i}": waves[i], f"vol{i}": vols[i], f"coarse{i}": coarse[i], f"finel{i}": fine[i][0],
                      f"finer{i}": fine[i][1], f"pan{i}": pan[i], f"stphdetun{i}": spread[i], f"phoffset{i}": phase[i],
                      f"userwavefile{i}": ""})
    return attrs


def kicker(start, end, decay_ms, *, slope=0.1, env=0.5, click=0.4, dist=(0.8, 0.8), gain=1.0, noise=0.0, follow_note=False) -> dict:
    """Kicker settings: sine sweep start->end Hz over decay_ms.

    env: amplitude curve (1 = linear fade, small = fast drop). dist=(start, end): higher start adds punch harmonics
    (100-1000 Hz) to the attack. noise: adds noise for as long as the kick sounds, which is heard as hiss on every
    hit, so leave it at 0 unless that is the sound wanted. (All Kicker tracks also share one noise stream, so with
    noise on two of them the render changes from run to run unless LMMS runs on one core.)
    The library kicks (trance_kick, psy_kick ...) are separate clean one-shots computed in kit.py."""
    return {"startfreq": start, "endfreq": end, "decay": decay_ms, "slope": slope, "env": env, "click": click,
            "dist": dist[0], "distend": dist[1], "gain": gain, "noise": noise, "startnote": 0,
            "endnote": 1 if follow_note else 0, "version": 1}


def sample(path: str, *, reversed_: bool = False, loop: bool = False, amp: float = 100) -> dict:
    """AudioFileProcessor settings. path is relative to an LMMS samples folder (factory or the project's own)."""
    return {"src": path, "amp": amp, "sframe": 0, "eframe": 1, "lframe": 0, "looped": 1 if loop else 0,
            "reversed": 1 if reversed_ else 0, "stutter": 0, "interp": 1}


def acid(*, cutoff=0.45, resonance=0.85, env_mod=0.6, decay=0.3, dist=0.15, square=False, slide_time=0.6, db24=False) -> dict:
    """LB302 (TB-303 style) settings; all knobs 0-1 except resonance 0-1.25. Overlapping notes slide."""
    return {"vcf_cut": cutoff, "vcf_res": resonance, "vcf_mod": env_mod, "vcf_dec": decay, "dist": dist,
            "shape": 1 if square else 0, "slide_dec": slide_time, "slide": 0, "dead": 0, "db24": 1 if db24 else 0}


def _drum(plugin, attrs, role, gate, vol=100, **extra) -> dict:
    return {"plugin": plugin, "attrs": attrs, "role": role, "gate_s": gate, "basenote": DRUM_BASENOTE, "vol": vol, **extra}


def _ogg(path, role, gate, vol=100, **extra) -> dict:
    return _drum("audiofileprocessor", sample(path), role, gate, vol, **extra)


WIDE = ((-12, 9), (11, -13), (-4, 5))             # supersaw detune in cents, different per side for width
PATCHES: dict[str, dict] = {
    # ---- synthesized low hits (Kicker without noise: reproducible) -----------------------------------
    "sub_drop": _drum("kicker", kicker(130, 28, 2400, slope=0.6, env=0.9, click=0.0), "fx", 2.4),
    # ---- acoustic / generic one-shots (LMMS factory samples) ---------------------------------------
    "kick_acoustic": _ogg("drums/bassdrum_acoustic01.ogg", "kick", 0.5), "kick_hardcore": _ogg("drums/kick_hardcore01.ogg", "kick", 0.5),
    "kick_distorted": _ogg("drums/kick_distorted01.ogg", "kick", 0.5), "kick_hiphop": _ogg("drums/kick_hiphop01.ogg", "kick", 0.6),
    "snare_acoustic": _ogg("drums/snare_acoustic01.ogg", "snare", 0.5), "snare_hiphop": _ogg("drums/snare_hiphop01.ogg", "snare", 0.5),
    "snare_electro": _ogg("drums/snare_electro01.ogg", "snare", 0.4), "snare_harsh": _ogg("drums/snare_harsh01.ogg", "snare", 0.5),
    "snare_short": _ogg("drums/snare_short01.ogg", "snare", 0.25), "rim": _ogg("drums/rim01.ogg", "perc", 0.2),
    "clap": _ogg("drums/clap01.ogg", "clap", 0.5), "clap_tight": _ogg("drums/clap03.ogg", "clap", 0.4),
    "hat": _ogg("drums/hihat_closed01.ogg", "hat", 0.12), "hat_tight": _ogg("drums/hihat_closed03.ogg", "hat", 0.1),
    "ohat": _ogg("drums/hihat_opened01.ogg", "hat", 0.5), "ride": _ogg("drums/ride01.ogg", "cymbal", 1.2),
    "crash": _ogg("drums/crash01.ogg", "cymbal", 2.5), "crash2": _ogg("drums/crash02.ogg", "cymbal", 2.5),
    "reverse_crash": _drum("audiofileprocessor", sample("drums/crash01.ogg", reversed_=True), "fx", 2.5),
    "shaker": _ogg("drums/shaker01.ogg", "hat", 0.2), "tom_low": _ogg("drums/tom_low01.ogg", "perc", 0.6),
    "tom_mid": _ogg("drums/tom_mid01.ogg", "perc", 0.5), "tom_hi": _ogg("drums/tom_hi01.ogg", "perc", 0.5),
    "zap": _ogg("drums/zap01.ogg", "fx", 0.5),
    # ---- basses ---------------------------------------------------------------------------------
    "sub_bass": {"plugin": "tripleoscillator", "attrs": osc3((SINE, SINE, SINE), (80, 0, 0)), "role": "sub",
                 "env": {"attack": 0.005, "sustain": 1.0, "release": 0.08}},
    "offbeat_bass": {"plugin": "tripleoscillator", "role": "bass",
                     "attrs": osc3((SAW, SQUARE, SINE), (45, 30, 40), fine=((-5, 5), (4, -4), (0, 0))),
                     "env": {"attack": 0.002, "decay": 0.25, "sustain": 0.6, "release": 0.06},
                     "filter": (420, 0.6, FILTER_LP24), "cut_env": {"decay": 0.16, "sustain": 0.0, "amount": 0.45}},
    "rolling_bass": {"plugin": "tripleoscillator", "role": "bass",
                     "attrs": osc3((SAW, SAW, SINE), (55, 25, 30), coarse=(0, 0, 0), fine=((0, 0), (6, -6), (0, 0))),
                     "env": {"attack": 0.001, "decay": 0.13, "sustain": 0.0, "release": 0.03},
                     "filter": (180, 0.9, FILTER_MOOG), "cut_env": {"decay": 0.07, "sustain": 0.0, "amount": 0.5}},
    "reese_bass": {"plugin": "tripleoscillator", "role": "bass",
                   "attrs": osc3((SAW, SAW, SINE), (45, 45, 45), fine=((-18, -14), (16, 19), (0, 0))),
                   "env": {"attack": 0.01, "sustain": 1.0, "release": 0.12}, "filter": (550, 0.8, FILTER_LP24)},
    "ebm_bass": {"plugin": "tripleoscillator", "role": "bass",
                 "attrs": osc3((SAW, SQUARE, SINE), (50, 35, 35), fine=((-3, 3), (3, -3), (0, 0))),
                 "env": {"attack": 0.001, "decay": 0.18, "sustain": 0.35, "release": 0.04},
                 "filter": (500, 1.4, FILTER_LP24), "cut_env": {"decay": 0.12, "sustain": 0.0, "amount": 0.6}},
    "fm_bass": {"plugin": "tripleoscillator", "role": "bass",
                "attrs": osc3((SINE, SINE, SINE), (70, 55, 45), coarse=(0, 0, 0), mod=(MOD_PM, MOD_MIX)),
                "env": {"attack": 0.001, "decay": 0.3, "sustain": 0.5, "release": 0.06}},
    "moog_bass": {"plugin": "tripleoscillator", "role": "bass",
                  "attrs": osc3((MOOG_SAW, MOOG_SAW, SINE), (50, 40, 30), coarse=(0, 12, 0), fine=((-4, 4), (3, -3), (0, 0))),
                  "env": {"attack": 0.003, "decay": 0.4, "sustain": 0.7, "release": 0.1},
                  "filter": (380, 0.5, FILTER_LP24), "cut_env": {"decay": 0.3, "sustain": 0.2, "amount": 0.45}},
    "pick_bass": {"plugin": "tripleoscillator", "role": "bass",
                  "attrs": osc3((SAW, TRIANGLE, SQUARE), (40, 55, 15), coarse=(0, 0, 0), fine=((-3, 3), (0, 0), (2, -2))),
                  "env": {"attack": 0.002, "decay": 0.9, "sustain": 0.35, "release": 0.12},
                  "filter": (700, 0.6, FILTER_LP24), "cut_env": {"decay": 0.25, "sustain": 0.1, "amount": 0.45},
                  "fx": [("chorus", {"rate_hz": 0.6, "depth_ms": 2.0, "wet": 0.35})]},
    "acid_bass": {"plugin": "lb302", "attrs": acid(), "role": "bass"},
    "acid_square": {"plugin": "lb302", "attrs": acid(square=True, cutoff=0.4, resonance=0.95), "role": "bass"},
    "808_bass": {"plugin": "kicker", "attrs": kicker(140, 55, 1400, slope=0.03, env=0.85, click=0.1, follow_note=True),
                 "role": "bass", "gate_s": 1.2},
    "wobble_bass": {"plugin": "tripleoscillator", "role": "bass",
                    "attrs": osc3((SAW, SQUARE, SINE), (45, 40, 40), fine=((-8, 8), (7, -7), (0, 0))),
                    "env": {"attack": 0.005, "sustain": 1.0, "release": 0.08}, "filter": (350, 2.5, FILTER_LP24),
                    "cut_lfo": {"beats": 0.5, "amount": 0.45}},
    # ---- leads and plucks -------------------------------------------------------------------------
    "supersaw_lead": {"plugin": "tripleoscillator", "role": "lead",
                      "attrs": osc3((SAW, SAW, SAW), (33, 33, 33), fine=WIDE, spread=(0, 40, 80), pan=(-30, 30, 0)),
                      "env": {"attack": 0.008, "decay": 0.3, "sustain": 0.8, "release": 0.28}, "filter": (14000, 0.3, FILTER_LP),
                      "fx": [("chorus", {"rate_hz": 0.35, "depth_ms": 2.5, "wet": 0.45})]},
    "supersaw_high": {"plugin": "tripleoscillator", "role": "lead",
                      "attrs": osc3((SAW, SAW, SAW), (30, 30, 25), coarse=(12, 12, 0), fine=((-17, 13), (15, -19), (-7, 8)),
                                    spread=(20, 60, 100), pan=(-45, 45, 0)),
                      "env": {"attack": 0.01, "decay": 0.3, "sustain": 0.75, "release": 0.3}, "filter": (14000, 0.3, FILTER_LP)},
    "saw_lead": {"plugin": "tripleoscillator", "role": "lead",
                 "attrs": osc3((SAW, SAW, SQUARE), (45, 40, 15), coarse=(0, 0, -12), fine=((-6, 6), (5, -5), (0, 0))),
                 "env": {"attack": 0.005, "decay": 0.25, "sustain": 0.8, "release": 0.15}, "filter": (5500, 0.9, FILTER_LP24)},
    "square_lead": {"plugin": "tripleoscillator", "role": "lead",
                    "attrs": osc3((SQUARE, SQUARE, TRIANGLE), (38, 30, 30), coarse=(0, 0, 12), fine=((-5, 5), (6, -6), (0, 0))),
                    "env": {"attack": 0.004, "decay": 0.2, "sustain": 0.75, "release": 0.12}, "filter": (4200, 0.7, FILTER_LP24)},
    "rave_stab": {"plugin": "tripleoscillator", "role": "lead",
                  "attrs": osc3((SAW, SAW, SQUARE), (40, 40, 30), coarse=(0, -12, 0), fine=((-25, 20), (22, -27), (-9, 9)),
                                spread=(0, 50, 100)),
                  "env": {"attack": 0.002, "decay": 0.35, "sustain": 0.5, "release": 0.18}, "filter": (6500, 1.0, FILTER_LP),
                  "fx": [("chorus", {"rate_hz": 0.8, "depth_ms": 3.5, "wet": 0.6})]},
    "chip_lead": {"plugin": "tripleoscillator", "role": "lead",
                  "attrs": osc3((SQUARE, SQUARE, SQUARE), (45, 25, 0), coarse=(0, 12, 0)),
                  "env": {"attack": 0.001, "sustain": 1.0, "release": 0.03}},
    "acid_lead": {"plugin": "lb302", "attrs": acid(cutoff=0.6, resonance=1.0, env_mod=0.75, decay=0.25, dist=0.35), "role": "lead"},
    "pluck": {"plugin": "tripleoscillator", "role": "pluck",
              "attrs": osc3((SAW, SQUARE, SAW), (42, 28, 25), coarse=(0, 0, 12), fine=((-6, 6), (5, -5), (-8, 8))),
              "env": {"attack": 0.001, "decay": 0.4, "sustain": 0.0, "release": 0.2},
              "filter": (500, 0.9, FILTER_LP24), "cut_env": {"decay": 0.2, "sustain": 0.0, "amount": 0.75}},
    "trance_pluck": {"plugin": "tripleoscillator", "role": "pluck",
                     "attrs": osc3((SAW, SAW, SAW), (35, 35, 28), coarse=(0, 0, 12), fine=WIDE, spread=(0, 40, 80), pan=(-25, 25, 0)),
                     "env": {"attack": 0.001, "decay": 0.5, "sustain": 0.0, "release": 0.25},
                     "filter": (900, 0.7, FILTER_LP24), "cut_env": {"decay": 0.28, "sustain": 0.0, "amount": 0.95}},
    "jangle_pluck": {"plugin": "tripleoscillator", "role": "pluck",
                     "attrs": osc3((SAW, SQUARE, SAW), (40, 22, 22), coarse=(0, 0, 12), fine=((-4, 4), (3, -3), (-6, 6))),
                     "env": {"attack": 0.002, "decay": 1.1, "sustain": 0.12, "release": 0.25},
                     "filter": (1800, 0.5, FILTER_LP), "cut_env": {"decay": 0.5, "sustain": 0.0, "amount": 0.6},
                     "fx": [("chorus", {"rate_hz": 0.9, "depth_ms": 3.0, "wet": 0.7})]},
    "bell": {"plugin": "tripleoscillator", "role": "pluck",
             "attrs": osc3((SINE, SINE, SINE), (60, 60, 20), coarse=(0, 19, 24), mod=(MOD_PM, MOD_MIX)),
             "env": {"attack": 0.001, "decay": 1.6, "sustain": 0.0, "release": 0.6}},
    # ---- pads, strings, keys ------------------------------------------------------------------------
    "warm_pad": {"plugin": "tripleoscillator", "role": "pad",
                 "attrs": osc3((SAW, SAW, TRIANGLE), (35, 35, 35), coarse=(0, 0, -12), fine=((-9, 7), (8, -10), (0, 0)), spread=(0, 60, 0)),
                 "env": {"attack": 0.6, "decay": 0.5, "sustain": 0.85, "release": 1.4}, "filter": (1700, 0.3, FILTER_LP24),
                 "fx": [("chorus", {"rate_hz": 0.3, "depth_ms": 3.0, "wet": 0.5})]},
    "string_pad": {"plugin": "tripleoscillator", "role": "pad",
                   "attrs": osc3((SAW, SAW, SAW), (33, 33, 30), coarse=(0, 0, 12), fine=WIDE, spread=(0, 45, 90), pan=(-35, 35, 0)),
                   "env": {"attack": 0.22, "decay": 0.4, "sustain": 0.85, "release": 0.9}, "filter": (7500, 0.3, FILTER_LP),
                   "fx": [("chorus", {"rate_hz": 0.4, "depth_ms": 2.5, "wet": 0.4})]},
    "dark_pad": {"plugin": "tripleoscillator", "role": "pad",
                 "attrs": osc3((TRIANGLE, SAW, SINE), (45, 25, 35), coarse=(0, 0, -12), fine=((-7, 7), (9, -9), (0, 0))),
                 "env": {"attack": 1.0, "decay": 0.6, "sustain": 0.9, "release": 2.0}, "filter": (650, 0.4, FILTER_LP24)},
    "cold_pad": {"plugin": "tripleoscillator", "role": "pad",
                 "attrs": osc3((SQUARE, SAW, SQUARE), (30, 35, 22), coarse=(0, 0, 12), fine=((-8, 6), (7, -9), (-11, 11))),
                 "env": {"attack": 0.15, "decay": 0.5, "sustain": 0.8, "release": 0.8}, "filter": (2400, 0.4, FILTER_LP),
                 "fx": [("chorus", {"rate_hz": 0.55, "depth_ms": 4.0, "wet": 0.8})]},
    "organ": {"plugin": "tripleoscillator", "role": "keys",
              "attrs": osc3((SINE, SINE, SINE), (45, 35, 22), coarse=(0, 12, 19)),
              "env": {"attack": 0.004, "sustain": 1.0, "release": 0.06}},
    "epiano": {"plugin": "tripleoscillator", "role": "keys",
               "attrs": osc3((SINE, SINE, TRIANGLE), (65, 22, 30), coarse=(0, 12, 0), mod=(MOD_PM, MOD_MIX)),
               "env": {"attack": 0.002, "decay": 1.4, "sustain": 0.15, "release": 0.3}},
    "chord_stab": {"plugin": "tripleoscillator", "role": "keys",
                   "attrs": osc3((SAW, SQUARE, SAW), (38, 28, 28), coarse=(0, 0, 12), fine=((-7, 7), (6, -6), (-9, 9))),
                   "env": {"attack": 0.001, "decay": 0.25, "sustain": 0.0, "release": 0.12},
                   "filter": (1500, 0.8, FILTER_LP24), "cut_env": {"decay": 0.15, "sustain": 0.0, "amount": 0.6}},
    # ---- noise and effects --------------------------------------------------------------------------
    "white_noise": {"plugin": "audiofileprocessor", "role": "fx", "attrs": sample(f"{KIT_FOLDER}/white_noise.wav", loop=True),
                    "basenote": DRUM_BASENOTE, "env": {"attack": 0.01, "sustain": 1.0, "release": 0.3}},
}

KIT_EXCLUDED = ("white_noise",)                   # frozen files that are not one-shot drums


def _kit_role(name: str) -> str:
    piece = name.split("_", 1)[-1]
    for role, words in (("kick", ("kick", "boom")), ("snare", ("snare",)), ("clap", ("clap",)),
                        ("hat", ("hat", "cabasa", "maracas")), ("cymbal", ("ride", "cymbal"))):
        if any(word in piece for word in words):
            return role
    return "perc"


def _load_kit() -> dict[str, dict]:
    """Patches for the kit one-shots (kit.py makes the files on first use; their lengths are fixed in kit_lengths.json)."""
    durations = kit._lengths()
    return {name: _drum("audiofileprocessor", sample(f"{KIT_FOLDER}/{name}.wav"), _kit_role(name), seconds + KIT_GATE_MARGIN)
            for name, seconds in durations.items() if name not in KIT_EXCLUDED}


PATCHES.update(_load_kit())

# Mix role of each patch decides its default mixer treatment (see compose.ROLE_STRIPS).
ROLES = ("kick", "snare", "clap", "hat", "cymbal", "perc", "sub", "bass", "lead", "pluck", "pad", "keys", "fx",
         "vocal", "vocal_bg")


def get(name: str, **overrides) -> dict:
    """Copy of a patch with top-level keys overridden (e.g. filter=(800, 0.5, FILTER_LP24))."""
    if name not in PATCHES:
        raise KeyError(f"unknown patch '{name}'. Available: {', '.join(sorted(PATCHES))}")
    patch = copy.deepcopy(PATCHES[name])
    for key, value in overrides.items():
        if key == "attrs":
            patch["attrs"].update(value)
        else:
            patch[key] = value
    return patch


def add(project: Project, track_name: str, patch: dict | str, *, fxch: int = 0, vol: float | None = None, pan: float = 0) -> Track:
    """Create an instrument track from a patch (name or dict)."""
    if isinstance(patch, str):
        patch = get(patch)
    track = project.add_instrument_track(track_name, patch["plugin"], patch["attrs"], fxch=fxch, pan=pan,
                                         vol=vol if vol is not None else patch.get("vol", 100),
                                         basenote=patch.get("basenote", DEFAULT_BASENOTE))
    if "env" in patch:
        project.set_envelope(track, "vol", **patch["env"])
    if "filter" in patch:
        project.set_filter(track, *patch["filter"])
    if "cut_env" in patch:
        project.set_envelope(track, "cut", **{"release": 0.1, **patch["cut_env"]})
    if "cut_lfo" in patch:
        set_cutoff_lfo(project, track, **patch["cut_lfo"])
    for effect_name, arguments in patch.get("fx", []):
        getattr(fx, effect_name)(track.fx, **arguments)
    return track


def set_cutoff_lfo(project: Project, track: Track, beats: float, amount: float, wave: int = 0) -> None:
    """Per-note filter LFO with a period given in beats at the project tempo (wobble bass, slow pad motion)."""
    period_seconds = beats * project.seconds_per_beat()
    element = track.settings.find("eldata/elcut")
    element.attrib.update({"lspd": f"{min(1.0, period_seconds / LFO_SECONDS_AT_KNOB_ONE):.5f}", "lamt": str(amount),
                           "lshp": str(wave), "x100": "0", "lpdel": "0", "latt": "0"})
    if float(element.get("amt", "0")) == 0:
        element.set("amt", "0.001")           # LMMS skips the whole modulator when the envelope amount is exactly 0


def note_length_beats(patch: dict, bpm: float, default: float = 0.25) -> float:
    """Drum patches must be held for their whole sound (LMMS cuts a sample at note-off)."""
    return patch["gate_s"] * bpm / 60.0 if "gate_s" in patch else default


def install_kit(project: Project, project_path: str) -> list[str]:
    """Copy the kit one-shots a project uses into <project folder>/samples/kit so it renders and travels on its own.

    The kit itself is made on this machine the first time this is needed (see kit.py).
    """
    target = os.path.join(os.path.dirname(os.path.abspath(project_path)), "samples", KIT_FOLDER)
    copied = []
    used = sorted({os.path.basename(element.get("src", "")) for element in project.root.iter("audiofileprocessor")
                   if element.get("src", "").startswith(KIT_FOLDER + "/")})
    if not used:
        return []
    kit_dir = kit.ensure()
    os.makedirs(target, exist_ok=True)
    for name in used:
        installed = os.path.join(target, name)
        # Also replace a copy that differs: after the kit is rebuilt, an old copy beside the project must not live on.
        if not os.path.exists(installed) or not filecmp.cmp(os.path.join(kit_dir, name), installed, shallow=False):
            shutil.copyfile(os.path.join(kit_dir, name), installed)
        copied.append(name)
    kit.write_notices(target, [os.path.splitext(name)[0] for name in used])     # the sounds travel with their notice, licence and preset sources
    return sorted(set(copied))
