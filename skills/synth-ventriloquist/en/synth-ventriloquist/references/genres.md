# Genre recipes

Each recipe gives the idiom of a style in the notation of this toolkit: tempo, drum grids (16 steps per bar), bass, harmony, sounds, form. `python scripts/lmms_tool.py genres <name>` prints the matching profile (tempo range and default, loudness target, sidechain depth, swing, role levels, suggested kit and form). Profiles exist for 46 styles, and `genres` without a name lists them.

A recipe is where a track starts. What makes a track good is the one idea that departs from the recipe, so follow the user's references and wishes first and this page second.

For a style without a profile (the family of electronic genres is far larger than this list), work from knowledge of the style: take the nearest profile as a base, state the tempo, drum pattern, bass style and form you intend in the plan, and let the user correct it.

## Contents

- Grid legend
- House family
- Techno family
- Trance family (uplifting trance in detail)
- Psytrance family
- Hard dance: gabber, hardstyle, happy hardcore
- Breakbeat family: breakbeat, big beat, drum and bass, jungle, UK garage
- Bass music: dubstep, trap, hip hop
- Body and industrial: EBM, industrial, futurepop
- Synth styles: synthpop, synthwave, darksynth, doomer
- Listening styles: IDM, ambient, downtempo, trip hop, lo-fi, vaporwave, chiptune
- Song forms

## Grid legend

`x` hit, `X` accent, `o` ghost (quiet), `-` rest. One character is a 16th note, and a bar has 16. Bass patterns use chord degrees: `R` root, `5` fifth, `8` octave, `.` rest, `_` hold.

## House family

House, deep house, tech house, electro house, future house, progressive house, disco. 118 to 130 BPM.

```
kick   x---x---x---x---        clap   ----x-------x---
ohat   --x---x---x---x-        chat   x-x-x-x-x-x-x-x-   (or 16ths with ghosts: xoxoxoxoxoxoxoxo)
```

- Swing of 0.1 to 0.15 on hats and percussion gives the shuffle. Deep house swings more and plays softer.
- Bass: short notes between the kicks (`. . R . . . R . . R . . . . R .`), or a rolling octave line. `moog_bass`, `fm_bass`.
- Harmony: minor 7th and 9th chords (`Am7 Dm7 Gmaj7 Cmaj7`), played as off-beat stabs (`chord_stab`, `epiano`, `organ`) with the rhythm `--x--x----x--x--`.
- Sidechain 4 to 8 dB on bass and music. Electro and future house pump harder and use a loud detuned saw lead in the drop.
- Tech house: fewer chords, more percussion (rim, conga, shaker) and a short repeating bass hook.
- Disco: live-feeling kit (`kick_acoustic`, `clap`), octave bass (`R . 8 . R . 8 .`), string pad stabs.
- Form: 16 bar drum intro, build, drop, break, build, drop, 16 bar outro.

## Techno family

Techno, minimal, hard techno, dub techno, acid house. 122 to 150 BPM.

```
kick   x---x---x---x---        clap or rim   ----x-------x---
chat   --x---x---x---x-        ride (peak)   x-x-x-x-x-x-x-x-
```

- Little harmony: one note or one chord for the whole track. Interest comes from timbre changing slowly: filter sweeps over 16 to 32 bars, parts entering and leaving one at a time.
- Bass is often just the tail of the kick plus a low rumble or a one-note off-beat line. Keep the low end mono.
- Hard techno: `industrial_kick` with saturation, phrygian riffs, 16th hats.
- Dub techno: minor 7th chord stabs through long delay and reverb sends (`sends={"delay": 0.6, "reverb": 0.5}`), soft kick, slow filter movement.
- Acid house: a 16 step `acid_bass` pattern with slides (overlapping notes) and accents (louder notes). The filter opening and closing across the track is the melody of the style: sweep a resonant low-pass on the acid part's channel section by section (`song.sweep("acid", at, bars, 300, 9000, resonance=3.0, rest_hz=9000)`), with the LB302's own cutoff, resonance and envelope knobs set once in the patch. Automating those knobs directly sounds closest to the hardware, but such a project does not always render the same file twice, so use it only when the user prefers that sound over exact repeatability. 909 or 606 kit, swing about 0.1. The acid line is the lead, so give it `level_db=+2` or the role `lead`.

## Trance family (uplifting trance in detail)

Trance, progressive trance, hard trance, goa, uplifting. 130 to 145 BPM.

