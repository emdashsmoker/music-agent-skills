# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""High-level song builder: sections, parts, buses, sidechain, transitions, master chain.

A song script creates a Song, declares sections, adds parts (one LMMS track + mixer channel each)
and writes clips into them. The result is an ordinary LMMS project plus a small plan file that
records what the mix tools cannot read from the project itself (roles, key, chords, lyrics).
Bars are counted from 0 in this API; reports print LMMS bar numbers (from 1).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import fx, genres, sounds, theory
from .project import PROGRESSION_LINEAR, Note, Param, Project, Track

PLAN_SUFFIX = ".plan.json"
VOCALS_SUFFIX = ".vocals.json"
LYRICS_SUFFIX = ".lyrics.txt"
DRUM_ROLES = ("kick", "snare", "clap", "hat", "cymbal", "perc")
BUS_OF_ROLE = {**{role: "drums" for role in DRUM_ROLES}, "sub": "bass", "bass": "bass", "lead": "music", "pluck": "music",
               "pad": "music", "keys": "music", "fx": "music", "vocal": "vocals", "vocal_bg": "vocals"}
BUS_ORDER = ("drums", "bass", "music", "vocals")
# Default send amounts (0-1) into the shared effect buses. Vocals get their own reverb so the
# kick sidechain never pumps the vocal tail.
SENDS_OF_ROLE = {"snare": {"reverb": 0.12}, "clap": {"reverb": 0.18}, "perc": {"reverb": 0.1}, "cymbal": {"reverb": 0.1},
                 "lead": {"reverb": 0.22, "delay": 0.15}, "pluck": {"reverb": 0.25, "delay": 0.2}, "pad": {"reverb": 0.3},
                 "keys": {"reverb": 0.18}, "fx": {"reverb": 0.3}, "vocal": {"vocal_reverb": 0.22, "delay": 0.08},
                 "vocal_bg": {"vocal_reverb": 0.35}}
# High-pass corner per role (Hz): everything that is not kick or bass gives up its low end.
HIGHPASS_OF_ROLE = {"kick": 28, "sub": 28, "bass": 35, "snare": 110, "clap": 180, "hat": 400, "cymbal": 350, "perc": 90,
                    "lead": 160, "pluck": 180, "pad": 180, "keys": 120, "fx": 150, "vocal": 90, "vocal_bg": 160}
MONO_ROLES = ("kick", "sub")
# Target loudness of each role relative to the anchor (the kick, else the loudest part), in LU.
# Measured as active loudness (90th percentile momentary LUFS) of the solo stem. A starting point:
# genre profiles shift these, and Part.level_db shifts a single part.
LEVEL_OF_ROLE = {"kick": 0.0, "snare": -2.0, "clap": -3.0, "hat": -8.0, "cymbal": -10.0, "perc": -8.0, "sub": -5.0,
                 "bass": -3.0, "lead": -1.0, "pluck": -3.0, "pad": -6.0, "keys": -4.0, "fx": -8.0, "vocal": -2.0,
                 "vocal_bg": -10.0}
# Highest peak a percussive part may reach, in dB against the peak of the kick. Loudness alone lets short sounds
# through far too hot: a loudness meter averages over 400 ms, so a 50 ms clap reads quiet, gets turned up, and
# then towers 6 dB over the kick as a peak that the limiter has to crush. Sustained parts are set by loudness only.
PEAK_OF_ROLE = {"kick": 0.0, "snare": -1.0, "clap": -3.0, "hat": -7.0, "cymbal": -8.0, "perc": -5.0}
# Mix taste: offsets in LU on top of the role and genre levels (and with them the peak ceilings). The default keeps
# the backbeat and the lead vocal a little forward: more than a tucked-in modern mix, well short of an 80s-size
# snare. Change it in 1 dB steps and run the checks again; {} gives the plain role levels.
MIX_TASTE = {"clap": 1.5, "snare": 1.0, "vocal": 1.5}
SIDECHAIN_TARGET_BUSES = ("bass", "music")
FULL_VOLUME_PERCENT = 100.0
LOWEST_BASS_ROOT = 28                             # E1
VOCAL_DUCK_JOIN_BEATS, VOCAL_DUCK_RAMP_BEATS = 2.0, 0.5
DUCK_CURVE_STEPS = 4
TICK_BEATS = 1.0 / 48.0
SWEEP_POINTS = 24
MASTER_CEILING_DB = -1.0
VOCAL_PRESENCE_HZ, VOCAL_PRESENCE_OCTAVES = 2600.0, 1.5   # centre and width of the dip that clears sung consonants
# 1.5 octaves spans about 1.5-4.5 kHz, the consonant band. The earlier 3 octaves reached 0.9-7.3 kHz and took
# about 6 dB out of the music up to 9 kHz under every sung line, which made choruses sound covered.
# Ducking of the music bus under every sung lead line, applied to any song with a vocal part unless the script calls
# duck_for_vocals itself or the genre profile carries its own pair. Chosen over a louder vocal: in the test songs
# +1.5 LU of vocal sounded the same as this dip, but cost 1.2 dB of limiter headroom and kept the vocal near its
# +9 dB ceiling, while the dip costs no headroom and leaves the master loudness unchanged.
VOCAL_DUCK_DB, VOCAL_PRESENCE_DB = 2.5, 6.0


