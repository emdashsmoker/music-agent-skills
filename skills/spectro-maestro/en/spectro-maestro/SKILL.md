---
name: spectro-maestro
license: AGPL-3.0-or-later
description: Spectro Maestro (English edition) composes, arranges, synthesises, mixes and masters complete songs in code, mainly electronic music, and exports mp3, ogg, wav, MIDI and DAW projects. Use it whenever the user asks to compose or produce a song, track, beat, loop or BGM, or names a genre (house, techno, trance, drum and bass, synthwave, industrial, EBM, futurepop, psytrance, gabber, IDM, hip hop, trap), even for just "make me a beat". Also for sung lyrics (speech voices turned into singing, or a user-supplied DiffSinger voicebank), lyric intelligibility checks, mix review, editing a song file, MIDI import, LMMS and DAWproject export. Read the reference for the step you are on - references/planning.md (planning), song-format.md (song file syntax, required), composition.md (writing, arranging, lint), genres.md, sound.md (instruments, effects), mixing-qa.md (review after rendering, required), vocals.md (all vocal work, required), export.md (export, LMMS check).
---

# Spectro Maestro (English edition)

## Licence and notices
- Spectro Maestro, Copyright (C) 2026 Em Dash Smoker
- This skill is free software distributed under the GNU Affero General Public License, version 3 or any later version (AGPL-3.0-or-later)
    + The full text is in `LICENSE`; there is no warranty of any kind
    + A modified or redistributed copy of the skill keeps the same licence and the copyright notice
- The licence does not apply to what is made with this skill
    + Song files, audio, MIDI, stems, project JSON, LMMS projects, DAWproject files, pictures and reports belong to whoever made them
    + Material from the genre files and starter songs that ends up in such output may also be used without the conditions of the AGPL (additional permission under section 7 of AGPL version 3)
    + The usage terms of the voice model or voicebank that sang a vocal still apply to that output
- Third-party notices
    + The only outside material contained in the skill is two DAWproject schema files (Copyright (c) 2020 Bitwig, MIT)
    + The packages and models used at run time are not contained in the skill and follow their own licences
    + Main items : NumPy and SciPy (BSD-3-Clause), pyworld, ONNX Runtime and faster-whisper (MIT), the Kokoro-82M model (Apache-2.0), piper-tts, phonemizer and cmudict (GPL-3.0-or-later)
    + The complete list and terms are in `THIRD-PARTY-NOTICES.md`
- When the user asks about the licence, answer from this section and those two files

## Translation notice
- This skill was written and tested in Korean and then translated into English
    + The translation may not carry the logic of the original exactly
    + Behaviour and quality may differ from what the original was designed and measured to deliver
- The scripts, genre files and measured thresholds are identical to the Korean original (`spectro-maestro`)
    + Only this file and the files under `references/` are translated
- If an instruction here is unclear or seems to contradict the tool's behaviour, trust the tool's own output and help text

## What this skill is
- A production environment in which one song is written as a YAML song file and rendered with a command-line tool
    + The composer writes the song file; the tool does synthesis, mixing, mastering and produces the review material
    + It is designed for a worker who cannot hear: every judgement is backed by numbers and pictures
- The result is a song that is complete from start to finish
    + Pop and vocal songs 3-4 minutes, club genres 5-8 minutes, uplifting trance 7-15 minutes
    + A structure with an introduction, development, a peak and an ending
- All sound is synthesised by built-in synthesiser and drum machine models
    + No outside samples: 47 drums and 49 synths, including the 909, 808 and 303 families
    + Orchestral timbres are a secondary resource

## Where the tool is
- Every command runs through `scripts/studio.py` in this skill folder
    + Below, `studio` means `python <skill folder>/scripts/studio.py`
    + `python` may be `python3` or `py` depending on the system; quote paths that contain spaces