```
kick   x---x---x---x---        clap   ----x-------x---
ohat   --x---x---x---x-        chat   xoxoxoxoxoxoxoXo
bass   . R R R . R R R . R R R . R R R     (rolling 16ths after each kick, offbeat_bass)
```

Uplifting trance, 136 to 142 BPM, 7 to 15 minutes (extend the groove, breakdown and climax sections in 16 or 32 bar steps for the longer forms):

- Harmony: a four chord minor loop, two bars per chord: `i VI III VII` (Am F C G), `VI VII i i`, `i VII VI VII`. The emotional lift comes from the major chords VI and III.
- Layers in the drop: kick, rolling bass, sub, 16th pluck arpeggio following the chords (`R 5 8 5 3+ 5 8 5`), string pad, and a supersaw lead playing a long-note theme of about 8 bars. Double the lead an octave up in the last section.
- Sidechain 8 dB on bass and music: the pump is part of the sound.
- Form (bars): intro 32 (drums, bass and arp enter one by one, filter opening), groove 32, breakdown 16 to 32 (no kick, pad and a soft statement of the theme on bell or piano), build 16 (snare roll, riser, rising filter), drop 32 (full theme), second breakdown 32 (the emotional centre: theme on pads and lead with the filter opening), build 16, climax 32 to 48 (everything, ride cymbal added), outro 32 (parts leave in reverse order).
- Every 16 bars: crash on the first beat, a one-bar fill before it.

Hard trance uses a harder kick and an off-beat bass. Goa uses phrygian dominant scales and layered acid lines. Progressive trance is slower and subtler, with long filter movements and fewer big breakdowns.

## Psytrance family

Psytrance, dark psytrance, goa. 138 to 150 BPM, dark psy 148 to 180.

```
kick   x---x---x---x---
bass   . R R R . R R R . R R R . R R R     (rolling_bass, one pitch, very short notes)
chat   --x---x---x---x-        snare (snare_short)   ----x-------x---
```

