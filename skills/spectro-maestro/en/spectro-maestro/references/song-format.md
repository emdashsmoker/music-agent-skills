# Song file syntax

## Role of the file
- One song is written as one YAML file
    + Every decision of composition (key, tempo, chords, patterns, structure, lyrics, mix settings) is recorded in it
    + `render` also saves a flattened `*.project.json`, so the same result can be reproduced at any time
- YAML booleans are only `true` and `false`
    + `on`, `off`, `yes`, `no` are read as strings, so they can be used as part names
- Errors are reported in one line with their location
    + Example message : `tracks.vox.parts.v1.lyrics[1]: bar line reached at beat 4.5`

## Top-level keys
| Key | Required | Meaning |
|---|---|---|
| `title`, `artist`, `notes` | optional | Metadata; record the intent of the plan in `notes` |
| `genre` | recommended | Genre id; that genre's mix profile and QA thresholds apply |
| `bpm` | required | Fixed tempo (tempo changes inside a song are not supported) |
| `key` | required | Written as `A minor`, `F# dorian` |
| `meter` | optional | Beats per bar, default 4 |
| `seed` | optional | Base of the random numbers; the same value gives the same result |
| `swing`, `swing_step` | optional | How far even-numbered steps are delayed (as a share of the step length); step length defaults to 0.25 beat |
| `humanize` | optional | Small random variation, written as `{timing_ms: 6, velocity: 0.04}` |
| `ending` | recommended | How the song ends, `hit` or `fade` (see below) |
| `chords` | recommended | Named chord progressions |
| `tracks` | required | Track definitions |
| `sections` | required | Song structure, played from top to bottom |
| `patches` | optional | Instruments defined for this song |
| `mix`, `master` | optional | Return effect settings and master settings |

- Available modes : major, minor, dorian, phrygian, lydian, mixolydian, locrian, harmonic_minor, melodic_minor, phrygian_dominant

## Chord progressions
- Bars are separated by `|`
    + `Am | F | C G | %` : two chords in a bar split it evenly, `%` repeats the previous bar
    + `Am:3 G:1` : give the number of beats directly
- Both absolute and Roman numeral notation are supported
    + Absolute : `Am7`, `F#m/C#`, `Csus4`, `Gadd9`
    + Roman numerals : `i | VI | III | VII`, lower case means a minor triad
    + A Roman numeral without an accidental follows the song's scale (`VI` in A minor is F)
    + A Roman numeral with an accidental is read against the major scale (`bVI` in A minor is also F)
- Written in Roman numerals, the whole song can be transposed by changing the single `key` line
- Supported chord types : maj, m, 5, dim, aug, sus2, sus4, 6, m6, 7, maj7, m7, mmaj7, dim7, m7b5, 7sus4, add9, madd9, 9, maj9, m9, 11, m11

## Tracks
```yaml
tracks:
  bass:
    inst: bass_fm          # instrument name, or a modified one such as {base: bass_fm, filter: {cutoff: 900}}
    role: bass             # mix role
    octave: 2              # optional, can be set again in a part
    mix: {gain_db: -2}     # optional
    parts:
      main: {grid: "1 . 1 . 1' . 1 ."}
```
- `role` decides level, bus, reverb amount and sidechain depth
    + Drums : kick, snare, hat, perc
    + Low end : bass, sub
    + Melody : lead, pluck, arp
    + Harmony : pad, chord, keys
    + Others : fx, vocal, backing
- Define several named patterns under `parts`, then choose which to play in each section
- Options common to all parts
    + `vel` : velocity multiplier for the whole part
    + `gate` : note length ratio, default 0.9
    + `octave`, `transpose` : move the register
    + `step` : step length in beats, default 0.25 (a sixteenth note)
    + `loop: false` : play once at the start of the section
    + `swing` : swing for this part

## Drum notation (hits)
- One character is one step
    + `x` normal, `X` strong, `o` soft, `.` rest
    + `r` two quick hits, `t` three quick hits
