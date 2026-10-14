# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""First Light - uplifting trance, 138 BPM, A minor, 256 bars (7:25), instrumental.

Usage: python song.py
The project is written into the current folder, so run it from a work folder outside the skill.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from lmmskit import theory as T                      # noqa: E402
from lmmskit.compose import Song                     # noqa: E402
from lmmskit.project import Note                     # noqa: E402

song = Song("First Light", 138, "A minor", "uplifting_trance")
song.structure([("intro", 32), ("groove", 32), ("breakdown1", 16), ("build1", 16), ("drop1", 32), ("breakdown2", 32),
                ("build2", 16), ("climax", 48), ("outro", 32)])
PROG = ["Am", "F", "C", "G"]                                     # two bars each: i - VI - III - VII
for section in song.sections:
    song.chords(section.name, "Am F C G", bars_each=2, repeats=section.bars // 8)


def chords_for(bars: int) -> list[str]:
    return (PROG * (bars // 8 + 1))[:bars // 2]


# ---- parts -----------------------------------------------------------------------------------------
kick = song.add("kick", "trance_kick")
clap = song.add("clap", "909_clap")
ohat = song.add("open hat", "909_ohat")
chat = song.add("closed hat", "909_hat")
ride = song.add("ride", "808_ride", level_db=-2)
snare = song.add("snare roll", "909_snare", level_db=-1, sends={"reverb": 0.25})
shaker = song.add("shaker", "shaker", role="hat", level_db=-3)
crash = song.add("crash", "crash", sends={"reverb": 0.4})
bass = song.add("bass", "offbeat_bass")
sub = song.add("sub", "sub_bass", level_db=-2)
pluck = song.add("pluck", "trance_pluck")
pad = song.add("pad", "string_pad")
keys = song.add("keys", "epiano", sends={"reverb": 0.35})
bell = song.add("bell", "bell", level_db=-2, sends={"reverb": 0.4, "delay": 0.25})
lead = song.add("lead", "supersaw_lead")
lead_high = song.add("lead high", "supersaw_high", level_db=-5)

# ---- drums -----------------------------------------------------------------------------------------
FOUR = "x---x---x---x---"
for name, start, bars in (("intro", 0, 32), ("groove", 0, 32), ("build1", 0, 14), ("drop1", 0, 32), ("climax", 0, 48), ("outro", 0, 32)):
    kick.hits((name, start), FOUR, bars=bars)
kick.hits(("build2", 8), "x-x-x-x-x-x-x-x-", bars=6)              # doubled kick drives the last build
for name, start, bars in (("intro", 16, 16), ("groove", 0, 32), ("drop1", 0, 32), ("climax", 0, 48), ("outro", 0, 16)):
    clap.hits((name, start), "----x-------x---", bars=bars)
for name, start, bars in (("intro", 8, 24), ("groove", 0, 32), ("drop1", 0, 32), ("climax", 0, 48), ("outro", 0, 24)):
    ohat.hits((name, start), "--x---x---x---x-", bars=bars)
for name, start, bars in (("intro", 0, 32), ("groove", 0, 32), ("build1", 0, 8), ("drop1", 0, 32), ("climax", 0, 48), ("outro", 0, 32)):
    chat.hits((name, start), "xoxoxoxoxoxoxoXo", bars=bars, vol=80)
for name, start, bars in (("groove", 16, 16), ("drop1", 16, 16), ("climax", 0, 48)):
    shaker.hits((name, start), "o-xoo-xoo-xoo-xo", bars=bars)
ride.hits(("climax", 16), "x-x-x-x-x-x-x-x-", bars=32, vol=80)
snare.roll(("build1", 8), 8)
snare.roll("build2", 16, divisions=(1.0, 0.5, 0.25, 0.125))
for name in ("groove", "drop1", "climax", "outro"):
    crash.hits(name, "x", bars=1 / 16)
crash.hits(("climax", 16), "x", bars=1 / 16)
crash.hits(("climax", 32), "x", bars=1 / 16)
# One-bar clap fills hand each 16-bar phrase over to the next.
for name, bar in (("groove", 15), ("groove", 31), ("drop1", 15), ("climax", 15), ("climax", 31)):
    snare.hits((name, bar), "--------x-x-xxxx", vol=90)

# ---- bass: three 16ths after every kick, on the chord root -------------------------------------------
ROLL = ". R R R . R R R . R R R . R R R"
for name, start, bars in (("intro", 8, 24), ("groove", 0, 32), ("drop1", 0, 32), ("climax", 0, 48), ("outro", 0, 16)):
    bass.riff((name, start), chords_for(bars), ROLL, bars_each=2, octave=1, gate=0.8)
    sub.riff((name, start), chords_for(bars), ". . R _ . . R _ . . R _ . . R _", bars_each=2, octave=1)

# ---- harmony ---------------------------------------------------------------------------------------
ARP_A = "R 5 8 5 3+ 5 8 5 R 5 8 5 3+ 5 8 3+"
ARP_B = "8 5 3+ 5 8 3+ 5+ 3+ 8 5 3+ 5 8 5 3+ 5"
for name, start, bars, pattern in (("intro", 16, 16, ARP_A), ("groove", 0, 32, ARP_A), ("breakdown1", 0, 16, ARP_A),
                                   ("build1", 0, 16, ARP_A), ("drop1", 0, 32, ARP_B), ("breakdown2", 16, 16, ARP_A),
                                   ("build2", 0, 16, ARP_A), ("climax", 0, 48, ARP_B), ("outro", 0, 16, ARP_A)):
    pluck.riff((name, start), chords_for(bars), pattern, bars_each=2, octave=3, gate=0.7)
for name, start, bars in (("groove", 16, 16), ("breakdown1", 0, 16), ("build1", 0, 16), ("drop1", 0, 32), ("breakdown2", 0, 32),
                          ("build2", 0, 16), ("climax", 0, 48), ("outro", 0, 16)):
    pad.chords((name, start), chords_for(bars), bars_each=2, octave=3)
keys.chords("breakdown2", chords_for(32), bars_each=2, octave=3, rhythm="x-----x---x-----", gate=1.0)

# ---- melody ----------------------------------------------------------------------------------------
THEME = ["E5 E5 D5 C5 C5 D5", "E5 A5 G5 E5 E5 D5", "F5 F5 E5 C5 C5 E5", "F5 A5 G5 F5 F5 E5",
         "G5 G5 E5 C5 C5 E5", "G5 C6 B5 G5 G5 E5", "D5 D5 B4 G4 G4 B4", "D5 G5 E5 D5 B4 D5"]
THEME_LIFT = THEME[:7] + ["D5 G5 B5 A5 G5 E5"]                   # second pass climbs into the repeat
STARTS, LENGTHS = [0, 0.75, 1.5, 2.0, 2.75, 3.5], [0.75, 0.75, 0.5, 0.75, 0.75, 0.5]


def theme_notes(bars: list[str], transpose: int = 0, gate: float = 0.92) -> list[Note]:
    notes = []
    for bar, text in enumerate(bars):
        for start, length, name in zip(STARTS, LENGTHS, text.split()):
            notes.append(Note(bar * 4 + start, length * gate, T.note(name) + transpose))
    return notes


SLOW = "E5 _ _ _ C5 _ _ _ A5 _ _ _ G5 _ E5 _ F5 _ _ _ C5 _ _ _ A5 _ _ _ G5 _ F5 _ G5 _ _ _ E5 _ _ _ C6 _ _ _ B5 _ G5 _ D5 _ _ _ B4 _ _ _ G5 _ _ _ E5 _ D5 _"
bell.seq("breakdown1", SLOW, bars=16, step=0.5, octave=5)
bell.seq("breakdown2", SLOW, bars=16, step=0.5, octave=5)
for start in (0, 16):
    lead.notes(("drop1", start), theme_notes(THEME + THEME_LIFT))
lead.notes(("breakdown2", 16), theme_notes(THEME + THEME_LIFT))
for start in (0, 16, 32):
    lead.notes(("climax", start), theme_notes(THEME + THEME_LIFT))
lead_high.notes(("drop1", 16), theme_notes(THEME + THEME_LIFT))
for start in (0, 16, 32):
    lead_high.notes(("climax", start), theme_notes(THEME + THEME_LIFT))

# ---- motion and transitions ------------------------------------------------------------------------
song.sidechain("kick", ["bass", "music"], depth_db=8)
song.sweep("bass", ("intro", 8), 24, 180, 6000)                   # bass opens up through the intro
song.sweep("pluck", ("intro", 16), 16, 400, 9000)
song.sweep("pad", ("groove", 16), 16, 500, 9000)
song.sweep("pluck", "build1", 16, 900, 12000)
song.sweep("lead", ("breakdown2", 16), 16, 700, 9000)             # the theme returns muffled and brightens
song.sweep("music", "outro", 16, 12000, 600, rest_hz=600)
song.fade("pad", ("groove", 16), 8, -12, 0)
song.fade("pluck", ("intro", 16), 8, -10, 0)
song.fade("pluck", ("outro", 8), 8, 0, -18, rest_db=-60)
song.riser(("breakdown1", 8), 8)
song.riser(("build1", 8), 8, level_db=2)
song.riser(("breakdown2", 24), 8)
song.riser("build2", 16, level_db=3)
song.impact("groove", level_db=-3)
song.impact("drop1")
song.impact("climax", level_db=1)
song.impact("outro", level_db=-3)
song.tail_bars = 4
song.master(low_shelf=(70.0, -1.5))          # the kick and the rolling bass already fill the bottom octave

if __name__ == "__main__":
    print(song.save(os.path.join(os.getcwd(), "first_light.mmp")))
