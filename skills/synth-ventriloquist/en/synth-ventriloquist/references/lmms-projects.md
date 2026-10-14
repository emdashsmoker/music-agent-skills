# Working with LMMS projects: import, analysis, editing, export

The toolkit reads and writes LMMS project files directly (`.mmp` is XML, `.mmpz` the compressed form) and uses LMMS itself, without its window, to render. This page covers projects that did not come from a song script: a user's own LMMS project, a downloaded one, or a project from an earlier session.

## Contents

- First look at a project
- What can and cannot be relied on
- Analysing
- Advising
- Editing
- Export formats
- Bringing material in
- File facts worth knowing

## First look at a project

```bash
python scripts/lmms_tool.py inspect song.mmpz          # structure as JSON
python scripts/lmms_tool.py lint song.mmpz             # notes, harmony, arrangement, repeatability
python scripts/lmms_tool.py check song.mmpz -o review  # render, measurements, figures
```

`inspect` reports tempo, length, every track (instrument, clips, notes, pitch range, bars used, effects, mixer channel), the mixer (channels, effects, sends), Beat/Bassline parts, controllers, automation clips, and two lists that decide how far the work can go:

- `external_dependencies`: VST instruments and effects, SoundFonts, GIG banks. LMMS needs those files on the machine that renders.
- `missing_samples`: sample files the project refers to that cannot be found.

Work on a copy. Keep the user's original file untouched and write results under a new name.

## What can and cannot be relied on

Tell the user plainly at the start when any of these applies:

- Missing samples or plugins: affected tracks render silent or wrong. The analysis of notes and structure still holds. The audio measurements do not describe the real song. Ask for the files (put samples into `samples/` beside the project) or agree to continue with those tracks excluded.
- VST plugins: headless rendering of VSTs depends on the user's system and often fails. Their settings are opaque data that can be kept but not understood or edited.
- Large projects (dozens of tracks, many minutes): rendering stems takes a long time. Say how long, and offer to start with the note-level `lint` (no rendering) or an excerpt (`render --bars`).
- A project made with a newer LMMS than the installed one may not load. `lmms upgrade in.mmp out.mmp` converts older files forward, never backward.
- Projects using a peak-controller sidechain, DrumSynth presets or automated instrument knobs can render slightly differently on each run (`unrepeatable_*` findings in lint). The same goes for some third-party effect plugins. Measurements are still valid within a fraction of a dB.
- Without a plan file the tools guess each track's mix role from its name, instrument and register. Check the guesses in the `part_levels` table and correct them by renaming tracks or by passing roles in a script when they matter.

## Analysing

- Key and harmony: `lint` detects the best-fitting key when none is declared (`--key "F# minor"` to state it) and reports out-of-scale notes, clashes, bass range and low-register mud with bar numbers.
- Arrangement: `visual.arrangement` (drawn by `check` as `fig_arrangement.png`) shows which track plays in which bar. The `section_density` table needs declared sections, which a foreign project lacks, so describe the structure from the figure: where parts enter, where the low end drops out, where the peak is.
- Mix: `check` measures loudness, peaks, stereo, band balance, part levels and masking exactly as for scripted songs (`mixing.md`), and draws the figures (`visual-qa.md`).
- A closer look at notes: `visual.piano_roll(project, out, start_bar, bars, tracks, scale_pitch_classes)` draws selected tracks with out-of-scale notes marked.

Report findings to the user in musical terms with bar numbers ("the bass and the pad both hold close chords below C3 in bars 17 to 32, which reads as mud in the 150 to 400 Hz band").

## Advising

Separate three kinds of statement, and label them:

- Measured defects: clipping, phase cancellation, missing files, notes outside the key the user named.
- Deviations from convention: band balance, loudness, level relations. Present these as observations with the usual range, and ask whether they are intended.
- Suggestions of taste: arrangement ideas, sound choices. Offer them as options.

Give the two or three changes that would matter most, in order, instead of a full list of everything measurable.

## Editing

`lmmskit.project.Project` gives direct access:

```python
from lmmskit.project import Project, Note
from lmmskit import fx, sounds

project = Project.load("song.mmpz")
bass = project.track("Bass")
bass.param("vol").set(85)
for pattern in bass.patterns():                       # raw clips; bass.notes() gives Note objects
    ...
fx.eq(project.mixer.fx(3), highpass=120)              # add an effect to mixer channel 3
lead = sounds.add(project, "New lead", "supersaw_lead", fxch=project.mixer.add_channel("Lead"))
lead.add_pattern(start_beat=64, notes=[Note(0, 1, 76), Note(1, 1, 79)])
project.automate(bass.param("vol"), [(0, 60), (16, 100)])
project.save("song_v2.mmp")
```

