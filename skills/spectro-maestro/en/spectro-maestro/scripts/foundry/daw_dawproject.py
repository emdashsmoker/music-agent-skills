# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
# Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill.
"""Export a project as a DAWproject file (.dawproject, the open exchange format read by Bitwig Studio,
Studio One, Cubase and others).

Every track with notes becomes a note track with one clip per section. Tracks that cannot be expressed
as notes (vocals, transition sweeps) are embedded as audio when their stems exist (`render --stems`).
The project XML is checked against the format's schema when lxml is available."""
from __future__ import annotations

import glob
import os
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from . import export, mixprofile

SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "dawproject",
                      "Project.xsd")


class _Ids:
    def __init__(self):
        self.count = 0

    def new(self) -> str:
        self.count += 1
        return f"id{self.count}"


def _channel(track_el, ids: _Ids, master_id: str | None, volume: float, pan: float, role: str = "regular") -> str:
    attrs = {"audioChannels": "2", "role": role, "solo": "false", "id": ids.new()}
    if master_id:
        attrs["destination"] = master_id
    channel = ET.SubElement(track_el, "Channel", **attrs)
    ET.SubElement(channel, "Mute", value="false", id=ids.new())
    ET.SubElement(channel, "Pan", max="1", min="0", unit="normalized", value=f"{0.5 + 0.5 * pan:.3f}", id=ids.new())
    ET.SubElement(channel, "Volume", max="2", min="0", unit="linear", value=f"{volume:.4f}", id=ids.new())
    return attrs["id"]


def _audio_clip(clips, ids: _Ids, name: str, entry: tuple, seconds_per_beat: float) -> None:
    path, seconds, channels, rate = entry
    clip = ET.SubElement(clips, "Clip", time="0", duration=f"{seconds / seconds_per_beat:.4f}", playStart="0",
                         contentTimeUnit="seconds", name=name)
    audio = ET.SubElement(clip, "Audio", algorithm="raw", channels=str(channels), sampleRate=str(rate),
                          duration=f"{seconds:.4f}", id=ids.new())
    ET.SubElement(audio, "File", path=path)


def build_xml(project: dict, audio_files: dict, extra_audio: dict | None = None) -> ET.Element:
    """Project XML. `audio_files` maps track name -> (path inside the archive, seconds, channels, sample rate);
    `extra_audio` holds stems that belong to no note track (vocal doubles and harmonies), added as audio tracks."""
    meta = project["meta"]
    ids = _Ids()
    root = ET.Element("Project", version="1.0")
    ET.SubElement(root, "Application", name="spectro-maestro", version="1")
    transport = ET.SubElement(root, "Transport")
    ET.SubElement(transport, "Tempo", unit="bpm", value=f"{meta['bpm']:g}", id=ids.new())
    ET.SubElement(transport, "TimeSignature", numerator=str(int(meta["meter"])), denominator="4", id=ids.new())
    structure = ET.SubElement(root, "Structure")
    master = ET.SubElement(structure, "Track", contentType="audio notes", loaded="true", id=ids.new(), name="Master")
    master_id = _channel(master, ids, None, 1.0, 0.0, "master")
    arrangement = ET.SubElement(root, "Arrangement", id=ids.new())
    lanes = ET.SubElement(arrangement, "Lanes", timeUnit="beats", id=ids.new())
    seconds_per_beat = 60.0 / meta["bpm"]
    for track in project["tracks"]:
        settings = mixprofile.track_settings(track, {})
        volume = float(np.clip(10.0 ** ((settings["level"] + settings["gain_db"]) / 20.0), 0.05, 2.0))
        is_audio = track["name"] in audio_files
        key = export.gm_drum_key(track["inst"]) if track.get("kind") == "drums" else None
        if not is_audio and (not track["notes"] or (track.get("kind") == "drums" and key is None)):
            continue
        track_el = ET.SubElement(structure, "Track", contentType="audio" if is_audio else "notes", loaded="true",
                                 id=ids.new(), name=track["name"])
        _channel(track_el, ids, master_id, 1.0 if is_audio else volume, float(settings.get("pan", 0.0)))
        lane = ET.SubElement(lanes, "Lanes", track=track_el.get("id"), id=ids.new())
        clips = ET.SubElement(lane, "Clips", id=ids.new())
        if is_audio:
            _audio_clip(clips, ids, track["name"], audio_files[track["name"]], seconds_per_beat)
            continue
        for section in project["sections"]:
            start, end = section["start"], section["start"] + section["bars"] * meta["meter"]
            inside = [n for n in track["notes"] if start - 1e-6 <= n[0] < end - 1e-6]
            if not inside:
                continue
            clip = ET.SubElement(clips, "Clip", time=f"{start:g}", duration=f"{end - start:g}", playStart="0",
                                 name=section["name"])
            notes = ET.SubElement(clip, "Notes", id=ids.new())
            for note in inside:
                pitch = key if key is not None else int(np.clip(round(note[2]), 0, 127))
                ET.SubElement(notes, "Note", time=f"{note[0] - start:.5f}", duration=f"{max(note[1], 0.01):.5f}",
                              channel="9" if key is not None else "0", key=str(pitch), vel=f"{note[3]:.3f}", rel="0.5")
    for name, entry in (extra_audio or {}).items():
        track_el = ET.SubElement(structure, "Track", contentType="audio", loaded="true", id=ids.new(), name=name)
        _channel(track_el, ids, master_id, 1.0, 0.0)
        lane = ET.SubElement(lanes, "Lanes", track=track_el.get("id"), id=ids.new())
        _audio_clip(ET.SubElement(lane, "Clips", id=ids.new()), ids, name, entry, seconds_per_beat)
    markers = ET.SubElement(arrangement, "Markers", id=ids.new())
    for section in project["sections"]:
        ET.SubElement(markers, "Marker", time=f"{section['start']:g}", name=section["name"])
    return root


