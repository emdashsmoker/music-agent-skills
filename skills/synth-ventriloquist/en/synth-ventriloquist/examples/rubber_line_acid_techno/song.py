# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Rubber Line - acid techno, 130 BPM, A phrygian, 120 bars (3:41), instrumental. Shows the 303-style bass under a moving resonant filter.

Usage: python song.py
The project is written into the current folder, so run it from a work folder outside the skill.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from lmmskit import fx, sounds, theory as T          # noqa: E402
from lmmskit.compose import Song                     # noqa: E402

song = Song("Rubber Line", 130, "A phrygian", "acid_house")
song.structure([("intro", 16), ("acid_in", 16), ("lift", 8), ("main1", 24), ("breakdown", 16), ("main2", 24), ("outro", 16)])
for section in song.sections:
    if section.name == "breakdown":
        song.chords(section.name, "Am A# Am Am", bars_each=4)
    else:
        song.chords(section.name, "Am", bars_each=section.bars)

kick = song.add("kick", "909_kick")
clap = song.add("clap", "909_clap")
chat = song.add("closed hat", "909_hat")
ohat = song.add("open hat", "909_ohat")
ride = song.add("ride", "808_ride", level_db=-3)
rim = song.add("rim", "808_rim", sends={"delay": 0.3})
tom = song.add("tom", "808_tom_lo", sends={"reverb": 0.2})
acid = song.add("acid", sounds.get("acid_bass", attrs={"vcf_cut": 0.8, "vcf_res": 0.9, "vcf_mod": 0.6}), sends={"delay": 0.15})
acid2 = song.add("acid high", "acid_square", role="lead", level_db=0, sends={"delay": 0.3, "reverb": 0.15})
sub = song.add("sub", "sub_bass", level_db=-5)
stab = song.add("stab", "chord_stab", level_db=2, sends={"delay": 0.4, "reverb": 0.3})
pad = song.add("pad", "dark_pad", sends={"reverb": 0.5})
fx.saturator(acid.track.fx, drive=5.0, character=0.4)                 # grit is part of the acid sound itself

FOUR = "x---x---x---x---"
for name, start, bars in (("intro", 0, 16), ("acid_in", 0, 16), ("lift", 0, 6), ("main1", 0, 24), ("main2", 0, 24), ("outro", 0, 16)):
    kick.hits((name, start), FOUR, bars=bars)
for name, start, bars in (("acid_in", 8, 8), ("main1", 0, 24), ("main2", 0, 24), ("outro", 0, 8)):
    clap.hits((name, start), "----x-------x---", bars=bars)
for name, start, bars in (("intro", 4, 12), ("acid_in", 0, 16), ("lift", 0, 8), ("main1", 0, 24), ("main2", 0, 24), ("outro", 0, 12)):
    chat.hits((name, start), "x-xxX-xxx-xxX-xo", bars=bars, vol=80)
for name, start, bars in (("intro", 8, 8), ("acid_in", 0, 16), ("main1", 0, 24), ("main2", 0, 24), ("outro", 0, 8)):
    ohat.hits((name, start), "--x---x---x---x-", bars=bars)
ride.hits(("main2", 8), "x-x-x-x-x-x-x-x-", bars=16, vol=80)
for name, start, bars in (("acid_in", 0, 16), ("main1", 0, 24), ("breakdown", 8, 8), ("main2", 0, 24)):
    rim.hits((name, start), "--x--x----x--x-x", bars=bars, vol=75)
for name, bar in (("intro", 15), ("acid_in", 15), ("main1", 7), ("main1", 23), ("main2", 7), ("main2", 23)):
    tom.hits((name, bar), "--------x--x-xxx")
clap.roll(("lift", 4), 4, divisions=(0.5, 0.25, 0.125))

# The acid line: sixteenths around A with the flat second (Bb) and octave jumps. '_' ties make the 303 slide.
LINE_A = "A1 A1 . A2 A1 . C2 A1 | A#1 _ A1 . A2 . G1 A1"
LINE_B = "A1 . A2 A1 A#1 A1 . E2 | A1 A2 _ A1 . C2 A#1 A1"
LINE_C = "A2 A1 A1 A2 . A1 A#1 . | E2 _ D2 A1 C2 . A#1 A2"
for name, start, bars, line in (("acid_in", 0, 16, LINE_A), ("lift", 0, 8, LINE_B), ("main1", 0, 24, LINE_B), ("breakdown", 8, 8, LINE_A),
                                ("main2", 0, 24, LINE_C), ("outro", 0, 8, LINE_A)):
    acid.seq((name, start), line, bars=bars, octave=1, gate=1.05)
acid2.seq(("main2", 8), "E4 . A4 . C5 . A4 E4 | . A#4 . A4 . E4 G4 .", bars=16, octave=4, gate=0.9)
for name, start, bars in (("intro", 8, 8), ("acid_in", 0, 16), ("main1", 0, 24), ("main2", 0, 24), ("outro", 0, 16)):
    sub.seq((name, start), ". . A1 _ . . A1 _ . . A1 _ . . A1 _", bars=bars, octave=1)
for name, start, bars in (("main1", 8, 16), ("main2", 0, 24)):
    stab.loop((name, start), T.chord_notes(T.chord("Am", 4), 0.5, 0.25) + T.chord_notes(T.chord("Am", 4), 2.75, 0.25, vol=80), bars=bars)
stab.loop("breakdown", T.chord_notes(T.chord("A#", 4), 2.5, 0.25) + T.chord_notes(T.chord("Am", 4), 6.5, 0.25), bars=16, unit_bars=2)
pad.chords("breakdown", ["Am", "A#", "Am", "Am"], bars_each=4, octave=3)
pad.chords("intro", ["Am", "Am"], bars_each=8, octave=3)

# Filter movement is the melody of this style. The 303's own knobs stay fixed (automation of an instrument's knobs
# did not always render the same way twice); a resonant low-pass on the acid channel does the opening and closing.
MOVES = [("acid_in", 0, 16, 300, 1800), ("lift", 0, 8, 1800, 9000), ("main1", 0, 8, 2500, 6000), ("main1", 8, 8, 6000, 2000),
         ("main1", 16, 8, 2000, 10000), ("breakdown", 8, 8, 400, 7000), ("main2", 0, 12, 3000, 10000), ("main2", 12, 4, 10000, 2500),
         ("main2", 16, 8, 2500, 12000), ("outro", 0, 8, 3000, 300)]
for name, start, bars, start_hz, end_hz in MOVES:
    song.sweep("acid", (name, start), bars, start_hz, end_hz, resonance=3.0, rest_hz=end_hz)

song.sidechain("kick", ["bass", "music"], depth_db=5)
song.sweep("drums", ("lift", 4), 4, 30, 600, kind="highpass", rest_hz=20)     # thin the drums before the drop
song.riser(("lift", 0), 8)
song.riser(("breakdown", 8), 8, level_db=2)
song.impact("main1")
song.impact("main2", level_db=1)
song.fade("music", ("outro", 8), 8, 0, -18, rest_db=-60)
song.tail_bars = 3
song.master()

if __name__ == "__main__":
    print(song.save(os.path.join(os.getcwd(), "rubber_line.mmp")))
