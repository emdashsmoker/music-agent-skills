# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""LMMS project file model: load, build, query, edit and save .mmp / .mmpz.

The XML tree is the single source of truth, so anything this module does not understand
(VST data, unknown plugins, GUI state) survives a load-edit-save round trip untouched.
Musical positions are given in beats (quarter notes) and pitches as MIDI note numbers;
conversion to LMMS ticks and keys happens only at the XML boundary.
"""
from __future__ import annotations

import os
import random
import struct
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass

TICKS_PER_BEAT = 48                 # LMMS 1.2 resolution: 192 ticks per 4/4 bar
MIDI_MINUS_LMMS_KEY = 12            # LMMS key 57 is A4 (440 Hz), MIDI calls that 69
DEFAULT_BASENOTE = 57
ENVELOPE_SECONDS_AT_KNOB_ONE = 5.0  # LMMS: seconds = 5 * knob^2
KNOB_MAX = 2.0
XML_HEADER = '<?xml version="1.0"?>\n<!DOCTYPE lmms-project>\n'
COMPRESSED_EXTENSIONS = (".mmpz",)
ID_RANGE = (1_000_000, 9_999_999)
AUTOQUIT_MAX_MS = 8000.0

TRACK_INSTRUMENT, TRACK_BB, TRACK_SAMPLE, TRACK_AUTOMATION, TRACK_HIDDEN_AUTOMATION = 0, 1, 2, 5, 6
PROGRESSION_DISCRETE, PROGRESSION_LINEAR, PROGRESSION_CUBIC = 0, 1, 2

# Control element tag of each native effect (LMMS 1.2.2 source, *Controls::nodeName).
NATIVE_EFFECT_TAGS = {
    "amplifier": "AmplifierControls", "bassbooster": "bassboostercontrols", "bitcrush": "bitcrushcontrols",
    "crossovereq": "crossoevereqcontrols", "delay": "Delay", "dualfilter": "DualFilterControls",
    "dynamicsprocessor": "dynamicsprocessor_controls", "eq": "Eq", "flanger": "Flanger",
    "multitapecho": "multitapechocontrols", "peakcontrollereffect": "peakcontrollereffectcontrols",
    "reverbsc": "ReverbSCControls", "stereoenhancer": "stereoenhancercontrols",
    "stereomatrix": "stereomatrixcontrols", "waveshaper": "waveshapercontrols",
}

_EMPTY_PROJECT = """<lmms-project version="1.0" creator="LMMS" creatorversion="1.2.2" type="song">
  <head timesig_numerator="4" mastervol="100" timesig_denominator="4" bpm="140" masterpitch="0"/>
  <song>
    <trackcontainer width="900" x="5" y="5" maximized="0" height="420" visible="1" type="song" minimized="0"/>
    <fxmixer width="900" x="5" y="430" maximized="0" height="335" visible="1" minimized="0">
      <fxchannel num="0" muted="0" volume="1" name="Master" soloed="0">
        <fxchain numofeffects="0" enabled="0"/>
      </fxchannel>
    </fxmixer>
    <ControllerRackView width="258" x="920" y="5" maximized="0" height="200" visible="0" minimized="0"/>
    <pianoroll width="900" x="5" y="5" maximized="0" height="480" visible="0" minimized="0"/>
    <automationeditor width="900" x="5" y="5" maximized="0" height="400" visible="0" minimized="0"/>
    <projectnotes width="640" x="700" y="10" maximized="0" height="400" visible="0" minimized="0"/>
    <timeline lp1pos="192" lp0pos="0" lpstate="0"/>
    <controllers/>
  </song>
</lmms-project>"""


def beats_to_ticks(beats: float) -> int:
    return int(round(beats * TICKS_PER_BEAT))


def ticks_to_beats(ticks: int) -> float:
    return ticks / TICKS_PER_BEAT


def seconds_to_knob(seconds: float) -> float:
    """Envelope time in seconds to the LMMS knob value that produces it."""
    return min(KNOB_MAX, (max(seconds, 0.0) / ENVELOPE_SECONDS_AT_KNOB_ONE) ** 0.5)


def fmt(value) -> str:
    """Number formatting LMMS reads back exactly: booleans as 0/1, floats without noise."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(round(value, 6)).rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