- Commands in brief
    + `doctor` : report on this machine (packages, outside tools, settings, what is missing)
    + `genres [id]` : genre list, conventions of one genre
    + `new <genre> -o song.yaml` : write a starter song
    + `instruments`, `audition <instrument>` : instrument list, one instrument alone with a picture
    + `lint song.yaml` : check harmony, ranges, structure and lyrics
    + `voices`, `vocal-check`, `vocal-try`, `diffsinger-inspect` : vocals
    + `render song.yaml` : audio, MIDI, review report and pictures
    + `plot` : extra pictures
    + `export --to json,midi,lmms,dawproject`, `import-midi` : export and import
    + `lmms-check` : re-render an exported LMMS project in LMMS as a check (optional, only when LMMS is present)
- See `studio <command> -h` for the options of each command

## Before starting
- Run `studio doctor` first
    + It works with no package installed, and it installs, downloads and changes nothing
    + It reports the operating system, the kind of Python, missing packages, outside tools, and every setting with its source
- Decide first what kind of environment this is
    + Disposable environment (container, sandbox, CI) : install right away without asking
    + The user's own computer : before installing or downloading, say what will be fetched, where it goes and how large it is, and get consent
    + When in doubt, treat it as the user's own computer
- Rules for installing packages
    + Instrumental songs need only `requirements.txt`; install `requirements-vocal.txt` only for songs with a voice
    + On a personal computer install into an isolated environment (venv, conda, uv or whatever the user already uses)
    + Do not force packages into a Python that the operating system manages (`--break-system-packages`, `sudo pip`); disposable environments are the only exception
    + Do not run anything that needs administrator rights yourself; give the user the command instead
    + Do not move on to composing until installation is finished
- Settings are given from outside, without editing the scripts
    + Priority : command option, environment variable `SPECTRO_MAESTRO_<NAME>`, JSON config file, default for the operating system
    + Config file : searched as `--config <file>` (placed before the command name), then `spectro-maestro.json` in the working folder, then `spectro-maestro/config.json` in the user's config folder
    + Names : `cache_dir`, `models_dir`, `offline`, `download_timeout_s`, `native`, `compiler`, `ffmpeg`, `lmms`, `asr_model`
    + `doctor` shows the current values, where each came from, and the config paths it looked at
    + Example : `{"models_dir": "D:/music-models", "offline": true}`
- Voice models are downloaded into `models_dir` on first use (about 1 GB for a voice plus the recognition model)
    + The default location is under the operating system's per-user cache folder; change it with `--models` or a setting
    + When a download fails, the error message gives the file's address and the path to put it at, so the user can place it by hand
    + With `offline` switched on no download is attempted
    + If the models cannot be obtained, tell the user and either continue with an instrumental or ask for the model files
- Outside tools are all optional
    + C compiler : when present, a fast filter kernel is built once into `cache_dir`; without one a slower path gives identical results (`native: off` disables it)
    + ffmpeg : used only when the audio library cannot write mp3 itself; with neither, deliver ogg, flac or wav
    + LMMS : needed only to open or re-render an exported LMMS project, and only dealt with when the user wants it (`references/export.md`)
    + Do not stop work because a tool is missing: do what is possible and note it in the report
- Output is collected in `<song name>_out/` next to the song file
    + Final audio and MIDI, `report.json`, `qa/` pictures, `stems/`, `vocals/`, `build/` (cache)
    + The tool writes files only to the output paths named in a command, to `cache_dir` and to `models_dir`

## Workflow
- Step 1 : planning (agreed with the user)
- Step 2 : skeleton (structure, chords, rhythm)
- Step 3 : melody and arrangement
- Step 4 : vocals (songs with lyrics)
- Step 5 : render and review
- Step 6 : revise and repeat
- Step 7 : export and report
- Each step ends with something that can be checked
    + Planning summary, lint passing, vocal check table, review numbers and pictures
    + Skipping the check of an earlier step widens what has to be fixed later

## Step 1 Planning
- Agree with the user on genre, mood, tempo, key, length, structure, vocals or not, and delivery formats
    + Offer a default for each item so the user only answers what they want changed
    + The questions, defaults and summary form are in `references/planning.md`
- Start by reading the genre's conventions with `studio genres <id>`
    + For genres that are not in the list see `references/genres.md`
