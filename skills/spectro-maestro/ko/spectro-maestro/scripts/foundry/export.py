# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Audio files (WAV, FLAC, OGG, MP3), MIDI files and the project JSON."""
from __future__ import annotations

import json
import os
import subprocess

import numpy as np
import soundfile as sf

from . import settings
from .dsp import SR

MIDI_TICKS = 480
DRUM_CHANNEL = 9
# General MIDI percussion keys, matched against the instrument name from the most specific word.
GM_DRUMS = [("hat_closed", 42), ("hat_open", 46), ("hat_pedal", 44), ("kick", 36), ("snare", 38), ("clap", 39),
            ("snap", 39), ("ride", 51), ("crash", 49), ("splash", 55), ("tom_low", 45), ("tom_mid", 47),
            ("tom_high", 50), ("timpani", 41), ("rim", 37), ("clave", 75), ("cowbell", 56), ("shaker", 70),
            ("tambourine", 54), ("conga", 63), ("metal", 81), ("anvil", 81)]
GM_PROGRAMS = {"bass": 38, "sub": 39, "lead": 81, "pluck": 84, "arp": 80, "pad": 89, "chord": 90, "keys": 4,
               "vocal": 53, "backing": 52, "fx": 97}
DITHER_SEED = 20240229
READABLE_FORMATS = ("spectro-maestro/", "track-foundry/")      # the second is the name this format had before
OGG_BLOCK = 1 << 15
MP3_COMPRESSION = 0.0           # libsndfile scale: 0 is the highest quality


def write_audio(path: str, audio: np.ndarray, sr: int = SR) -> str:
    """Format follows the extension. 16-bit WAV gets TPDF dither with a fixed seed (reproducible files)."""
    ext = os.path.splitext(path)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if ext == ".wav":
        rng = np.random.default_rng(DITHER_SEED)
        dither = (rng.random(audio.shape) - rng.random(audio.shape)) / 32768.0
        sf.write(path, np.clip(audio + dither, -1.0, 1.0), sr, subtype="PCM_16")
    elif ext == ".flac":
        sf.write(path, audio, sr, subtype="PCM_24")
    elif ext == ".ogg":
        # libsndfile's Vorbis encoder overflows its stack on one large write; feed it in blocks.
        with sf.SoundFile(path, "w", samplerate=sr, channels=audio.shape[1] if audio.ndim == 2 else 1,
                          format="OGG", subtype="VORBIS") as handle:
            for start in range(0, len(audio), OGG_BLOCK):
                handle.write(audio[start:start + OGG_BLOCK])
    elif ext == ".mp3":
        if "MP3" in sf.available_formats():
            try:                                         # best variable-bitrate quality (about 260 kbps)
                sf.write(path, audio, sr, format="MP3", subtype="MPEG_LAYER_III", compression_level=MP3_COMPRESSION)
            except TypeError:                            # older soundfile without the quality argument
                sf.write(path, audio, sr, format="MP3", subtype="MPEG_LAYER_III")
        elif settings.command("ffmpeg", ("ffmpeg",)):
            temp = path + ".tmp.wav"
            sf.write(temp, audio, sr, subtype="PCM_24")
            try:
                subprocess.run(settings.command("ffmpeg", ("ffmpeg",)) + ["-y", "-loglevel", "error", "-i", temp, "-b:a", "256k", path],
                               check=True)
            finally:
                os.remove(temp)
        else:
            raise RuntimeError("MP3 needs libsndfile 1.1+ or ffmpeg and neither is available here; "
                               "choose ogg, flac or wav with --formats, or install ffmpeg")
    else:
        raise ValueError(f"unsupported audio extension {ext!r}; use .wav .flac .ogg .mp3")
    return path