- Splitting bars with `|` makes the step count get checked
```yaml
kick:  {hits: "x...x...x...x..."}
snare: {hits: "....x.......x...|....x.......x.xx"}   # two-bar pattern with a fill at the end of the second bar
```
- A pattern repeats for the length of the section
    + To put a fill only in the last bar of an 8-bar section, write an 8-bar pattern
- The `note: E4` option moves the pitch of a drum
    + C4 is the original pitch; move up or down in semitones

## Chord-relative notation (grid)
- One token per step; a number is a degree of the current chord
    + `1 3 5 7` : root, third, fifth and seventh of the chord
    + `2 4 6` : scale notes above the chord root
    + `b3`, `b7`, `#4` : a degree with an accidental is read against the major scale on the chord root
    + `c` : the whole chord, voiced with smooth voice leading
- Modifiers
    + `'` one octave up, `,` one octave down
    + `!` accent, `?` ghost note
    + `-` hold the previous note, `.` rest
    + `~` slide into the next note (mono synths), `-~` hold and then slide
```yaml
bass: {grid: ". 1 1 1 . 1 1 1 . 1 1 1 . 1 1 1"}          # rolling bass that leaves the kick's slot empty
acid: {grid: "1 1' 1~ b3 1 . 1'! 1 5~ 5 1 1'! . b3 1 b7,!"}
pad:  {grid: "c - - - - - - - - - - - - - - -"}          # hold the chord for one bar
```
- When the chord changes, the same pattern follows the new chord
    + For the bass role, `1` follows the bass note of a slash chord
- For the bass role, leaving out `octave` puts the root at the lowest place at or above E1

