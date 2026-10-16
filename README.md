# music-agent-skills

Music production agent skills that finish songs without diffusion models, following the principles of harmony and rhythm and the production process written into each skill. They cover composing, arranging, mixing and mastering. Vocals come from speech synthesis voices (Kokoro, Piper) turned into singing. Every skill ships as a Korean original and an English translation.

화성, 리듬 같은 음악 이론과 제작 과정을 담은 스킬 지침에 따라 확산 모델 없이 곡을 완성하는 음악 제작 에이전트 스킬 모음입니다. 작곡부터 편곡, 믹싱, 마스터링까지 다룹니다. 보컬은 음성 합성 모델(Kokoro, Piper)의 목소리를 노래로 바꿔 만듭니다. 모든 스킬은 한국어 원본과 영어 번역본을 함께 제공합니다.

<details>
<summary><b>English</b></summary>

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
├── en/synth-ventriloquist/         English source
└── demo/                           demo songs
```

- A `.skill` file is a zip archive of the skill folder. Where only `.zip` uploads are accepted, rename the extension to `.zip`.
- To install from source, copy the folder named after the skill (for example `ko/synth-ventriloquist/`) into your agent's skills folder.
- The Korean and English editions of a skill share one skill name. Install one of the two.

## Limitations

- Testing used Claude Opus 5.5 and Claude Fable 5.1. Results may differ with other models and environments.
- Testing did not cover every edge case.
- The model uses the example songs bundled in each skill as a reference for edge cases and mixing, so results may come out close to those examples or the demos.
- For results that do not resemble them, add an instruction such as `Do not make it similar to the examples or demos in the skill.` to your request.
- Speech voices turned into singing sound synthetic, and some words may come out mispronounced.
- The terms of each voice model or voicebank also apply to the sung audio. Some allow non-commercial use only.
- Every skill needs a code execution environment and network access.
- Making a song uses a large number of tokens. This is because the model reads the long instructions and reference pages of each stage. Because it cannot hear, the model checks the measurements and figures of a new render after each fix. Check the usage limits or token pricing of the service you use before you start.
- `synth-ventriloquist` works where LMMS is installed. The LMMS integration was tested with LMMS 1.2.2 on Linux.

## Disclaimer

The skills come as they are, without any warranty. Correct operation in every environment is not guaranteed. The end user bears responsibility for using the skills and their output.

## License

[AGPL-3.0-or-later](LICENSE). Copyright (C) 2026 Em Dash Smoker.

Each skill carries its own `LICENSE` and third-party notice. Under the output exception, the songs, audio, MIDI and project files you make with a skill are free of AGPL terms. The example songs in each skill's `examples/` folder stay under AGPL-3.0-or-later with the skill.

The demo songs in the `demo/` folders (audio, lyrics and project files) are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). The drum samples in `samples/kit/` inside the LMMS project archives are recordings of LMMS DrumSynth presets and stay under GPL-2.0-or-later.

</details>

<details>
<summary><b>한국어</b></summary>

## 스킬 목록

### LMMS 기반

- [`synth-ventriloquist`](skills/synth-ventriloquist): LMMS 프로젝트를 작성하고 창 없이 실행한 LMMS로 모든 소리를 렌더링합니다. 기존 LMMS 프로젝트(.mmp, .mmpz)의 분석과 편집도 지원합니다.

### 비LMMS 기반

- [`spectro-maestro`](skills/spectro-maestro): YAML 곡 파일을 자체 파이썬 신시사이저, 믹서, 마스터링 체인으로 렌더링해 DAW 없이 완성곡을 만듭니다. 완성곡은 오디오, MIDI, 프로젝트 JSON, LMMS, DAWproject 파일로 내보낼 수 있습니다.

## 데모

스킬 폴더의 `demo/` 폴더에 곡별 음원(.ogg), 프로젝트 파일, 가사가 있습니다.

- [`synth-ventriloquist`](skills/synth-ventriloquist)
    - [Anyway](skills/synth-ventriloquist/demo/anyway): 콜드웨이브, 142 BPM, F 단조
    - [Second Brain](skills/synth-ventriloquist/demo/second_brain): 퓨처팝, 136 BPM, F 단조
- [`spectro-maestro`](skills/spectro-maestro)
    - [Abundance](skills/spectro-maestro/demo/abundance): 퓨처팝, 132 BPM, D 단조
    - [Coat by the Door](skills/spectro-maestro/demo/coat_by_the_door): 콜드웨이브, 144 BPM, D 단조

LMMS 데모의 프로젝트 압축 파일은 LMMS 1.2 이상에서 열 수 있습니다. 여는 방법은 압축 파일 안의 `HOW_TO_OPEN.txt`에 있습니다.

## 설치

스킬 폴더마다 설치용 패키지, 소스 폴더, 데모 곡이 들어 있습니다.

```
skills/synth-ventriloquist/
├── synth-ventriloquist-ko.skill    한국어판 설치용 패키지
├── synth-ventriloquist-en.skill    영어판 설치용 패키지
├── ko/synth-ventriloquist/         한국어판 소스
├── en/synth-ventriloquist/         영어판 소스
└── demo/                           데모 곡
```

- `.skill` 파일은 스킬 폴더를 묶은 zip 파일입니다. `.zip` 파일만 올릴 수 있는 환경에서는 확장자를 `.zip`으로 바꿔 업로드하면 됩니다.
- 소스로 설치할 때는 스킬 이름과 같은 폴더(예를 들어 `ko/synth-ventriloquist/`)를 에이전트의 스킬 폴더에 복사합니다.
- 한국어판과 영어판은 같은 스킬 이름을 씁니다. 둘 중 하나만 설치합니다.

## 한계

- 테스트는 Claude Opus 5.5와 Claude Fable 5.1에서 진행했습니다. 다른 모델과 실행 환경에서는 결과가 달라질 수 있습니다.
- 모든 예외 상황을 테스트하지는 못했습니다.
- 모델은 예외 상황과 믹싱을 처리할 때 스킬에 들어 있는 예제 곡을 기준 자료로 참고합니다. 그래서 결과물이 예제나 데모와 비슷해질 수 있습니다.
- 예제를 닮지 않은 결과물이 필요하면 요청할 때 `스킬에 들어 있는 예제나 데모와 비슷하게 만들지 마세요` 같은 제외 지시를 함께 적기를 권장합니다.
- 음성 합성 목소리로 부른 노래에는 기계음이 섞입니다. 일부 단어는 발음이 틀릴 수 있습니다.
- 음성 모델과 보이스뱅크의 이용 조건은 노래한 오디오에도 적용됩니다. 비상업 전용인 모델도 있습니다.
- 모든 스킬은 코드 실행 환경과 네트워크 연결이 있어야 작동합니다.
- 곡을 완성하는 데 많은 토큰이 소모됩니다. 모델이 단계마다 긴 스킬 지침과 참고 문서를 읽기 때문입니다. 모델은 소리를 듣지 못해서 곡을 고칠 때마다 렌더링 결과의 측정값과 그림을 다시 확인합니다. 작업을 시작하기 전에 이용 중인 서비스의 토큰 한도나 요금을 살펴보기를 권장합니다.
- `synth-ventriloquist`는 LMMS가 설치된 환경에서 작동합니다. LMMS 연동은 Linux의 LMMS 1.2.2에서 테스트했습니다.

## 면책 고지

이 저장소의 스킬은 어떠한 보증 없이 있는 그대로 제공합니다. 모든 환경에서 정상 작동을 보장하지 않습니다. 스킬 사용과 결과물에 대한 책임은 최종 사용자에게 있습니다.

## 라이선스

[AGPL-3.0-or-later](LICENSE)를 따릅니다. Copyright (C) 2026 Em Dash Smoker.

스킬마다 `LICENSE`와 제3자 고지 파일이 들어 있습니다. 출력물 예외 조항에 따라 스킬로 만든 곡, 오디오, MIDI, 프로젝트 파일은 AGPL 조건 없이 쓸 수 있습니다. 스킬 안의 `examples/` 예제 곡은 스킬과 함께 AGPL-3.0-or-later를 따릅니다.

`demo/` 폴더의 데모 곡(음원, 가사, 프로젝트 파일)은 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ko)을 따릅니다. LMMS 프로젝트 압축 파일 안의 드럼 샘플(`samples/kit/`)은 LMMS DrumSynth 프리셋을 녹음한 소리라서 CC BY-NC 4.0 대신 GPL-2.0-or-later를 따릅니다.

</details>

## References

Thanks to the developers and contributors of these projects.

이 프로젝트들의 개발자와 기여자분들께 감사드립니다.

- [LMMS](https://lmms.io)
- [DAWproject](https://github.com/bitwig/dawproject)
- [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M)
- [Piper](https://github.com/OHF-Voice/piper1-gpl)
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng)
- [WORLD](https://github.com/mmorise/World)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