- Tracks: `project.tracks()`, `track(name)`, `add_instrument_track`, `add_preset_track`, `remove_track`. Per track: `param("vol" | "pan")`, `plugin_param(name)`, `shaping_param("fcut")`, `fx` (the track's own effect chain), `patterns()`, `notes()`, `add_pattern`, `clear_patterns`.
- Mixer: `project.mixer.channels()`, `add_channel`, `fx(n)`, `volume(n)`, `send(a, b, amount)`.
- Time is in beats. Tempo is `project.bpm`.
- `lmmskit.mix.balance` and `master_to_loudness` work on any project. `balance` moves instrument tracks only and lists Beat/Bassline and sample tracks it left alone under `not_adjusted`, with how far each is from its target. On a user's project, offer them as a proposal and compare before and after (`visual.compare_spectrograms`, and the two reports) before replacing anything.
- To extend a foreign project with the song-script comfort (sections, riffs, sidechain automation), write new tracks with `Project` calls as above. `Song` creates projects from scratch and does not wrap existing ones.
- After every edit: render, `check`, and look at the figures. An edit that looks right in XML can be silent in audio.

Keep changes minimal and listed. The user should be able to read exactly what was altered: tracks added, notes changed in which bars, effects added on which channel, levels moved by how many dB.

## Export formats

| Format | Command | Contains | Use |
|---|---|---|---|
| Audio | `render song.mmp -o out.ogg` (`.mp3`, `.flac`, `.wav`), or the files `produce` writes | The mix | Listening, publishing. Needs `ffmpeg` for ogg and mp3 |
| LMMS project | the `.mmp` itself, or `export --mmp copy.mmpz` | Everything | Continue in LMMS |
| Portable project | `pack song.mmp -o song.zip` | Project, plan files, the samples it uses, a note on where to copy them | Send to another LMMS user. Voicebanks are never included |
| MIDI | `export song.mmp --midi song.mid` | Tempo and notes, one track per part. Drums on channel 10 with General MIDI note numbers. Sung melodies as notes | Any DAW or notation program. Sounds are not carried |
| DAWproject | `export song.mmp --dawproject song.dawproject --stems stems/` | Tempo, note tracks, and with `--stems` one audio track per rendered part | Bitwig Studio, Studio One, Cubase and other DAWs that read the format. The file is checked against the official schema when `xmlschema` is installed. LMMS instruments and effects do not transfer: the stems carry the sound, the notes allow re-voicing |
| JSON | `export song.mmp --json song.json`, back with `import-json song.json -o song.mmp` | The whole project, losslessly | Diffing, version control, processing by other tools |

For moving a song into another DAW, give both MIDI and stems (or the DAWproject with stems). Say clearly that synth patches and effects stay behind.

## Bringing material in

- MIDI files: `export.read_midi_notes(path)` returns notes per track in beats. Put them on tracks with `add_pattern` or `part.notes`, then choose sounds.
- Audio (a recorded vocal, a loop the user owns): copy it under `samples/` beside the project and place it with `song.add_audio(name, "folder/file.wav", role=...)` and `song.place_audio(part, at, seconds)`, or `sounds.sample(path)` on an instrument track. Tempo-matching of loops is up to the material: this toolkit does not time-stretch arbitrary audio.
- Another project's tracks: load both projects and copy the `<track>` elements, or rebuild the part in a script from `track.notes()`.

## File facts worth knowing

- 48 ticks per beat. LMMS key numbers are MIDI minus 12 (the toolkit converts: all pitches in this API are MIDI numbers, middle C = 60).
- Note volume runs 0 to 200 with 100 as unity. Track volume the same.
- Audio clips on "sample tracks" bypass the mixer channels in LMMS 1.2, so the toolkit plays audio through sample-player instrument tracks instead. A foreign project's sample tracks are left as they are.
- An effect goes silent after its "decay" time without input. The toolkit sets that to the maximum so delay and reverb tails ring out.
- LMMS renders one bar past the last clip. `Project.set_length` or `song.tail_bars` adds room for tails.
- Relative sample paths resolve against the LMMS factory samples and against `samples/` beside the project.