- Respect lyrics, melodies and references the user provides as they are
    + When something looks wrong, show where and offer alternatives, and let the user choose
    + Review lyrics against what the chosen voice can sing too (`references/vocals.md`)
    + Do not change them on your own and carry on
- If the plan or the lyrics would badly hurt quality, say so before proceeding
    + In this order: explain the problem, offer alternatives, take the user's choice
    + If the user keeps the original, follow it and state clearly what loss of quality to expect
- For a vocal song choose the engine and the voice in this step
    + Pass the list from `studio voices` and its usage terms on to the user
    + Singing voicebanks are used only when the user provides them; do not search for or download one on the user's behalf

## Step 2 Skeleton
- Create a starter with `studio new <genre> -o song.yaml --title ... --bpm ... --key ...`
    + A starter is a complete song with that genre's standard instruments and patterns
- Rewrite the starter to fit the plan
    + Match the section list and bar counts to the planned length
    + Replace the chord progression to suit the song's character
    + Add variations and fills to the drum and bass patterns
    + Decide how the song ends (`ending: hit` or `ending: fade`, or a closing section of your own)
- The song file syntax is in `references/song-format.md`
    + Read it through once before writing for the first time
- Check with `studio lint song.yaml`
    + Errors are reported with their location, so fix them at once

## Step 3 Melody and arrangement
- Compose the main melody and the hook yourself
    + Do not reuse the starter's melody as it is
    + Chord tones on strong beats, mostly stepwise motion, resolution at phrase ends
- Design the energy of every section
    + Create rises and falls with the number of parts, filters, register and rhythmic density
    + Mark boundaries with transition devices (riser, snare roll, impact, dropping the kick)
- Guidance on writing and arranging and notes on the lint items are in `references/composition.md`
- Instrument choice and patch changes are in `references/sound.md`
    + Check an unfamiliar instrument with the picture and numbers from `studio audition <instrument>`
- Judge each `lint` warning one by one
    + Keep what is intended and record the reason in `notes`

## Step 4 Vocals
- Read the lyric writing rules first : `references/vocals.md`
- Order
    + Check the strengths and weaknesses of the chosen engine and voice, and choose words and sentence structure to suit them
    + Fix the rhythm of the melody, write the lyrics, check syllable counts and stress with `lint`
    + `studio vocal-check song.yaml` : sing the vocal alone before mixing and check the recognition match per line, rough syllables (`ROUGH`) and pitch error
    + For weak lines and lines marked `ROUGH`, look at the picture and the solo clip
    + `studio vocal-try song.yaml --line N --text "candidate"` : compare candidates with the same number of syllables
- The match score is a detector that picks lines to listen to
    + Whether a line passes is decided by a person listening
    + Lyrics the user wrote or approved are not changed because of a warning alone: present the original and the candidate clips and let the user choose
- When given a DiffSinger voicebank, run `studio diffsinger-inspect <path>` first
    + Read the terms-of-use files and give the user a summary
    + Of the lyric rules in `references/vocals.md`, only the singing craft and the model-voice habits apply to the bank
    + `lint` runs those two groups on the bank's lines
- After changing the voice, check the vocal and the mix numbers again

## Step 5 Render and review
- Check with partial renders first
    + `studio render song.yaml --sections chorus1` : timbre and balance of one section
- Full render
    + `studio render song.yaml --formats wav,mp3,ogg,mid`
    + On a 2-core CPU a 3-4 minute song takes 2-3 minutes and a 7 minute song about 4 minutes; vocal synthesis takes extra time
    + Where commands have a time limit, run it in the background and read the log
- Review means doing all three
    + Numbers and findings (`== metrics ==`, `== findings ==`)
    + The section table (`== sections ==`)
    + The six pictures in the `qa/` folder
- Looking at the pictures is a formal step
    + Open overview, spectrogram, spectrum, arrangement, pianoroll and stereo yourself
    + Faults that no threshold catches show up in the pictures (an empty band, a constant stripe, a lopsided image, unexpected silence)
    + When you see something no rule covers, trace the cause with extra pictures and single-track renders
