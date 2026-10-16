# Composing: writing a song as a script

A song is a short Python script that uses `lmmskit.compose.Song`. Running it writes an ordinary LMMS project (`.mmp`) plus three small files next to it: `<name>.plan.json` (key, sections, chords, part roles), and for vocal songs `<name>.vocals.json` and `<name>.lyrics.txt`. Keep the script: it is the source of the song, and editing it and running it again is how every later change is made.

## Contents

- Skeleton of a song script
- Positions and time
- Parts and roles
- Writing notes (five notations)
- Chords and harmony
- Movement: sidechain, sweeps, fades, risers, impacts
- Arrangement craft
- Vocal parts
- Humanizing and swing
- What the lint checks

## Skeleton of a song script

```python
import os, sys
sys.path.insert(0, "<skill folder>/scripts")
from lmmskit.compose import Song

song = Song("Night Drive", 128, "A minor", "house")          # title, bpm, key, genre profile
song.structure([("intro", 8), ("verse", 16), ("drop", 16), ("outro", 8)])
chords = song.chords("drop", "Am F C G", repeats=4)          # declares the harmony for lint, returns the symbols

kick = song.add("kick", "house_kick")
hat = song.add("hat", "909_hat")
bass = song.add("bass", "moog_bass")
pad = song.add("pad", "warm_pad")

kick.hits("drop", "x---x---x---x---", bars=16)
hat.hits("drop", "--x---x---x---x-", bars=16)
bass.riff("drop", chords, ". . R . . . R . . . R . . R . 8", octave=1)
pad.chords("drop", chords, octave=3)

song.sidechain("kick", ["bass", "music"], depth_db=6)
song.master()                                                # call once, last
print(song.save(os.path.join(os.getcwd(), "night_drive.mmp")))
```

`Song.save()` installs the drum one-shots the song uses into `samples/kit/` beside the project (making the kit on this machine first if it does not exist yet, see `setup.md`), renders any vocal parts, and writes the files. Section names must be unique (`drop1`, `drop2`).

## Positions and time

Every method that places something takes a position `at` in one of three forms: a section name (`"drop"`), a tuple `("drop", 4)` meaning four bars into that section, or an absolute bar number counted from 0. Reports and LMMS itself count bars from 1, so "bar 33" in a report is bar 32 here. Note lengths and steps are in beats (a quarter note is 1, a 16th is 0.25).

## Parts and roles

`song.add(name, patch, role=None, level_db=0.0, pan=0.0, sends=None, highpass=None, strip=True)` creates one LMMS instrument track with its own mixer channel.

- `patch` is a name from the sound library (`lmms_tool.py sounds` lists them by role) or a patch dictionary (see `sounds-effects.md`).
- `role` defaults to the patch's role. The role decides the bus (drums, bass, music, vocals), the standard channel treatment (high-pass, mono for kick and sub), the default reverb and delay sends, and the level the automatic balance aims for. Roles: kick, snare, clap, hat, cymbal, perc, sub, bass, lead, pluck, pad, keys, fx, vocal, vocal_bg.
- `level_db` is an offset from the role's usual level. Use it for intent ("this pad should sit further back": `level_db=-3`). Do not set absolute volumes by hand; the balance step measures and sets them.
- `sends` replaces the role's default sends, for example `{"reverb": 0.4, "delay": 0.2}`.

The role is a mix decision, so assign it by function. An arpeggio that carries the hook can be `role="lead"`. A second bass line that plays high is better as `lead` or `pluck` than as `bass`.

## Writing notes (five notations)

| Method | Use | Example |
|---|---|---|
| `part.hits(at, grid, bars, pitch=None, step=0.25, vol=100, swing=0.0)` | drums | `"x---x---x---x---"`: `x` hit, `X` accent, `o` ghost, `-` rest. The grid repeats to fill `bars`. |
| `part.seq(at, text, bars=None, step=0.25, octave=3, gate=1.0, vol=100)` | melodies and bass lines by note name | `"A2 . . C3 _ _ . E3"`: name plays, `.` rests, `_` holds, `[A2 C3 E3]` is a chord, bar lines are optional. |
| `part.riff(at, symbols, pattern, bars_each=1.0, step=0.25, octave=2, gate=1.0)` | one pattern that follows the chords | `"R . R 5 8 _ 5 ."`: `R` root, `3`, `5`, `7`, `8` (octave), `+`/`-` suffix shifts an octave, `!` accent, `?` ghost. |
| `part.chords(at, symbols, bars_each=1.0, octave=3, rhythm=None, gate=0.95)` | pads, stabs, keys | `rhythm=None` holds each chord. `rhythm="x--x--x---x--x--"` plays it as stabs. Voicings are led smoothly from chord to chord. |
| `part.notes(at, [Note(start, length, pitch, vol)])` | anything else | `Note` comes from `lmmskit.project`. Starts are beats from the clip start. `theory.note("E5")` gives the pitch number. |

Also: `part.roll(at, bars)` writes a build-up roll that gets denser and louder, and `part.loop(at, notes, bars, unit_bars)` tiles a phrase.

Bass and sub riffs never go below E1 (41 Hz): a chord whose root would fall lower is played an octave up, because lower fundamentals vanish on most speakers. Pass `floor=` to change that on purpose.

Drum one-shots are held for the full length of the sample automatically.

## Chords and harmony

- `song.chords(at, "Am F C G", bars_each=1.0, repeats=1)` declares what the harmony is. The lint uses it to check bass notes and long melody notes. It returns one symbol per chord for the whole stretch (the progression times `repeats`), which is what `riff` and `chords` on a part expect.
- Roman numerals work with a key: `theory.progression("i VI III VII", "A minor")` gives `["Am", "F", "C", "G"]`.
- Chord symbols: major, `m`, `7`, `maj7`, `m7`, `dim`, `aug`, `sus2`, `sus4`, `add9`, `m9`, `9`, slash bass (`C/E`).
- Modes are accepted as keys: `"A phrygian"`, `"D dorian"`, `"E harmonic minor"`.

