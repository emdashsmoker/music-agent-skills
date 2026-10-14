# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""The drum kit: one-shot WAV files made on this machine the first time a song needs them.

The skill ships no audio. The kit has two kinds of sound:

- Named kicks and a noise loop are computed here with numpy from fixed settings and seeds, so every machine
  gets the same files.
- Drum-machine hits are recorded once from the DrumSynth presets of the LMMS that is installed here. LMMS
  synthesizes those presets with fresh random noise on every start, so a song that played them directly would
  never render the same way twice. Recorded once, they make every later render on this machine identical.
  Noise-based hits (snares, hats, claps) differ slightly between two machines, as two takes of the same
  drum machine would.

The files live in the kit folder (settings key kit_dir, default <cache>/kit) and are copied into
samples/kit beside each project that uses them.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile

import numpy as np

from . import audio, render, settings

KIT_VERSION = 1                         # raise when the settings below change, so existing kit folders are rebuilt
STATE_FILE, NOTICE_FILE = "kit.json", "NOTICE.txt"
RATE = 44100
PEAK_DB = -1.0

# -- named kicks ------------------------------------------------------------------------------------------
# A kick is a sine whose pitch drops fast to the note that carries the weight, an envelope that holds briefly and
# then decays, and a click of a few milliseconds so the hit cuts through. No noise layer under the body: noise
# that lasts as long as the kick is heard as hiss on every beat. Harder styles get their edge from saturating the sine.
CLICK_SEED = 909
CLICK_TAU_S = 0.0012
CLICK_HIGHPASS_HZ = 1500.0
END_FADE_SHARE = 0.2                    # last part of the sound eased to exact silence
# name: start Hz, end Hz, pitch-drop time constant ms, length ms, hold ms, decay time constant ms, click dB, drive
KICKS = {
    "trance_kick":     (190, 50, 18, 230, 30, 55, -16, 1.6),
    "house_kick":      (150, 50, 25, 320, 30, 90, -22, 1.3),
    "techno_kick":     (130, 44, 30, 420, 60, 110, -24, 2.2),
    "psy_kick":        (380, 52, 9, 170, 25, 45, -12, 1.5),
    "dnb_kick":        (230, 56, 14, 200, 20, 55, -14, 2.0),
    "hard_kick":       (480, 55, 35, 420, 150, 120, -14, 12.0),
    "industrial_kick": (210, 45, 28, 360, 60, 100, -16, 5.0),
    "boom_kick":       (120, 42, 40, 850, 80, 260, -30, 1.1),
}
NOISE_NAME, NOISE_SECONDS, NOISE_SEED, NOISE_PEAK = "white_noise", 6.0, 20240, 0.5

