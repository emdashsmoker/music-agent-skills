---
name: synth-ventriloquist
description: Compose, arrange, sing, mix, master and export finished electronic tracks by driving LMMS without its window, and analyse, edit and export existing LMMS projects (.mmp, .mmpz). Use whenever the user asks to make or produce a song, track, beat, instrumental, demo or loop in an electronic style (house, techno, trance, drum and bass, EBM, industrial, futurepop, synthpop, synthwave, doomer, gabber, hip hop, ambient), asks for synthesized or sung vocals, wants audio, MIDI, DAWproject or LMMS project files, or mentions LMMS, even when they do not name this skill. Read the reference page of each stage before acting on it - references/setup.md (environment and installing), composing.md (song script API, arrangement, lint), genres.md (style idioms), sounds-effects.md (patches, effects, repeatability), vocals.md (voices, lyrics, intelligibility), mixing.md (produce, report, fixes), visual-qa.md (figures), lmms-projects.md (existing projects, export formats). English edition of the Korean skill synth-ventriloquist.
license: AGPL-3.0-or-later
---

# Synth Ventriloquist (English edition)

> **License.** Copyright (C) 2026 Em Dash Smoker. This skill (its instructions, scripts and example songs) is free software: you may redistribute and modify it under the GNU Affero General Public License, version 3 or (at your option) any later version. It comes without any warranty. The full text is in `LICENSE`.
>
> **Third-party notices.** The skill contains no audio. The third-party material in it is the DAWproject schema, MIT-licensed work of Bitwig, the G2P tables ported from OpenUtau (MIT, StAkira), and copies of LMMS DrumSynth preset files under GPL-2.0-or-later, kept as the source of the recorded drum hits. LMMS, FFmpeg, the Python packages and the speech models are not part of the skill and are installed separately under their own licenses. The drum kit is made on the user's machine at first use, partly by recording presets of the user's own LMMS. Details: `THIRD_PARTY_NOTICES.md`.
>
> **What is made with the skill is not covered.** Songs, audio, MIDI, LMMS and DAW project files, lyrics, figures and reports produced by running the skill belong to the person who made them and are not subject to this license. Voices, voicebanks and samples brought into a song keep their own terms.
>
> **Translation notice.** This edition was translated from the Korean original (`synth-ventriloquist`). A translation can shift meaning, so its logic and performance may not come out as the original intends. Where the two differ, the Korean original is the reference.

The skill is a ventriloquist for a synthesizer: it never plays a note itself. It writes a real LMMS project, and LMMS, running without its window, makes every sound. A song is written as a short Python script. The bundled toolkit (`scripts/lmmskit`, command line `scripts/lmms_tool.py`) turns it into the project, LMMS renders the audio, and measurement tools check harmony, arrangement, mix and sung words the way a compiler checks code. Existing LMMS projects can be opened, analysed, edited and exported with the same tools.

What to expect from the result: a complete, structured, genre-correct track built from synthesizer patches, classic drum-machine sounds and optional synthesized vocals, at the level of a well-made sequencer production or a solid demo. It is not a commercial studio master and a synthesized voice is not a human singer. Say this once when planning, so the user's expectations match.

## Principles

- You cannot hear. Every judgement about sound must rest on a measurement or a figure you actually looked at. Never describe how something sounds from the script alone.
- Findings are compile errors, taste is the user's. `ERROR` and `WARN` findings get fixed, or get reported to the user as a deliberate choice. When the user insists on something a check dislikes (a buried vocal, a distorted master, an "ugly" chord), warn once with the concrete consequence, then do it their way and record it in the delivery notes.
- Same input, same output. Every random choice takes a fixed seed, and `produce` proves repeatability by rendering twice. Keep the song script: it is the source, and all later changes go through it.
- The numbers in this skill (levels, ranges, thresholds) are conventions and measured starting points. Adapt them to the song and the user. When a reference page and the situation disagree, reason from what the rule is for.
- Ask before doing anything that costs the user: installs on a person's machine, large downloads, long renders, anything involving a voicebank's terms, lyrics that will be sung.
- Stay within what the user gave. Do not fetch samples, voicebanks or other people's material on your own initiative.

