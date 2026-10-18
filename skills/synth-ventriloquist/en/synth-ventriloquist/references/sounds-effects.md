# Sounds and effects

Every sound is an LMMS instrument with settings (a "patch"). The library holds about 130 patches. They are starting points: copy one and change it whenever the song needs something else.

## Contents

- Finding and auditioning sounds
- Drum machines in the library
- Synth patches by role
- Changing a patch
- Building a patch from scratch
- Using LMMS presets, samples and SoundFonts
- Effects
- Automation targets
- Reproducibility rules for sounds

## Finding and auditioning sounds

```bash
python scripts/lmms_tool.py sounds                       # names by role
python scripts/lmms_tool.py sounds moog_bass acid_bass reese_bass --out work/audition
```

The second form renders each named patch alone, prints a table (loudness, length, brightness, main frequency), and writes `sounds.png`, a sheet of small spectrograms. Use it when choosing between candidates and after changing a patch: it is the way to "hear" a sound through numbers and a picture. `sounds all` profiles the whole library.

## Drum machines in the library

The machine kits are one-shot recordings of LMMS's own drum synthesis, and the named kicks are clean synthesized one-shots (a pitch-dropping sine with a short click). The hits without a prefix (`kick_acoustic`, `kick_hardcore`, `snare_harsh`, `clap`, `ohat`, `ride` and so on) play samples that come with LMMS. The skill ships none of them as audio: the kit is made on this machine the first time a song needs it (`lmms_tool.py kit` shows it, `kit --build` makes it now) and kept in the kit folder, so the drums sound the same on every later render here. The named kicks are identical on every machine. The recorded hits with noise in them (snares, hats, claps) differ slightly from one machine to another, as two takes of the same drum machine would.

| Prefix | Character | Typical genres |
|---|---|---|
| `909_` | punchy kick, bright hats, sharp clap and snare (Roland TR-909 style) | house, techno, trance, futurepop, gabber |
| `808_` | deep long kick, snappy snare, cowbell, clave, toms (TR-808 style) | hip hop, trap, electro, synthpop |
| `606_` | thin, dry and tight (TR-606 style) | acid, IDM, electro |
| `linn_` | natural-sounding 80s drums with toms, cabasa, tambourine (LinnDrum style) | synthpop, synthwave, doomer and post-punk |
| `cr78_` | soft vintage preset rhythm box (CR-78 style) | coldwave, lo-fi, downtempo |
| `electro_`, `8bit_`, `jazz_`, `amen_`, `reverb_` | electro kit, chip sounds, acoustic-flavoured hits, gated-reverb hits | electro, chiptune, breakbeat, 80s styles |
| named kicks | `trance_kick`, `house_kick`, `techno_kick`, `hard_kick`, `industrial_kick`, `psy_kick`, `dnb_kick`, `boom_kick` | the genre in the name |
| hits without a prefix (LMMS factory samples) | `kick_acoustic`, `kick_hardcore`, `kick_distorted`, `kick_hiphop`, `snare_acoustic`, `snare_harsh`, `clap`, `hat`, `ohat`, `ride`, `crash`, `tom_low` and more | breakbeat, hardcore, industrial, hip hop |

