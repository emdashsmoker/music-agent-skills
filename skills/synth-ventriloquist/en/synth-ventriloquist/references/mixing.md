# Mixing and mastering by measurement

An agent cannot hear the mix, so every mix decision here rests on a measurement of rendered audio. The tools set levels and loudness from those measurements and then report what still looks wrong. The numbers are conventions taken from well-mixed electronic music. They locate problems. They do not define taste: when the user wants a buried vocal or a blown-out kick, keep it and note in the report that it was a choice.

## Contents

- One command
- What the balance step does
- What the loudness step does
- Reading the report
- Findings and fixes
- Mixing moves in the song script
- Loudness targets
- Checking part of a song quickly

## One command

```bash
python scripts/lmms_tool.py produce song.mmp -o out
```

`produce` runs, in order: balance the part levels, set the master loudness, render, run all checks, draw the review figures, render once more to prove the result is repeatable, and export ogg and mp3 (when ffmpeg is present), MIDI, DAWproject, JSON and a copy of the project. Everything lands in `out/`, with `report.txt` (readable) and `report.json` (all measurements). Options: `--genre` (default: from the plan file), `--lufs` to override the loudness target, `--no-balance` to keep the faders as they are, `--no-tone-fit` to keep the tone as mixed, `--no-repeat-check` to skip the second render.

`check` runs only the render, checks and figures. `balance` and `master` run those single steps.

Rough time on two CPU cores: a 4 minute song with 15 parts takes about 6 minutes, an 8 minute trance track with 25 parts about 15 minutes. Tell the user before starting a long one.

## What the balance step does

1. Renders every part alone ("stems") with the master effects off.
2. Measures each stem's loudness while it is playing (the 90th percentile of 400 ms loudness, so rests do not count).
3. Picks an anchor, normally the kick, and puts its peak at −9 dBFS before the master chain. That leaves the limiter room to work.
4. Compares the brightness of the densest 20 seconds with finished records and, when the mix is dull, puts one high shelf on the melodic parts, the effects and the vocals (`tone_fit` in the report, see below).
5. Sets every other part relative to the anchor: the role's level plus the part's own `level_db`, in loudness units. Percussive parts also get a peak ceiling against the kick's peak, and the lower of the two levels wins.
6. When there is a lead vocal, measures how far its consonant band (1.3 to 5 kHz) clears the backing and adds a presence lift of up to 6 dB to the vocal if it falls short (`vocal_presence` in the report).

Role loudness relative to the kick, in loudness units: snare −2, clap −3, bass −3, sub −5, lead −1, vocal −2, pluck −3, keys −4, pad −6, perc −8, fx −8, hat −8, cymbal −10, backing vocal −10. A genre profile replaces some of them with the levels usual in that style (`lmms_tool.py genres <name>` shows them under `levels`).

Peak ceilings relative to the kick's peak, in dB: snare −1, clap −3, perc −5, hat −7, cymbal −8. The ceiling is what sets claps, hats, rim shots and other short sounds. A loudness meter averages over 400 ms, so a 50 ms clap reads quiet. Set by loudness alone, the clap in a test song ended up peaking 6 dB above the kick, and the limiter crushed the whole mix on every backbeat. The `part_levels` table lists each part's peak next to its loudness.

On top of these sits the mix taste (`compose.MIX_TASTE`): clap +1.5, snare +1, lead vocal +1.5. It keeps the backbeat and the voice a little forward, between a tucked-in modern mix and an 80s-size snare. How big the snare, the clap and the vocal should be is taste, so ask when it matters and move in steps of 1 to 2 dB: per song with `level_db` on those parts, or for everything by editing `MIX_TASTE`. After each step read three numbers again: the limiter cut (bigger drum peaks cost loudness), the vocal margins (above +9 dB the voice sits on top of the track), and `drums_vs_rest`.

### Brightness and the tone fit

A mix built from filtered synth patches and quiet hats comes out dull: everything is audible, yet the result sounds covered. The measure for it is the energy above 2.8 kHz against the three octaves below it (354 Hz to 2.8 kHz), taken over the densest 20 seconds. Two published references frame it: pink noise reads 0 dB, and a spectrum falling 4.5 dB per octave, the usual analyser setting for judging a finished mix, reads −4.5 dB. Analyses of released dance tracks show a full drop approaching pink noise and quieter passages falling more steeply. The usual range is therefore −7.5 to −1.5 dB. A genre whose profile lowers the `air` band (doomer, lo-fi, dub techno and others) is allowed to be darker by that amount.

The tone fit aims at −6 dB, the careful side of the reference. When the densest passage is more than 0.5 dB below that, it adds a high shelf at 3 kHz, the same gain on every melodic, effect and vocal part, sized on the stems so that the mix reaches the aim and capped at 5 dB. The level pass that follows holds each part at its loudness, so parts get brighter without getting louder. Drums, bass and sub are left alone: their peaks decide how hard the limiter works, and a shelf over the whole master would raise the clap above the kick and cost 2 dB of loudness (measured on a test song).