@dataclass
class Note:
    """One note. start and length are beats relative to the clip start; vol is LMMS 0-200 (100 = unity)."""
    start: float
    length: float
    pitch: int
    vol: float = 100.0
    pan: float = 0.0


@dataclass
class Param:
    """Address of one automatable value: an attribute `name` on `owner` (or its child element form)."""
    owner: ET.Element
    name: str

    def _child(self):
        return self.owner.find(self.name)

    def get(self) -> float:
        child = self._child()
        raw = child.get("value") if child is not None and child.get("value") is not None else self.owner.get(self.name)
        return float(raw) if raw is not None else 0.0

    def set(self, value) -> None:
        child = self._child()
        if child is not None and child.get("value") is not None:
            child.set("value", fmt(value))
        else:
            self.owner.set(self.name, fmt(value))

    def ensure_id(self, project: "Project") -> int:
        """LMMS stores an automated value as <name value= id=> instead of an attribute; convert when needed."""
        child = self._child()
        if child is None:
            child = ET.SubElement(self.owner, self.name)
        if child.get("id") is None:
            value = self.owner.attrib.pop(self.name, child.get("value", "0"))
            child.set("value", value)
            child.set("scale_type", "linear")
            child.set("id", str(project.new_id()))
        return int(child.get("id"))


class EffectChain:
    """Wrapper around an <fxchain> element (on an instrument track, sample track or mixer channel)."""

    def __init__(self, element: ET.Element):
        self.el = element

    def _append(self, effect: ET.Element) -> ET.Element:
        self.el.append(effect)
        self.el.set("numofeffects", str(len(self.el.findall("effect"))))
        self.el.set("enabled", "1")
        return effect

    @staticmethod
    def _shell(name: str, wet: float, autoquit_ms: float) -> ET.Element:
        # LMMS stops an effect once its output has been silent for `autoquit` milliseconds. The LMMS default of
        # 1 ms silences a delay before its first echo arrives, so effects here wait the maximum time instead.
        return ET.Element("effect", {"name": name, "on": "1", "wet": fmt(wet), "gate": "0", "autoquit": fmt(float(autoquit_ms)),
                                     "autoquit_numerator": "4", "autoquit_denominator": "4", "syncmode": "0"})

    def add_native(self, name: str, controls: dict | None = None, wet: float = 1.0, autoquit_ms: float = AUTOQUIT_MAX_MS) -> ET.Element:
        if name not in NATIVE_EFFECT_TAGS:
            raise ValueError(f"unknown native effect '{name}'; known: {sorted(NATIVE_EFFECT_TAGS)}")
        effect = self._shell(name, wet, autoquit_ms)
        ET.SubElement(effect, NATIVE_EFFECT_TAGS[name], {k: fmt(v) for k, v in (controls or {}).items()})
        ET.SubElement(effect, "key")
        return self._append(effect)

    def add_ladspa(self, file: str, plugin: str, ports: dict[int, float], port_count: int, channels: int = 1,
                   wet: float = 1.0, autoquit_ms: float = AUTOQUIT_MAX_MS) -> ET.Element:
        """ports maps LADSPA port index -> value. channels=2 for mono plugins LMMS runs twice (linked)."""
        effect = self._shell("ladspaeffect", wet, autoquit_ms)
        controls = ET.SubElement(effect, "ladspacontrols", {"ports": str(port_count * channels)})
        if channels > 1:
            controls.set("link", "1")
        for channel in range(channels):
            for index, value in sorted(ports.items()):
                port = ET.SubElement(controls, f"port{channel}{index}", {"data": fmt(float(value))})
                if channels > 1:
                    port.set("link", "1")
        key = ET.SubElement(effect, "key")
        ET.SubElement(key, "attribute", {"name": "file", "value": file})
        ET.SubElement(key, "attribute", {"name": "plugin", "value": plugin})
        return self._append(effect)

    def effects(self) -> list[ET.Element]:
        return self.el.findall("effect")

    @staticmethod
    def describe(effect: ET.Element) -> str:
        key = {a.get("name"): a.get("value") for a in effect.findall("key/attribute")}
        if effect.get("name") == "ladspaeffect":
            return f"ladspa:{key.get('file', '?').removesuffix('.so')}:{key.get('plugin', '?')}"
        if effect.get("name") == "vsteffect":
            return f"vst:{key.get('file', '?')}"
        return effect.get("name", "?")

    @staticmethod
    def controls(effect: ET.Element) -> ET.Element:
        return next(child for child in effect if child.tag != "key")


