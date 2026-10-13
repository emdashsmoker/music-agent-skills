# music-agent-skills

[한국어](README.ko.md)

Composing agent skills that finish songs without diffusion models, following the principles of harmony and rhythm and the composing process written into each skill. They cover composing, arranging, mixing and mastering. Vocals come from speech synthesis voices (Kokoro, Piper) turned into singing. Every skill ships as a Korean original and an English translation.

## Skills

### LMMS-based

- [`synth-ventriloquist`](skills/synth-ventriloquist): Writes an LMMS project and renders every sound through LMMS running without its window. It also analyzes and edits existing LMMS projects (.mmp, .mmpz).

### Non-LMMS

- [`spectro-maestro`](skills/spectro-maestro): Renders a YAML song file with its own Python synthesizer, mixer and mastering chain, so a finished song needs no DAW. It can export the result as audio, MIDI, project JSON, LMMS and DAWproject files.

## Demos

The `demo/` folder of each skill holds the audio (.ogg), the project file and the lyrics of each song.

- [`synth-ventriloquist`](skills/synth-ventriloquist)
    - [Anyway](skills/synth-ventriloquist/demo/anyway): coldwave, 142 BPM, F minor
    - [Second Brain](skills/synth-ventriloquist/demo/second_brain): futurepop, 136 BPM, F minor
- [`spectro-maestro`](skills/spectro-maestro)
    - [Abundance](skills/spectro-maestro/demo/abundance): futurepop, 132 BPM, D minor
    - [Coat by the Door](skills/spectro-maestro/demo/coat_by_the_door): coldwave, 144 BPM, D minor

The project archives of the LMMS demos open in LMMS 1.2 or newer. `HOW_TO_OPEN.txt` inside each archive explains how.

## Installation

Each skill folder holds the install packages, the source folders and the demo songs.

```
skills/synth-ventriloquist/
├── synth-ventriloquist-ko.skill    Korean install package
├── synth-ventriloquist-en.skill    English install package
├── ko/synth-ventriloquist/         Korean source
├── en/synth-ventriloquist-en/      English source
└── demo/                           demo songs
```

- A `.skill` file is a zip archive of the skill folder. Where only `.zip` uploads are accepted, rename the extension to `.zip`.
- To install from source, copy the folder named after the skill (for example `ko/synth-ventriloquist/`) into your agent's skills folder.

## Limitations

- Testing used Claude Opus 5.5 and Claude Fable 5.1. Results may differ with other models and environments.
- Testing did not cover every edge case.
- The model uses the example songs bundled in each skill as a reference for edge cases and mixing, so results may come out close to those examples or the demos.
- For results that do not resemble them, add an instruction such as `Do not make it similar to the examples or demos in the skill.` to your request.
- Speech voices turned into singing sound synthetic, and some words may come out mispronounced.
- The terms of each voice model or voicebank also apply to the sung audio. Some allow non-commercial use only.
- Every skill needs a code execution environment and network access.
- `synth-ventriloquist` works where LMMS is installed. The LMMS integration was tested with LMMS 1.2.2 on Linux.

## Disclaimer

The skills come as they are, without any warranty. Correct operation in every environment is not guaranteed. The end user bears responsibility for using the skills and their output.

## License

[AGPL-3.0-or-later](LICENSE). Copyright (C) 2026 Em Dash Smoker.

Each skill carries its own `LICENSE` and third-party notice. Under the output exception, the songs, audio, MIDI and project files you make with a skill are free of AGPL terms. The example songs in each skill's `examples/` folder stay under AGPL-3.0-or-later with the skill.

The demo songs in the `demo/` folders (audio, lyrics and project files) are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). The drum samples in `samples/kit/` inside the LMMS project archives are recordings of LMMS DrumSynth presets and stay under GPL-2.0-or-later.
