# Export and import

## Audio and MIDI
- `render --formats wav,mp3,ogg,flac,mid` writes them in one go
    + `wav` : 16 bit, dither with a fixed seed
    + `flac` : 24 bit
    + `ogg` : Vorbis
    + `mp3` : needs libsndfile 1.1 or later, or ffmpeg
    + `mid` : one channel per track, drums on channel 10 with General MIDI keys, lyrics included as lyric events
- The default is `wav,mp3,mid`
- `render --stems` saves one stem per track as `stems/<track>.flac`
    + Bus stems (`bus_drums.flac` and so on) are always saved
    + All stems added together have the same balance as the mix before mastering

## Project JSON
- `render` and `export --to json` save `<song>.project.json`
    + A flat format in which every note, chord, section and mix setting is written out
    + The song can be rendered again from this JSON alone, without the song file
- Import : `python scripts/studio.py render song.project.json`
    + `lint`, `export`, `plot` and `vocal-check` accept the JSON as it is
- The JSON can be edited by hand to change single notes
    + A track's `notes` entry : `[start beat, length in beats, MIDI pitch, velocity]`

## LMMS project
- `python scripts/studio.py export song.yaml --to lmms`
    + Result : `lmms/<song>.mmp`, `lmms/samples/<song>/` and `lmms/HOW_TO_OPEN.txt`
- How things are converted
    + Drum tracks : sampler tracks holding the same drum sounds as one-shot samples; hits can be edited
    + Pitched tracks : Triple Oscillator tracks that approximate the patch; notes can be edited
    + Vocals and transition effects : sample tracks holding rendered stems
- To include vocals and transition effects, run `render --stems` first
- The sound re-rendered in LMMS differs from the original
    + Notes, structure and drum sounds are the same
    + Synth timbres are approximations
    + Bus processing, return effects and mastering are not included
    + Automation (filter movement, level changes, the fade at the end of the song) is not included, so draw it again in LMMS
    + All track volumes are exported 6 dB lower to prevent clipping
- Sample paths are written relative to the LMMS samples folder (`<song>/<file>.wav`)
    + To open the project, copy `samples/<song>/` into the LMMS samples folder; `HOW_TO_OPEN.txt` says the same
    + The project then opens on any computer
- The project file is in the LMMS 1.2 format

## Checking in LMMS
- LMMS is an optional outside program
    + Export works without LMMS
    + If the user did not ask for an LMMS project, do not look for LMMS or install it
    + If the user does not use LMMS, suggest DAWproject, or MIDI with stems
- Check command : `python scripts/studio.py lmms-check song.yaml`
    + Re-renders the project with the LMMS it finds and prints length, peak level and the number of clipped samples
    + The command adds by itself whatever a display-less environment, an administrator account, an AppImage or a Flatpak needs to run
    + If there is no LMMS it only says so and ends with exit code 3; the exported files are unaffected
- Order in which LMMS is looked for
    + The setting `lmms` (`--lmms`, environment variable `SPECTRO_MAESTRO_LMMS`, config file) : a path to the program, or a command such as `flatpak run io.lmms.LMMS`
    + `lmms` on PATH
    + LMMS installed through Flatpak
    + An `lmms*.AppImage` placed in the `tools/` folder of `cache_dir`, then Snap
    + The Applications folder on macOS, Program Files on Windows
- When there is no LMMS but the user wants the check
    + Look at the operating system and environment with `doctor`, then pick the form of distribution that suits it
    + Check the available forms, the current version and the download address directly on the official LMMS download page and in the releases of the official repository
    + Do not state an address or a version from memory
    + On a personal computer get the user's consent before installing
| Environment | Forms to consider first | Notes |
|---|---|---|
| Linux desktop | Flatpak (per-user install), AppImage, distribution package | A distribution package needs administrator rights, so give the user the command |
| Linux container, no privileges | AppImage | No administrator rights needed; found automatically when placed in `tools/` under `cache_dir` |
| macOS | Official disk image, Homebrew | Found automatically in the Applications folder |
| Windows | Official installer, a package manager such as winget | Found automatically at the default install location |
- If the user already has a way of managing packages, follow it
- If LMMS was installed somewhere else, give the path in the setting `lmms`
- If it cannot be installed or the user does not want it, skip the check
    + Record in the report that the LMMS re-render check was not done

## DAWproject
- `python scripts/studio.py export song.yaml --to dawproject`
    + Result : `<song>.dawproject` (an open exchange format read by Bitwig Studio, Studio One, Cubase and others)
- How things are converted
    + Tracks with notes : note tracks, one clip per section
    + Vocals and transition effects : included as audio clips when stems exist (run `render --stems` first)
    + Tempo, meter, section markers, track volume and pan are included
- Instrument timbres are not included
    + Assign an instrument to each track in the receiving DAW
- Automation (filter movement, level changes, the fade at the end of the song) is not included
    + Draw it again in the receiving DAW
- The exported XML is checked against the format's schema (when lxml is installed)

## MIDI import
- `python scripts/studio.py import-midi input.mid -o song.yaml --key "A minor"`
    + Creates a song file draft that keeps pitches and rhythm
    + Instruments and roles are guesses from the register, so review and correct them
    + Drums are aligned to sixteenths, everything else to 1/48 of a beat
- An imported song arrives as a single section
    + Divide the structure and assign mix roles, then render

## What to deliver
- Standard delivery
    + Finished audio (`mp3` or the format the user named)
    + MIDI
    + The song file (`.yaml`) and the project JSON
- Added on request
    + Stems, LMMS project, DAWproject
    + Lyrics file, QA pictures