- Check the start and the end of the song separately
    + See that the overview waveform tapers at the end and that there is no `ending_drop_db` finding
- Balances that must hold
    + The beat is not buried and the beat does not swallow the mix (`drums_vs_rest_db`)
    + Neither the vocal nor the backing is buried (`vocal_body_db`, `vocal_consonant_db`)
- What the numbers mean, how to read the pictures and remedies by symptom are in `references/mixing-qa.md`
- If pictures cannot be viewed in this environment, say so in the report and judge from the numbers and the section table alone

## Step 6 Revise and repeat
- Change one thing at a time and check again
    + Render only the problem section, look at how the numbers moved, then render in full
- Order of adjustment
    + Arrangement (remove a part, move a register), track `gain_db`, section `vel`, sends and filters, insert EQ, master EQ
- If a finding is an intended effect, leave it and record the reason in the report
- A cache means only changed tracks are recomputed

## Step 7 Export and report
- Standard delivery : finished audio, MIDI, the song file, the project JSON
    + On request: stems, LMMS project, DAWproject, a lyrics file, review pictures
    + Contents and limits of each format are in `references/export.md`
- What the report contains
    + The planning summary and what changed along the way
    + Final numbers (loudness, true peak, the main balance figures) and remaining findings
    + What was seen in the pictures
    + For a vocal song, a summary of match scores per line, weak lines and what was done about them
    + What was not checked and known limits
    + If a voice with usage terms was used, the terms such as required credit
- Take the user's listening comments and go back to step 6
    + The final judgement belongs to the user's ears

## Principles of judgement
- Rules and thresholds are starting points
    + Genre and intent may justify leaving them
    + When you do, leave the reason on record
- Numbers are detectors, pictures are instruments of observation
    + Even when both pass, the user's listening comment takes precedence
- Do not report as checked what was not checked
    + Keep in the report the premise that you did not hear the sound
- Keep results reproducible
    + The same song file and `seed` give the same sound
    + When the result should differ, change the `seed`

## Example songs
- `examples/` holds four finished songs made with this skill
| Folder | Song | Worth looking at |
|---|---|---|
| `examples/first_light/` | First Light, uplifting trance at 138 bpm, 7 min 16 s | Long structure, reuse of one theme, breaks and climaxes |
| `examples/signal_fires/` | Signal Fires, futurepop at 128 bpm, 3 min 50 s | Vocal song (Kokoro `af_heart`), doubles and harmonies, `ending: hit` |
| `examples/last_tram/` | Last Tram, doomer at 156 bpm, 3 min 4 s | Vocal song (Kokoro `am_michael`), lyrics at one syllable per beat, `ending: fade` |
| `examples/silver_box/` | Silver Box, acid house at 124 bpm, 4 min 12 s | Instrumental that develops through filter automation |
- Each folder has the song file (`.yaml`) and MIDI; vocal songs include the lyrics (`lyrics.txt`)
    + No audio is included; rendering the song file produces the same sound
- What they are for
    + Working examples of song file syntax, structure and lyric notation
    + Something to render as a check of the installation
- When rendering one again, put the output folder outside the skill
    + `studio render <skill folder>/examples/silver_box/silver_box.yaml -o <working folder>/silver_box_out`
- Do not carry an example's melody, lyrics or chord progression over into a new song
    + A new song is composed afresh to its plan

## Reference files
| File | When to read |
|---|---|
| `references/planning.md` | Planning questions, handling user input, responding to unworkable requests |
| `references/song-format.md` | Before writing a song file (required) |
| `references/composition.md` | When writing chords, melody and arrangement, and when reading lint results |
| `references/genres.md` | Choosing a genre, genres not in the list, adding a genre file |
| `references/sound.md` | Choosing instruments, changing patches, effects |
| `references/mixing-qa.md` | Review after rendering and fixing the mix (required) |
| `references/vocals.md` | The whole vocal process (required) |
| `references/export.md` | Export and import, checking in LMMS |
