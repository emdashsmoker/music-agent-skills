# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Export a project as an LMMS song (.mmp, LMMS 1.2 format).

What goes where
  drums            AudioFileProcessor tracks loaded with one-shots rendered by this engine: same sounds, editable hits
  tonal tracks     TripleOscillator tracks with oscillators, envelope and filter approximated from the patch:
                   editable notes, close but not identical tone
  vocals, sweeps   sample tracks holding rendered stems (written by `render --stems`)
Notes are grouped into one pattern per section so the arrangement stays readable in LMMS.
Samples go to samples/<song>/ beside the project and are referenced as "<song>/<file>", relative to the LMMS
samples folder, because LMMS 1.2 resolves relative paths there and not beside the project file. Copying that one
folder into the LMMS samples folder makes the project open on any machine; HOW_TO_OPEN.txt says so."""
from __future__ import annotations

import glob
import os
import xml.etree.ElementTree as ET

import numpy as np
import soundfile as sf

from . import export, fx, instruments, mixprofile
from .dsp import SR

TICKS_PER_BEAT = 48
LMMS_BASE_NOTE = 57             # LMMS 1.2 counts keys from C0, so A4 is 57 where MIDI says 69
MIDI_TO_LMMS = -12
ENVELOPE_SECONDS = 5.0          # LMMS envelope knobs map x -> x^2 * 5 seconds
HEADROOM_DB = -6.0              # LMMS sums tracks without a limiter; this keeps the exported song below clipping
STEM_VOLUME = 100.0 * 10.0 ** (HEADROOM_DB / 20.0)     # stems already carry their mix level
SAMPLES_SUBDIR = "samples"       # LMMS resolves relative sample paths under <working directory>/samples
HOW_TO_OPEN = ("Open {name}.mmp in LMMS 1.2 or newer.\n"
               "Copy the folder samples/{name} into your LMMS samples folder first (LMMS: Edit > Settings > Paths > "
               "'LMMS working directory', subfolder 'samples'), otherwise the drum and vocal tracks stay silent.\n")
WAVES = {"sine": 0, "tri": 1, "saw": 2, "square": 3, "pulse": 3, "noise": 6}


def _knob(seconds: float) -> str:
    return f"{min(1.0, np.sqrt(max(seconds, 0.0) / ENVELOPE_SECONDS)):.4f}"


def _envelope(parent, tag: str, adsr, amount: float) -> None:
    attack, decay, sustain, release = adsr
    ET.SubElement(parent, tag, pdel="0", att=_knob(attack), hold="0", dec=_knob(decay), sustain=f"{sustain:.3f}",
                  rel=_knob(release), amt=f"{amount:.3f}", lpdel="0", latt="0", lspd="0.1", lamt="0", lshp="0", x100="0",
                  ctlenvamt="0", lspd_numerator="4", lspd_denominator="4", syncmode="0", userwavefile="")


def _oscillators(patch: dict) -> list:
    """Up to three (wave, coarse, fine_left, fine_right, volume) taken from the patch's own oscillators."""
    engine = patch.get("engine", "sub")
    if engine == "fm":
        return [(0, 0, 0, 0, 60), (0, 12, 0, 0, 25), (1, 0, 0, 0, 20)]
    if engine == "organ":
        return [(0, 0, 0, 0, 55), (0, 12, 0, 0, 30), (0, 19, 0, 0, 15)]
    if engine == "pluck":
        return [(2, 0, -3, 3, 60), (1, 0, 0, 0, 30)]
    out = []
    for osc in patch.get("osc", [{"wave": "saw"}])[:3]:
        half = float(osc.get("spread", 0.0)) / 2.0 + abs(float(osc.get("detune", 0.0)))
        coarse = int(osc.get("octave", 0)) * 12 + int(osc.get("semi", 0))
        out.append((WAVES.get(osc.get("wave", "saw"), 2), coarse, -half, half, 33.0 * float(osc.get("level", 1.0))))
    return out