@dataclass
class Section:
    name: str
    start_bar: int
    bars: int

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.bars


@dataclass
class Part:
    """One instrument: an LMMS track, its own mixer channel and a mix role."""
    song: "Song"
    name: str
    track: Track
    patch: dict
    role: str
    channel: int
    level_db: float = 0.0
    clips: list = field(default_factory=list)

    # -- writing clips -----------------------------------------------------------------------------
    def notes(self, at, notes: list[Note], name: str | None = None) -> "Part":
        """Add one clip at a bar position (section name, bar number, or (section, bar offset))."""
        start_beat = self.song.beat(at)
        self.clips.append(self.track.add_pattern(start_beat, notes, name or f"{self.name} {self.song.label(at)}"))
        return self

    def loop(self, at, notes: list[Note], bars: float, unit_bars: float = 1.0, name: str | None = None) -> "Part":
        """Tile a phrase of unit_bars across `bars` bars in one clip."""
        beats_per_bar = self.song.project.beats_per_bar
        times = int(round(bars / unit_bars))
        return self.notes(at, theory.repeat(notes, times, unit_bars * beats_per_bar), name)

    def hits(self, at, grid: str, bars: float = 1.0, pitch: int | None = None, step: float = 0.25, vol: float = 100,
             swing: float = 0.0, name: str | None = None) -> "Part":
        """Drum grid ('x---x---x---x---'), repeated to fill `bars`. The grid may span several bars."""
        length = sounds.note_length_beats(self.patch, self.song.bpm, default=step)
        unit = theory.hits(grid, pitch if pitch is not None else sounds.DRUM_PITCH, step, vol, length=length)
        steps = len(grid.replace(" ", "").replace("|", ""))
        unit_bars = steps * step / self.song.project.beats_per_bar
        if swing:
            unit = theory.swing(unit, swing, step)
        return self.loop(at, unit, bars, unit_bars, name)

    def seq(self, at, text: str, bars: float | None = None, step: float = 0.25, vol: float = 100, gate: float = 1.0,
            octave: int = 3, name: str | None = None) -> "Part":
        """Step-sequence text (see theory.seq), repeated to fill `bars` if given."""
        unit = theory.seq(text, step, vol, gate, octave)
        if bars is None:
            return self.notes(at, unit, name)
        tokens = len(theory.re.findall(r"\[[^\]]+\][!?]?|\S+", text.replace("|", " ")))
        return self.loop(at, unit, bars, tokens * step / self.song.project.beats_per_bar, name)

    def chords(self, at, symbols: list[str], bars_each: float = 1.0, octave: int = 3, rhythm: str | None = None,
               step: float = 0.25, vol: float = 100, gate: float = 0.95, lead_voices: bool = True,
               name: str | None = None) -> "Part":
        """Play a chord progression. rhythm is a one-bar hit grid ('x--x--x-x--x--x-'); None holds each chord."""
        beats_per_bar = self.song.project.beats_per_bar
        voicings = [theory.chord(symbol, octave) for symbol in symbols]
        if lead_voices:
            centre = 12 * (octave + 1) + 6
            voicings = theory.voice_lead(voicings, centre - 8, centre + 16)
        notes: list[Note] = []
        for index, pitches in enumerate(voicings):
            start = index * bars_each * beats_per_bar
            length = bars_each * beats_per_bar
            if rhythm is None:
                notes += theory.chord_notes(pitches, start, length * gate, vol)
                continue
            pattern = theory.hits(rhythm, 0, step, vol)
            bar_count = int(round(bars_each))
            for bar in range(max(1, bar_count)):
                for hit_index, hit in enumerate(pattern):
                    following = pattern[hit_index + 1].start if hit_index + 1 < len(pattern) else beats_per_bar
                    notes += theory.chord_notes(pitches, start + bar * beats_per_bar + hit.start, (following - hit.start) * gate, hit.vol)
        return self.notes(at, notes, name)

    def riff(self, at, symbols: list[str], pattern: str, bars_each: float = 1.0, step: float = 0.25, octave: int = 2,
             vol: float = 100, gate: float = 1.0, floor: int | None = None, name: str | None = None) -> "Part":
        """Play one chord-degree pattern (see theory.degree_seq) under each chord, repeated to fill the chord's bars.

        floor is the lowest root allowed (MIDI); a chord whose root falls below it is played an octave higher.
        Bass and sub parts default to E1 (41 Hz), the lowest fundamental most speakers reproduce.
        """
        beats_per_bar = self.song.project.beats_per_bar
        tokens = len(pattern.replace("|", " ").split())
        unit_beats = tokens * step
        if floor is None and self.role in ("bass", "sub"):
            floor = LOWEST_BASS_ROOT
        notes: list[Note] = []
        for index, symbol in enumerate(symbols):
            chord_start = index * bars_each * beats_per_bar
            repeats = int(round(bars_each * beats_per_bar / unit_beats))
            lift = octave
            while floor is not None and theory.chord_tone(symbol, "R", lift) < floor:
                lift += 1
            for k in range(max(1, repeats)):
                notes += theory.degree_seq(pattern, symbol, step, lift, vol, gate, chord_start + k * unit_beats)
        return self.notes(at, notes, name)

    def roll(self, at, bars: float, pitch: int | None = None, start_vol: float = 40, end_vol: float = 120,
             divisions: tuple[float, ...] = (0.5, 0.25, 0.125), name: str | None = None) -> "Part":
        """Build-up roll: hits get denser (8ths, 16ths, 32nds by default) and louder toward the end of `bars`."""
        beats = bars * self.song.project.beats_per_bar
        length = min(sounds.note_length_beats(self.patch, self.song.bpm, default=0.125), min(divisions))
        notes, position = [], 0.0
        while position < beats - 1e-6:
            stage = min(len(divisions) - 1, int(position / beats * len(divisions)))
            notes.append(Note(position, length, pitch if pitch is not None else sounds.DRUM_PITCH,
                              start_vol + (end_vol - start_vol) * position / beats))
            position += divisions[stage]
        return self.notes(at, notes, name)

    # -- mix shortcuts ------------------------------------------------------------------------------
    def send(self, bus: str, amount: float) -> "Part":
        self.song.mixer.send(self.channel, self.song.bus(bus), amount)
        return self

    @property
    def chain(self):
        """Effect chain of this part's mixer channel (mix processing; sound design sits on track.fx)."""
        return self.song.mixer.fx(self.channel)

    def volume_param(self) -> Param:
        return self.track.param("vol")


