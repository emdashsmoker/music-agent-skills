# Example songs

Four finished songs written with the toolkit. Each folder holds the song script, the MIDI file of the finished song and, for vocal songs, the lyrics. Rendered audio is not included: run the script and `produce` to hear a song. The examples are part of the skill and covered by its license. A song you write yourself is your own work.

| Folder | Song | Shows |
|---|---|---|
| `first_light_uplifting_trance/` | First Light, 138 BPM, A minor, 256 bars, instrumental | Long club form with two breakdowns and a climax, energy curve by adding and removing parts, filter sweeps and fades, supersaw lead with a high double, rolling off-beat bass, shared riser and impact tracks |
| `rubber_line_acid_techno/` | Rubber Line, 130 BPM, A phrygian, 120 bars, instrumental | 303-style bass line with slides and accents, a resonant channel filter moved through the song in place of knob automation (which would not render repeatably), 909 kit, saturation |
| `signal_fires_futurepop/` | Signal Fires, 132 BPM, A minor, 104 bars, sung | Song form with verse, pre-chorus, chorus and bridge, a sung lead with harmony and double in the choruses, vocal ducking, a vocal EQ decided from the brightness check, and two drum arrangements from one script: `trance` (soft kick, clap backbeat) and `hard` (punchy kick, snare backbeat, rim, fills, pickup kicks) |
| `grey_light_doomer/` | Grey Light, 124 BPM, E minor, 112 bars, sung | A dark, slow-moving mix kept on purpose, low deadpan vocal style, two-bar chorus lines written for intelligibility, guitar-like pluck riff, Linn-style drums |

## Running one

Run from a work folder of your own, since the project is written into the current folder:

```bash
mkdir work && cd work
python <skill>/examples/first_light_uplifting_trance/song.py
python <skill>/scripts/lmms_tool.py produce first_light.mmp -o out

python <skill>/examples/signal_fires_futurepop/song.py kokoro:af_heart signal_fires hard
python <skill>/scripts/lmms_tool.py produce signal_fires.mmp -o out_signal_fires
```

The vocal songs take a voice as their first argument (see `references/vocals.md` for the choices) and download the speech model on first use. The trance song takes about a quarter of an hour to produce on two CPU cores, the others five to ten minutes.

## Using them as models

- Copy the structure, not the notes: how sections are declared, how one loop over the sections places drums and bass, how the hook is stated by an instrument before the voice takes it.
- The comments say why a value was chosen. Several of them record a measurement from the report (a level, a filter, an EQ).
- The futurepop script shows how to keep two arrangements in one source with a parameter, which is the way to offer a user alternatives without forking the song.