def _triple_oscillator(track_el, patch: dict) -> None:
    instrument = ET.SubElement(track_el, "instrument", name="tripleoscillator")
    attrs = {}
    oscillators = _oscillators(patch) + [(0, 0, 0, 0, 0)] * 3
    for index, (wave, coarse, left, right, volume) in enumerate(oscillators[:3]):
        attrs.update({f"wavetype{index}": str(wave), f"coarse{index}": str(coarse), f"finel{index}": f"{left:.1f}",
                      f"finer{index}": f"{right:.1f}", f"vol{index}": f"{min(volume, 200):.1f}", f"pan{index}": "0",
                      f"phoffset{index}": "0", f"stphdetun{index}": "0", f"userwavefile{index}": ""})
    attrs.update({"modalgo1": "2", "modalgo2": "2", "modalgo3": "2"})
    ET.SubElement(instrument, "tripleoscillator", **attrs)
    flt = patch.get("filter") or {}
    cutoff = float(flt.get("cutoff", 14000.0)) * 2.0 ** (0.4 * float(flt.get("env", 0.0)))
    eldata = ET.SubElement(track_el, "eldata", fwet="1" if flt else "0", ftype={"lp": "0", "hp": "1", "bp": "2"}.get(
        flt.get("type", "lp"), "0"), fcut=f"{min(max(cutoff, 30.0), 14000.0):.0f}", fres=f"{0.5 + 4.0 * float(flt.get('res', 0.1)):.2f}")
    amp = patch.get("amp", (0.005, 0.2, 0.7, 0.2))
    _envelope(eldata, "elvol", amp, 1.0)
    fenv = patch.get("fenv", (0.005, float(patch.get("fenv_decay", 0.25)), 0.0, 0.2))
    _envelope(eldata, "elcut", fenv, 0.35 if flt.get("env") else 0.0)
    _envelope(eldata, "elres", (0, 0.5, 0.5, 0.1), 0.0)


def _sample_player(track_el, sample_path: str) -> None:
    instrument = ET.SubElement(track_el, "instrument", name="audiofileprocessor")
    ET.SubElement(instrument, "audiofileprocessor", src=sample_path, amp="100", reversed="0", looped="0", sframe="0",
                  eframe="1", lframe="0", stutter="0", interp="1")
    eldata = ET.SubElement(track_el, "eldata", fwet="0", ftype="0", fcut="14000", fres="0.5")
    _envelope(eldata, "elvol", (0, 0.5, 1.0, 0.3), 0.0)
    _envelope(eldata, "elcut", (0, 0.5, 0.5, 0.1), 0.0)
    _envelope(eldata, "elres", (0, 0.5, 0.5, 0.1), 0.0)


def _instrument_track(container, name: str, volume: float, pan: float):
    track = ET.SubElement(container, "track", type="0", name=name, muted="0", solo="0")
    inner = ET.SubElement(track, "instrumenttrack", vol=f"{volume:.1f}", pan=f"{pan * 100:.0f}", pitch="0", pitchrange="1",
                          basenote=str(LMMS_BASE_NOTE), fxch="0", usemasterpitch="1")
    return track, inner


def _finish_instrument(inner) -> None:
    ET.SubElement(inner, "chordcreator", chord="0", chordrange="1", **{"chord-enabled": "0"})
    ET.SubElement(inner, "arpeggiator", arp="0", arprange="1", arptime="100", arpgate="100", arpdir="0", arpmode="0",
                  **{"arp-enabled": "0", "arptime_numerator": "4", "arptime_denominator": "4", "arpsyncmode": "0",
                     "arpcycle": "0", "arpskip": "0", "arpmiss": "0"})
    ET.SubElement(inner, "midiport", readable="0", writable="0", inputchannel="0", outputchannel="1", inputcontroller="0",
                  outputcontroller="0", fixedinputvelocity="-1", fixedoutputvelocity="-1", fixedoutputnote="-1",
                  outputprogram="1", basevelocity="63")
    ET.SubElement(inner, "fxchain", numofeffects="0", enabled="0")


def _patterns(track_el, notes: list, sections: list, meter: float, fixed_key: int | None, hold_ticks: int | None) -> None:
    for section in sections:
        start, end = section["start"], section["start"] + section["bars"] * meter
        inside = [n for n in notes if start - 1e-6 <= n[0] < end - 1e-6]
        if not inside:
            continue
        pattern = ET.SubElement(track_el, "pattern", type="1", name=section["name"], muted="0", steps="16",
                                pos=str(int(round(start * TICKS_PER_BEAT))))
        for note in inside:
            length = hold_ticks or max(1, int(round(note[1] * TICKS_PER_BEAT)))
            key = fixed_key if fixed_key is not None else int(round(note[2])) + MIDI_TO_LMMS
            ET.SubElement(pattern, "note", pos=str(int(round((note[0] - start) * TICKS_PER_BEAT))), len=str(length),
                          key=str(int(np.clip(key, 0, 107))), vol=str(int(np.clip(note[3] * 125, 1, 200))), pan="0")


