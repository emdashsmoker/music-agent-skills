# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Project interchange: inspection summary, lossless JSON, Standard MIDI File and DAWproject.

JSON is a faithful mirror of the LMMS XML, so a project can be diffed, edited by any tool and
converted back without loss. MIDI and DAWproject carry what other DAWs understand: tempo, tracks,
notes, levels and audio files. LMMS instruments and effects do not exist elsewhere, so those
exports can include rendered stems to keep the sound.
"""
from __future__ import annotations

import json
import os
import struct
import xml.etree.ElementTree as ET
import zipfile

import soundfile as sf

from . import render
from .project import TRACK_AUTOMATION, TRACK_BB, TRACK_INSTRUMENT, TRACK_SAMPLE, EffectChain, Note, Project, resolve_sample

MIDI_TICKS_PER_BEAT = 480
MIDI_DRUM_CHANNEL = 9
LMMS_FULL_VOLUME = 200.0                       # note volume that maps to MIDI velocity 127 (LMMS's own convention)
GM_DRUM_NOTES = {"kick": 36, "snare": 38, "clap": 39, "hat": 42, "cymbal": 49, "perc": 45}
GM_DRUM_KEYWORDS = [("ohat", 46), ("open", 46), ("ride", 51), ("crash", 49), ("rim", 37), ("cowbell", 56), ("clave", 75),
                    ("tamb", 54), ("shaker", 70), ("maracas", 70), ("cabasa", 69), ("tom_hi", 50), ("tom hi", 50),
                    ("tom_lo", 41), ("tom lo", 41), ("tom", 45)]
EXTERNAL_INSTRUMENTS = {"vestige": "VST instrument", "sf2player": "SoundFont", "gigplayer": "GIG sample bank",
                        "patman": "GUS patch", "zynaddsubfx": "ZynAddSubFX (runs as a helper process)"}
SAMPLE_PLUGINS = ("audiofileprocessor", "sf2player", "gigplayer", "patman")
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")
DAWPROJECT_VERSION = "1.0"
APPLICATION_NAME = "lmmskit"


# -- inspection -----------------------------------------------------------------------------------------
def _effects(chain_element) -> list[str]:
    return [EffectChain.describe(e) for e in chain_element.findall("effect")] if chain_element is not None else []


def inspect(project: Project) -> dict:
    """Structured summary of a project: what an agent reads first after importing someone's .mmp."""
    data_dir = render.find_data_dir()
    sample_dirs = [os.path.join(os.path.dirname(project.path or "."), render.SAMPLES_SUBDIR)] + \
                  ([os.path.join(data_dir, "samples")] if data_dir else [])
    beats_per_bar = project.beats_per_bar
    all_notes = project.all_notes()
    tracks, external, missing = [], [], []
    for track in project.tracks():
        entry = {"name": track.name, "type": {TRACK_INSTRUMENT: "instrument", TRACK_BB: "beat/bassline", TRACK_SAMPLE: "sample",
                                              TRACK_AUTOMATION: "automation"}.get(track.type, f"type {track.type}"),
                 "muted": track.muted}
        if track.type == TRACK_INSTRUMENT:
            notes = track.notes()
            entry.update({"plugin": track.plugin, "vol": track.param("vol").get(), "pan": track.param("pan").get(),
                          "mixer_channel": int(float(track.settings.get("fxch", "0"))), "clips": len(track.patterns()),
                          "notes": len(notes), "effects": _effects(track.settings.find("fxchain"))})
            if notes:
                entry["pitch_range"] = [min(n.pitch for n in notes), max(n.pitch for n in notes)]
                entry["bars"] = [int(min(n.start for n in notes) // beats_per_bar) + 1, int(max(n.start for n in notes) // beats_per_bar) + 1]
            if track.plugin in EXTERNAL_INSTRUMENTS:
                external.append(f"track '{track.name}': {EXTERNAL_INSTRUMENTS[track.plugin]}")
            source = track.plugin_el.get("src") if track.plugin_el is not None and track.plugin in SAMPLE_PLUGINS else None
            if source:
                entry["sample"] = source
                if resolve_sample(source, sample_dirs) is None:
                    missing.append(f"track '{track.name}': {source}")
        elif track.type == TRACK_SAMPLE:
            clips = track.el.findall("sampletco")
            entry.update({"clips": len(clips), "samples": sorted({c.get("src", "") for c in clips})})
            missing += [f"track '{track.name}': {c.get('src')}" for c in clips if c.get("src") and resolve_sample(c.get("src"), sample_dirs) is None]
        elif track.type == TRACK_BB:
            entry["clips"] = len(track.el.findall("bbtco"))
        tracks.append(entry)
    for effect in project.root.iter("effect"):
        if effect.get("name") == "vsteffect":
            external.append(f"VST effect: {EffectChain.describe(effect)}")
    mixer = [{"channel": int(c.get("num")), "name": c.get("name"), "volume": project.mixer.volume(int(c.get("num"))).get(),
              "muted": c.get("muted", "0") == "1", "effects": _effects(c.find("fxchain")),
              "sends": {int(send.get("channel")): float(send.get("amount", "1")) for send in c.findall("send")}}
             for c in project.mixer.channels()]
    length = project.length_beats()
    return {
        "file": project.path, "creator_version": project.root.get("creatorversion"), "bpm": project.bpm,
        "timesig": list(project.timesig), "length_bars": round(length / beats_per_bar, 2),
        "length_seconds": round(length * 60.0 / project.bpm, 1), "tracks": tracks, "mixer": mixer,
        "bb_parts": sorted(project.bb_notes()), "sounding_parts": len(all_notes),
        "controllers": [c.get("name", c.tag) for c in (project.song.find("controllers") or [])],
        "automation_clips": len(project.automation_clips()), "external_dependencies": sorted(set(external)),
        "missing_samples": sorted(set(missing)), "notes": project.notes_text.strip()[:500],
    }


# -- lossless JSON ----------------------------------------------------------------------------------------
def _to_node(element: ET.Element) -> dict:
    node = {"tag": element.tag}
    if element.attrib:
        node["attrs"] = dict(element.attrib)
    if element.text and element.text.strip():
        node["text"] = element.text
    if len(element):
        node["children"] = [_to_node(child) for child in element]
    return node


def _from_node(node: dict) -> ET.Element:
    element = ET.Element(node["tag"], node.get("attrs", {}))
    element.text = node.get("text")
    for child in node.get("children", []):
        element.append(_from_node(child))
    return element


def to_json(project: Project, path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"format": "lmms-project-json", "version": 1, "root": _to_node(project.root)}, handle, ensure_ascii=False, indent=1)
    return path


def from_json(path: str) -> Project:
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    if document.get("format") != "lmms-project-json":
        raise ValueError(f"{path} is not an lmms-project-json file")
    return Project(_from_node(document["root"]))


# -- MIDI -------------------------------------------------------------------------------------------------
def _variable_length(value: int) -> bytes:
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def _midi_track(events: list[tuple[int, bytes]]) -> bytes:
    """events: (absolute tick, message bytes). Adds delta times and the end-of-track marker."""
    body, last = b"", 0
    for tick, message in sorted(events, key=lambda e: (e[0], e[1][0] & 0xF0 == 0x90)):      # note-offs before note-ons
        body += _variable_length(max(0, tick - last)) + message
        last = tick
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _meta(kind: int, payload: bytes) -> bytes:
    return bytes([0xFF, kind]) + _variable_length(len(payload)) + payload


def gm_drum_note(name: str, role: str) -> int | None:
    lowered = name.lower()
    for keyword, note in GM_DRUM_KEYWORDS:
        if keyword in lowered:
            return note
    return GM_DRUM_NOTES.get(role)


def to_midi(project: Project, path: str, roles: dict[str, str] | None = None) -> str:
    """Type-1 MIDI file: tempo track plus one track per part. Parts with a drum role go to channel 10 on GM drum notes."""
    roles = roles or {}
    numerator, denominator = project.timesig
    conductor = [(0, _meta(0x51, struct.pack(">I", int(round(60_000_000 / project.bpm)))[1:])),
                 (0, _meta(0x58, bytes([numerator, denominator.bit_length() - 1, 24, 8])))]
    chunks = [_midi_track(conductor)]
    melodic_channel = 0
    from . import compose
    for name, notes in compose.notes_with_vocals(project, project.path).items():
        if "trigger" in name.lower():
            continue
        drum_note = gm_drum_note(name, roles.get(name, ""))
        if drum_note is not None:
            channel = MIDI_DRUM_CHANNEL
        else:
            channel = melodic_channel
            melodic_channel = (melodic_channel + 1) % 16
            melodic_channel += melodic_channel == MIDI_DRUM_CHANNEL
        events = [(0, _meta(0x03, name.encode("utf-8")))]
        spans = []
        for n in sorted(notes, key=lambda item: item.start):
            key = drum_note if drum_note is not None else max(0, min(127, n.pitch))
            start = int(round(n.start * MIDI_TICKS_PER_BEAT))
            end = max(start + 1, int(round((n.start + n.length) * MIDI_TICKS_PER_BEAT)))
            spans.append([start, end, key, max(1, min(127, int(round(n.vol * 127 / LMMS_FULL_VOLUME))))])
        next_start: dict[int, int] = {}
        for span in reversed(spans):                      # a note must end before the same key starts again
            if span[2] in next_start:
                span[1] = max(span[0] + 1, min(span[1], next_start[span[2]]))
            next_start[span[2]] = span[0]
        for start, end, key, velocity in spans:
            events.append((start, bytes([0x90 | channel, key, velocity])))
            events.append((end, bytes([0x80 | channel, key, 0])))
        chunks.append(_midi_track(events))
    with open(path, "wb") as handle:
        handle.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), MIDI_TICKS_PER_BEAT) + b"".join(chunks))
    return path