class Song:
    def __init__(self, title: str, bpm: float, key: str, genre: str = "", timesig: tuple[int, int] = (4, 4)):
        self.title, self.bpm, self.key, self.genre = title, float(bpm), key, genre
        self.project = Project.new(bpm=bpm, timesig=timesig)
        self.mixer = self.project.mixer
        self.sections: list[Section] = []
        self.parts: dict[str, Part] = {}
        self.chord_plan: list[dict] = []
        self.lyrics: list[dict] = []
        self.notes_for_humans: list[str] = []
        self._buses: dict[str, int] = {}
        self._ducks: list[dict] = []
        self._pump_hits: list[float] = []
        self.vocals: list = []
        self.vocal_reports: list[dict] = []
        self.vocal_duck_db: float | None = None          # None until decided: the script's call, else the genre, else the default
        self.vocal_presence_db: float | None = None
        self.tail_bars = 2
        for bus in BUS_ORDER:
            self._buses[bus] = self.mixer.add_channel(bus.upper())

    # -- time ---------------------------------------------------------------------------------------
    def section(self, name: str, bars: int) -> Section:
        if any(s.name == name for s in self.sections):
            raise ValueError(f"section name '{name}' is already used; names must be unique (intro, drop1, drop2 ...)")
        start = self.sections[-1].end_bar if self.sections else 0
        self.sections.append(Section(name, start, bars))
        return self.sections[-1]

    def structure(self, items: list[tuple[str, int]]) -> None:
        for name, bars in items:
            self.section(name, bars)

    def find(self, name: str) -> Section:
        for section in self.sections:
            if section.name == name:
                return section
        raise KeyError(f"no section '{name}'; have {[s.name for s in self.sections]}")

    def bar(self, at) -> float:
        """Absolute bar (0-based) of a position: 'drop1', 12, or ('drop1', 4) for 4 bars into drop1."""
        if isinstance(at, str):
            return self.find(at).start_bar
        if isinstance(at, tuple):
            return self.find(at[0]).start_bar + at[1]
        return at

    def beat(self, at) -> float:
        return self.bar(at) * self.project.beats_per_bar

    def label(self, at) -> str:
        return at if isinstance(at, str) else f"{at[0]}+{at[1]}" if isinstance(at, tuple) else f"bar{at + 1}"

    @property
    def total_bars(self) -> int:
        return self.sections[-1].end_bar if self.sections else 0

    def seconds(self, bar: float) -> float:
        return bar * self.project.beats_per_bar * 60.0 / self.bpm

    # -- buses --------------------------------------------------------------------------------------
    def bus(self, name: str) -> int:
        """Mixer channel number of a bus; effect buses (reverb, delay, vocal_reverb) are created on first use."""
        if name in self._buses:
            return self._buses[name]
        if name == "reverb":
            number = self.mixer.add_channel("REVERB")
            fx.reverb(self.mixer.fx(number), decay_s=2.4, room="large", predelay_ms=20)
        elif name == "vocal_reverb":
            number = self.mixer.add_channel("VOCAL REVERB")
            fx.reverb(self.mixer.fx(number), decay_s=1.8, room="medium", predelay_ms=40, low_cut=350, high_cut=7000)
        elif name == "delay":
            number = self.mixer.add_channel("DELAY")
            fx.delay(self.mixer.fx(number), self.bpm)
            fx.eq(self.mixer.fx(number), highpass=300, lowpass=6000)
        else:
            raise KeyError(f"unknown bus '{name}'; buses: {sorted(set(self._buses) | {'reverb', 'delay', 'vocal_reverb'})}")
        self._buses[name] = number
        return number

    # -- parts --------------------------------------------------------------------------------------
    def add(self, name: str, patch: str | dict, *, role: str | None = None, level_db: float = 0.0, pan: float = 0.0,
            sends: dict[str, float] | None = None, highpass: float | None = None, strip: bool = True) -> Part:
        """Add an instrument with its own mixer channel, routed to the bus of its role.

        strip=True applies the role's standard channel treatment (high-pass, mono for kick/sub).
        sends overrides the role's default reverb/delay sends, e.g. {'reverb': 0.4}.
        """
        if name in self.parts:
            raise ValueError(f"part '{name}' already exists")
        patch = sounds.get(patch) if isinstance(patch, str) else patch
        role = role or patch.get("role", "lead")
        if role not in BUS_OF_ROLE:
            raise ValueError(f"unknown role '{role}'; roles: {sorted(BUS_OF_ROLE)}")
        channel = self.mixer.add_channel(name, send_to_master=None)
        self.mixer.send(channel, self._buses[BUS_OF_ROLE[role]], 1.0)
        track = sounds.add(self.project, name, patch, fxch=channel, pan=pan)
        part = Part(self, name, track, patch, role, channel, level_db)
        if strip:
            corner = highpass if highpass is not None else HIGHPASS_OF_ROLE[role]
            fx.eq(part.chain, highpass=corner, slope=12 if role in ("kick", "sub", "bass") else 24)
            if role in MONO_ROLES:
                fx.mono(part.chain)
        for bus, amount in (sends if sends is not None else SENDS_OF_ROLE.get(role, {})).items():
            if amount > 0:
                part.send(bus, amount)
        self.parts[name] = part
        return part

    def add_audio(self, name: str, sample_path: str, *, role: str = "vocal", level_db: float = 0.0, pan: float = 0.0,
                  sends: dict[str, float] | None = None) -> Part:
        """Part that plays audio files (vocals, recorded stems) through a mixer channel.

        sample_path is relative to the project's samples folder. Use place_audio() to put more files on it.
        """
        patch = {"plugin": "audiofileprocessor", "attrs": sounds.sample(sample_path), "role": role,
                 "basenote": sounds.DRUM_BASENOTE}
        return self.add(name, patch, role=role, level_db=level_db, pan=pan, sends=sends)

    def place_audio(self, part: Part, at, seconds: float, name: str | None = None) -> None:
        """Trigger the part's audio file at a position for `seconds` (LMMS stops a sample at note end)."""
        beats = seconds * self.bpm / 60.0 + 0.25
        part.notes(at, [Note(0.0, beats, sounds.DRUM_PITCH)], name)

    # -- vocals -------------------------------------------------------------------------------------
    def vocal(self, name: str, voice: str, *, role: str = "vocal", method: str = "auto", lang: str = "en", speed: float = 1.0,
              style=None, level_db: float = 0.0, pan: float = 0.0, sends: dict[str, float] | None = None,
              effects: list[tuple[str, dict]] | None = None, **options) -> "SongVocal":
        """Declare a sung part. voice is kokoro:<voice>, piper:<voice> or diffsinger:<folder>[#colour].

        Lines are added with .line(at, text, melody); the audio is rendered when the song is saved.
        effects are character effects after the standard vocal strip, as [(fx builder name, arguments)],
        e.g. [("distortion", {"drive": 4.0})]. options go to the engine (speech voices: fix_ending;
        DiffSinger: steps, gender, velocity, tension, breathiness, expressiveness, own_pitch).
        """
        from .vocal.part import VocalPart
        from .vocal.singing import Style
        part = VocalPart(name, voice, role, method, lang, speed, style or Style(), options)
        wrapper = SongVocal(self, part, level_db, pan, sends, effects)
        self.vocals.append(wrapper)
        return wrapper

    def duck_for_vocals(self, depth_db: float, presence_db: float = 0.0) -> None:
        """Set how much room the music bus makes while a lead vocal line is sung (automation written from the line timings).

        Every song with a vocal part is ducked without this call: VOCAL_DUCK_DB and VOCAL_PRESENCE_DB, or the
        genre profile's 'vocal_duck' pair. Call it to choose the numbers yourself; duck_for_vocals(0) turns the
        ducking off. depth_db lowers the whole bus a little. presence_db dips only the band where consonants live
        (around 1.3-5 kHz), which clears the words without thinning the music as a level dip that deep would.
        """
        self.vocal_duck_db, self.vocal_presence_db = abs(depth_db), abs(presence_db)

    def vocal_ducking(self) -> tuple[float, float]:
        """(depth_db, presence_db) that will be written: the script's call wins, then the genre profile, then the default."""
        if self.vocal_duck_db is not None:
            return self.vocal_duck_db, self.vocal_presence_db
        depth, presence = genres.get(self.genre).get("vocal_duck", (VOCAL_DUCK_DB, VOCAL_PRESENCE_DB))
        return abs(depth), abs(presence)

    def render_vocals(self, project_path: str, cache: str | None = None) -> list[dict]:
        """Sing every vocal part into <project folder>/samples/<project name>/<part>.flac and put it on a track."""
        from .vocal import part as vocal_part
        folder = os.path.dirname(os.path.abspath(project_path))
        slug = os.path.splitext(os.path.basename(project_path))[0]
        cache = cache or os.path.join(folder, ".vocal_cache")
        total_beats = self.total_bars * self.project.beats_per_bar
        self.vocal_reports = []
        for wrapper in self.vocals:
            self._fit_harmony_to_chords(wrapper.part)
            file_name = wrapper.part.name.replace(" ", "_") + ".flac"
            rendered = vocal_part.render_part(wrapper.part, self.bpm, self.key, total_beats,
                                              os.path.join(folder, "samples", slug, file_name), cache)
            self.vocal_reports.append(rendered)
            if wrapper.part.name not in self.parts:
                audio = self.add_audio(wrapper.part.name, f"{slug}/{file_name}", role=wrapper.part.role, level_db=wrapper.level_db,
                                       pan=wrapper.pan, sends=wrapper.sends)
                self._vocal_strip(audio, wrapper.part.voice)
                for effect_name, arguments in wrapper.effects:
                    getattr(fx, effect_name)(audio.chain, **arguments)
            audio = self.parts[wrapper.part.name]
            audio.track.clear_patterns()
            self.place_audio(audio, 0, rendered["stem_seconds"], name=f"{wrapper.part.name} stem")
        self.lyrics = [{"part": r["part"], "role": r["role"], "voice": r["voice"],
                        "lines": [{k: row[k] for k in ("text", "melody", "start_beat", "first_note_s", "audio_start_s", "audio_end_s", "section", "kind")}
                                  for row in r["lines"]]} for r in self.vocal_reports]
        return self.vocal_reports

    def _fit_harmony_to_chords(self, part) -> None:
        """Write out each harmony line as its own melody, kept clear of semitone rubs against the declared chords."""
        from .vocal import lines as line_tools
        beats_per_bar = self.project.beats_per_bar

        def tones_at(beat: float) -> set[int] | None:
            entry = next((e for e in self.chord_plan if e["bar"] * beats_per_bar <= beat < (e["bar"] + e["bars"]) * beats_per_bar), None)
            return set(theory.chord_pitch_classes(entry["symbol"])) if entry else None
        for line in part.lines:
            if line.harmony:
                line.melody = line_tools.harmonize(line.melody, self.key, line.harmony, lambda beat, start=line.start_beat: tones_at(start + beat))
                line.harmony = 0

    def _vocal_strip(self, part: Part, voice: str) -> None:
        """Standard vocal channel: tone shaping and levelling compression; extra air for band-limited speech voices.

        No de-esser: the Calf Deesser bundled with LMMS 1.2 cuts everything above its split frequency whatever its
        threshold and ratio (measured on a sung stem: 9-16 kHz -7 dB, 5-9 kHz -2 dB with the threshold at 0 dBFS),
        which took back the air this strip adds and left speech voices dull. Sibilance is handled by the voices'
        own band limit (Kokoro renders at 24 kHz) and by the master limiter.
        """
        speech_voice = voice.split(":", 1)[0] in ("kokoro", "piper")
        fx.eq(part.chain, peaks=[(280.0, -2.0, 1.0), (3200.0, 2.5, 1.2)], high_shelf=(9000.0, 3.0 if speech_voice else 1.5))
        fx.compressor(part.chain, threshold_db=-22.0, ratio=3.0, attack_ms=8.0, release_ms=120.0, makeup_db=3.0)

    def _write_vocal_ducking(self) -> None:
        """Automation on the music bus for the time a lead line is sung: a small level dip and a presence-band dip."""
        depth_db, presence_db = self.vocal_ducking()
        if not (depth_db or presence_db) or not self.vocal_reports:
            return
        track_name = "Vocal ducking"
        holder = self.project._automation_track(track_name)
        for clip in holder.findall("automationpattern"):
            holder.remove(clip)
        chain = self.mixer.fx(self._buses["music"])
        if not hasattr(self, "_vocal_duck_amp"):
            self._vocal_duck_amp = fx.gain(chain, 100.0)
            self._vocal_presence_eq = fx.eq(chain, peaks=[(VOCAL_PRESENCE_HZ, 0.0, VOCAL_PRESENCE_OCTAVES)])
        low = FULL_VOLUME_PERCENT * fx.db_to_gain(-depth_db)
        seconds_per_beat = 60.0 / self.bpm
        spans = sorted((row["audio_start_s"] / seconds_per_beat, row["audio_end_s"] / seconds_per_beat)
                       for report in self.vocal_reports if report["role"] == "vocal" for row in report["lines"])
        merged: list[list[float]] = []
        for start, end in spans:
            if merged and start - merged[-1][1] < VOCAL_DUCK_JOIN_BEATS:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        ramp = VOCAL_DUCK_RAMP_BEATS
        curves = [(fx.control(self._vocal_duck_amp, "volume"), FULL_VOLUME_PERCENT, low, "level", depth_db),
                  (fx.control(self._vocal_presence_eq, "Peak1gain"), 0.0, -presence_db, "presence", presence_db)]
        for param, rest, sung, label, wanted in curves:
            for start, end in merged if wanted else []:
                self.project.automate(param, [(max(0.0, start - ramp), rest), (start, sung), (end, sung), (end + ramp, rest)],
                                      track_name=track_name, clip_name=f"vocal line {label}")

    # -- harmony plan -------------------------------------------------------------------------------
    def chords(self, at, text: str, bars_each: float = 1.0, repeats: int = 1) -> list[str]:
        """Declare the chord progression for a stretch of the song (used by lint).

        Returns one symbol per chord for the whole stretch (the progression times `repeats`), ready to hand to
        Part.riff or Part.chords with the same bars_each.
        """
        symbols = theory.progression(text, self.key) * repeats
        start = self.bar(at)
        for index, symbol in enumerate(symbols):
            self.chord_plan.append({"bar": start + index * bars_each, "bars": bars_each, "symbol": symbol})
        return symbols

    # -- dynamics between parts ---------------------------------------------------------------------
    def sidechain(self, source: str = "kick", targets: list[str] | None = None, depth_db: float = 6.0,
                  hold_beats: float = 0.05, release_beats: float = 0.4, shape: float = 1.0) -> None:
        """Duck `targets` (bus or part names; default the bass and music buses) on every hit of `source`.

        Written as volume automation of a 'duck' amplifier on each target channel, generated from the
        source's notes when the song is saved: full depth_db at the hit, held for hold_beats, back to
        unity after release_beats (shape > 1 recovers late for a stronger pump, < 1 recovers early).
        Automation is used instead of an LMMS peak controller because controllers are read by the mixer's
        worker threads in no fixed order, which makes two renders of the same project differ.
        Call again with other targets for a different depth; use pump() where the source rests.
        """
        numbers = [self._buses[t] if t in self._buses else self.parts[t].channel for t in targets or SIDECHAIN_TARGET_BUSES]
        self._ducks.append({"source": source, "channels": numbers, "depth_db": abs(depth_db), "hold": hold_beats,
                            "release": release_beats, "shape": shape, "amps": None})

    def pump(self, at, grid: str = "x---x---x---x---", bars: float = 1.0) -> None:
        """Extra ducking hits where the source is silent (keeps a breakdown pad pumping)."""
        unit = theory.hits(grid, 0, 0.25)
        steps = len(grid.replace(" ", "").replace("|", ""))
        times = int(round(bars / (steps * 0.25 / self.project.beats_per_bar)))
        self._pump_hits += [self.beat(at) + n.start for n in theory.repeat(unit, times, steps * 0.25)]

    def _write_ducking(self) -> None:
        """Turn each sidechain() request into automation clips, one per section (done at save time)."""
        for index, duck in enumerate(self._ducks):
            track_name = f"Sidechain {index + 1} (-{duck['depth_db']:g} dB)"
            holder = self.project._automation_track(track_name)
            for clip in holder.findall("automationpattern"):
                holder.remove(clip)
            if duck["amps"] is None:
                duck["amps"] = [fx.gain(self.mixer.fx(number), 100.0) for number in duck["channels"]]
            hits = sorted({round(n.start, 4) for n in self.parts[duck["source"]].track.notes()} | {round(h, 4) for h in self._pump_hits})
            points = duck_curve(hits, duck["depth_db"], duck["hold"], duck["release"], duck["shape"])
            params = [fx.control(amp, "volume") for amp in duck["amps"]]
            beats_per_bar = self.project.beats_per_bar
            for section in self.sections:
                low, high = section.start_bar * beats_per_bar, section.end_bar * beats_per_bar
                inside = [(beat, value) for beat, value in points if low <= beat < high]
                if inside:
                    self.project.automate(params, [(low, FULL_VOLUME_PERCENT)] + inside + [(high, FULL_VOLUME_PERCENT)],
                                          track_name=track_name, clip_name=f"duck {section.name}")

    # -- automation helpers -------------------------------------------------------------------------
    def automate(self, param: Param, points: list[tuple[float, float]], name: str = "automation", track: str = "Automation") -> None:
        """points are (absolute bar, value)."""
        beats_per_bar = self.project.beats_per_bar
        self.project.automate(param, [(bar * beats_per_bar, value) for bar, value in points], track_name=track,
                              clip_name=name, progression=PROGRESSION_LINEAR)

    def sweep(self, target: str, at, bars: float, start_hz: float, end_hz: float, kind: str = "lowpass",
              resonance: float = 0.9, rest_hz: float | None = None) -> None:
        """Filter sweep on a part or bus over `bars` (build-up opening, breakdown closing).

        The curve is exponential in Hz so it sounds even. After the sweep the filter jumps to rest_hz
        (default: fully open for lowpass, fully closed for highpass).
        """
        number = self._buses[target] if target in self._buses else self.parts[target].channel
        key = (number, kind)
        if not hasattr(self, "_sweep_filters"):
            self._sweep_filters = {}
        if key not in self._sweep_filters:
            open_hz = 20000.0 if kind.startswith("lowpass") or kind == "moog" else 20.0
            self._sweep_filters[key] = (fx.filter_sweep(self.mixer.fx(number), open_hz, resonance, kind), open_hz)
        effect, open_hz = self._sweep_filters[key]
        start_bar = self.bar(at)
        points = [(start_bar + bars * i / (SWEEP_POINTS - 1), start_hz * (end_hz / start_hz) ** (i / (SWEEP_POINTS - 1)))
                  for i in range(SWEEP_POINTS)]
        # A hair after the end, snap back so the next section is unfiltered.
        points.append((start_bar + bars + 1 / 96, rest_hz if rest_hz is not None else open_hz))
        self.automate(fx.control(effect, "cut1"), points, name=f"{target} {kind} sweep", track=f"{target} filter")

    def fade(self, target: str, at, bars: float, start_db: float, end_db: float, rest_db: float = 0.0) -> None:
        """Volume ramp on a part's mixer channel in dB relative to its fader position, then back to rest_db."""
        number = self._buses[target] if target in self._buses else self.parts[target].channel
        if not hasattr(self, "_fade_amps"):
            self._fade_amps = {}
        if number not in self._fade_amps:
            self._fade_amps[number] = fx.gain(self.mixer.fx(number), 100.0)
        start_bar = self.bar(at)
        steps = 12
        points = [(start_bar + bars * i / steps, 100.0 * fx.db_to_gain(start_db + (end_db - start_db) * i / steps)) for i in range(steps + 1)]
        points.append((start_bar + bars + 1 / 96, 100.0 * fx.db_to_gain(rest_db)))
        self.automate(fx.control(self._fade_amps[number], "volume"), points, name=f"{target} fade", track=f"{target} volume")

    def riser(self, at, bars: float, level_db: float = 0.0, start_hz: float = 400.0, end_hz: float = 12000.0) -> Part:
        """White-noise riser ending at at+bars: a band-pass opens upward while the level climbs.

        All risers share one track; level_db shapes each one through the fade, so the part count stays small.
        """
        if "riser" not in self.parts:
            self.add("riser", "white_noise", role="fx", sends={"reverb": 0.35}, highpass=200)
            self.fade("riser", 0, 0, -60.0, -60.0, rest_db=-60.0)        # silent between risers
        part = self.parts["riser"]
        part.notes(at, [Note(0.0, bars * self.project.beats_per_bar, 60)])
        self.sweep("riser", at, bars, start_hz, end_hz, kind="bandpass", resonance=1.5, rest_hz=end_hz)
        self.fade("riser", at, bars, level_db - 24.0, level_db, rest_db=-60.0)
        return part

    def impact(self, at, level_db: float = 0.0) -> list[Part]:
        """Downbeat impact for a drop: crash plus sub drop. All impacts share two tracks; level_db sets the hit strength."""
        if "impact crash" not in self.parts:
            self.add("impact crash", "crash2", role="cymbal", level_db=3.0, sends={"reverb": 0.4})
            self.add("impact sub", "sub_drop", role="fx", level_db=4.0, sends={}, highpass=25)
        crash, boom = self.parts["impact crash"], self.parts["impact sub"]
        beats = self.project.beats_per_bar
        vol = min(200.0, 100.0 * fx.db_to_gain(level_db))
        crash.notes(at, [Note(0.0, sounds.note_length_beats(crash.patch, self.bpm), sounds.DRUM_PITCH, vol)])
        boom.notes(at, [Note(0.0, min(2 * beats, sounds.note_length_beats(boom.patch, self.bpm)), sounds.DRUM_PITCH, vol)])
        return [crash, boom]

    # -- master -------------------------------------------------------------------------------------
    def master(self, *, highpass: float = 25.0, glue: bool = True, limiter_gain_db: float = 0.0,
               ceiling_db: float = MASTER_CEILING_DB, eq_peaks: list[tuple[float, float, float]] | None = None,
               high_shelf: tuple[float, float] | None = None, low_shelf: tuple[float, float] | None = None) -> None:
        """Master chain: clean-up EQ, gentle glue compression, brickwall limiter. Call once, last."""
        chain = self.mixer.fx(0)
        fx.eq(chain, highpass=highpass, slope=24, peaks=eq_peaks, high_shelf=high_shelf, low_shelf=low_shelf)
        if glue:
            fx.compressor(chain, threshold_db=-14.0, ratio=2.0, attack_ms=30.0, release_ms=200.0, knee_db=6.0)
        self.limiter = fx.limiter(chain, ceiling_db=ceiling_db, input_gain_db=limiter_gain_db)

    # -- output -------------------------------------------------------------------------------------
    def plan(self) -> dict:
        return {
            "title": self.title, "bpm": self.bpm, "key": self.key, "genre": self.genre,
            "timesig": list(self.project.timesig),
            "sections": [{"name": s.name, "start_bar": s.start_bar, "bars": s.bars} for s in self.sections],
            "parts": {name: {"role": p.role, "bus": BUS_OF_ROLE[p.role], "level_db": p.level_db,
                             "patch": p.patch.get("plugin", "")} for name, p in self.parts.items()},
            "chords": self.chord_plan, "lyrics": self.lyrics,
            "vocal_duck": dict(zip(("depth_db", "presence_db"), self.vocal_ducking())) if self.vocals else None,
        }

    def save(self, path: str, vocal_cache: str | None = None) -> str:
        """Write the .mmp/.mmpz and its plan file next to it. Vocal parts are sung first (cached between runs)."""
        beats_per_bar = self.project.beats_per_bar
        if self.vocals:
            self.render_vocals(path, vocal_cache)
            self._write_vocal_ducking()
        self._write_ducking()
        self.project.set_length((self.total_bars + self.tail_bars) * beats_per_bar)
        summary = [f"{self.title}: {self.bpm:g} BPM, {self.key}" + (f", {self.genre}" if self.genre else "")]
        summary += [f"bar {s.start_bar + 1}: {s.name} ({s.bars} bars)" for s in self.sections] + self.notes_for_humans
        self.project.notes_text = "\n".join(summary)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.project.save(path)
        sounds.install_kit(self.project, path)
        with open(plan_path(path), "w", encoding="utf-8") as handle:
            json.dump(self.plan(), handle, indent=1, ensure_ascii=False)
        if self.vocal_reports:
            from .vocal import part as vocal_part
            base = os.path.splitext(path)[0]
            # Stem paths are stored relative to the project so that the folder can be moved or packed.
            folder = os.path.dirname(os.path.abspath(path))
            vocal_part.save_report(base + VOCALS_SUFFIX, [{**report, "stem": os.path.relpath(report["stem"], folder)} for report in self.vocal_reports])
            with open(base + LYRICS_SUFFIX, "w", encoding="utf-8") as handle:
                handle.write(vocal_part.lyric_sheet(self.vocal_reports, self.title))
        return path


