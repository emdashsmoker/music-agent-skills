# Choosing sounds

## How to inspect an instrument
- List of names : `python scripts/studio.py instruments`
- One instrument alone : `python scripts/studio.py audition bass_303 --notes A1,A2,C2 --beats 1`
    + Outputs a picture of waveform and spectrum (`audition/<name>.png`) and numbers (spectral centroid, strongest frequency, duration)
    + Since the sound cannot be heard, the timbre is checked through the picture and the numbers
- Audition a modified patch : `--patch '{filter: {cutoff: 900, res: 0.6}}'`

## Drum instruments
| Class | Names |
|---|---|
| Kick | kick_909, kick_808, kick_house, kick_techno, kick_trance, kick_psy, kick_gabber, kick_hardstyle, kick_dnb, kick_linn, kick_lofi, kick_industrial, kick_break |
| Snare | snare_909, snare_808, snare_linn, snare_dnb, snare_trap, snare_break, snare_industrial, snare_lofi |
| Clap | clap_909, clap_808, clap_big, snap |
| Hi-hat | hat_closed_909, hat_open_909, hat_closed_808, hat_open_808, hat_closed_lofi, hat_pedal |
| Cymbal | ride_909, crash_909, splash |
| Percussion | tom_low, tom_mid, tom_high, conga, timpani, rim_808, clave, cowbell_808, shaker, tambourine, metal_hit, anvil |
- When a closed hi-hat sounds, the open hi-hat of the same family is cut off automatically
- Example of changing drum parameters : `inst: {base: kick_909, decay: 0.6, drive: 0.4}`
    + Kick : `tune_hz` (pitch of the body), `start_hz`, `sweep` (time of the pitch fall), `decay`, `click`, `drive`
    + Snare : `tune_hz`, `tone`, `snappy`, `noise_decay`
    + Hi-hat : `decay`, `band_hz`, `metal`

## Transition effects
- Used through `rise` and `hit` of a section
    + Rising : riser, noise_sweep, reverse_crash, snare_roll
    + Hits : impact, crash, downlifter, sub_drop

## Synth instruments
| Class | Names | Character |
|---|---|---|
| Bass | bass_303, bass_303_square | Acid bass that responds to slides and accents |
| Bass | bass_sub, bass_808 | Pure low end; the 808 has a long tail |
| Bass | bass_reese, bass_wobble, bass_hoover | Detuned low mids, for drum and bass and dubstep |
| Bass | bass_moog, bass_fm, bass_pluck, bass_organ | Firm sequence basses |
| Bass | bass_offbeat, bass_rolling | Off-beat bass and rolling bass of the trance family |
| Bass | bass_picked, bass_saw_dist | Picked bass guitar feel, distorted sawtooth |
| Lead | lead_supersaw, lead_saw, lead_square, lead_sine | Basic leads |
| Lead | lead_acid, lead_psy, lead_hoover, lead_chip | Genre-specific leads |
| Lead | lead_guitar, lead_guitar_dist, lead_fm_bell | Plucked string feel, bell |
| Pluck | pluck_saw, pluck_square, pluck_supersaw, pluck_fm, pluck_string, arp_pulse | Short decaying sounds |
| Pad | pad_warm, pad_supersaw, pad_strings, pad_pwm, pad_dark, pad_glass, pad_choir, drone | Sustained sounds |
| Chord | chord_stab, chord_supersaw, chord_rave | Short chord hits |
| Keys | keys_piano, keys_ep, keys_organ | FM piano, electric piano, organ |
| Other | brass_synth, strings_orch, bell_tubular | Orchestral support timbres (synthesised) |
- Orchestral timbres are synth imitations and a secondary resource
    + Do not expect the realism of real instruments

## Patch structure
- Five engines
    + `sub` : several oscillators and a filter (most timbres)
    + `mono` : monophonic, with slide and accent (303 family, reese bass)
    + `fm` : frequency modulation (bells, piano, metallic bass)
    + `pluck` : plucked string model
    + `organ` : summed harmonics
- Common keys
    + `amp: [attack, decay, sustain, release]` : amplitude envelope (seconds; sustain from 0 to 1)
    + `drive` : amount of distortion
    + `fx` : effect chain belonging to the patch
    + `vibrato: {rate, depth, delay}` : depth in cents
    + `pitch_env: {semis, time}` : starts above the pitch and falls to it
- Oscillators of `sub` and `mono` (the `osc` list)
    + `wave` : saw, square, pulse, tri, sine, noise
    + `voices`, `spread` : number of unison voices and their spread (cents)
    + `octave`, `semi`, `detune`, `level`
    + `pw`, `pwm_rate`, `pwm_depth` : pulse width and its modulation
- Filter (`filter`)
    + `type` : lp, hp, bp
    + `cutoff` (Hz), `res` (0 to 1), `poles` (2 or 4)
    + `env` : depth of the filter envelope (octaves), `fenv: [a, d, s, r]`
    + `track` : follows pitch, `vel` : follows velocity
    + `lfo_rate`, `lfo_depth` : slow movement; the rate accepts note values such as `1/4`
- `mono` only
    + `glide` : slide time, `accent` : how much further the filter opens on an accent, `fenv_decay`
- Operators of `fm` (the `ops` list)
    + `ratio`, `mod_ratio`, `index`, `index_env`, `level`, `detune`
- `pluck` only
    + `decay`, `damp`, `pick`, `body` (reinforces the fundamental)

## Effects
| Name | Main parameters | Use |
|---|---|---|
| `eq` | `bands: [[peak, 3000, 2.5, 1.0], [highshelf, 9000, 3]]` | Each band is [kind, frequency (Hz), gain (dB), Q]; gain defaults to 0 and Q to 0.707. Kinds : peak, lowshelf, highshelf, hp, lp, notch |
| `hpf`, `lpf` | `freq`, `poles` | Tidying a band |
| `tilt` | `db_per_octave`, `pivot` | Overall brightness |
| `comp` | `threshold`, `ratio`, `attack`, `release`, `makeup`, `mix` | Evening out level |
| `gate` | `threshold`, `release` | Cutting tails |
| `soft_clip` | `drive_db` | Gentle saturation |
| `dist` | `drive`, `tone`, `mix`, `kind` | Distortion |
| `crush` | `bits`, `rate`, `mix` | Bit reduction |
| `chorus`, `flanger`, `phaser` | `rate`, `mix` and others | Movement and width |
| `tremolo` | `rate`, `depth` | Level wobble |
| `width` | `amount`, `mono_below` | Stereo width |
| `lofi` | `wow`, `noise_db`, `top` | Tape texture |
| `delay` | `time`, `feedback`, `mix`, `pingpong` | Delay belonging to one track |
| `reverb`, `gated_reverb` | `decay`, `mix` | Reverb belonging to one track |
- For space, the track's `reverb` and `delay` sends are the default
    + Use an insert reverb when a track needs an effect of its own, such as a gated snare
- Picture of an effect chain's frequency response : `python scripts/studio.py plot song.yaml --chain <track>`

## Guidance on choosing sounds
- The starter song of a genre file is that genre's basic set of instruments
    + Before swapping in another instrument of the same role, compare range and duration with `audition`
- One thing at a time in the low end
    + Check the kick's `tune_hz` and the bass register so that the fundamentals of kick and bass do not overlap for long in one band
- At most two sustained sounds in one register
    + Pad, strings and supersaw chords all sounding in one section clog the mids
- In genres where filter movement takes the place of melody (acid, techno), build the development by moving `lpf` with a section's `auto`