def write(project: dict, out_dir: str, name: str, stems_dir: str | None = None) -> str:
    """Write <out_dir>/<name>.mmp, its samples in <out_dir>/samples/<name>/ and HOW_TO_OPEN.txt. Returns the project path."""
    os.makedirs(os.path.join(out_dir, SAMPLES_SUBDIR, name), exist_ok=True)

    def sample_file(label: str) -> tuple:
        """(where the WAV is written, how the project refers to it); LMMS wants forward slashes on every system."""
        return os.path.join(out_dir, SAMPLES_SUBDIR, name, f"{label}.wav"), f"{name}/{label}.wav"

    meta = project["meta"]
    ctx = fx.FxContext(meta["bpm"], meta["seed"])
    root = ET.Element("lmms-project", version="1.0", creator="LMMS", creatorversion="1.2.2", type="song")
    ET.SubElement(root, "head", bpm=f"{meta['bpm']:g}", mastervol="100", masterpitch="0",
                  timesig_numerator=str(int(meta["meter"])), timesig_denominator="4")
    song = ET.SubElement(root, "song")
    container = ET.SubElement(song, "trackcontainer", type="song", visible="1", x="5", y="5", width="900", height="400",
                              maximized="0", minimized="0")
    notes_written, audio_written, skipped = 0, 0, []
    seconds_per_beat = 60.0 / meta["bpm"]
    for track in project["tracks"]:
        settings = mixprofile.track_settings(track, {})
        volume = float(np.clip(100.0 * 10.0 ** ((settings["level"] + settings["gain_db"] + HEADROOM_DB) / 20.0), 2.0, 200.0))
        stem = os.path.join(stems_dir, f"{track['name']}.flac") if stems_dir else None
        resolved = None if track.get("kind") == "vocal" else instruments.resolve(track["inst"], project.get("patches"))
        if resolved is not None and resolved["kind"] == "drum":
            sample, src = sample_file(track["name"])
            pitches = sorted({n[2] for n in track["notes"]})
            hit = instruments.render_track(resolved, [[0.0, 1.0, pitches[0] if len(pitches) == 1 else 60, 1.0]], ctx, 3 * SR, 1)
            length = max(1, int(np.nonzero(np.abs(hit) > 1e-4)[0][-1]) + 1) if np.any(hit) else SR // 10
            export.write_audio(sample, hit[:length])
            track_el, inner = _instrument_track(container, track["name"], volume, float(settings.get("pan", 0.0)))
            _sample_player(inner, src)
            _finish_instrument(inner)
            hold = max(1, int(np.ceil(length / SR / seconds_per_beat * TICKS_PER_BEAT)))
            fixed = LMMS_BASE_NOTE if len(pitches) == 1 else None
            _patterns(track_el, track["notes"], project["sections"], meta["meter"], fixed, hold)
            notes_written += len(track["notes"])
        elif resolved is not None and resolved["kind"] == "synth":
            track_el, inner = _instrument_track(container, track["name"], volume * 0.6, float(settings.get("pan", 0.0)))
            _triple_oscillator(inner, resolved["patch"])
            _finish_instrument(inner)
            _patterns(track_el, track["notes"], project["sections"], meta["meter"], None, None)
            notes_written += len(track["notes"])
        elif stem and os.path.exists(stem):
            layers = sorted(glob.glob(os.path.join(stems_dir, f"{glob.escape(track['name'])}.*.flac")))   # vocal doubles, harmonies
            for source in [stem] + layers:
                label = os.path.splitext(os.path.basename(source))[0]
                audio, rate = sf.read(source)
                sample, src = sample_file(label)
                export.write_audio(sample, audio, rate)
                track_el = ET.SubElement(container, "track", type="2", name=label, muted="0", solo="0")
                sample_track = ET.SubElement(track_el, "sampletrack", vol=f"{STEM_VOLUME:.1f}", pan="0")
                ET.SubElement(sample_track, "fxchain", numofeffects="0", enabled="0")
                ticks = int(np.ceil(len(audio) / rate / seconds_per_beat * TICKS_PER_BEAT))
                ET.SubElement(track_el, "sampletco", pos="0", len=str(ticks), muted="0", src=src)
                audio_written += 1
        else:
            skipped.append(track["name"])
    mixer = ET.SubElement(song, "fxmixer")
    channel = ET.SubElement(mixer, "fxchannel", num="0", name="Master", volume="1", muted="0", soloed="0")
    ET.SubElement(channel, "fxchain", numofeffects="0", enabled="0")
    ET.SubElement(song, "timeline", lp0pos="0", lp1pos="192", lpstate="0")
    ET.SubElement(song, "controllers")
    path = os.path.join(out_dir, f"{name}.mmp")
    ET.indent(root)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0"?>\n<!DOCTYPE lmms-project>\n' + ET.tostring(root, encoding="unicode"))
    with open(os.path.join(out_dir, "HOW_TO_OPEN.txt"), "w", encoding="utf-8") as handle:
        handle.write(HOW_TO_OPEN.format(name=name))
    if skipped:
        print(f"[lmms] no audio stem for {skipped}; run `render --stems` first to include them as sample tracks")
    print(f"[lmms] {notes_written} notes on instrument tracks, {audio_written} sample tracks")
    return path