Write the melody against the chords: long notes and notes on strong beats should be chord tones, and passing notes belong on weak beats. The lint reports the exceptions with bar numbers.

## Movement: sidechain, sweeps, fades, risers, impacts

- `song.sidechain(source="kick", targets=["bass", "music"], depth_db=6.0, hold_beats=0.05, release_beats=0.4)` ducks the targets (bus or part names) on every hit of the source. It is written as volume automation derived from the source's notes, which makes every render identical. `song.pump(at, grid, bars)` adds ducking where the kick is silent, so a breakdown pad keeps breathing.
- `song.sweep(target, at, bars, start_hz, end_hz, kind="lowpass", resonance=0.9, rest_hz=None)` automates a filter on a part or bus. Opening a low-pass through a build-up and closing it into an outro are the two standard uses.
- `song.fade(target, at, bars, start_db, end_db, rest_db=0.0)` ramps the level of a part or bus and then jumps to `rest_db`. For a fade-out at the end, pass `rest_db=-60`.
- `song.riser(at, bars, level_db=0.0)` puts a filtered-noise riser that ends at `at + bars`. `song.impact(at, level_db=0.0)` puts a crash and a sub drop on a downbeat. All risers share one track and all impacts share two.
- `song.automate(param, [(bar, value), ...])` automates a parameter: an effect control (`fx.control(effect, "name")`), track volume or pan, or the track filter. Automating an instrument's own knobs is possible but does not render the same way every time (`sounds-effects.md` lists the targets).
- `song.tail_bars` (default 2) is the room left after the last bar for reverb and delay tails.

## Arrangement craft

These habits separate a finished track from a loop. They are defaults to reason from, and the user's taste overrides any of them.

- Think in 8 and 16 bar phrases. Something should change at every phrase boundary: a part enters or leaves, a filter opens, a fill plays.
- One or two parts own the foreground at any moment. The others support. When the vocal sings, the lead rests or answers in the gaps.
- Energy has a shape. The loudest and densest section comes late (final chorus, climax). A breakdown removes the kick and bass so their return has weight.
- Mark transitions: a fill or roll in the last bar, a riser into the new section, an impact on its first beat, and a short silence just before a drop when the genre likes drama.
- Give the low end one owner per moment. Kick and bass share it through sidechain or through rhythm (bass notes between the kicks).
- Repetition needs variation every four or eight bars: an extra ghost note, an octave jump, an open hat, a changed last bar. The lint reports parts that repeat unchanged for long stretches.
- Intros and outros in club genres are drum-led and 16 to 32 bars long so that DJs can mix them. Songs for listening can start with the hook in 4 to 8 bars.

## Vocal parts

```python
vocal = song.vocal("lead vocal", "kokoro:af_heart")           # or piper:<voice>, diffsinger:<folder>[#colour]
vocal.line(("verse", 0), "Empty roads below a paper sky", "E4/0.5 E4/0.5 G4/0.5 G4/0.5 A4/2 A4/0.5 G4/0.5 F4/0.5 E4/2")
vocal.harmony("harmony vocal", steps=2, only_kind="chorus", pan=20)
vocal.double("double vocal", only_kind="chorus", pan=-20)
song.duck_for_vocals(4.0, presence_db=6.0)     # optional: a song with vocals is ducked at 2.5 and 6.0 without this call
```

The melody has one token per sung syllable. Everything about voices, the notation, lyric writing and the checks is in `vocals.md`. Read it before writing any lyric.

## Humanizing and swing

`hits(..., swing=0.33)` delays every second 16th by a third of a step. `theory.humanize(notes, seed, timing=0.01, volume=6)` adds small seeded offsets. Always pass a fixed seed: the same script must produce the same song.

## What the lint checks

`python scripts/lmms_tool.py lint song.mmp` reads the notes and the plan file and reports findings with bar numbers. Treat `ERROR` and `WARN` like compiler messages: fix the script and run again, or decide the finding is intended and say so in the report to the user.

| Finding | Meaning | Usual fix |
|---|---|---|
| `out_of_scale`, `key_mismatch` | Notes outside the declared key, or another key fits better | Correct the notes, or declare the real key or mode |
| `bass_off_chord` | The bass does not land on a chord tone when the chord changes | Start the bar on the root (or the slash bass) |
| `avoid_note` | A long note on a strong beat sits a semitone above a chord tone | Move it to a chord tone or shorten it into a passing note |
| `semitone_clash` | Two parts hold notes a semitone (or minor ninth) apart | Change one of the two notes. Harmony vocals are kept clear of the chords automatically |
| `low_mud` | Close intervals below about C3 | Play single notes or octaves down there and move chords up |
| `bass_too_low`, `bass_too_high`, `bass_polyphony`, `range` | Notes outside the useful range of the role | Shift the octave |
| `silent_bars`, `empty_tracks` | Bars where nothing plays, tracks with no notes | Usually a mistake in a position. A deliberate pause before a drop is fine |
| `monotony` | A part repeats unchanged for a long stretch | Add variation every 4 or 8 bars, or automate a filter |
| `unrepeatable_automation`, `unrepeatable_peak_controller`, `unrepeatable_drumsynth`, and on systems without one-core rendering `unrepeatable_kicker_noise` | Something LMMS renders differently on each run | Use the repeatable alternative named in the message (see `sounds-effects.md`) |
| `section_density` (info) | How many parts play in each section | Compare with the intended energy curve |