class Track:
    """Wrapper around a <track> element of any type."""

    def __init__(self, project: "Project", element: ET.Element):
        self.project, self.el = project, element

    # -- identity ---------------------------------------------------------------------------------
    @property
    def type(self) -> int:
        return int(self.el.get("type", "0"))

    @property
    def name(self) -> str:
        return self.el.get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        self.el.set("name", value)

    @property
    def muted(self) -> bool:
        return Param(self.el, "muted").get() >= 0.5

    @muted.setter
    def muted(self, value: bool) -> None:
        Param(self.el, "muted").set(bool(value))

    # -- instrument / sample settings -----------------------------------------------------------
    @property
    def settings(self) -> ET.Element | None:
        """<instrumenttrack> or <sampletrack>: holds vol, pan, fxch, pitch and the effect chain."""
        return self.el.find("instrumenttrack") if self.type == TRACK_INSTRUMENT else self.el.find("sampletrack")

    def param(self, name: str) -> Param:
        """Track-level value: vol (0-200), pan (-100..100), pitch (cents), fxch."""
        return Param(self.settings, name)

    @property
    def plugin(self) -> str:
        instrument = self.el.find("instrumenttrack/instrument")
        return instrument.get("name", "") if instrument is not None else ""

    @property
    def plugin_el(self) -> ET.Element | None:
        """The plugin's own settings element, e.g. <tripleoscillator ...>."""
        instrument = self.el.find("instrumenttrack/instrument")
        return instrument[0] if instrument is not None and len(instrument) else None

    def plugin_param(self, name: str) -> Param:
        """A knob of the instrument itself. Fine to set. Automating it does not render the same way every time;
        shaping_param('fcut'), param('vol') and channel effects are the targets that do."""
        return Param(self.plugin_el, name)

    def shaping_param(self, name: str) -> Param:
        """Filter value on <eldata>: fcut (Hz), fres, ftype, fwet."""
        return Param(self.settings.find("eldata"), name)

    @property
    def fx(self) -> EffectChain:
        chain = self.settings.find("fxchain")
        if chain is None:
            chain = ET.SubElement(self.settings, "fxchain", {"numofeffects": "0", "enabled": "0"})
        return EffectChain(chain)

    @property
    def basenote(self) -> int:
        return int(float(self.settings.get("basenote", DEFAULT_BASENOTE)))

    # -- clips ---------------------------------------------------------------------------------------
    def add_pattern(self, start_beat: float, notes: list[Note], name: str | None = None, length_beats: float | None = None) -> ET.Element:
        """Add a melody clip. Note starts are relative to the clip start."""
        pattern = ET.SubElement(self.el, "pattern", {"type": "1", "muted": "0", "steps": "16", "name": name or self.name,
                                                    "pos": str(beats_to_ticks(start_beat))})
        if length_beats is not None:
            pattern.set("len", str(beats_to_ticks(length_beats)))
        for note in sorted(notes, key=lambda n: (n.start, n.pitch)):
            ET.SubElement(pattern, "note", {
                "pos": str(beats_to_ticks(note.start)), "len": str(max(1, beats_to_ticks(note.length))),
                "key": str(int(note.pitch) - MIDI_MINUS_LMMS_KEY), "vol": fmt(round(float(note.vol))), "pan": fmt(round(float(note.pan)))})
        return pattern

    def patterns(self) -> list[ET.Element]:
        return self.el.findall("pattern")

    def clear_patterns(self) -> None:
        for pattern in self.patterns():
            self.el.remove(pattern)

    def notes(self) -> list[Note]:
        """All notes of this track's song-editor clips with absolute start beats (muted clips skipped)."""
        result = []
        for pattern in self.patterns():
            if pattern.get("muted", "0") == "1":
                continue
            offset = int(pattern.get("pos", "0"))
            for note in pattern.findall("note"):
                length = int(note.get("len", "0"))
                result.append(Note(ticks_to_beats(offset + int(note.get("pos", "0"))),
                                   ticks_to_beats(length) if length > 0 else 0.25,      # negative len = step note
                                   int(note.get("key", "57")) + MIDI_MINUS_LMMS_KEY,
                                   float(note.get("vol", "100")), float(note.get("pan", "0"))))
        return sorted(result, key=lambda n: (n.start, n.pitch))

    def add_sample_clip(self, start_beat: float, path: str, length_beats: float) -> ET.Element:
        return ET.SubElement(self.el, "sampletco", {"pos": str(beats_to_ticks(start_beat)), "len": str(beats_to_ticks(length_beats)),
                                                    "muted": "0", "src": path})