## Before the first song in an environment

Run `python scripts/lmms_tool.py doctor`. It changes nothing and reports what the machine has: LMMS in any of its forms (a system package, an AppImage, a Flatpak, an app bundle), ffmpeg, Python packages, and whether this is a disposable container or a person's computer. Then read `references/setup.md` and act on what kind of machine it is:

- In a disposable container, install what is missing and report it afterwards.
- On a person's computer, propose what to install and how, prefer ways that need no administrator rights, and wait for the answer. Use an LMMS that is already there. Never run commands with administrator rights yourself, and never change or remove what the user installed.

`python scripts/lmms_tool.py selftest` proves the installation in under a minute. The first run also makes the drum kit on this machine (a few seconds, needs LMMS). Settings (an LMMS in an unusual place, a cache folder, fewer parallel renders) are environment variables or `lmms_tool.py configure`.

## Making a new song

Work through the stages in order. Each stage ends with a check that can fail. Do not move on while it fails.

### Stage 1: Plan with the user

Collect the plan in one round of questions. Skip what the user already stated, and offer the default in brackets so that a short answer is enough:

- Style or genre, and any reference artists or tracks (for feel, never for copying melodies or lyrics)
- Mood and energy
- Tempo [the genre profile's default], key [a minor key that suits the genre]
- Length and form [3 to 4 minutes in song or club form. Uplifting trance runs 7 to 15 minutes, default about 7 and a half]
- Vocals: none, sung by a built-in speech voice, or sung by a singer voicebank the user supplies. Offer the voice options from `references/vocals.md`. Language [English]
- Recognition model for the vocal check [base]: offer small when the machine has room (4 or more CPU cores, 2 GB or more of free memory), above all for lyrics in another language, where base flags clearly sung lines more often. Medium or larger only when the user asks. Store the choice with `configure --set asr_model=<model>`; the costs per model are in `references/vocals.md`
- Reading speed of a speech voice [the agent decides]: offer three choices. The agent decides: you pick one of the other two for each part and say which, and why, in the delivery notes. Matched to the melody: the voice reads slower under long notes and faster under short ones (speed 0.7 to 1.15), so less has to be stretched and two nasals across words stay apart (read at 1.0 and stretched, "Come, my love" was heard as "Come, I love"). Fixed: every line at one pace, 1.0 being the voice's own. When the choice is yours, start from matched, which left fewer weak lines in measurements, and fix the speed for a part meant to sound spoken or a part whose lines the vocal check finds weaker matched than fixed. Pass a fixed speed as `song.vocal(..., speed=1.0)`; leaving `speed` out matches the melody (the `held` method then reads at 1.0). Voicebanks have no reading speed
- Lyrics: the user's own, or written here from a theme they give. Read the lyric craft in `references/vocals.md` before drafting a line, because a draft written first tends to keep its faults. Review the user's own lyrics by the same craft once the voice is chosen, offer revised lines, and follow the user's choice
- Sound preferences [the genre's usual kit: 909, 808, 606, Linn or CR-78 style drums, 303-style acid bass, and so on]
- Mix style [balanced, flexible]: where the foreground (the backbeat, the lead, the lead vocal) sits in the track. Balanced is the default, with the backbeat and the lead vocal a little forward. Forward is a pop or radio mix: the voice and the backbeat stand on top of the track. Vocal puts only the voice and the lead forward and keeps the backbeat at balanced; backbeat is the reverse. Blended is a club mix: the voice and the lead sit inside the track. Offer instrumentals the list without vocal; their foreground is the backbeat and the lead. Adherence is flexible, flexible-HITL (Human in the Loop) or fixed. Flexible means the style is a starting point: parts move 1 to 2 dB as the findings ask, the style itself changes without asking when another fits better, and each move and change is written in the delivery note. Flexible-HITL is the same, except that the user is asked before the style changes. Fixed keeps the foreground parts' levels and the ducking at the style's values and fixes everything else. The choice goes into the script as `song.mix_style()`; how far each style moves the levels, the ducking and the judging window, and the adherence rules, are in the Mix styles section of `references/mixing.md`. Brightness is matched to finished records by the tone fit, so mention it only when the user wants a dark mix
- Master strength [the genre target, clean limiting]: the default is a clean master whose limiter cuts at most 3 dB from the loudest moments. A hot master raises the genre target by 1 to 2 LU and lets the limiter cut up to 5 dB, which the user accepts together with its pumping and a smeared kick (the loudness step and the Loudness targets sections of `references/mixing.md`). Streaming services turn loud masters down to about -14 LUFS, so a higher value only buys density
- Render mode [repeatable]: always ask this one and say what each choice costs. Repeatable gives the same file on every render and is slower in the full-mix renders. Fast finishes those sooner, and some songs may then differ slightly between renders. Gentle uses fewer cores so the computer stays usable, and the longest stage takes longer. The table and settings are in `references/setup.md`, Render mode
- Deliverables [ogg, mp3, MIDI, the LMMS project, a DAWproject file, lyrics]
- Title [suggest one]

`python scripts/lmms_tool.py genres <name>` prints the profile for a style, and `references/genres.md` describes the idiom. For a style without a profile, plan from your own knowledge of the genre and state your assumptions.

Then write the plan back in a few lines: title, genre, tempo, key, sections with bar counts and total length, parts per section, the chord progression, the vocal approach, the mix style and its adherence, and what will be delivered. Wait for the user's confirmation or changes. If nobody is there to answer, proceed with the defaults and put the assumptions at the top of the delivery notes.

Pause and ask when a request is unclear or surprising for the stated goal, for example lyrics that contradict the mood, a tempo far outside the genre, or a length the form cannot fill. Say what seems off and offer two concrete alternatives. Do not change the plan on your own. If the user keeps the original plan, state once, clearly, what loss of quality to expect, then go ahead with the plan and record the measurements and limits of that part in the delivery notes. For lyrics: show the full text and get approval before any line is sung.

Check for this stage: the user confirmed the plan, or the assumptions are written down.

### Stage 2: Compose

Read `references/composing.md`. Write the song script: sections, chords, parts, notes, transitions. Run it, then:

```bash
python scripts/lmms_tool.py lint song.mmp
```

Fix every `ERROR` and `WARN` in the script and run again. A finding you decide to keep must have a reason you can state. Read the `section_density` table and compare it with the planned energy curve.

Check: lint shows no unexplained warnings.

### Stage 3: Choose and shape sounds

Read `references/sounds-effects.md` when the default patches do not fit. Audition candidates (`lmms_tool.py sounds a b c --out work/audition`) and look at the table and the picture before choosing. Render a short excerpt of the busiest section (`render --bars`) once the main parts exist.

Check: every part is audible in the excerpt's measurements, and no patch is silent or far off in level.

### Stage 4: Vocals (only when the song has them)

Read `references/vocals.md` first. In short: first settle the words and sentence structure the chosen voice sings well, write lines as whole sentences with one melody token per syllable, check each line with `lyric-lint` as you write it, sing the lines alone before the mix, run the word-choice procedure on weak lines, and give the user the dry vocal and the lyrics for approval. Settle a line's `lyric-lint` warnings before it goes into the script: saving the script sings the lines, so a fault caught earlier costs nothing. `lint` repeats the lyric checks on every lead line once the project exists.

With a singer voicebank, read its terms with the user before the first render and credit it as required. Of the lyric rules, only the singing craft and the model-voice habits apply to the bank.

Check: the lead vocal's lines are approved by the user, or flagged lines are listed with what the recogniser heard, their pitch error in cents and their `ROUGH` syllables.

### Stage 5: Mix and master

```bash
python scripts/lmms_tool.py produce song.mmp -o out
```

This balances part levels by measurement, sets the master loudness for the genre, renders, runs all checks, draws figures and writes every export. Tell the user first when it will take more than a few minutes (see `references/mixing.md` for timings).

Check: `produce` finished and `out/report.txt` exists.

### Stage 6: Review

Read `references/visual-qa.md` and do the review pass: `report.txt`, then every figure. Look at the images. Compare what they show with the plan. For each problem, find the cause in `references/mixing.md`, change the script (arrangement and levels before EQ), and run Stage 5 again.

Stop iterating when the report is clean or when the remaining findings are intended. If the same three or more warnings survive two rounds, stop and show them to the user with the figures.

Check: every figure was opened, and each remaining `WARN` has a stated reason.

### Stage 7: Deliver

Hand over, with a short note:

- Audio: `.ogg` and `.mp3` (and `.wav` on request)
- `.mid`, the `.mmp` project, `.dawproject`, `.project.json`. For use on another machine in LMMS: `lmms_tool.py pack song.mmp -o song.zip`
- The lyrics file and the dry lead vocal for vocal songs
- The overview figure
- The song script, when the user may want changes later

The note states: title, genre, tempo, key, length, loudness, mix style and adherence (with the parts moved from the style and by how much, when flexible or flexible-HITL, and the planned style and the reason, when the style was changed), and the render mode used. What was checked and what the figures showed. Remaining warnings and why they were kept. Assumptions made. Credits and terms that apply (voices, voicebanks). Which parts are synthesized speech or a voicebank. Keep it to what the user needs to decide whether they are happy.

## Working on an existing LMMS project

Read `references/lmms-projects.md`. The short form:

1. Copy the file and work on the copy. `inspect`, then `lint`, then `check` (render, measurements, figures).
2. Tell the user up front what limits apply: missing samples, VST or SoundFont dependencies, a very large project, or sources that render differently each run.
3. Report findings in musical terms with bar numbers, separated into measured defects, deviations from convention and suggestions of taste.
4. Make only the edits the user asked for, list each change, render, check, and compare before and after.
5. Export in the formats they need.

## Changing a finished song

Edit the song script and run the stages from the change onward. Vocal lines are cached, so only changed lines are sung again. Never patch the rendered audio or hand-edit the generated project when a script exists: the next run would lose the change.

## Reference pages

Each page holds what its stage needs and this file does not repeat. Read the page before doing the stage, also when the task looks familiar.

| Page | Read it when |
|---|---|
| `references/setup.md` | The first run in a new environment, LMMS or a package is missing, a render fails, anything is to be installed or configured |
| `references/composing.md` | Writing or changing a song script. The API, the notations, arrangement craft, the lint findings |
| `references/genres.md` | Planning any track: tempo, drum grids, bass, harmony, sounds and form per style |
| `references/sounds-effects.md` | Choosing or designing sounds, adding effects, automation, repeatability rules |
| `references/vocals.md` | Any vocal: voices, voicebanks and their terms, lyric writing, word choice, line endings, vocal mix |
| `references/mixing.md` | Running `produce`, reading the report, fixing each finding |
| `references/visual-qa.md` | Reviewing a render through its figures |
| `references/lmms-projects.md` | Opening, analysing, editing or exporting a project that did not come from a song script, and all export formats |

## Example songs

`examples/` holds four finished songs as scripts, with their MIDI files and lyrics: an uplifting trance instrumental, an acid techno instrumental, a futurepop song with a sung vocal and two drum arrangements, and a doomer song with a low vocal. Read the one closest to the task before writing a new script: they show section planning, energy curves, vocal lines and mix moves in working form. `examples/README.md` says what each one demonstrates and how to run it. They write into the current folder, so run them from a work folder.

## Commands

`python scripts/lmms_tool.py <command> -h` documents every command: `doctor`, `configure`, `kit`, `selftest`, `genres`, `sounds`, `inspect`, `lint`, `render`, `balance`, `master`, `check`, `produce`, `export`, `import-json`, `pack`, `voices`, `sing`, `compare`, `lyric-lint`.