# -- drum-machine hits ----------------------------------------------------------------------------------
# name: DrumSynth preset, as a path under the 'drumsynth' folder of the LMMS factory samples. LMMS resolves these
# paths itself, so they work for any way LMMS is installed, also when its data folder cannot be seen from here.
DRUMSYNTH_FOLDER = "drumsynth"
MACHINE_HITS = {
    "909_kick": "tr909/TR909_Kick.ds", "909_kick2": "tr909/Kick.ds", "909_snare": "tr909/Snare.ds", "909_snare2": "tr909/Snare2.ds",
    "909_clap": "tr909/TR909_Clap.ds", "909_hat": "tr909/Hat-c.ds", "909_hat2": "tr909/Hat-c2.ds", "909_ohat": "tr909/Hat-o.ds",
    "808_kick": "tr808/Kick.ds", "808_kick_hard": "tr808/Kickhard.ds", "808_kick_long": "tr808/Kicklong.ds", "808_snare": "tr808/Snare.ds",
    "808_snare_snap": "tr808/Snr_snap.ds", "808_clap": "tr808/Handclap.ds", "808_hat": "tr808/Hat_c.ds", "808_ohat": "tr808/Hat_o.ds",
    "808_rim": "tr808/Rimshot.ds", "808_cowbell": "tr808/Cowbell.ds", "808_clave": "tr808/Clave.ds", "808_tom_lo": "tr808/Tom_lo.ds",
    "808_tom_mid": "tr808/Tom_mid.ds", "808_tom_hi": "tr808/Tom_hi.ds", "808_ride": "tr808/Ride.ds",
    "606_kick": "tr606/TR606_Kick.ds", "606_snare": "tr606/TR606_Snare.ds", "606_hat": "tr606/TR606_Hat_C.ds",
    "606_ohat": "tr606/TR606_Hat_O.ds", "606_cymbal": "tr606/TR606_Cymbal.ds", "606_tom_hi": "tr606/TR606_Tom_H.ds",
    "606_tom_lo": "tr606/TR606_Tom_L.ds",
    "linn_kick": "linn/linn_kik.ds", "linn_snare": "linn/linn_snr.ds", "linn_clap": "linn/linn_clp.ds", "linn_tamb": "linn/linn_tamb.ds",
    "linn_cabasa": "linn/linn_cab.ds", "linn_cowbell": "linn/linn_cow.ds", "linn_stick": "linn/linn_stk.ds",
    "linn_tom_hi": "linn/linn_tom1.ds", "linn_tom_mid": "linn/linn_tom3.ds", "linn_tom_lo": "linn/linn_tom5.ds",
    "linn_conga": "linn/linn_cga1.ds",
    "cr78_kick": "cr78/Kick.ds", "cr78_snare": "cr78/Snare.ds", "cr78_hat": "cr78/Hihat.ds", "cr78_cymbal": "cr78/Cymbal.ds",
    "cr78_maracas": "cr78/Maracas.ds", "cr78_rim": "cr78/Rim.ds", "cr78_tamb": "cr78/Tamb.ds", "cr78_conga": "cr78/Conga.ds",
    "cr78_bongo_hi": "cr78/Bongo_h.ds", "cr78_bongo_lo": "cr78/Bongo_l.ds", "cr78_clave": "cr78/Clave.ds",
    "electro_kick": "electro/K_Linn.ds", "electro_snare": "electro/S_Linn.ds", "reverb_kick": "electro/K_reverb.ds",
    "reverb_snare": "electro/S_reverb.ds", "8bit_kick": "electro/K_8bit.ds", "8bit_snare": "electro/S_8bit.ds",
    "electro_hat": "electro/H_closed.ds", "electro_ohat": "electro/H_open.ds", "syntom": "electro/Syntom_1.ds",
    "syntom2": "electro/Syntom_2.ds", "electro_boom": "electro/Boom.ds",
    "jazz_kick": "acoustic/JazzKick.ds", "jazz_snare": "acoustic/JazzSnr.ds", "brush": "acoustic/Brush1.ds",
    "acoustic_ride": "acoustic/Ride.ds", "big_beat_clap": "misc_claps/big_beat_clap.ds", "amen_ride": "misc_hats/amen_ride.ds",
}
SLOT_SECONDS, FREEZE_BPM, SILENCE_DB, FADE_SECONDS = 4.0, 120.0, -66.0, 0.004

# The recorded hits stay under the GPL of the presets, so they travel with the licence text and the preset files
# (their source). The skill carries copies of the presets above, taken from LMMS 1.2.2, for this purpose only:
# the recording itself always plays the presets of the installed LMMS.
PRESET_COPIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drumsynth")
LICENSE_FILE, SOURCE_FOLDER = "COPYING", "source"