class Mixer:
    """Wrapper around <fxmixer>. Channel 0 is the master; every other channel sends to it by default."""

    def __init__(self, project: "Project", element: ET.Element):
        self.project, self.el = project, element

    def channel(self, number: int) -> ET.Element | None:
        return next((c for c in self.el.findall("fxchannel") if int(c.get("num")) == number), None)

    def channels(self) -> list[ET.Element]:
        return sorted(self.el.findall("fxchannel"), key=lambda c: int(c.get("num")))

    def add_channel(self, name: str, volume: float = 1.0, send_to_master: float | None = 1.0) -> int:
        number = max(int(c.get("num")) for c in self.el.findall("fxchannel")) + 1
        channel = ET.SubElement(self.el, "fxchannel", {"num": str(number), "muted": "0", "volume": fmt(float(volume)),
                                                      "name": name, "soloed": "0"})
        ET.SubElement(channel, "fxchain", {"numofeffects": "0", "enabled": "0"})
        if send_to_master is not None:
            self.send(number, 0, send_to_master)
        return number

    def by_name(self, name: str) -> int:
        for channel in self.channels():
            if channel.get("name") == name:
                return int(channel.get("num"))
        raise KeyError(f"no mixer channel named '{name}'")

    def send(self, source: int, target: int, amount: float = 1.0) -> ET.Element:
        channel = self.channel(source)
        for send in channel.findall("send"):
            if int(send.get("channel")) == target:
                send.set("amount", fmt(float(amount)))
                return send
        return ET.SubElement(channel, "send", {"channel": str(target), "amount": fmt(float(amount))})

    def remove_send(self, source: int, target: int) -> None:
        channel = self.channel(source)
        for send in channel.findall("send"):
            if int(send.get("channel")) == target:
                channel.remove(send)

    def fx(self, number: int) -> EffectChain:
        return EffectChain(self.channel(number).find("fxchain"))

    def volume(self, number: int) -> Param:
        return Param(self.channel(number), "volume")