def save_project(project: dict, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(project, handle, ensure_ascii=False, separators=(",", ":"))
    return path


def load_project(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        project = json.load(handle)
    if not str(project.get("format", "")).startswith(READABLE_FORMATS):
        raise ValueError(f"{path} is not a project file of this toolkit")
    return project


def gm_drum_key(inst) -> int | None:
    name = str(inst.get("base") if isinstance(inst, dict) else inst)
    return next((key for word, key in GM_DRUMS if word in name), None)


def write_midi(project: dict, path: str) -> str:
    """Standard MIDI file, one track per project track. Drums go to channel 10 on General MIDI keys,
    lyric lines are written as lyric events on the vocal track."""
    import mido
    midi = mido.MidiFile(ticks_per_beat=MIDI_TICKS)
    meta = project["meta"]
    conductor = mido.MidiTrack()
    conductor.append(mido.MetaMessage("track_name", name=meta.get("title", "song"), time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(meta["bpm"]), time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=int(meta["meter"]), denominator=4, time=0))
    last = 0
    for section in project["sections"]:
        tick = int(round(section["start"] * MIDI_TICKS))
        conductor.append(mido.MetaMessage("marker", text=section["name"], time=tick - last))
        last = tick
    midi.tracks.append(conductor)
    channel = 0
    for track in project["tracks"]:
        events = []                                       # (tick, order, message)
        if track.get("kind") == "vocal":
            for line in track.get("lines", []):
                events.append((int(round(line["start"] * MIDI_TICKS)), 0, mido.MetaMessage("lyrics", text=line["text"])))
                for offset, dur, pitch, _tie in line["notes"]:
                    events += _note_events(line["start"] + offset, dur, pitch, 0.8, channel)
        elif track.get("kind") == "drums":
            key = gm_drum_key(track["inst"])
            if key is None:
                continue                                  # sweeps and unpitched effects have no MIDI meaning
            for start, dur, _pitch, velocity, *_ in track["notes"]:
                events += _note_events(start, min(dur, 0.25), key, velocity, DRUM_CHANNEL)
        else:
            for start, dur, pitch, velocity, *_ in track["notes"]:
                events += _note_events(start, dur, pitch, velocity, channel)
        if not events:
            continue
        out = mido.MidiTrack()
        out.append(mido.MetaMessage("track_name", name=track["name"], time=0))
        if track.get("kind") != "drums":
            out.append(mido.Message("program_change", channel=channel, program=GM_PROGRAMS.get(track.get("role"), 81), time=0))
            channel = channel + 1 if channel + 1 != DRUM_CHANNEL else channel + 2
            channel = min(channel, 15)
        last = 0
        for tick, _order, message in sorted(events, key=lambda e: (e[0], e[1])):
            out.append(message.copy(time=tick - last))
            last = tick
        midi.tracks.append(out)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    midi.save(path)
    return path


def _note_events(start: float, dur: float, pitch: float, velocity: float, channel: int) -> list:
    import mido
    on, off = int(round(start * MIDI_TICKS)), int(round((start + dur) * MIDI_TICKS))
    note = int(np.clip(round(pitch), 0, 127))
    return [(on, 1, mido.Message("note_on", channel=channel, note=note, velocity=int(np.clip(velocity * 127, 1, 127)))),
            (max(off, on + 1), 0, mido.Message("note_off", channel=channel, note=note, velocity=0))]


def read_midi(path: str, bpm: float | None = None) -> dict:
    """MIDI file -> song spec skeleton (tracks with absolute `line` parts in one section).
    Lets a composer start from an existing MIDI sketch; instruments are assigned by channel and register."""
    import mido
    midi = mido.MidiFile(path)
    tempo = next((m.tempo for t in midi.tracks for m in t if m.type == "set_tempo"), 500000)
    bpm = bpm or round(mido.tempo2bpm(tempo), 3)
    tracks, end_beat = {}, 0.0
    for index, track in enumerate(midi.tracks):
        tick, held, notes, name = 0, {}, [], f"track{index}"
        for message in track:
            tick += message.time
            if message.type == "track_name":
                name = message.name.strip().replace(" ", "_") or name
            elif message.type == "note_on" and message.velocity > 0:
                held[(message.channel, message.note)] = (tick, message.velocity)
            elif message.type in ("note_off", "note_on") and (message.channel, message.note) in held:
                start, velocity = held.pop((message.channel, message.note))
                notes.append((start / midi.ticks_per_beat, (tick - start) / midi.ticks_per_beat, message.note,
                              velocity / 127.0, message.channel))
        if notes:
            tracks[name if name not in tracks else f"{name}_{index}"] = notes
            end_beat = max(end_beat, max(n[0] + n[1] for n in notes))
    return {"bpm": bpm, "beats": end_beat, "tracks": tracks}
