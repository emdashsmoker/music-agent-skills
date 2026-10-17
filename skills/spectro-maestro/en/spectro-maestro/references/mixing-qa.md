# Mixing and review

## Structure of the mix
- Signal flow
    + Track : instrument render, insert effects, filters, sidechain, automatic alignment to a target level, pan
    + Buses : drums, bass, music, fx, vocals
    + Returns : reverb, delay (for instruments), vox_reverb, vox_delay (for vocals)
    + Master : 22 Hz high-pass, mono below 110 Hz, EQ, glue compressor, soft clip, limiter
- Level is set as a target level per role
    + The mixer measures the actual loudness of each track and moves it to the target of its role
    + A patch that is loud or quiet by nature still lands in the same place
- Priority of the adjustment knobs
    + First : the track's `mix.gain_db` (a few dB up or down from the role default)
    + Second : the section's `vel` (velocity in one section only)
    + Third : the track's `reverb`, `delay`, `duck`, `hpf`, `lpf`
    + Fourth : insert EQ
    + Master EQ is used last, after the bus balance is right

## Defaults per role
| Role | Level (dB) | Bus | Reverb | Delay | Sidechain (dB) |
|---|---|---|---|---|---|
| kick | -4 | drums | 0 | 0 | 0 |
| snare | -5 | drums | 0.10 | 0 | 0 |
| hat | -14 | drums | 0.04 | 0 | 0 |
| perc | -12.5 | drums | 0.10 | 0 | 0 |
| bass | -3 | bass | 0 | 0 | -7 |
| sub | -4.5 | bass | 0 | 0 | -9 |
| lead | -2 | music | 0.22 | 0.16 | -2.5 |
| pluck | -3.5 | music | 0.22 | 0.20 | -3 |
| arp | -5.5 | music | 0.18 | 0.22 | -3 |
| pad | -7 | music | 0.28 | 0 | -5 |
| chord | -3.5 | music | 0.18 | 0.08 | -4 |
| keys | -3.5 | music | 0.16 | 0.05 | -2 |
| fx | -8 | fx | 0.25 | 0 | 0 |
| vocal | 0 | vocals | 0.16 | 0.08 | 0 |
| backing | -8 | vocals | 0.24 | 0.06 | 0 |
- The genre profile overrides this table
    + It applies automatically when the song file names a `genre`
    + The profile is the `profile` entry of `assets/genres/<id>.yaml`
- The sidechain lowers a track briefly whenever the kick sounds
    + It does nothing in genres or sections without a kick
    + Deeper settings turn it into the audible pumping of some genres (trance, electro house)

## Master settings
| Key | Default | Meaning |
|---|---|---|
| `lufs` | -10 | Target integrated loudness |
| `ceiling` | -1 | True peak ceiling (dBTP) |
| `glue` | true | Light compressor that binds the buses |
| `clip` | true | Soft clip that shaves only the highest momentary peaks |
| `eq` | none | Master EQ bands |
| `vocal_carve` | -2.5 | How much of the music bus's 1.3-5 kHz is taken out while the vocal sounds (dB) |
| `mono_below` | 110 | Everything below this frequency is summed to mono |
| `sidechain_release` | 0.5 | Sidechain recovery time (beats) |
| `fade_out` | 0 | Fade at the end of the song (beats) |
- Starting points for target loudness by genre
    + Quiet and dynamic genres (ambient, lo-fi, doomer) : -16 to -12
    + Pop and the house family : -11 to -9
    + Hard club genres (hardstyle, gabber, dubstep) : -8 to -6
- The harder the limiter works, the more the kick is squashed and pumping appears
    + If `limiter_p95_db` exceeds 5, lower the target loudness or reduce the loudest bus

## Review procedure
- When `render` finishes, check three things in turn
    + Step 1 : numbers and findings (`== metrics ==`, `== findings ==`)
    + Step 2 : the section table (`== sections ==`)
    + Step 3 : open the six pictures yourself
- Looking at the pictures is a formal step that cannot be skipped
    + Numbers test only fixed items
    + Pictures reveal faults no rule covers (holes, stripes, a one-sided image, unexpected empty stretches)
- Even with zero findings, trace the cause when a picture shows something odd
    + Extra pictures : `plot --spectrogram <audio> --start 60 --end 90`, `plot --pianoroll <section>`, `plot --chain <track>`
    + A track alone : `render --only <track> --sections <section>`
- After a fix, check again with the same numbers and pictures
    + Compare to see that the fixed item did not make another one worse

## What the numbers mean
| Item | Normal range | Meaning when outside it |
|---|---|---|
| `lufs` | target ±0.5 | The master did not reach the target |
| `true_peak_db` | -0.3 or lower | Risk of clipping after conversion |
| `crest_db` | 6 - 16 | Low: over-compressed. High: one sound sticks out or the arrangement is thin |
| `limiter_p95_db` | 5 or lower | The limiter is overworked |
| `slope_db_per_octave` | -4.5 - -0.7 | Low: dark with too much low end. High: thin and sharp |
| `low_share_db` | -9 - -1.5 | Share of the energy below 120 Hz |
| `high_share_db` | -30 - -11 | Share of the energy above 6 kHz |
| `correlation` | 0.2 or higher | Left-right phase problem |
| `low_correlation` | 0.8 or higher | The low end may vanish in mono |
| `mono_loss_db` | -3 or higher | Loss of level in mono playback |
| `drums_vs_rest_db` | -5 - 7 | Low: the beat is buried. High: the beat swallows the mix |
| `kick_vs_bass_db` | -3 or higher | The bass covers the kick where the kick hits |
| `vocal_body_db` | 0 - 12 | Low: the vocal is buried. High: the vocal sits apart from the backing |
| `vocal_consonant_db` | 2 - 14 | Low: the words are masked |
| `energy_rank_correlation` | 0.5 or higher | Section loudness does not follow the planned energy curve |
| `ending_drop_db` | 18 or lower | The song stops dead with the last bar still full |
| `silences_s` | empty list | Unexpected silence inside the song |
- Thresholds are starting points taken from usual ranges
    + The `qa` entry of a genre profile adjusts them to the genre (example : ambient relaxes the drum-related thresholds)
    + If it is an intended effect, leave the finding and record the reason in the report