def validate(root: ET.Element) -> str:
    """'valid', 'not checked (reason)' or raises ValueError with the schema errors."""
    try:
        from lxml import etree
    except ImportError:
        return "not checked (lxml is not installed)"
    if not os.path.exists(SCHEMA):
        return "not checked (schema file missing)"
    schema = etree.XMLSchema(etree.parse(SCHEMA))
    document = etree.fromstring(ET.tostring(root, encoding="utf-8"))
    if not schema.validate(document):
        raise ValueError("DAWproject XML does not match the schema: " + "; ".join(str(e) for e in schema.error_log[:5]))
    return "valid"


def write(project: dict, path: str, stems_dir: str | None = None) -> str:
    import soundfile as sf
    audio_files, extra_audio, sources = {}, {}, {}

    def take(stem: str, target: dict, name: str) -> None:
        info = sf.info(stem)
        inside = f"audio/{name}.flac"
        target[name] = (inside, info.frames / info.samplerate, info.channels, info.samplerate)
        sources[inside] = stem

    for track in project["tracks"]:
        needs_audio = track.get("kind") == "vocal" or (track.get("kind") == "drums" and export.gm_drum_key(track["inst"]) is None)
        stem = os.path.join(stems_dir, f"{track['name']}.flac") if stems_dir else None
        if needs_audio and stem and os.path.exists(stem):
            take(stem, audio_files, track["name"])
            for layer in sorted(glob.glob(os.path.join(stems_dir, f"{glob.escape(track['name'])}.*.flac"))):
                take(layer, extra_audio, os.path.splitext(os.path.basename(layer))[0])      # doubles and harmonies
        elif needs_audio:
            print(f"[dawproject] no stem for {track['name']}; run `render --stems` first to embed it as audio")
    root = build_xml(project, audio_files, extra_audio)
    status = validate(root)
    meta = ET.Element("MetaData")
    ET.SubElement(meta, "Title").text = project["meta"].get("title", "")
    ET.SubElement(meta, "Artist").text = project["meta"].get("artist", "")
    ET.SubElement(meta, "Genre").text = project["meta"].get("genre", "")
    ET.indent(root)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("project.xml", '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode"))
        bundle.writestr("metadata.xml", '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(meta, encoding="unicode"))
        for inside, source in sources.items():
            bundle.write(source, inside)
    print(f"[dawproject] schema check: {status}; {len(audio_files) + len(extra_audio)} audio tracks embedded")
    return path