class SongVocal:
    """A vocal part bound to its song: positions are given like everywhere else (section name, bar, or (section, bar))."""

    def __init__(self, song: Song, part, level_db: float, pan: float, sends: dict[str, float] | None,
                 effects: list[tuple[str, dict]] | None = None):
        self.song, self.part, self.level_db, self.pan, self.sends, self.effects = song, part, level_db, pan, sends, effects or []

    def line(self, at, text: str, melody: str, kind: str | None = None, beats: float = 0.0) -> "SongVocal":
        """Add a line whose melody starts at `at` (+ `beats`; negative for a pickup). kind defaults from the section name."""
        bar = self.song.bar(at)
        section = next((s.name for s in self.song.sections if s.start_bar <= bar < s.end_bar), "")
        guessed = "chorus" if any(word in section.lower() for word in ("chorus", "hook", "drop")) else "verse"
        self.part.line(self.song.beat(at) + beats, text, melody, section=section, kind=kind or guessed)
        return self

    def harmony(self, name: str, steps: int = 2, only_kind: str | None = "chorus", level_db: float = 0.0, pan: float = 0.0,
                voice: str | None = None) -> "SongVocal":
        """Add a harmony part moving `steps` scale steps from this one (2 = a third above, -3 = a fourth below)."""
        part = self.part.derive(name, harmony=steps, only_kind=only_kind, voice=voice)
        wrapper = SongVocal(self.song, part, level_db, pan, self.sends, self.effects)
        self.song.vocals.append(wrapper)
        return wrapper

    def double(self, name: str, seed: int | None = None, only_kind: str | None = "chorus", level_db: float = -3.0, pan: float = 0.0) -> "SongVocal":
        """Add a second take of the same lines (different pitch drift and vibrato) to thicken them."""
        part = self.part.derive(name, seed=seed, only_kind=only_kind)
        wrapper = SongVocal(self.song, part, level_db, pan, self.sends, self.effects)
        self.song.vocals.append(wrapper)
        return wrapper