## How to read the pictures
- `overview.png` : waveform, short-term loudness with planned energy, loudness per bus
    + Check that the waveform tapers at the end; a cliff means a song without an ending
    + A waveform filled like a brick is over-compressed
    + Check that the loudness curve rises and falls with the orange steps of planned energy
    + A bus that stays on top of the bus curves the whole time dominates the mix
    + Check whether the vocal curve is more than 6 dB above every other bus, or buried beneath them
- `spectrogram.png` : frequency content over time
    + Vertical stripes at regular spacing mean kick and hi-hat are alive
    + A band that stays empty has no part covering that register
    + A dark horizontal band that persists is a resonance or too much of one note
    + Filter movement appears as a triangle opening upward
    + Check that the boundaries of breaks and drops are clear vertical lines
- `spectrum.png` : third-octave average spectrum with a curve per bus; grey is the usual range
    + See in which bands the master curve leaves the grey area
    + Drums and bass curves overlapping at the same height at 60-120 Hz means kick and bass collide
    + In a vocal song, vocals must lie above music at 1-4 kHz for the words to be heard
- `arrangement.png` : where each track plays
    + Check that the intended tracks are on in every section
    + If every section has the same shape there is no development
    + Check that transition effects (fx_*) sit on section boundaries
- `pianoroll.png` : notes and chords
    + Orange notes are outside the key
    + Check whether parts overlap in the same register
    + Check that the bass follows the chord roots
- `stereo.png` : left-right correlation and width per band
    + Stretches where correlation drops below 0 lose sound in mono
    + The low end must stay in the centre

## Common problems and remedies
| Symptom | Where to look | Remedy |
|---|---|---|
| The beat is buried | `drums_vs_rest_db` low, the drums curve in overview | Lower `gain_db` of pads and chords, deepen the sidechain, raise the kick's `gain_db` |
| The beat swallows the mix | `drums_vs_rest_db` high, the waveform shows only kick shapes | Lower `gain_db` of kick and snare, add parts to the music bus |
| Kick and bass collide | `kick_vs_bass_db` low, 60-120 Hz in spectrum | Deepen the bass `duck`, delete bass notes on the kick, change the kick's `tune_hz` |
| Muddy low mids | A bump at 200-500 Hz in spectrum | `hpf` 250-350 on pads and chords, raise low voicings |
| Sharp highs | `slope` high, `high_share_db` high | Lower `gain_db` of hi-hat and ride, `lpf` on the lead |
| Dark mix | `slope` low | Open the filters of lead and pluck, add hi-hats; master EQ is the last resort |
| The vocal is buried | `vocal_body_db` low | Remove parts in the same register during vocal passages, raise the vocal's `gain_db` |
| The words are masked | `vocal_consonant_db` low | Reduce lead and hi-hat during vocal passages, deepen `vocal_carve`, boost the vocal at 3-4 kHz |
| Consonants sting (t, s, z) | Listen to each vocal line first; the numbers do not show it | `style: {consonant_ceiling: -6}`, then confirm the match with `vocal-check` |
| An ee word drops under its neighbours | Listen; `ROUGH` can miss it | Change the lyric or shorten its note; a level boost raises the hiss with it |
| The vocal sits apart from the backing | `vocal_body_db` high | Lower the vocal's `gain_db`, add vocal reverb |
| The drop is weak | `energy_rank_correlation` low | Empty the section before the drop and add parts to the drop |
| The limiter is overworked | `limiter_p95_db` high | Lower the target `lufs`, lower the loudest bus |
| Sound vanishes in mono | `correlation` low | Lower `width` of wide pads, weaken chorus effects |
| The song stops dead | `ending_drop_db` high, the overview waveform ends in a cliff | `ending: hit` or `ending: fade`, a level decay on the last chord |
- Change one thing at a time and render again
    + With several changes at once there is no telling which one worked
- Cut iteration time with partial renders
    + Render only the problem section with `--sections`, see how the numbers move, then render in full

## Resource use of long songs
- For songs longer than 6 minutes the bus buffers are kept as temporary files in `build/work/` of the output folder
    + They are deleted automatically when the render ends
    + For a 15 minute song: about 3 GB of memory and about 3 GB of temporary disk
- The track cache in `build/cache/` exists to speed up re-rendering
    + If disk is short it can be deleted; the result is the same
- Reference render times (2-core CPU)
    + 3-4 minute song : 2-3 minutes
    + 7 minute song : about 4 minutes
    + Vocal synthesis : 3-5 seconds per line for speech voices, about 10 seconds per line for singing voicebanks

## Reproducibility
- The same song file and the same `seed` produce the same audio
    + Drum noise, humanize and the small variations of the vocal are all derived from the seed
- Speech engines and singing models also run with fixed seeds
- Intermediate results are cached in `build/` of the output folder, so only changed tracks are recomputed
