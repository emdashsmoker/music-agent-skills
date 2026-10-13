# Third-party notices

Synth Ventriloquist is Copyright (C) 2026 Em Dash Smoker and is licensed under the GNU Affero General Public License, version 3 or (at your option) any later version (`LICENSE`). This file lists material from other authors that the skill contains, what it makes on the user's machine, and the separate programs and models it drives. License names are those the projects stated when this file was written. Check each project for its current terms.

## Contained in this skill

| What | Where | Origin | License |
|---|---|---|---|
| DAWproject schema files | `scripts/lmmskit/schemas/Project.xsd`, `MetaData.xsd` | Copyright (c) 2020 Bitwig, https://github.com/bitwig/dawproject | MIT, full text in `scripts/lmmskit/schemas/LICENSE-dawproject.txt` |

The skill contains no audio files. Two data files hold facts only and no third-party work: `scripts/lmmskit/ladspa_catalog.json` lists the names, port names and value ranges of the LADSPA plugins that LMMS ships (Calf, SWH, TAP, CAPS, CMT), and `scripts/lmmskit/kit.py` lists the file names of LMMS DrumSynth presets.

## Made on the user's machine: the drum kit

The first time a song needs drums, the skill makes a kit of one-shot WAV files in the user's cache folder. Nothing of it is distributed with the skill.

- Named kicks and a noise loop are computed by the skill's own code.
- Drum-machine hits are recorded from the DrumSynth presets of the LMMS installed on that machine (LMMS and its presets: GPL-2.0-or-later, DrumSynth renderer (c) 1998-2000 Paul Kellett, mda-vst.com). A hit that sounds in a finished song is in the same position as the sound of any song made in LMMS with those presets. A notice file is written beside the recordings and travels with them into project folders and project packs.

## Not contained: installed separately and driven by the skill

The skill starts these as separate programs or loads them as libraries. None of them is distributed with it. The person who installs them accepts their terms.

| Software or model | Used for | License |
|---|---|---|
| LMMS 1.2.x, with its bundled LADSPA plugins and factory samples | All synthesis, mixing and rendering | GPL-2.0-or-later |
| FFmpeg | ogg, mp3 and flac encoding | LGPL-2.1-or-later or GPL, depending on the build |
| NumPy, SciPy | Measurement and signal processing | BSD-3-Clause |
| python-soundfile, libsndfile | Reading and writing audio | BSD-3-Clause, LGPL-2.1-or-later |
| Matplotlib | Review figures | Matplotlib license (PSF-style) |
| ONNX Runtime | Running speech and singing models | MIT |
| ONNX | Reading model graphs | Apache-2.0 |
| kokoro-onnx | Kokoro speech voices | MIT |
| Kokoro-82M model and voices | Kokoro speech voices | Apache-2.0 |
| piper-tts | Piper speech voices | GPL-3.0-or-later (the earlier rhasspy/piper releases: MIT) |
| Piper voice models | Piper speech voices | Each voice has its own license and model card |
| pyworld, WORLD vocoder | Turning speech into singing | MIT, modified BSD |
| faster-whisper, Whisper models | Recognition check of sung lines | MIT |
| PyYAML | Reading singer voicebank settings | MIT |
| xmlschema | Validating DAWproject files | MIT |
| imageio-ffmpeg | An optional way to obtain FFmpeg | BSD-2-Clause, and it downloads an FFmpeg build |

Singer voicebanks are supplied by the user and are never part of the skill. Each has terms set by its maker.

## What you make with the skill

Songs, audio files, MIDI files, LMMS and DAW project files, lyrics, figures and reports that you produce by running the skill are your own works. They are not covered by the skill's license, and the copyright holder of the skill claims no rights in them. Material you bring into a song (voices, voicebanks, samples, other people's projects) keeps its own terms, and crediting a voice or voicebank where its terms ask for it remains your responsibility.

The example songs in `examples/` are part of the skill and are covered by its license.