- The "KBBB" kick and bass grid is the genre. The bass stays on one note (E, F or F#, octave 1) for long stretches. No sidechain needed: kick and bass never overlap in time. Keep bass notes short (gate 0.5 to 0.7) so each one ends before the next kick.
- Scale: phrygian or phrygian dominant. Leads are short squelchy 16th phrases (`acid_lead`, `zap`, filtered saws) with delay, that mutate every 8 bars. No long chords.
- Atmosphere, effects and filter automation carry the journey. Breaks are short (8 to 16 bars).
- Dark psytrance: faster, almost no melody. Dissonant or chromatic stabs, noise textures, rising and falling pitch effects, heavy use of `fx` parts. Locrian or chromatic colour. Lower the lead level and raise the fx level, as the profile does.

## Hard dance: gabber, hardstyle, happy hardcore

Gabber, 160 to 200 BPM:

```
kick   x---x---x---x---        (kick_hardcore or hard_kick: the distorted kick is also the bass)
ohat   --x---x---x---x-        clap   ----x-------x---  (optional)
```

- The kick is the centrepiece: long, distorted, pitched. Add `fx.saturator(kick.chain, drive=8)` or `fx.distortion(kick.chain, drive=7)` for more. There is usually no separate bass line. The profile puts the bass role 12 dB down for that reason.
- Leads: `rave_stab` or a detuned saw "hoover", playing short minor or phrygian riffs in 8ths and 16ths. Simple, aggressive, repeated.
- Kick variations make the arrangement: double-time rolls (`x-x-x-x-`), a pitched-down kick at phrase ends, bars of silence before the kick returns.
- Loudness target −8 LUFS, and distortion is welcome. Expect `over_limited` findings and judge them against the style.

Hardstyle, 150 BPM: a kick with a hard attack and a pitched tail playing on every beat, with a "reverse bass" feel between kicks, plus a big melodic supersaw lead in the climax. Happy hardcore, 170 BPM: major key, piano stabs, a fast off-beat bass and breakbeat layers over the four-on-the-floor kick.

## Breakbeat family: breakbeat, big beat, drum and bass, jungle, UK garage

Breakbeat, 120 to 140 BPM:

```
kick   x---------x-----        snare  ----x-------x---
chat   x-x-x-x-x-x-x-x-        ghost snare  -------o-o------
```

- The kick is syncopated and the snare stays on beats 2 and 4. Acoustic-flavoured kit (`kick_acoustic`, `snare_acoustic`, `amen_ride`). Ghost snares and small variations every bar keep it alive: write 2 or 4 bar grids.
- Bass: a syncopated riff or a `reese_bass` line.

Big beat, 100 to 140 BPM: breakbeat drums made heavy with compression and saturation on the drum bus (`big_beat_clap`, `kick_hiphop`), a distorted bass riff or an acid line as the hook, rock-like riffs in minor pentatonic or blues scale, rises and big drops. Loud and rough (−9 LUFS).

Drum and bass, 170 to 176 BPM:

```
kick   x---------x-----        snare  ----x-------x---
chat   x-x-x-x-x-x-x-x-        (two-step; add ghost snares and shuffled hats)
```

- Bass: a sub line with long notes (`sub_bass`), under a `reese_bass` in the mids. Liquid DnB adds 7th chords on `epiano` or pads and a softer mix. Jungle uses chopped breaks: vary the kick and snare placement every bar and add ghost notes.
- Drops come after a 16 bar intro and a build.

UK garage, 130 to 135 BPM: two-step kick (`x---------x-----` or `x------x--x-----`), snare on 2 and 4, heavily swung hats (swing 0.3), organ or plucked bass, chopped vocal-like stabs.

## Bass music: dubstep, trap, hip hop

Dubstep, 140 BPM, half-time feel:

```
kick   x---------x-----        snare  --------x-------
chat   x-x-x-x-x-x-x-x-
```

- `wobble_bass` with a tempo-synced filter LFO whose rate changes from bar to bar (1/4, 1/8, triplets), over a clean `sub_bass`. Sparse minor or phrygian harmony. A long build and a drop on the bass.

Trap, 130 to 160 BPM, half-time feel:

```
kick   x-------x--x----        snare or clap  --------x-------
chat   x-x-x-x-x-x-xxxx   (8ths with 16th and 32nd rolls; use step=0.125 for the rolls)
```

- `808_bass` or `808_kick_long` playing a melody of long sliding notes that follows the kick. Dark minor or harmonic minor melodies on bell, pluck or keys, sparse. No sidechain: the 808 and the kick share notes.

Hip hop (boom bap), 80 to 100 BPM: swung 16ths (0.2), kick `x-----x---x-----`, snare on 2 and 4, a 2 or 4 bar sample-like loop of keys or strings, a round bass following the kick. Lo-fi hip hop slows this down, softens everything, adds 7th chords and more swing.

## Body and industrial: EBM, industrial, futurepop

EBM, 110 to 130 BPM:

```
kick   x---x---x---x---        snare (electro_snare)  ----x-------x---
bass   R . R R 8 . R R R . R R 8 . R 8      (ebm_bass: a sequenced 16th line, the core of the style)
```

- The sequenced bass is the hook: one bar, root and octave, minor or phrygian, with the filter moving slowly. Dry, tight, mono. Few chords. Shouted or spoken vocals with short commanding lines.
- Hats on 8ths or 16ths, metallic percussion hits.

Industrial, 90 to 140 BPM: distorted and noisy sound design is the point. `industrial_kick`, `snare_harsh`, saturation or bitcrush on drums and bass, noise sweeps, phrygian or locrian riffs, detuned pads. Mid-tempo stomps or fast machine rhythms. Vocals are processed: add `fx.distortion` or `fx.bitcrush` on the vocal chain when the user wants that sound.

Futurepop, 125 to 140 BPM: EBM's sequenced bass under trance's melodies, with clean sung vocals.

- Four-on-the-floor trance kick, clap on 2 and 4, off-beat open hat.
- `ebm_bass` 16th line plus `sub_bass`, a `trance_pluck` arpeggio, `string_pad`, and a `supersaw_lead` hook stated in the intro and between verses.
- Minor key, anthem-like chorus over `VI VII i` movements (F G Am in A minor). Verse 8 to 16 bars, pre-chorus, chorus with a held last note and a harmony voice.
- The vocal is in front (profile: vocal +0, lead −3). The lead synth rests while the voice sings and returns in the gaps.
- For a harder edge, closer to the EBM side of the style: a punchy `909_kick` in place of the soft trance kick, `electro_snare` on 2 and 4 with the clap layered 3 dB under it in the big sections, a rim shot on off-16ths (`-------x--x----x`), a pickup kick at the end of every fourth bar, half-bar snare fills into new sections, hat accents on the off-8ths, and a little saturation on the sequenced bass. Keep the kick clean: a noisy or distorted kick reads as dirt in this style and costs loudness. `examples/signal_fires_futurepop` holds both arrangements in one script.

## Synth styles: synthpop, synthwave, darksynth, doomer

Synthpop, 100 to 130 BPM: verse and chorus song form, Linn or 808 kit with a snare on 2 and 4, a simple 8th-note bass (`moog_bass`, `fm_bass`), bright hooks on `square_lead` or `bell`, major or minor keys, chorus melody doubled by a synth.

Synthwave, 80 to 118 BPM: the 1980s film score sound.

```
kick   x-------x-------   (or four on the floor)      snare (reverb_snare)  ----x-------x---
bass   R R R R R R R R R R R R R R R R                 (16th or 8th pulse on the root, moog_bass or fm_bass)
```

- `i VI III VII` and similar loops, lush `warm_pad` or `string_pad`, arpeggios, a singing lead with delay, tom fills (`linn_tom_*`), gated reverb snare. Sidechain about 5 dB.

Darksynth, 95 to 130 BPM: synthwave made aggressive. Distorted `reese_bass` or saturated saw bass playing 16th riffs, phrygian and harmonic minor, `industrial_kick`, big reverb snare, horror-film stabs and choir-like pads, sudden stops and drops.

Doomer (the Russian post-punk and coldwave revival sound), 95 to 150 BPM:

```
kick   x-----x-x-------        snare (linn_snare)  ----x-------x---
chat   x-x-x-x-x-x-x-x-        (drum machine, dry, steady; cr78 or linn kit)
bass   R _ R _ R _ R _ R _ R _ 5 _ 8 _      (pick_bass: driving 8th notes high on the neck, the melodic centre)
```

- The bass carries the song. A chorused guitar-like part (`jangle_pluck` with reverb and delay) plays arpeggios or a two-note figure. A cold monophonic synth line (`square_lead`) answers the voice. Pads are thin and far back (`cold_pad`).
- Minor key, two to four chords for the whole song (`i VI III VII`, `i iv`, `i VII VI`). Low, flat, baritone vocal with little vibrato, lines of resignation and everyday images, long gaps between lines. Reverb on snare and voice, darker top end (the profile lowers the air band) and a modest loudness target (−12 LUFS).
- For speech voices, set `vocal = song.vocal(..., style=Style(vibrato=0.3, scoop=0.3))` for the deadpan delivery.

## Listening styles: IDM, ambient, downtempo, trip hop, lo-fi, vaporwave, chiptune

IDM, any tempo: the rule is that the drum programming does not repeat. Write 4 or 8 bar grids with shifting kick and snare placement, bursts of 32nd notes (`step=0.125`), odd groupings (3+3+2), and sounds that change role. 606 or glitchy kit, `bitcrush`, delay throws. Under the busy rhythm, slow warm chords with added notes (`maj7`, `add9`, `m9`) and a simple, almost childlike melody on bell or epiano. Use `theory.humanize` with a fixed seed for controlled irregularity. A form like A B A' C B' works better than build and drop.

Ambient, 60 to 100 BPM or no pulse: long pad chords (2 to 8 bars each) in lydian, major or dorian, slow attacks, large reverb sends, sparse bell or piano notes, no drums or a very soft pulse. Movement comes from slow filter and level automation. Target −16 LUFS and leave the dynamics alone.

Downtempo and trip hop, 70 to 110 BPM: a slow heavy break (`kick_acoustic`, `snare_acoustic`, swing 0.15), deep bass, minor 7th chords on `epiano`, melancholic strings, room for a vocal.

Vaporwave: slow, major 7th chords, soft 80s sounds, heavy reverb, everything slightly detuned and dull. Chiptune: `chip_lead` and `8bit_` drums, fast arpeggios standing in for chords (three chord notes cycling in 16ths or 32nds), square and triangle basses, no reverb.

## Song forms

Club form (house, techno, trance, DnB): intro 16 to 32, build, drop 16 to 32, breakdown 16 to 32, build, second drop or climax (longer and fuller than the first), outro 16 to 32. Total 4 to 8 minutes. Uplifting trance runs 7 to 15 minutes with two breakdowns (three in the longest forms).

Song form (synthpop, futurepop, doomer, synthwave with vocals): intro 4 to 8, verse 16, pre-chorus 4 to 8, chorus 8, verse 2, pre-chorus, chorus, bridge or instrumental 8 to 16, final chorus doubled, outro 8. Total 3 to 4 minutes. The final chorus carries something new: a harmony, a lead doubling the melody, an extra percussion layer.

Bars to minutes: minutes = bars × 4 ÷ BPM (in 4/4). 112 bars at 132 BPM is 3:24. 256 bars at 138 BPM is 7:25.