class Project:
    def __init__(self, root: ET.Element, path: str | None = None):
        self.root, self.path = root, path
        self._rng = random.Random(0)          # seeded: the same build script must give the same file
        self._used_ids = {int(e.get("id")) for e in root.iter() if e.get("id", "").isdigit() and e.tag != "connection"}

    # -- file io -----------------------------------------------------------------------------------
    @classmethod
    def new(cls, bpm: float = 140, timesig: tuple[int, int] = (4, 4)) -> "Project":
        project = cls(ET.fromstring(_EMPTY_PROJECT))
        project.bpm, project.timesig = bpm, timesig
        return project

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "rb") as handle:
            data = handle.read()
        if not data.lstrip().startswith(b"<"):          # .mmpz: 4-byte big-endian size + zlib stream
            data = zlib.decompress(data[4:])
        return cls(ET.fromstring(data), path)

    def to_bytes(self) -> bytes:
        ET.indent(self.root, space="  ")
        return (XML_HEADER + ET.tostring(self.root, encoding="unicode") + "\n").encode("utf-8")

    def save(self, path: str) -> str:
        data = self.to_bytes()
        if path.lower().endswith(COMPRESSED_EXTENSIONS):
            data = struct.pack(">I", len(data)) + zlib.compress(data)
        with open(path, "wb") as handle:
            handle.write(data)
        self.path = path
        return path

    def new_id(self) -> int:
        while True:
            candidate = self._rng.randint(*ID_RANGE)
            if candidate not in self._used_ids:
                self._used_ids.add(candidate)
                return candidate

    # -- global values ----------------------------------------------------------------------------
    @property
    def head(self) -> ET.Element:
        return self.root.find("head")

    @property
    def song(self) -> ET.Element:
        return self.root.find("song")

    @property
    def bpm(self) -> float:
        return Param(self.head, "bpm").get()

    @bpm.setter
    def bpm(self, value: float) -> None:
        Param(self.head, "bpm").set(value)

    @property
    def timesig(self) -> tuple[int, int]:
        return int(Param(self.head, "timesig_numerator").get() or 4), int(Param(self.head, "timesig_denominator").get() or 4)

    @timesig.setter
    def timesig(self, value: tuple[int, int]) -> None:
        Param(self.head, "timesig_numerator").set(value[0])
        Param(self.head, "timesig_denominator").set(value[1])

    @property
    def beats_per_bar(self) -> float:
        numerator, denominator = self.timesig
        return numerator * 4.0 / denominator

    def master_param(self, name: str) -> Param:
        """bpm, mastervol (0-200) or masterpitch (semitones)."""
        return Param(self.head, name)

    @property
    def mixer(self) -> Mixer:
        return Mixer(self, self.song.find("fxmixer"))

    @property
    def notes_text(self) -> str:
        node = self.song.find("projectnotes")
        return (node.text or "") if node is not None else ""

    @notes_text.setter
    def notes_text(self, text: str) -> None:
        node = self.song.find("projectnotes")
        if node is None:
            node = ET.SubElement(self.song, "projectnotes", {"visible": "0"})
        node.text = text

    # -- tracks -------------------------------------------------------------------------------------
    @property
    def _container(self) -> ET.Element:
        return self.song.find("trackcontainer")

    def tracks(self, kind: int | None = None) -> list[Track]:
        found = [Track(self, element) for element in self._container.findall("track")]
        return [t for t in found if kind is None or t.type == kind]

    def track(self, name: str) -> Track:
        matches = [t for t in self.tracks() if t.name == name]
        if not matches:
            raise KeyError(f"no track named '{name}'; have {[t.name for t in self.tracks()]}")
        return matches[0]

    def add_instrument_track(self, name: str, plugin: str, plugin_attrs: dict | None = None, *, vol: float = 100,
                             pan: float = 0, fxch: int = 0, pitch: float = 0, pitchrange: int = 1,
                             basenote: int = DEFAULT_BASENOTE, plugin_xml: ET.Element | None = None) -> Track:
        """plugin is the LMMS plugin id (tripleoscillator, kicker, lb302, audiofileprocessor, ...)."""
        track = ET.SubElement(self._container, "track", {"type": str(TRACK_INSTRUMENT), "muted": "0", "solo": "0", "name": name})
        settings = ET.SubElement(track, "instrumenttrack", {
            "vol": fmt(vol), "pan": fmt(pan), "fxch": str(fxch), "pitch": fmt(pitch), "pitchrange": str(pitchrange),
            "basenote": str(basenote), "usemasterpitch": "1"})
        instrument = ET.SubElement(settings, "instrument", {"name": plugin})
        if plugin_xml is not None:
            instrument.append(plugin_xml)
        else:
            ET.SubElement(instrument, plugin, {k: fmt(v) for k, v in (plugin_attrs or {}).items()})
        shaping = ET.SubElement(settings, "eldata", {"fcut": "14000", "fres": "0.5", "ftype": "0", "fwet": "0"})
        for tag in ("elvol", "elcut", "elres"):
            ET.SubElement(shaping, tag, _envelope_attrs())
        ET.SubElement(settings, "fxchain", {"numofeffects": "0", "enabled": "0"})
        return Track(self, track)

    def add_preset_track(self, name: str, preset_path: str, *, vol: float | None = None, pan: float = 0, fxch: int = 0) -> Track:
        """Create a track from an LMMS preset file (.xpf), e.g. one bundled under <lmms data>/presets."""
        preset_root = Project.load(preset_path).root
        source = preset_root.find("instrumenttracksettings")
        if source is None:
            source = preset_root.find(".//instrumenttrack")
        if source is None:
            raise ValueError(f"{preset_path} holds no instrument settings")
        track = ET.SubElement(self._container, "track", {"type": str(TRACK_INSTRUMENT), "muted": "0", "solo": "0", "name": name})
        settings = ET.SubElement(track, "instrumenttrack", dict(source.attrib))
        settings.extend(list(source))
        settings.set("fxch", str(fxch))
        settings.set("pan", fmt(pan))
        if vol is not None:
            settings.set("vol", fmt(vol))
        if settings.find("fxchain") is None:
            ET.SubElement(settings, "fxchain", {"numofeffects": "0", "enabled": "0"})
        return Track(self, track)

    def add_sample_track(self, name: str, vol: float = 100, pan: float = 0) -> Track:
        """Plain audio track. LMMS 1.2 sample tracks always feed the master channel directly."""
        track = ET.SubElement(self._container, "track", {"type": str(TRACK_SAMPLE), "muted": "0", "solo": "0", "name": name})
        settings = ET.SubElement(track, "sampletrack", {"vol": fmt(vol), "pan": fmt(pan)})
        ET.SubElement(settings, "fxchain", {"numofeffects": "0", "enabled": "0"})
        return Track(self, track)

    def remove_track(self, track: Track) -> None:
        self._container.remove(track.el)

    # -- envelopes and filter ---------------------------------------------------------------------
    @staticmethod
    def set_envelope(track: Track, target: str = "vol", *, attack: float = 0.0, hold: float = 0.0, decay: float = 0.0,
                     sustain: float = 1.0, release: float = 0.05, amount: float = 1.0, predelay: float = 0.0) -> None:
        """ADSR in seconds for target 'vol', 'cut' (filter cutoff) or 'res'. sustain is a 0-1 level."""
        element = track.settings.find(f"eldata/el{target}")
        # LMMS scales the decay knob by (1 - sustain), so undo that to hit the requested time.
        decay_knob = min(KNOB_MAX, seconds_to_knob(decay) / max(1.0 - sustain, 1e-3)) if decay > 0 else 0.0
        element.attrib.update({"pdel": fmt(seconds_to_knob(predelay)), "att": fmt(seconds_to_knob(attack)),
                               "hold": fmt(seconds_to_knob(hold)), "dec": fmt(decay_knob), "sustain": fmt(float(sustain)),
                               "rel": fmt(seconds_to_knob(release)), "amt": fmt(float(amount))})

    @staticmethod
    def set_filter(track: Track, cutoff: float, resonance: float = 0.5, kind: int = 0) -> None:
        """Per-note filter. kind: 0 LP, 1 HP, 2 BP, 4 notch, 6 Moog LP, 7 2x LP, 11 RC LP24, 16 SV LP ..."""
        track.settings.find("eldata").attrib.update({"fcut": fmt(float(cutoff)), "fres": fmt(float(resonance)),
                                                    "ftype": str(kind), "fwet": "1"})

    # -- automation ---------------------------------------------------------------------------------
    def _automation_track(self, name: str) -> ET.Element:
        for track in self._container.findall("track"):
            if int(track.get("type")) == TRACK_AUTOMATION and track.get("name") == name:
                return track
        track = ET.SubElement(self._container, "track", {"type": str(TRACK_AUTOMATION), "muted": "0", "solo": "0", "name": name})
        ET.SubElement(track, "automationtrack")
        return track

    def automate(self, param: "Param | list[Param]", points: list[tuple[float, float]], *, track_name: str = "Automation",
                 clip_name: str | None = None, progression: int = PROGRESSION_LINEAR) -> ET.Element:
        """Draw an automation curve. points are (absolute beat, value) pairs in the parameter's own unit.

        A list of parameters makes one clip drive all of them (they must share the same value range)."""
        if not points:
            raise ValueError("automation needs at least one point")
        params = param if isinstance(param, list) else [param]
        points = sorted(points)
        start = beats_to_ticks(points[0][0])
        end = max(beats_to_ticks(points[-1][0]), start + 1)
        clip = ET.SubElement(self._automation_track(track_name), "automationpattern", {
            "pos": str(start), "len": str(end - start), "name": clip_name or params[0].name, "prog": str(progression),
            "tens": "1", "mute": "0"})
        for beat, value in points:
            ET.SubElement(clip, "time", {"pos": str(beats_to_ticks(beat) - start), "value": fmt(float(value))})
        for item in params:
            ET.SubElement(clip, "object", {"id": str(item.ensure_id(self))})
        return clip

    def automation_clips(self) -> list[ET.Element]:
        return [clip for clip in self.root.iter("automationpattern") if clip.find("object") is not None]

    def set_length(self, total_beats: float) -> None:
        """Extend the song so the render includes effect tails after the last note."""
        track = self._automation_track("Song length")
        for clip in track.findall("automationpattern"):
            track.remove(clip)
        ET.SubElement(track, "automationpattern", {"pos": "0", "len": str(beats_to_ticks(total_beats)), "name": "length",
                                                   "prog": "0", "tens": "1", "mute": "0"})

    # -- controllers (sidechain, LFO) -------------------------------------------------------------
    def _controllers(self) -> ET.Element:
        node = self.song.find("controllers")
        return node if node is not None else ET.SubElement(self.song, "controllers")

    def add_peak_controller(self, chain: EffectChain, name: str, *, base: float = 1.0, amount: float = -1.0,
                            attack: float = 0.0, decay: float = 0.9, mute_output: bool = False, multiplier: float = 1.0) -> int:
        """Put a peak follower on `chain` and return the controller index to connect() parameters to.

        Controller output = base + amount * envelope, so base 1 / amount -1 ducks a parameter when
        the source is loud (classic sidechain). mute_output silences the source itself (ghost trigger).
        """
        effect_id = self.new_id()
        chain.add_native("peakcontrollereffect", {"effectId": effect_id, "base": base, "amount": amount, "attack": attack,
                                                  "decay": decay, "mute": mute_output, "abs": True, "amountmult": multiplier,
                                                  "treshold": 0})
        ET.SubElement(self._controllers(), "Peakcontroller", {"name": name, "effectId": str(effect_id), "type": "3"})
        return len(self._controllers()) - 1

    def add_lfo_controller(self, name: str, *, speed: float = 1.0, amount: float = 1.0, base: float = 0.5,
                           wave: int = 0, phase: float = 0.0) -> int:
        ET.SubElement(self._controllers(), "lfocontroller", {
            "name": name, "type": "1", "base": fmt(base), "speed": fmt(speed), "amount": fmt(amount), "phase": fmt(phase),
            "wave": str(wave), "multiplier": "0", "userwavefile": "", "syncmode": "0", "speed_numerator": "4",
            "speed_denominator": "4"})
        return len(self._controllers()) - 1

    @staticmethod
    def connect(param: Param, controller_index: int) -> None:
        """Let a controller drive a parameter (the controller output 0-1 spans the parameter's full range)."""
        connection = param.owner.find("connection")
        if connection is None:
            connection = ET.SubElement(param.owner, "connection")
        ET.SubElement(connection, param.name, {"id": str(controller_index)})

    # -- note access across the whole song ----------------------------------------------------------
    def bb_notes(self) -> dict[str, list[Note]]:
        """Beat/Bassline content expanded onto the song timeline, keyed by inner track name."""
        bb_tracks = self.tracks(TRACK_BB)
        result: dict[str, list[Note]] = {}
        if not bb_tracks:
            return result
        container = next((t.el.find("bbtrack/trackcontainer") for t in bb_tracks if t.el.find("bbtrack/trackcontainer") is not None), None)
        if container is None:
            return result
        bar_ticks = beats_to_ticks(self.beats_per_bar)
        for inner in container.findall("track"):
            patterns = inner.findall("pattern")
            for bb_index, bb_track in enumerate(bb_tracks):
                if bb_track.muted or bb_index >= len(patterns) or inner.get("muted", "0") == "1":
                    continue
                source = patterns[bb_index]
                notes = source.findall("note")
                if not notes:
                    continue
                last = max(int(n.get("pos")) + max(int(n.get("len")), 1) for n in notes)
                steps_len = int(source.get("steps", "16")) * bar_ticks // 16
                loop = max(bar_ticks, -(-max(last, steps_len) // bar_ticks) * bar_ticks)
                for clip in bb_track.el.findall("bbtco"):
                    if clip.get("muted", "0") == "1":
                        continue
                    clip_start, clip_len = int(clip.get("pos")), int(clip.get("len"))
                    for note in notes:
                        position = int(note.get("pos"))
                        while position < clip_len:
                            length = int(note.get("len"))
                            result.setdefault(inner.get("name", "bb"), []).append(Note(
                                ticks_to_beats(clip_start + position), ticks_to_beats(length) if length > 0 else 0.25,
                                int(note.get("key", "57")) + MIDI_MINUS_LMMS_KEY, float(note.get("vol", "100")),
                                float(note.get("pan", "0"))))
                            position += loop
        return result

    def all_notes(self) -> dict[str, list[Note]]:
        """Every sounding note by track name: song-editor clips plus expanded Beat/Bassline patterns."""
        result: dict[str, list[Note]] = {}
        for track in self.tracks(TRACK_INSTRUMENT):
            if not track.muted and track.notes():
                result.setdefault(track.name, []).extend(track.notes())
        for name, notes in self.bb_notes().items():
            result.setdefault(name, []).extend(notes)
        return result

    def length_beats(self) -> float:
        end = 0
        for clip in self.root.iter():
            if clip.tag in ("pattern", "bbtco", "sampletco", "automationpattern") and clip.get("pos") is not None:
                length = int(clip.get("len", "0"))
                if clip.tag == "pattern":
                    notes = clip.findall("note")
                    length = max([length] + [int(n.get("pos")) + max(int(n.get("len")), 1) for n in notes])
                end = max(end, int(clip.get("pos")) + length)
        return ticks_to_beats(end)

    def seconds_per_beat(self) -> float:
        return 60.0 / self.bpm


def _envelope_attrs() -> dict:
    return {"pdel": "0", "att": "0", "hold": "0.5", "dec": "0.5", "sustain": "0.5", "rel": "0.1", "amt": "0",
            "x100": "0", "lpdel": "0", "latt": "0", "lspd": "0.1", "lamt": "0", "lshp": "0", "lspd_syncmode": "0",
            "lspd_numerator": "4", "lspd_denominator": "4", "ctlenvamt": "0", "userwavefile": ""}


def resolve_sample(path: str, data_dirs: list[str]) -> str | None:
    """Find a sample the way LMMS does: absolute path first, then relative to each samples directory."""
    if os.path.isabs(path):
        return path if os.path.exists(path) else None
    for base in data_dirs:
        candidate = os.path.join(base, path)
        if os.path.exists(candidate):
            return candidate
    return None


def excerpt(project: Project, start_beat: float, length_beats: float) -> Project:
    """Copy of the project holding only [start, start+length): for fast previews of one section.

    Clips are cropped and shifted to bar 1. Automation is cut at the window and starts from the value
    it had at the window start, so filters and volumes sound as they do at that point of the song.
    """
    import copy
    result = Project(copy.deepcopy(project.root), project.path)
    low, high = beats_to_ticks(start_beat), beats_to_ticks(start_beat + length_beats)
    for parent in list(result.root.iter()):
        for clip in list(parent):
            if clip.tag not in ("pattern", "bbtco", "sampletco", "automationpattern") or clip.get("pos") is None:
                continue
            if clip.tag == "pattern" and parent.tag == "track" and _inside_bb(result.root, parent):
                continue                                   # Beat/Bassline step patterns are not on the song timeline
            position = int(clip.get("pos"))
            if clip.tag == "pattern":
                kept = False
                for note in list(clip.findall("note")):
                    absolute = position + int(note.get("pos"))
                    if low <= absolute < high:
                        note.set("pos", str(absolute - low))
                        kept = True
                    else:
                        clip.remove(note)
                if not kept:
                    parent.remove(clip)
                    continue
                clip.set("pos", "0")
                clip.attrib.pop("len", None)
            elif clip.tag == "automationpattern":
                points = sorted((position + int(t.get("pos")), float(t.get("value"))) for t in clip.findall("time"))
                if not points:                             # length marker: just crop
                    clip.set("pos", "0")
                    clip.set("len", str(max(1, min(position + int(clip.get("len", "0")), high) - low)))
                    continue
                before = [p for p in points if p[0] <= low]
                inside = [p for p in points if low < p[0] < high]
                if not before and not inside:
                    parent.remove(clip)
                    continue
                if before and inside and int(clip.get("prog", "0")) != PROGRESSION_DISCRETE:
                    (t0, v0), (t1, v1) = before[-1], inside[0]
                    first_value = v0 + (v1 - v0) * (low - t0) / (t1 - t0)
                else:
                    first_value = before[-1][1] if before else inside[0][1]
                for time_node in clip.findall("time"):
                    clip.remove(time_node)
                target = clip.find("object")
                for tick, value in [(low, first_value)] + inside:
                    node = ET.Element("time", {"pos": str(tick - low), "value": fmt(value)})
                    clip.insert(list(clip).index(target) if target is not None else len(clip), node)
                clip.set("pos", "0")
                clip.set("len", str(high - low))
            else:
                length = int(clip.get("len", "0"))
                if position + length <= low or position >= high:
                    parent.remove(clip)
                    continue
                clip.set("pos", str(max(position, low) - low))
                clip.set("len", str(min(position + length, high) - max(position, low)))
    return result


def _inside_bb(root: ET.Element, track: ET.Element) -> bool:
    return any(track in list(container) for container in root.iter("trackcontainer") if container.get("type") == "bbtrackcontainer")