def duck_curve(hits: list[float], depth_db: float, hold: float, release: float, shape: float = 1.0) -> list[tuple[float, float]]:
    """Automation points (beat, volume %) for sidechain-style ducking at each hit."""
    low = FULL_VOLUME_PERCENT * fx.db_to_gain(-abs(depth_db))
    points: list[tuple[float, float]] = []
    for index, hit in enumerate(hits):
        limit = hits[index + 1] - TICK_BEATS if index + 1 < len(hits) else float("inf")
        if not points or points[-1][0] < hit - TICK_BEATS:
            points.append((hit - TICK_BEATS, FULL_VOLUME_PERCENT if not points else points[-1][1]))
        points.append((hit, low))
        points.append((min(hit + hold, limit), low))
        for step in range(1, DUCK_CURVE_STEPS + 1):
            beat = hit + hold + release * step / DUCK_CURVE_STEPS
            if beat >= limit:
                break
            points.append((beat, low + (FULL_VOLUME_PERCENT - low) * (step / DUCK_CURVE_STEPS) ** shape))
    return [(beat, value) for beat, value in points if beat >= 0]


def sung_notes(project_path: str) -> dict[str, list[Note]]:
    """Melody of every rendered vocal part as notes ({part name: notes}), read from the vocals file next to the project.

    A vocal part is one audio file on the timeline; its notes exist only in that file, so lint, figures and MIDI
    export take them from here.
    """
    path = os.path.splitext(project_path)[0] + VOCALS_SUFFIX
    if not project_path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        rendered = json.load(handle)
    plan = load_plan(project_path) or {}
    seconds_per_beat = 60.0 / float(plan.get("bpm", 120.0))
    result: dict[str, list[Note]] = {}
    for part in rendered:
        notes = []
        for row in part["lines"]:
            for syllable in row["syllables"]:
                span = (syllable["end_s"] - syllable["start_s"]) / max(len(syllable["pitches"]), 1)
                for index, pitch in enumerate(syllable["pitches"]):
                    notes.append(Note((syllable["start_s"] + index * span) / seconds_per_beat, max(span / seconds_per_beat, 0.05), int(round(pitch))))
        result[part["part"]] = notes
    return result


def notes_with_vocals(project: Project, project_path: str | None) -> dict[str, list[Note]]:
    """All sounding notes by part, with each vocal part's audio trigger replaced by the melody it sings."""
    notes = project.all_notes()
    notes.update(sung_notes(project_path) if project_path else {})
    return notes


def plan_path(project_path: str) -> str:
    return os.path.splitext(project_path)[0] + PLAN_SUFFIX


def load_plan(project_path: str) -> dict | None:
    path = plan_path(project_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
