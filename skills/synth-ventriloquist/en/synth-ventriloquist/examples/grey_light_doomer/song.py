# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Grey Light - doomer / post-punk, 124 BPM, E minor, 112 bars (3:37), low vocal.

Usage: python song.py <voice> <output name> [method]
   e.g. python song.py kokoro:am_michael grey_light_kokoro
The project is written into the current folder, so run it from a work folder outside the skill.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from lmmskit.compose import Song                     # noqa: E402
from lmmskit.vocal.singing import Style              # noqa: E402

# Every verse line is sung over Em | C and answered by two instrumental bars (G | D).
VERSE_LINES = [
    [("Grey light on the stairwell wall", "E3/1 E3/1 G3/0.5 G3/0.5 F#3/1 E3/1 E3/2 R/1"),
     ("Snow is falling slow", "G3/1 G3/1 A3/1 G3/1 E3/3 R/1"),
     ("Another tram goes by below", "E3/0.5 E3/0.5 E3/0.5 G3/0.5 G3/1 F#3/1 E3/1 E3/2 R/1"),
     ("There is nowhere left to go", "E3/0.5 E3/0.5 G3/1 A3/1 G3/1 G3/1 E3/2 R/1")],
    [("Kettle on the window glows", "E3/1 E3/1 G3/0.5 G3/0.5 F#3/1 E3/1 E3/2 R/1"),
     ("Voices through the wall", "G3/1 G3/1 A3/1 G3/1 E3/3 R/1"),
     ("The same old song comes on again", "E3/0.5 E3/0.5 E3/0.5 G3/0.5 G3/1 F#3/1 E3/1 E3/2 R/1"),
     ("And I remember it all", "E3/0.5 E3/0.5 G3/1 A3/1 G3/1 G3/1 E3/2 R/1")],
]
# Chorus: one sung sentence per two bars over C D | Em Em. Sung as fragments of one bar the same words came out unclear.
CHORUS = [("Night after night the same old sky", "G3/1 G3/0.5 G3/0.5 A3/2 A3/0.5 A3/1 F#3/0.5 A3/2"),
          ("Day after day I let it go", "B3/1 B3/0.5 B3/0.5 G3/2 G3/0.5 G3/1 F#3/0.5 E3/2")]
DEADPAN = Style(vibrato=0.3, scoop=0.3)              # flat, resigned delivery


def build(voice: str, output: str, method: str = "auto") -> str:
    song = Song("Grey Light", 124, "E minor", "doomer")
    song.structure([("intro", 8), ("riff1", 8), ("verse1", 16), ("chorus1", 8), ("riff2", 8), ("verse2", 16), ("chorus2", 8),
                    ("solo", 16), ("chorus3", 16), ("outro", 8)])
    loop, chorus = "Em C G D", "C D Em Em"
    chords = {}
    for section in song.sections:
        text = chorus if section.name.startswith("chorus") else loop
        chords[section.name] = song.chords(section.name, text, repeats=section.bars // 4)

    kick = song.add("kick", "linn_kick")
    snare = song.add("snare", "linn_snare", sends={"reverb": 0.3})
    hat = song.add("hat", "cr78_hat")
    ohat = song.add("open hat", "606_ohat", level_db=-2)
    tom = song.add("tom", "linn_tom_mid", sends={"reverb": 0.3})
    bass = song.add("bass", "pick_bass")
    guitar = song.add("guitar", "jangle_pluck", sends={"reverb": 0.35, "delay": 0.25})
    pad = song.add("pad", "cold_pad", sends={"reverb": 0.4})
    synth = song.add("synth", "square_lead", level_db=-3, sends={"reverb": 0.4, "delay": 0.2})

    for section in song.sections:
        name, bars = section.name, section.bars
        symbols = chords[name]
        kick.hits(name, "x-----x-x-------", bars=bars)
        if name != "intro":
            snare.hits(name, "----x-------x---", bars=bars)
        else:
            snare.hits((name, 4), "----x-------x---", bars=4)
        hat.hits(name, "x-x-x-x-x-x-x-x-" if name.startswith(("verse", "intro")) else "xoxoxoxoxoxoxoxo", bars=bars, vol=85)
        if name.startswith(("chorus", "solo", "riff")):
            ohat.hits(name, "--------------x-", bars=bars)
        tom.hits((name, bars - 1), "----------x-x-xx", pitch=60)                 # one-bar fill into the next section
        tom.hits((name, bars - 1), "------------x---", pitch=55)
        # Driving eighth-note bass: root with a lift to the fifth and octave at the end of the bar.
        bass.riff(name, symbols, "R _ R _ R _ R _ R _ R _ 5 _ 8 _" if not name.startswith("chorus") else "R _ R _ R _ 8 _ R _ R _ 5 _ R _",
                  octave=1, gate=0.85)
        if name != "intro":
            guitar.riff(name, symbols, "R _ 5 _ 8 _ 5 _ 3+ _ 5 _ 8 _ 5 _", octave=3, gate=0.95)
        if name.startswith(("chorus", "solo", "outro")):
            pad.chords(name, symbols, octave=3)
    # Synth melody: the riff sections and the solo carry the tune the voice leaves open.
    RIFF = "B4 _ _ _ A4 _ G4 _ | G4 _ _ _ E4 _ G4 _ | D5 _ _ _ B4 _ G4 _ | A4 _ _ _ F#4 _ A4 _"
    SOLO = ("B4 _ _ A4 G4 _ E4 _ | G4 _ _ E4 C5 _ B4 _ | D5 _ _ B4 G4 _ B4 _ | A4 _ F#4 _ D5 _ _ _ | "
            "E5 _ _ D5 B4 _ G4 _ | E5 _ _ C5 G4 _ C5 _ | D5 _ B4 _ G4 _ D5 _ | F#5 _ E5 _ D5 _ A4 _")
    for name in ("riff1", "riff2", "outro"):
        synth.seq(name, RIFF, bars=8, step=0.5, octave=4, gate=0.9)
    synth.seq("solo", SOLO, bars=16, step=0.5, octave=4, gate=0.9)
    # Answers to the sung lines: the riff's second half in the gaps of each verse.
    for name in ("verse1", "verse2"):
        for start in (2, 6, 10, 14):
            synth.seq((name, start), "D5 _ _ _ B4 _ G4 _ | A4 _ _ _ F#4 _ A4 _", step=0.5, octave=4, gate=0.9, vol=70)

    vocal = song.vocal("lead vocal", voice, method=method, style=DEADPAN)
    for lines, section in zip(VERSE_LINES, ("verse1", "verse2")):
        for index, (text, melody) in enumerate(lines):
            vocal.line((section, index * 4), text, melody)
    for section, repeats in (("chorus1", 2), ("chorus2", 2), ("chorus3", 4)):
        for repeat in range(repeats):
            for index, (text, melody) in enumerate(CHORUS):
                vocal.line((section, repeat * 4 + index * 2), text, melody, kind="chorus")
    vocal.harmony("low vocal", steps=-2, only_kind="chorus", level_db=1)

    song.duck_for_vocals(1.5)
    song.sweep("guitar", "riff1", 4, 600, 8000)
    song.fade("music", ("outro", 4), 4, 0, -14, rest_db=-60)
    song.fade("bass", ("outro", 6), 2, 0, -12, rest_db=-60)
    song.tail_bars = 3
    song.master()
    return song.save(os.path.join(os.getcwd(), output + ".mmp"))


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "auto"))
