# Writing and arranging

## Order of work
- Go from large decisions to small ones
    + Genre, tempo, key
    + Song structure (section list and bar counts, energy per section)
    + Chord progressions
    + Rhythm (drums, bass)
    + Main melody and hook
    + Supporting parts (arpeggio, pad, counter-melody)
    + Transitions (fills, risers, filter movement)
- Check with `lint` at every step before moving on
    + The later a harmonic error is found, the more has to be fixed

## Song length
- One bar of 4/4 lasts `240 / bpm` seconds
    + 128 bpm : 1.875 s, 3 min 30 s is 112 bars
    + 138 bpm : 1.74 s, 7 min is 242 bars
    + 174 bpm : 1.38 s, 4 min is 174 bars
- Sections are normally 4, 8, 16 or 32 bars
- For the standard structure of a genre see the Arrangement entry of `genres <id>`

## Chord progressions
- Two or three progressions are enough for one song
    + One for the verse, one for the chorus, one for the bridge
    + Electronic music often keeps one progression and develops through timbre and density
- Basic progressions for minor-key genres
    + `i | VI | III | VII` : the most general
    + `VI | VII | i | i` : lifting, for choruses and climaxes
    + `i | iv | VI | V` : tension (V is the major triad of the harmonic minor)
    + `i | i | bVII | bVII` : small movement for one-chord genres
- A chorus that starts on a different chord from the verse stands apart clearly
- Written in Roman numerals, the progression survives a change of key

## Melody
- Put mostly chord tones on strong beats (first and third beat)
    + Passing and neighbour notes go on weak beats
- Do not hold the note a semitone above a chord tone
    + Typical cases: the major third over a minor triad, the fourth over a major chord
- Move mainly by step, with one or two leaps per phrase
    + After a leap, continue by step in the opposite direction
- End a phrase on the root, third or fifth of the chord
    + The root closes, the fifth leads on
- A hook repeats a motif of about two bars and changes only its ending
    + Moving the same motif onto a different chord is the easiest way to develop it
- Place the chorus melody a third to a fifth higher than the verse

## Bass
- Where the chord changes, play the root (for a slash chord, its bass note)
- Bass notes that fall on the kick are short or left out
    + The off-beat bass of four-on-the-floor genres and the rolling bass (`. 1 1 1`) follow this principle
- The normal range is E1 to C3
    + Lower than that is inaudible on most playback devices

## Registers
| Role | Recommended centre | Range allowed by lint |
|---|---|---|
| sub | E1 - E2 | C1 - D3 |
| bass | E1 - C3 | D1 - C4 |
| pad | C3 - C5 | E2 - E6 |
| chord | C3 - C5 | G2 - E6 |
| keys | C2 - C6 | A1 - D7 |
| arp, pluck | C3 - C6 | C3 - D7 |
| lead | C4 - C6 | E3 - D7 |
| vocal | Within one octave above the voice's speaking pitch | Check per engine |
- Below C3 do not stack intervals narrower than a fifth
- Three or more melodic parts crowded into one octave (G3-C5) mask each other
    + Spread them over octaves or drop one

## Designing energy in the arrangement
- Decide `energy` (0-1) for every section first
    + Starting points: intro 0.3, verse 0.5, build 0.7, chorus 0.9, drop 1.0, break 0.35
- Ways to raise energy
    + Add tracks (especially hi-hat, ride, clap)
    + Open a filter (`lpf` in `auto`)
    + Widen the register (add a part an octave up)
    + Subdivide the rhythm (from eighth-note to sixteenth-note hi-hats)
- Ways to lower energy
    + Removing kick and bass has the largest effect
    + Close a filter, leave only a pad with plenty of reverb
- Transition devices
    + End of a section : `rise` with riser, snare_roll, reverse_crash
    + Start of a section : `hit` with crash, impact
    + Leave the kick out for one bar or one beat right before a drop (`gap`)
    + Start of a break : downlifter
- When a section returns, change one thing
    + One of: an added part, added harmony, a different fill, an octave shift
- QA compares the measured loudness ranking of the sections with the `energy` ranking, so the gap between plan and result can be seen

## The end of the song
- The ending is part of the arrangement
    + Playing at full strength to the last bar and stopping sounds as if the music was cut off
- Choose one of three ways
    + Closing hit : `ending: hit`, one tonic chord and its decay (club genres, pop)
    + Fade-out : `ending: fade`, for a looping outro (lo-fi, doomer, synthwave)
    + Written by hand : an outro that sheds parts, and a last chord
- Even when the outro closes a filter or lowers the level, decide where the last point is
    + A reverb tail that ends closed is kept, so use it together with a last hit or a fade

## Groove
- `swing` : delays the second sixteenth of each pair; house 0.04-0.1, hip hop 0.15-0.3
- `humanize: {timing_ms: 5}` : leave it at 0 when machine precision is a trait of the genre
- Velocity variation is half of the groove
    + Mix `x` and `o` in the hi-hat pattern
    + Snare ghost notes are `o`

## Arranging a vocal song
- While the voice sings, a lead in the same register rests
    + The lead answers on the long note or the rest at the end of a vocal line
- Keep the verse open: drums, bass and perhaps a light arpeggio
- Add pad and stabs in the chorus, but do not stack sustained notes in the vocal register (around C4-A4)
- Use harmonies and doubles only in the chorus

## Notes on the lint items
| Code | Meaning | Response |
|---|---|---|
| `key.outside` | A note that belongs to neither the key nor the chord | Check whether the chromaticism is intended; a warning when the share exceeds 15% |
| `harmony.avoid_note` | A long note a semitone above a chord tone | Change the note, shorten it or move it to a weak beat |
| `harmony.strong_beats` | Fewer than half of the notes on strong beats are chord tones | Adjust strong-beat notes to chord tones |
| `bass.off_chord` | The bass at a chord change is not a chord tone | Change to the root or the fifth |
| `clash.semitone` | Two tracks overlap for long a semitone apart | Change the note on one side |
| `range.<role>` | A note outside the usual range of the role | Adjust `octave` |
| `mud.low_voicing` | A narrow interval below C3 | Raise the voicing |
| `mono.chord` | A chord given to a monophonic instrument | Change the instrument or write a single line |
| `melody.leap` | A leap wider than an octave (for vocals, wider than a major sixth) | Check that it is intended |
| `density.register` | Too many parts in one register | Spread over octaves or delete a part |
| `structure.flat` | All sections have about the same energy | Add contrast |
| `structure.odd_length` | A section with an odd number of bars | Check that it is intended |
| `structure.short` | The song is only sketch length | Extend the structure |
| `structure.no_ending` | Playing continues to the last bar and nothing ends the song | `ending: hit` or `ending: fade`, or write a closing section |
| `chords.missing` | No chords defined | Give `chords` to get the harmony checks |
| `vocal.overlap` | Lyric lines overlap each other | Adjust line length or start position |
| `lyrics.*` | Lyric matters | See `vocals.md` |
- Errors (ERROR) must be fixed before rendering
- Warnings (WARN) are judged one by one
    + Keep them when they are intended dissonance or genre convention
    + Leaving the reasoning in the song file's `notes` saves going through the same question next time
- Information (INFO) is for reference