NOTICE = """Drum one-shots in this folder
=============================

These files were made on the computer that built this kit, by the Synth Ventriloquist skill.

- The 606_, 808_, 909_, linn_, cr78_, electro_, 8bit_, reverb_, jazz_ and similar drum-machine hits are
  recordings of the DrumSynth presets of the LMMS installed there (https://lmms.io). LMMS and its presets are
  licensed under the GNU General Public License, version 2 or later. A hit that sounds in a finished song
  is in the same position as the sound of any song made in LMMS with those presets. When you pass these
  files on as files (for example inside a project pack), keep this notice, COPYING and the source folder
  with them.
- COPYING holds the text of the GNU General Public License, version 2, as shipped with LMMS.
- source/drumsynth/ holds the DrumSynth preset files of these hits, as shipped with LMMS 1.2.2
  (https://github.com/LMMS/lmms/tree/v1.2.2/data/samples/drumsynth). Copyright (c) 1998-2000 Paul Kellett
  (mda-vst.com) and the LMMS developers. Opening a preset in LMMS plays the same sound.
  If the hits were recorded with another LMMS version, its own presets were used: they are at the same
  path under data/samples/drumsynth in the source of that version (https://github.com/LMMS/lmms).
- The named kicks (trance_kick, house_kick, techno_kick, psy_kick, dnb_kick, hard_kick, industrial_kick,
  boom_kick) and white_noise.wav were computed by the skill from fixed settings. They are plain program
  output and carry no restrictions from the skill.
"""


