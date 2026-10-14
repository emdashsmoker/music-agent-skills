# Third-party notices

Spectro Maestro
Copyright (C) 2026 Em Dash Smoker
Licensed under the GNU Affero General Public License, version 3 or (at your option) any later version. See `LICENSE`.

This file lists the third-party material this skill contains, the software and models it uses at run time without containing them, and the terms that apply to what you make with it.

## 1. What the licence covers
- Covered by AGPL-3.0-or-later: the scripts under `scripts/`, the documents (`SKILL.md`, `references/`), the genre files under `assets/genres/`, and the example songs under `examples/`
- Not covered: the files listed in section 2, which keep their own licences

## 2. Third-party material contained in this skill
| Files | Origin | Licence |
|---|---|---|
| `assets/dawproject/Project.xsd`, `assets/dawproject/MetaData.xsd` | DAWproject exchange format, Copyright (c) 2020 Bitwig | MIT, text in `assets/dawproject/LICENSE.dawproject.txt` |

No other third-party source code, sample, model or voice data is contained in this skill.

## 3. Output exception
- Songs and other files you create with this skill are not covered by its licence and are yours: song files you write, audio, MIDI, stems, project JSON, LMMS projects, DAWproject files, pictures and reports
- Additional permission under section 7 of the GNU Affero General Public License version 3: material taken from the bundled genre files, starter songs and instrument definitions that becomes part of such output may be used, copied, modified and distributed without the conditions of the AGPL
- This exception does not change the licence of the skill itself: a modified or redistributed copy of the scripts, documents, genre files or example songs stays under AGPL-3.0-or-later
- Output can still be subject to terms that come from elsewhere, namely the voice model or voicebank that sang it (section 5)

## 4. Software used at run time and not contained here
These packages are installed separately by the user (`requirements.txt`, `requirements-vocal.txt`) and are used under their own licences. Licences are given as declared by each project at the time of writing; check the project for the authoritative text.

| Package | Used for | Licence |
|---|---|---|
| NumPy | all signal processing | BSD-3-Clause (with bundled components under 0BSD, MIT, Zlib, CC0-1.0) |
| SciPy | filters, resampling | BSD-3-Clause |
| PyYAML | song files | MIT |
| python-soundfile | audio files | BSD-3-Clause (wraps libsndfile, LGPL-2.1-or-later) |
| Mido | MIDI files | MIT |
| Matplotlib | review pictures | Matplotlib licence (PSF-based) |
| lxml | schema check of DAWproject exports | BSD-3-Clause |
| pyworld | voice analysis and synthesis | MIT (wraps WORLD by M. Morise, modified BSD) |
| ONNX Runtime | running voice models | MIT |
| ONNX | preparing Piper models | Apache-2.0 |
| kokoro-onnx | Kokoro phonemiser and model access | MIT |
| phonemizer, eSpeak NG (through kokoro-onnx and Piper) | text to phonemes | GPL-3.0-or-later |
| piper-tts | Piper speech engine | GPL-3.0-or-later |
| faster-whisper, CTranslate2 | speech recognition for vocal checks | MIT |
| huggingface_hub, tokenizers | model download and decoding for recognition | Apache-2.0 |
| cmudict | pronunciations for DiffSinger voicebanks | package GPL-3.0-or-later; dictionary data Copyright (C) 1993-2015 Carnegie Mellon University, BSD-style |

Optional outside programs, started only when present: a C compiler, FFmpeg (LGPL-2.1-or-later or GPL depending on the build), LMMS (GPL-2.0-or-later), git.

## 5. Voice models and voicebanks
Models are downloaded on first use or supplied by the user. None is contained in this skill.

| Model | Source | Licence and terms |
|---|---|---|
| Kokoro-82M v1.0, ONNX build with timestamps | `onnx-community/Kokoro-82M-v1.0-ONNX-timestamped`, an ONNX release of `hexgrad/Kokoro-82M` | Apache-2.0 |
| Piper voices | `rhasspy/piper-voices` | Repository declared MIT; each voice also carries the terms of the dataset it was trained on, which `studio.py voices` summarises and each voice's model card states |
| Whisper models in CTranslate2 format | `Systran/faster-whisper-*` | MIT |
| DiffSinger voicebanks | supplied by the user | The terms of each voicebank; read them with `studio.py diffsinger-inspect` before use |

- Audio sung by a voice model or voicebank is subject to that model's or voicebank's terms (for example non-commercial use or required credit)
- The DiffSinger runner in `scripts/foundry/diffsinger.py` reads voicebanks in the layout used by OpenUtau (MIT) and DiffSinger (Apache-2.0); it contains no source code from either project

## 6. Example songs
- `examples/` holds the song files, MIDI and lyrics of four songs made with this skill: First Light, Signal Fires, Last Tram and Silver Box; no audio is included
- Music, lyrics and song files: Copyright (C) 2026 Em Dash Smoker, provided under AGPL-3.0-or-later as part of this skill
- The vocal parts of Signal Fires and Last Tram are written for Kokoro-82M voices (`af_heart`, `am_michael`), Apache-2.0, and are synthesised when the songs are rendered
- All instrument sounds are synthesised by this skill; no samples are used

## 7. No warranty
This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