def read_midi_notes(path: str) -> dict[str, list[Note]]:
    """Minimal reader (used to verify exports): {track name: notes} with beats as time unit."""
    with open(path, "rb") as handle:
        data = handle.read()
    division = struct.unpack(">H", data[12:14])[0]
    position, result, index = 14, {}, 0
    while position < len(data):
        length = struct.unpack(">I", data[position + 4:position + 8])[0]
        chunk, position = data[position + 8:position + 8 + length], position + 8 + length
        cursor, tick, status, name, pending, notes = 0, 0, 0, f"track {index}", {}, []
        while cursor < len(chunk):
            delta = 0
            while True:
                byte = chunk[cursor]
                cursor += 1
                delta = (delta << 7) | (byte & 0x7F)
                if not byte & 0x80:
                    break
            tick += delta
            if chunk[cursor] == 0xFF:
                kind, cursor = chunk[cursor + 1], cursor + 2
                size = 0
                while True:
                    byte = chunk[cursor]
                    cursor += 1
                    size = (size << 7) | (byte & 0x7F)
                    if not byte & 0x80:
                        break
                if kind == 0x03:
                    name = chunk[cursor:cursor + size].decode("utf-8", "replace")
                cursor += size
                continue
            if chunk[cursor] & 0x80:
                status = chunk[cursor]
                cursor += 1
            key, value = chunk[cursor], chunk[cursor + 1]
            cursor += 2
            if status & 0xF0 == 0x90 and value > 0:
                pending[key] = (tick, value)
            elif status & 0xF0 in (0x80, 0x90) and key in pending:
                start, velocity = pending.pop(key)
                notes.append(Note(start / division, (tick - start) / division, key, velocity * LMMS_FULL_VOLUME / 127))
        if notes:
            result[name] = notes
        index += 1
    return result