What the cap leaves is a matter of sounds, and the `brightness` warning says so. In order of effect: open the low-pass filters of the lead and pad patches, raise the hats by 1 to 2 dB (`level_db`), add a bright layer (a shaker, a ride, a high octave of the lead), and for a dull voice add `("exciter", {})` to the vocal's `effects`. A mix can also be dull because the mids are overfull: check `band_owners` for the 250 to 500 Hz range and thin out what crowds it.

The step moves each part's mixer fader. To change the balance, change `level_db` in the song script and run `produce` again. Do not fight the balance with raw volume numbers.

## What the loudness step does

It renders the mix once without the limiter, then sets the limiter's drive to the lower of two values: the drive the loudness target needs, and the drive at which the limiter would cut more than 3 dB from the loudest moments (the 99.5th percentile of 10 ms peaks). The file is then lowered so that its true peak is at −1 dBTP.

Clean comes before loud. A limiter asked for 8 or 10 dB pumps the whole mix and smears the kick, and no listener thanks you for the extra loudness. When the cap stops the master short of the genre target, the report says how far (`limiter` finding). To get closer to the target, lower the peaks that stick out (kick, snare, clap levels) or thicken the arrangement. Raising the cap (`mix.master_to_loudness(..., max_reduction_db=5)`) is for users who ask for a hot master and accept the sound of it.

## Reading the report

`report.txt` lists findings, worst first. `ERROR` means the file is defective (clipping, phase cancellation, a lyric that does not fit its melody). `WARN` means a measurement is outside the usual range. `INFO` lines carry tables worth reading every time:

- `master_summary`: loudness, true peak, crest factor, stereo correlation, band levels, brightness of the densest passage.
- `tone_fit`: the high shelf the balance step added to a dull mix, and to how many parts.
- `limiter`: how many dB the master limiter cuts from the loudest moments, and the loudness reached against the genre target.
- `part_levels`: each part's loudness against its target, and its peak. No drum except the kick should peak above the kick.
- `section_energy`: loudness and brightness per section. Compare it with the intended energy curve: the chorus or drop should be the loudest, a breakdown clearly lower.
- `band_owners`: the two strongest parts in each frequency band. Two parts at nearly the same level in one band mask each other.
- `kick_presence`, `drums_vs_rest`, `vocal_body`, `vocal_consonants`: how the foreground elements sit against everything else. The two vocal findings measure only the moments a lead line is sung (the line times of the vocals file, else the frames where the voice is heard); they carry a table of per-section values next to the whole-song value and mark the section whose backing is densest (usually a chorus). Floor and ceiling are both judged on that section's value. A sparse verse lifts the whole-song value.

## Findings and fixes