## Melody notation (line)
- A list of tokens written as `pitch:beats`
    + Note names : `C4`, `F#3`, `Bb4` (only capital letters are read as note names)
    + Degrees : `5`, `b3`, `1'`, `7,` (against the song's scale; with an accidental, against the major scale; `'` raises an octave, `,` lowers one)
    + Rest : `r:1`
    + Chord : `[C4 E4 G4]:2`
    + When the beats are left out, the previous value is used
- `|` is a bar check line
    + A bar boundary that does not line up is reported as an error, so mistakes in counting beats are found at once
- `~` joins a note to the next (example : `E4:1~D4:1`)
    + In a vocal, the joined notes are sung as one syllable
- Put `!` after a note to accent it, or `?` to make it a ghost note
```yaml
lead: {line: "5:1.5 3:.5 5:1 1':1 | 1':1.5 7:.5 6:2", octave: 4}
```

## Lyric parts (lyrics)
```yaml
vox:
  role: vocal
  vocal: {engine: kokoro, voice: af_heart}
  layers:
    - {type: double, sections: [chorus]}
    - {type: harmony, steps: 2, sections: [chorus]}
  parts:
    verse:
      octave: 4
      lyrics:
        - {bar: 1, text: "Cold light upon the station wall", notes: "r:.5 E4:.5 E4:.5 D4:.5 E4:.5 D4:.5 C4:.5 D4:.5 | C4:3 r:1"}
        - {bar: 3, text: "I count the trains that never slow", notes: "r:.5 E4:.5 G4:.5 E4:.5 E4:.5 D4:.5 E4:.5 D4:.5 | D4:3 r:1"}
```
- One entry is one line of lyrics
    + `bar`, `beat` : where the line starts inside the section
    + `text` : the lyric
    + `notes` : melody notation, one note per syllable
    + `phonemes` : give the engine's phonetic symbols directly (optional)
- When the number of syllables and the number of notes differ, `lint` reports it with the syllable count of each word
- To sing one syllable on several notes, join the notes with `~`
- Vocal settings and lyric writing rules are in `vocals.md`

## Sections
```yaml
sections:
  - name: chorus1
    type: chorus            # intro verse prechorus build drop chorus break bridge outro
    bars: 16
    chords: chorus          # a progression name or a progression string
    energy: 0.9             # optional, planned energy from 0 to 1
    play: {kick: four, bass: oct, pad: hold, vox: chorus, piano: [theme, chords]}
    rise: {riser: 4, snare_roll: 2}     # effects leading to the end of the section; the number is bars
    hit: [impact, crash]                # effects on the first beat of the section
    gap: {kick: 4}                      # leave that track empty for the last N beats of the section
    auto: {pad: {lpf: [600, 9000]}, master: {volume: [0, -12]}}
    vel: {pad: 0.7}                     # velocity multiplier for this section only
    transpose: 2                        # transpose this section only, in semitones
```
- Only the tracks written in `play` sound in that section
    + Several parts of one track can be layered as a list
- `rise` kinds : riser, snare_roll, reverse_crash, noise_sweep
- `hit` kinds : impact, crash, downlifter, sub_drop
- `auto` moves in a straight line from the value at the section start to the value at its end
    + Parameters : `lpf` (Hz), `hpf` (Hz), `volume` (dB)
    + With `master` as the target it applies to the whole mix
    + After the span ends, the end value is held until that track's next note starts (a closed filter does not reopen on the reverb tail)
- `energy` is compared in QA with the measured loudness ranking of the sections

## How the song ends
- `ending: hit` : a two-bar closing is added automatically after the last section
    + The first beat of the tonic chord is struck once by kick, bass, pad and crash and decays over two bars
    + Only tracks the song already uses are involved
    + Suits songs whose last section ends on a chord other than the tonic
- `ending: fade` : the last four bars fade out
    + Suits a looping outro
- Setting the length : `ending: {type: fade, bars: 8}`
- Leave out `ending` when you write a closing section yourself
    + The last chord sounds natural when it decays with `auto: {master: {volume: [0, -36]}}`
- Playing at full level up to the last bar with no treatment makes the song stop dead
    + `structure.no_ending` in `lint` and `ending_drop_db` in QA report this case
- The reverb after the last bar dies away over `master.tail` seconds, and the file ends 0.4 seconds after the sound has gone

## Mix settings per track
| Key | Meaning |
|---|---|
| `gain_db` | Add to or subtract from the role's default level (the knob used most) |
| `level` | Replace the role's default level itself |
| `pan`, `width` | Left-right position (-1 to 1), stereo width (0 to 1) |
| `reverb`, `delay` | Amount sent to the returns (0 to 1) |
| `duck` | Sidechain depth keyed to the kick (dB, negative) |
| `hpf`, `lpf` | Track filters (Hz) |
| `mono` | Force to mono |
| `inserts` | Effect chain, for example `[{fx: dist, drive: 0.4}, {fx: chorus, mix: 0.4}]` |
| `mute` | Switch the track off |
| `dry` | Vocals only: skip the default vocal chain |

## Mix settings for the whole song
```yaml
mix:
  style: balanced             # the foreground placement chosen in the plan: forward, balanced (default), blended (Mix styles in mixing-qa.md)
  returns:
    reverb: {decay: 2.6, damp: 5000}
    delay: {time: 1/8d, feedback: 0.4}
    vox_reverb: {decay: 2.2}
  sidechain_source: kick      # optional, the track the sidechain follows
master:
  lufs: -10                   # target loudness
  ceiling: -1                 # true peak ceiling (dBTP)
  eq: [[highshelf, 9000, 1.5]] # band format: eq in sound.md
  vocal_carve: -2.5           # how much of the backing's 1.3-5 kHz is taken out when there is a vocal
  fade_out: 8                 # length of the fade at the end of the song (beats)
  tail: 3                     # room for the reverb at the end of the song (seconds)
```
- Time values are numbers in seconds or note values
    + `1/4`, `1/8`, `1/16` : note lengths
    + `1/8d` : dotted, `1/8t` : triplet

## Instruments defined for the song
```yaml
patches:
  my_bass: {base: bass_reese, filter: {cutoff: 500}, drive: 0.5}
tracks:
  bass: {inst: my_bass, role: bass, parts: {...}}
```
- The instrument list and patch parameters are in `sound.md`

## Partial renders
- `render --sections chorus1,verse2` : render only the named sections
- `render --only kick,bass` : render only the named tracks
- Checking timbre and balance on one section before a full render cuts iteration time a great deal