There is no separate 707 kit. The 909 and Linn kits cover that territory. A TB-303 style bass line is the `acid_bass` and `acid_square` patches (LMMS's LB302): overlapping notes slide, and an accent is a louder note.

## Synth patches by role

| Role | Patches |
|---|---|
| bass | `808_bass`, `acid_bass`, `acid_square`, `ebm_bass`, `fm_bass`, `moog_bass`, `offbeat_bass`, `pick_bass`, `reese_bass`, `rolling_bass`, `wobble_bass` |
| sub | `sub_bass` |
| lead | `acid_lead`, `chip_lead`, `rave_stab`, `saw_lead`, `square_lead`, `supersaw_lead`, `supersaw_high` |
| pluck | `bell`, `jangle_pluck`, `pluck`, `trance_pluck` |
| keys | `chord_stab`, `epiano`, `organ` |
| pad | `cold_pad`, `dark_pad`, `string_pad`, `warm_pad` |
| fx | `reverse_crash`, `sub_drop`, `white_noise`, `zap` |

`python scripts/lmms_tool.py genres <name>` shows the kit a genre profile suggests, and `genres.md` names fitting patches for each style.

## Changing a patch

```python
from lmmskit import sounds
darker = sounds.get("supersaw_lead", filter=(2500, 0.4, sounds.FILTER_LP24),
                    env={"attack": 0.02, "decay": 0.4, "sustain": 0.6, "release": 0.5})
lead = song.add("lead", darker)
```

Top-level keys of a patch:

- `plugin` and `attrs`: the LMMS instrument and its raw settings. `sounds.get(name, attrs={...})` merges changes into the existing settings.
- `env`: volume envelope in seconds (`attack`, `hold`, `decay`, `release`) and `sustain` from 0 to 1.
- `filter`: `(cutoff Hz, resonance, type)` with the type constants `FILTER_LP`, `FILTER_HP`, `FILTER_BP`, `FILTER_NOTCH`, `FILTER_MOOG`, `FILTER_LP24`. `cut_env` adds a filter envelope (same keys as `env` plus `amount`), and `cut_lfo` a tempo-synced filter wobble (`{"beats": 0.5, "amount": 0.5}`).
- `fx`: effects that belong to the sound itself (chorus on a pad, saturation on a bass), as `[("chorus", {...}), ...]` using the effect builders below.
- `role`: the default mix role.

## Building a patch from scratch

These helpers produce the `attrs` for the instruments that cover most electronic sounds.

- `sounds.osc3(waves, vols, coarse, fine, pan, spread, phase, mod)` for TripleOscillator: three oscillators with wave shapes (the constants `SINE`, `TRIANGLE`, `SAW`, `SQUARE`, `MOOG_SAW`, `EXPONENTIAL`, `NOISE`), detune in semitones and cents, and a mix mode between them (`MOD_MIX`, `MOD_FM`, `MOD_PM`, `MOD_AM`, `MOD_SYNC`). Detuned saws make supersaws and pads, a sine plus a square an organ, FM a bell or a metallic bass.
- `sounds.acid(cutoff, resonance, env_mod, decay, dist, square)` for the LB302 acid synth.
- `sounds.kicker(start, end, decay_ms, ...)` for a synthesized kick: a sine that sweeps from `start` Hz to `end` Hz. Leave its `noise` knob at 0: the noise lasts as long as the kick and is heard as hiss on every beat. For a kick with a click, start from a library kick, or edit the `KICKS` table in `scripts/lmmskit/kit.py` and run `lmms_tool.py kit --rebuild`.
- `sounds.sample(path, loop=False, reversed_=False)` plays an audio file.

Example of a new patch:

```python
hoover = {"plugin": "tripleoscillator", "role": "lead",
          "attrs": sounds.osc3(waves=(sounds.SAW, sounds.SAW, sounds.SQUARE), vols=(40, 40, 30), coarse=(0, -12, 0),
                               fine=((-18, 14), (12, -16), (0, 0))),
          "env": {"attack": 0.01, "decay": 0.3, "sustain": 0.8, "release": 0.2},
          "filter": (5000, 0.4, sounds.FILTER_LP24),
          "fx": [("chorus", {"rate_hz": 0.6, "depth_ms": 4.0, "wet": 0.6})]}
```

Audition a new patch before using it. A patch that reads plausibly can still be silent, too quiet or harsh, and the audition table shows that in seconds. `sounds.set_cutoff_lfo(project, track, beats, amount)` adds a tempo-synced filter wobble.

## Using LMMS presets, samples and SoundFonts

- `Project.add_preset_track(name, preset_path)` loads any LMMS preset file (`.xpf`). The LMMS data folder (`lmms_tool.py doctor` prints it) ships presets for its instruments.
- `sounds.sample("drums/kick01.ogg")` plays a file from the LMMS factory samples folder or from `samples/` beside the project. The user's own samples go into `samples/` beside the project so that the project stays portable.
- SoundFont (`sf2player`) and VST instruments in an existing project keep working as long as the files they point to exist on the machine that renders. This toolkit does not create or bundle them.

## Effects

Builders in `lmmskit.fx` add an effect to a chain and return it. A part's mix chain is `part.chain`, a bus chain is `song.mixer.fx(song.bus("music"))`, and the master is `song.mixer.fx(0)`.

| Builder | Use |
|---|---|
| `fx.eq(chain, highpass, lowpass, low_shelf, high_shelf, peaks, slope)` | Tone. Shelves are `(Hz, dB)`. Up to four peaks `(Hz, dB, octaves)`. |
| `fx.compressor(chain, threshold_db, ratio, attack_ms, release_ms, makeup_db)` | Level control and punch |
| `fx.limiter(chain, ceiling_db, input_gain_db)` | Brickwall, last on the master (added by `song.master()`) |
| `fx.saturator(chain, drive, character)`, `fx.distortion(chain, drive)`, `fx.bitcrush` | Harmonics and grit: bass, drums, gabber kicks, industrial, lo-fi. `drive` runs to 10 |
| `fx.reverb(chain, decay_s, room, damp_hz, predelay_ms)` | Space. Defaults to fully wet for a send bus |
| `fx.delay(chain, bpm, left_16ths, right_16ths, feedback)` | Tempo-synced echo |
| `fx.chorus`, `fx.phaser`, `fx.flanger` | Width and motion |
| `fx.deesser`, `fx.exciter`, `fx.bass_boost` | Vocal sibilance, synthetic highs, low lift. The de-esser of LMMS 1.2 cuts everything above its split frequency whatever the threshold, so it is not in the standard vocal strip. Add it only when the user asks for it, with `song.vocal(..., deesser={})`, and check the stem spectrum |
| `fx.stereo_width`, `fx.mono` | Widen, or collapse to mono (kick and sub) |
| `fx.filter_sweep(chain, cutoff, resonance, kind)` | A filter meant for automation |
| `fx.ladspa(chain, "file:Label", {"Port name": value})` | Any of the 225 bundled LADSPA plugins. `fx.catalog()` lists them with port names, ranges and defaults |

Reverb and delay normally live on the shared send buses (`sends={"reverb": 0.3}` on a part), which keeps one space for the whole song and costs less CPU than one reverb per part.

## Automation targets

Pass a parameter to `song.automate(param, [(bar, value), ...])`:

- An effect control: `fx.control(effect, "name")`, with the port name for LADSPA effects (`"Input gain (dB)"`) and the attribute name for native ones (`"cut1"`). `song.sweep` and `song.fade` use this.
- Track volume and pan: `part.track.param("vol")`, `part.track.param("pan")`.
- The track's own filter: `part.track.shaping_param("fcut")` (Hz) and `"fres"`. This filter exists on note-based instruments such as TripleOscillator and the sample player. LB302 does not pass through it.
- A knob of the instrument itself (`part.track.plugin_param("vcf_cut")` on LB302, oscillator volumes on TripleOscillator) can be set freely. Automating one is not reliably repeatable (see below), and the lint warns about it. For a moving acid line, keep the LB302 knobs fixed and sweep a resonant filter on its channel: `song.sweep("acid", at, bars, 300, 9000, resonance=3.0, rest_hz=9000)`.

## Reproducibility rules for sounds

The same script must render the same audio every time. What was found by rendering the same projects repeatedly:

- Some LMMS behaviour depends on the timing between its threads. The toolkit therefore starts LMMS on a single CPU core wherever the operating system allows it (Linux), which made the timing-dependent case below repeatable in tests. On other systems it can vary.
- DrumSynth drum presets (`.ds` files) are synthesized with fresh random noise on every render, on any system. The library therefore plays recordings of them, made once per machine (the kit folder).
- A peak-controller sidechain differs on every render, on any system. `song.sidechain()` writes the same ducking as automation instead.
- Automation of an instrument's own knobs differed on every render on several cores. On one core most renders were identical, but one finished song still came out different on its second render. Treat it as unrepeatable.
- Timing-dependent: the Kicker noise knob when several Kicker tracks play.
- Some LADSPA plugins start up differently from run to run. Calf Saturator and TAP TubeWarmth did so on a busy machine, and the Chebyshev distortion did on every run. The builders in `fx` use only plugins that passed repeated-render tests under load. A plugin added through `fx.ladspa` is untested: let the repeat check of `produce` judge it.
- LB302, the 303-style synth, sometimes starts a render with slightly different internal state. Two renders of a song that uses it then differ by a low-frequency residue 65 to 72 dB under the mix. That cannot be heard, and `produce` reports it as `nearly_repeatable`.
- Anything random in a script needs a fixed seed.

`produce` renders the finished project a second time and reports whether the two files are identical (`repeatable` or `not_repeatable`). `lint` names the causes it can see in a project (`unrepeatable_*` findings).

When a user-supplied project contains such sources, renders can differ slightly from run to run. Say so in the report and offer to freeze the affected tracks to audio.