# -- DAWproject -------------------------------------------------------------------------------------------
class _Ids:
    def __init__(self):
        self.count = 0

    def new(self) -> str:
        self.count += 1
        return f"id{self.count}"


def _dawproject_channel(parent, ids, role, volume, pan, destination=None):
    channel = ET.SubElement(parent, "Channel", {"audioChannels": "2", "role": role, "solo": "false", "id": ids.new()})
    if destination:
        channel.set("destination", destination)
    ET.SubElement(channel, "Mute", {"value": "false", "id": ids.new(), "name": "Mute"})
    ET.SubElement(channel, "Pan", {"max": "1.000000", "min": "0.000000", "unit": "normalized", "value": f"{pan:.6f}", "id": ids.new(), "name": "Pan"})
    ET.SubElement(channel, "Volume", {"max": "2.000000", "min": "0.000000", "unit": "linear", "value": f"{volume:.6f}", "id": ids.new(), "name": "Volume"})
    return channel


def to_dawproject(project: Project, path: str, *, title: str = "", stems: dict[str, str] | None = None,
                  roles: dict[str, str] | None = None) -> str:
    """Write a .dawproject (Bitwig, Studio One, Cubase ...): tempo, note tracks, audio parts and optional stem tracks.

    stems: {name: wav path} adds one audio track per rendered stem so the song sounds right before
    any instrument is assigned. Tracks that play audio files (vocals) are exported as audio clips.
    """
    ids, audio_files = _Ids(), {}
    root = ET.Element("Project", {"version": DAWPROJECT_VERSION})
    ET.SubElement(root, "Application", {"name": APPLICATION_NAME, "version": "1"})
    transport = ET.SubElement(root, "Transport")
    ET.SubElement(transport, "Tempo", {"max": "666.000000", "min": "20.000000", "unit": "bpm", "value": f"{project.bpm:.6f}", "id": ids.new(), "name": "Tempo"})
    ET.SubElement(transport, "TimeSignature", {"denominator": str(project.timesig[1]), "numerator": str(project.timesig[0]), "id": ids.new()})
    structure = ET.SubElement(root, "Structure")
    master_track = ET.Element("Track", {"contentType": "audio notes", "loaded": "true", "id": ids.new(), "name": "Master"})
    master_channel = _dawproject_channel(master_track, ids, "master", 1.0, 0.5)
    arrangement = ET.Element("Arrangement", {"id": ids.new()})
    lanes = ET.SubElement(arrangement, "Lanes", {"timeUnit": "beats", "id": ids.new()})
    seconds_per_beat = 60.0 / project.bpm
    sample_dirs = [os.path.join(os.path.dirname(project.path or "."), render.SAMPLES_SUBDIR)]

    def add_track(name, content, volume=1.0, pan=0.5):
        track = ET.SubElement(structure, "Track", {"contentType": content, "loaded": "true", "id": ids.new(), "name": name})
        _dawproject_channel(track, ids, "regular", volume, pan, master_channel.get("id"))
        lane = ET.SubElement(lanes, "Lanes", {"track": track.get("id"), "id": ids.new()})
        return ET.SubElement(lane, "Clips", {"id": ids.new()})

    def add_audio_clip(clips, start_beats, wav_path, label):
        info = sf.info(wav_path)
        archive_name = audio_files.setdefault(wav_path, f"audio/{len(audio_files):03d}_{os.path.basename(wav_path)}")
        clip = ET.SubElement(clips, "Clip", {"time": f"{start_beats:.6f}", "duration": f"{info.duration / seconds_per_beat:.6f}",
                                             "contentTimeUnit": "seconds", "playStart": "0.0", "name": label})
        audio = ET.SubElement(clip, "Audio", {"algorithm": "raw", "channels": str(info.channels), "duration": f"{info.duration:.6f}",
                                              "sampleRate": str(info.samplerate), "id": ids.new()})
        ET.SubElement(audio, "File", {"path": archive_name})

    for track in project.tracks(TRACK_INSTRUMENT):
        if track.muted or "trigger" in track.name.lower() or not track.patterns():
            continue
        volume = min(2.0, track.param("vol").get() / 100.0)
        pan = 0.5 + track.param("pan").get() / 200.0
        source = track.plugin_el.get("src") if track.plugin == "audiofileprocessor" and track.plugin_el is not None else None
        sample_path = resolve_sample(source, sample_dirs) if source else None
        is_audio_part = sample_path is not None and (roles or {}).get(track.name, "") in ("vocal", "vocal_bg")
        clips = add_track(track.name, "audio" if is_audio_part else "notes", volume, pan)
        for pattern in track.patterns():
            start = int(pattern.get("pos", "0")) / 48.0
            if is_audio_part:
                for note in pattern.findall("note"):
                    add_audio_clip(clips, start + int(note.get("pos")) / 48.0, sample_path, track.name)
                continue
            notes = pattern.findall("note")
            if not notes:
                continue
            length = max(int(n.get("pos")) + max(int(n.get("len")), 12) for n in notes) / 48.0
            clip = ET.SubElement(clips, "Clip", {"time": f"{start:.6f}", "duration": f"{length:.6f}", "playStart": "0.0",
                                                 "name": pattern.get("name", track.name)})
            holder = ET.SubElement(clip, "Notes", {"id": ids.new()})
            for note in notes:
                velocity = max(0.01, min(1.0, float(note.get("vol", "100")) / LMMS_FULL_VOLUME))
                ET.SubElement(holder, "Note", {"time": f"{int(note.get('pos')) / 48.0:.6f}",
                                               "duration": f"{max(int(note.get('len')), 12) / 48.0:.6f}", "channel": "0",
                                               "key": str(int(note.get("key")) + 12), "vel": f"{velocity:.6f}", "rel": f"{velocity:.6f}"})
    for name, wav_path in (stems or {}).items():
        add_audio_clip(add_track(f"STEM {name}", "audio"), 0.0, wav_path, name)
    structure.append(master_track)
    master_lane = ET.SubElement(lanes, "Lanes", {"track": master_track.get("id"), "id": ids.new()})
    ET.SubElement(master_lane, "Clips", {"id": ids.new()})
    root.append(arrangement)
    ET.SubElement(root, "Scenes")
    metadata = ET.Element("MetaData")
    ET.SubElement(metadata, "Title").text = title or os.path.splitext(os.path.basename(path))[0]
    ET.SubElement(metadata, "Comment").text = "Exported from an LMMS project. Note tracks carry no instrument; STEM tracks hold the rendered sound."
    ET.indent(root)
    ET.indent(metadata)
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("project.xml", date_time=(2020, 1, 1, 0, 0, 0)), header + ET.tostring(root, encoding="unicode"))
        archive.writestr(zipfile.ZipInfo("metadata.xml", date_time=(2020, 1, 1, 0, 0, 0)), header + ET.tostring(metadata, encoding="unicode"))
        for wav_path, archive_name in audio_files.items():
            archive.write(wav_path, archive_name)
    return path


def validate_dawproject(path: str) -> list[str]:
    """Validate project.xml and metadata.xml against the official DAWproject 1.0 schemas (needs `xmlschema`)."""
    import xmlschema
    errors = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for member, schema in (("project.xml", "Project.xsd"), ("metadata.xml", "MetaData.xsd")):
            if member not in names:
                errors.append(f"{member} missing")
                continue
            validator = xmlschema.XMLSchema(os.path.join(SCHEMA_DIR, schema))
            errors += [f"{member}: {error.reason} at {error.path}" for error in validator.iter_errors(archive.read(member).decode("utf-8"))]
        document = ET.fromstring(archive.read("project.xml"))
        errors += [f"audio file {f.get('path')} missing from archive" for f in document.iter("File") if f.get("path") not in names]
    return errors
