# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Em Dash Smoker
"""Signal Fires - futurepop, 132 BPM, A minor, 104 bars (3:09), sung lead vocal, with two drum arrangements.

Usage: python song.py <voice> <output name> [beat] [harmony voice]
   e.g. python song.py kokoro:af_heart signal_fires_hard hard
beat: "trance" (soft four-on-the-floor kit, clap backbeat) or "hard" (the default: punchy kick, snare backbeat, rim and fills).
The project is written into the current folder, so run it from a work folder outside the skill.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from lmmskit import fx                               # noqa: E402
from lmmskit.compose import Song                     # noqa: E402

VERSE_A = "E4/0.5 E4/0.5 G4/0.5 G4/0.5 A4/2 A4/0.5 G4/0.5 F4/0.5 E4/2 R/0.5"       # over Am | F
VERSE_B = "G4/0.5 G4/0.5 E4/0.5 G4/0.5 C5/2 B4/0.5 A4/0.5 G4/0.5 D4/2 R/0.5"       # over C | G
VERSES = [["Empty roads below a paper sky", "Morning comes so slowly down my way",
           "Every song I knew has gone away", "Still I keep a glow for you today"],
          ["Voices on the line remember me", "Carried on the wind across the sea",
           "Show me you can see the same new day", "Tell me you will meet me on the way"]]
PRE = [("Hear my voice", "A4/0.5 A4/0.5 C5/2 R/1"), ("call again", "G4/0.5 G4/0.5 B4/2 R/1"),
       ("Over miles of open air", "A4/0.5 A4/0.5 C5/1 B4/0.5 A4/0.5 G4/1 B4/3 R/1")]
CHORUS = [("See the signal fires", "A4/1 A4/1 F4/1 A4/1 B4/3 R/1"), ("Burning all the way", "C5/1 C5/1 A4/1 G4/1 C5/3 R/1"),
          ("Far across the sea", "A4/1 A4/1 F4/1 A4/1 B4/3 R/1"), ("Shining back to you", "C5/1 C5/1 A4/1 G4/1 A4/3 R/1")]
BRIDGE = [("Hold on now", "F4/0.5 F4/0.5 A4/2 R/1"), ("hold on now", "E4/0.5 E4/0.5 A4/2 R/1"),
          ("Morning is on the way", "R/1.5 A4/0.5 A4/0.5 C5/0.5 A4/0.5 G4/0.5 B4/3 R/1")]


def build(voice: str, output: str, beat: str = "hard", harmony_voice: str | None = None) -> str:
    song = Song("Signal Fires", 132, "A minor", "futurepop")
    song.structure([("intro", 16), ("verse1", 8), ("pre1", 4), ("chorus1", 8), ("interlude", 8), ("verse2", 8), ("pre2", 4),
                    ("chorus2", 8), ("bridge", 8), ("chorus3", 16), ("outro", 16)])
    loop, pre, chorus, bridge = "Am F C G", "F G Am G", "F G Am C F G Am Am", "Dm Am F G"
    progressions = {"intro": loop, "verse1": loop, "pre1": pre, "chorus1": chorus, "interlude": loop, "verse2": loop, "pre2": pre,
                    "chorus2": chorus, "bridge": bridge, "chorus3": chorus, "outro": loop}
    chords = {}
    for section in song.sections:
        symbols = progressions[section.name].split()
        chords[section.name] = song.chords(section.name, progressions[section.name], repeats=section.bars // len(symbols))

    hard = beat == "hard"
    if hard:
        # Harder than a trance kit, short of industrial noise: a punchy 909 kick, a full snare on the backbeat with the
        # clap as its upper layer, a rim on the off-16ths, and the 909 snare kept for fills.
        kick = song.add("kick", "909_kick")
        snare = song.add("snare", "electro_snare")
        clap = song.add("clap", "909_clap", level_db=-3)
        fill = song.add("fill snare", "909_snare", level_db=-2)
        rim = song.add("rim", "808_rim")
    else:
        kick = song.add("kick", "trance_kick")
        clap = song.add("clap", "909_clap")
        fill = song.add("snare", "909_snare", level_db=-2)          # only plays the rolls into the choruses
    ohat = song.add("open hat", "909_ohat", level_db=1)
    chat = song.add("closed hat", "909_hat", level_db=1)
    crash = song.add("crash", "crash", sends={"reverb": 0.4})
    bass = song.add("bass", "ebm_bass")
    sub = song.add("sub", "sub_bass", level_db=-2)
    arp = song.add("arp", "trance_pluck", level_db=-2)
    pad = song.add("pad", "string_pad")
    lead = song.add("lead", "supersaw_lead", level_db=-2)
    stab = song.add("stab", "chord_stab", level_db=-3)

    FOUR_ON_FLOOR, BACKBEAT = "x---x---x---x---", "----x-------x---"
    kick_grid = FOUR_ON_FLOOR * 3 + "x---x---x---x-x-" if hard else FOUR_ON_FLOOR          # hard: a pickup kick closes every fourth bar
    hat_grid = "xoXoxoXoxoXoxoXo" if hard else "xoxoxoxoxoxoxoXo"                          # hard: accents on the off-8ths
    loud = ("intro", "chorus1", "interlude", "chorus2", "chorus3", "outro")
    for section in song.sections:
        name, bars = section.name, section.bars
        symbols = chords[name]
        sparse = name.startswith(("pre", "bridge"))
        first = 8 if name == "intro" else 0                       # the intro starts with pad and arp alone
        last = bars - 8 if name == "outro" else bars              # the outro ends on drums dropping out
        if not sparse:
            kick.hits((name, first), kick_grid, bars=last - first)
            if hard:
                snare.hits((name, first), BACKBEAT, bars=last - first)
            chat.hits((name, first), hat_grid, bars=last - first, vol=80)
            bass.riff((name, first), symbols[first:last], "R . R R 8 . R R R . R R 8 . R 8", octave=1, gate=0.75)
            sub.riff((name, first), symbols[first:last], "R _ _ _ . . R _ R _ _ _ . . R _", octave=1)
        else:
            kick.hits(name, "x-------x-------", bars=bars)
            bass.riff(name, symbols, "R _ _ _ _ _ _ _ R _ _ _ . . R _", octave=1)
            fill.roll((name, bars - 2), 2, divisions=(0.5, 0.25))
        if name in loud or (not hard and name.startswith("verse")):          # the trance kit carries its verses on the clap
            clap.hits((name, first), BACKBEAT, bars=last - first)
        if hard and name in loud:
            rim.hits((name, first), "-------x--x----x", bars=last - first, vol=85)
            if last == bars:                                      # a half-bar snare run into the next section
                fill.hits((name, bars - 1), "--------x-x-xxxx")
        if name in loud:
            ohat.hits((name, first), "--x---x---x---x-", bars=last - first)
            crash.hits((name, first), "x", bars=1 / 16)
            arp.riff(name, symbols, "R 5 8 5 3+ 5 8 5 R 5 8 5 3+ 8 5+ 8", octave=3, gate=0.7)
        else:
            arp.riff(name, symbols, "R . 5 . 8 . 5 . R . 5 . 3+ . 5 .", octave=3, gate=0.6)
        pad.chords(name, symbols, octave=3)
        if name.startswith("chorus"):
            stab.chords(name, symbols, octave=4, rhythm="x--x--x---x--x--", gate=0.6)
    # Lead hook: instrumental sections state it, the last chorus doubles the vocal with it.
    HOOK = "E5 _ C5 A4 E5 _ C5 A4 | F5 _ C5 A4 F5 _ C5 A4 | G5 _ E5 C5 G5 _ E5 C5 | G5 _ D5 B4 D5 _ G5 B4"
    lead.seq(("intro", 8), HOOK, bars=8, step=0.5, octave=5, gate=0.9)
    lead.seq("interlude", HOOK, bars=8, step=0.5, octave=5, gate=0.9)
    lead.seq("outro", HOOK, bars=8, step=0.5, octave=5, gate=0.9)
    lead.seq(("chorus3", 8), "A4 _ _ _ F4 _ A4 _ | B4 _ _ _ _ _ D5 _ | C5 _ _ _ A4 _ G4 _ | C5 _ _ _ E5 _ _ _ | "
             "A4 _ _ _ F4 _ A4 _ | B4 _ _ _ _ _ D5 _ | C5 _ C5 _ A4 _ G4 _ | A4 _ _ _ _ _ _ _", step=0.5, octave=5, gate=0.95)

    # Both voices pile up around 450 Hz and leave the chorus dull against the brightness reference: thin that range a little.
    vocal = song.vocal("lead vocal", voice, effects=[("eq", {"peaks": [(450.0, -3.0, 1.5)]})])
    for verse, section in zip(VERSES, ("verse1", "verse2")):
        for index, text in enumerate(verse):
            vocal.line((section, index * 2), text, VERSE_A if index % 2 == 0 else VERSE_B)
    for section in ("pre1", "pre2"):
        vocal.line((section, 0), *PRE[0])
        vocal.line((section, 1), *PRE[1])
        vocal.line((section, 2), *PRE[2])
    for section, repeats in (("chorus1", 1), ("chorus2", 1), ("chorus3", 2)):
        for repeat in range(repeats):
            for index, (text, melody) in enumerate(CHORUS):
                vocal.line((section, repeat * 8 + index * 2), text, melody, kind="chorus")
    for half in (0, 4):
        vocal.line(("bridge", half), *BRIDGE[0])
        vocal.line(("bridge", half + 1), *BRIDGE[1])
        vocal.line(("bridge", half + 2), *BRIDGE[2])
    vocal.harmony("harmony vocal", steps=2, only_kind="chorus", pan=20, voice=harmony_voice)
    vocal.double("double vocal", only_kind="chorus", pan=-20)

    if hard:
        fx.saturator(bass.chain, drive=2.5, character=0.4)                            # a little grit on the sequenced bass
    song.sidechain("kick", ["bass", "music"], depth_db=6)
    song.duck_for_vocals(1.5, presence_db=3.0)
    song.sweep("arp", "intro", 8, 500, 9000)
    song.sweep("pad", "intro", 8, 400, 8000)
    song.sweep("music", ("outro", 8), 8, 12000, 500, rest_hz=500)
    for name in ("pre1", "pre2"):
        song.riser((name, 2), 2, level_db=-2)
    song.riser(("bridge", 4), 4)
    for name in ("chorus1", "chorus2", "chorus3"):
        song.impact(name, level_db=-2)
    song.tail_bars = 3
    song.master()
    return song.save(os.path.join(os.getcwd(), output + ".mmp"))


if __name__ == "__main__":
    print(build(*sys.argv[1:5]))