def _lengths() -> dict[str, float]:
    """Length in seconds each kit sound is given. Fixed, so that note lengths do not depend on the machine."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit_lengths.json"), encoding="utf-8") as handle:
        return json.load(handle)


def names() -> list[str]:
    return sorted([*KICKS, *MACHINE_HITS, NOISE_NAME])


def folder() -> str:
    return settings.get("kit_dir") or os.path.join(settings.cache_dir(), "kit")


def path_of(name: str) -> str:
    return os.path.join(folder(), name + ".wav")


def synthesize_kick(start_hz: float, end_hz: float, pitch_ms: float, length_ms: float, hold_ms: float, decay_ms: float,
                    click_db: float, drive: float) -> np.ndarray:
    t = np.arange(int(length_ms / 1000 * RATE)) / RATE
    frequency = end_hz + (start_hz - end_hz) * np.exp(-t / (pitch_ms / 1000))
    body = np.sin(2 * np.pi * np.cumsum(frequency) / RATE)
    body = np.tanh(drive * body) / np.tanh(drive)                             # drive 1 is nearly a pure sine
    envelope = np.where(t < hold_ms / 1000, 1.0, np.exp(-(t - hold_ms / 1000) / (decay_ms / 1000)))
    fade = int(len(t) * END_FADE_SHARE)
    envelope[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))
    noise = np.random.default_rng(CLICK_SEED).standard_normal(len(t))
    alpha = np.exp(-2 * np.pi * CLICK_HIGHPASS_HZ / RATE)
    low = np.zeros(len(t))
    for i in range(1, min(len(t), int(10 * CLICK_TAU_S * RATE))):              # only the first milliseconds matter
        low[i] = alpha * low[i - 1] + (1 - alpha) * noise[i]
    click = (noise - low) * np.exp(-t / CLICK_TAU_S)
    click *= 10 ** (click_db / 20) / np.max(np.abs(click))
    sound = body * envelope + click
    return sound / np.max(np.abs(sound)) * 10 ** (PEAK_DB / 20)


def _write_computed(out_dir: str) -> None:
    for name, kick_settings in KICKS.items():
        audio.save(os.path.join(out_dir, name + ".wav"), synthesize_kick(*kick_settings), RATE)
    noise = np.random.default_rng(NOISE_SEED).uniform(-NOISE_PEAK, NOISE_PEAK, (int(NOISE_SECONDS * RATE), 2))
    audio.save(os.path.join(out_dir, NOISE_NAME + ".wav"), noise, RATE)        # seeded: loops as a deterministic noise source


def _record_machine_hits(out_dir: str) -> list[str]:
    """Play every preset once in one LMMS render, cut the render into hits, trim and normalise them. Returns silent names."""
    from .project import Note, Project
    from .sounds import DRUM_BASENOTE, DRUM_PITCH, sample
    lengths, hit_names = _lengths(), list(MACHINE_HITS)
    slot_beats = SLOT_SECONDS * FREEZE_BPM / 60.0
    project = Project.new(bpm=FREEZE_BPM)
    for index, name in enumerate(hit_names):
        track = project.add_instrument_track(name, "audiofileprocessor", sample(f"{DRUMSYNTH_FOLDER}/{MACHINE_HITS[name]}"), basenote=DRUM_BASENOTE)
        track.add_pattern(index * slot_beats, [Note(0.0, slot_beats - 0.25, DRUM_PITCH)])
    with tempfile.TemporaryDirectory(prefix="record-", dir=out_dir) as scratch:          # inside the kit folder: visible to a sandboxed LMMS
        project.save(os.path.join(scratch, "kit.mmp"))
        x, rate = audio.load(render.render(os.path.join(scratch, "kit.mmp"), os.path.join(scratch, "kit.wav"), oversampling=1))
    silent = []
    for index, name in enumerate(hit_names):
        slot = x[int(index * SLOT_SECONDS * rate):int((index + 1) * SLOT_SECONDS * rate)]
        start, end = audio.trim_silence(slot, rate, SILENCE_DB)
        if end <= start:
            silent.append(name)
            continue
        piece = slot[:min(end, int(lengths[name] * rate))].mean(axis=1)       # DrumSynth output is mono
        piece = piece / np.max(np.abs(piece)) * 10 ** (PEAK_DB / 20)
        fade = min(len(piece), int(FADE_SECONDS * rate))
        piece[-fade:] *= np.linspace(1.0, 0.0, fade)
        audio.save(os.path.join(out_dir, name + ".wav"), piece, rate)
    return silent


def write_notices(target: str, sound_names: list[str]) -> None:
    """Write the notice, the GPL text and the preset files of the drum-machine hits among sound_names into target."""
    with open(os.path.join(target, NOTICE_FILE), "w", encoding="utf-8") as handle:
        handle.write(NOTICE)
    shutil.copyfile(os.path.join(PRESET_COPIES, LICENSE_FILE), os.path.join(target, LICENSE_FILE))
    source = os.path.join(target, SOURCE_FOLDER)
    shutil.rmtree(source, ignore_errors=True)                                 # presets of hits a song no longer uses must not linger
    for name in sound_names:
        if name in MACHINE_HITS:
            preset = os.path.join(source, DRUMSYNTH_FOLDER, MACHINE_HITS[name])
            os.makedirs(os.path.dirname(preset), exist_ok=True)
            shutil.copyfile(os.path.join(PRESET_COPIES, MACHINE_HITS[name]), preset)


def status() -> dict:
    """What is in the kit folder now. Reads only."""
    state_path = os.path.join(folder(), STATE_FILE)
    state = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
    missing = [name for name in names() if not os.path.isfile(path_of(name))]
    return {"folder": folder(), "built": bool(state), "version": state.get("version"), "lmms": state.get("lmms"),
            "missing": missing, "ready": not missing and state.get("version") == KIT_VERSION}


def build(out_dir: str | None = None) -> dict:
    """Make the whole kit in out_dir (default: the kit folder). Needs LMMS for the drum-machine hits. One short render, a few seconds."""
    out_dir = out_dir or folder()
    os.makedirs(out_dir, exist_ok=True)
    _write_computed(out_dir)
    silent = _record_machine_hits(out_dir)
    if silent:
        raise RuntimeError(f"LMMS rendered no sound for {len(silent)} DrumSynth presets ({', '.join(silent[:5])} ...): this LMMS came without "
                           "its factory samples, or with another preset layout. See references/setup.md, Drum kit")
    write_notices(out_dir, list(MACHINE_HITS))
    state = {"version": KIT_VERSION, "lmms": render.lmms_version(), "sounds": len(names())}
    with open(os.path.join(out_dir, STATE_FILE), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=1)
    return {"folder": out_dir, **state}


def ensure() -> str:
    """The kit folder, built first if it is not complete."""
    if not status()["ready"]:
        build()
    return folder()