| Finding | What was measured | Fixes, most effective first |
|---|---|---|
| `clipping` | Runs of full-scale samples | Lower the limiter input gain, find the part that overloads a bus |
| `true_peak` | True peak above −0.3 dBTP | Run `produce` again or `render --trim` |
| `loudness` | More than 1.5 LU from the target | Run `master` |
| `limiter` (warn) | The clean-limiting cap left the master 3 LU or more under the genre target | The mix has peaks far above its body: lower kick, snare and clap `level_db`, shorten the kick, add sustained parts. Or accept the quieter master |
| `over_limited` | Crest factor under 7 dB | Lower the target, or tame the loudest part: usually the kick or the sub |
| `phase` | Negative stereo correlation | Remove or reduce stereo widening. Check in mono |
| `wide_low_end` | Low band not mono | `fx.mono` on kick and sub, no chorus or widening on bass |
| `band_sub` too strong | Energy below 60 Hz dominates | Choose a shorter kick, lower the sub part, raise the bass or sub riff floor, high-pass non-bass parts |
| `band_sub` or `band_bass` too weak | Thin low end | Add a sub part, lower the bass octave, pick a deeper kick |
| `band_low_mid` too strong | Mud around 150 to 400 Hz | High-pass pads and keys higher, thin out chords in the low register, cut 250 Hz on the bus |
| `band_low_mid` or `band_mid` too weak | Hollow middle: often only kick, sub and hats are audible | Raise leads, plucks and pads (`level_db`), add a mid-range part, open filters |
| `band_high_mid` too strong | Harsh 2 to 6 kHz | Lower the lead's filter cutoff, cut around 3 kHz, lower claps and snares |
| `brightness` dull | Highs above 2.8 kHz in the densest 20 s are more than 7.5 dB under the mids (genre-adjusted), after the tone fit did what it may | Open the filters of lead and pad patches, raise hats 1 to 2 dB, add a bright layer, add an exciter to a dull vocal, thin out the 250 to 500 Hz range. Keep it when the user wants a dark mix |
| `brightness` bright | The same measure is above −1.5 dB | Lower hats and cymbals, close lead filters a little, cut around 8 kHz on the brightest part named in `band_owners` |
| `band_air` too strong or weak | Hiss or dullness above 10 kHz | Hat levels, a high shelf on the master (`song.master(high_shelf=(10000, 1.5))`) |
| `part_level` | A part is far from its target after balancing | Usually a part with almost no notes, or one whose fader hit its limit. Check the patch volume |
| `part_buried` | A part sits more than 20 LU under the loudest part | Raise its `level_db`, or remove it if it adds nothing |
| `kick_hiss` | The kick carries noise or distortion for its whole length, heard as hiss or fuzz on every beat | Choose a cleaner kick. Expected and fine for a deliberately distorted hardcore or industrial kick |
| `kick_presence` low | The kick is buried in 40 to 120 Hz | Deeper sidechain, shorter bass notes on the kick, high-pass the bass a little higher |
| `drums_vs_rest` outside −7 to +5 LU | Beat buried, or beat swamping the music | Shift the drum or music parts with `level_db` |
| `vocal_body` below 0 dB in the densest section | The voice is covered between 300 and 3400 Hz | Deepen the ducking first (`song.duck_for_vocals(4.0, presence_db=6.0)`; the defaults are 2.5 and 6.0). Then lower or rest the pads and leads under the vocal. Raising the vocal `level_db` is the last resort: it spends limiter headroom and invites the ceiling warning in the chorus |
| `vocal_consonants` below +2 dB in the densest section | The 1.3 to 5 kHz band of the voice does not clear the backing: words will be hard to follow | The warning says what covers the consonants. Music parts: raise `presence_db` in `song.duck_for_vocals` above the default 6.0 by the amount it names. Drums (hats, claps, snares): thin out the bright drums under the vocal or raise the vocal's `level_db` by the amount it names. Do not sidechain the vocal reverb to the kick: that chops consonant tails |
| vocal margin above +9 dB in the densest section | The vocal towers over the track. Judged on the value of the section whose backing is densest in the per-section table | Reduce the ducking depth or lower the vocal `level_db`. The whole-song value is for reference; only the densest section's value is judged |
| `leading_silence`, `tail_cut` | Silence at the start, or sound cut off at the end | Check the first section, raise `song.tail_bars` |
| `not_repeatable` | A second render of the finished project differs audibly from the first (60 dB under the mix or closer) | Run `lint` and replace what its `unrepeatable_*` findings name. `repeatable` (info) confirms identical renders, and `nearly_repeatable` (info) a residue too small to hear |

Fix causes in the arrangement and sound choice before reaching for EQ. Three parts playing the same register is an arrangement problem.

When the same three or more warnings survive two rounds of fixes, stop and show them to the user with the figures instead of continuing to tweak.

## Mixing moves in the song script

- Level intent: `level_db` on `song.add(...)`.
- Room under the vocal: in every song with a vocal part the music bus drops 2.5 dB and loses 6 dB in the consonant band while a lead line is sung, by default. `song.duck_for_vocals(depth_db, presence_db)` changes that and `song.duck_for_vocals(0)` turns it off. `presence_octaves` changes the width of the consonant-band dip to suit the production the user wants (default 1.5 octaves). A wide dip such as 3.0 also takes the music's highs down to 9 kHz under every line and darkens the backing, so it is not recommended and is used only when the user asks for that sound. A genre profile's `vocal_duck` pair replaces the default when present.
- Space: `sends={"reverb": 0.3, "delay": 0.2}`. Dry and close means small sends, far away means large sends plus a lower level.
- Stereo: `pan` on parts. Keep kick, sub, bass and lead vocal in the centre. Spread hats, plucks, doubles and harmonies.
- Tone: `fx.eq(part.chain, ...)`, or change the patch filter.
- Glue and punch: `fx.compressor(song.mixer.fx(song.bus("drums")), threshold_db=-16, ratio=3)`.
- Master: `song.master(highpass=25, glue=True, eq_peaks=[(250, -1.5, 1.0)], high_shelf=(10000, 1.0))`.

## Loudness targets

The genre profile carries a target between −16 LUFS (ambient) and −8 LUFS (gabber, hardstyle). Streaming services turn loud masters down to about −14 LUFS, so a higher target buys density while the playback volume stays the same. When the user asks for a "loud" master, raise the target by 1 or 2 and check the crest factor in the report.

## Checking part of a song quickly

```bash
python scripts/lmms_tool.py render song.mmp -o work/drop.wav --bars 33:8     # 8 bars from LMMS bar 33
```

Render an excerpt while working on one section, and run the full `produce` when the arrangement is settled. Rendered vocal lines are cached, so re-running a vocal song only sings the lines that changed.
