# LMMS 프로젝트 다루기: 가져오기, 분석, 수정, 내보내기

툴킷은 LMMS 프로젝트 파일을 직접 읽고 쓰며(`.mmp`는 XML, `.mmpz`는 압축 형태), 창 없이 실행한 LMMS로 렌더한다. 이 문서는 곡 스크립트에서 나오지 않은 프로젝트를 다룬다. 사용자 자신의 LMMS 프로젝트, 내려받은 프로젝트, 이전 세션의 프로젝트가 해당한다.

## 목차

- 프로젝트 처음 살펴보기
- 믿을 수 있는 것과 없는 것
- 분석
- 조언
- 수정
- 내보내기 형식
- 자료 들여오기
- 알아 둘 파일 사실

## 프로젝트 처음 살펴보기

```bash
python scripts/lmms_tool.py inspect song.mmpz          # 구조를 JSON으로
python scripts/lmms_tool.py lint song.mmpz             # 음표, 화성, 편곡, 재현성
python scripts/lmms_tool.py check song.mmpz -o review  # 렌더, 측정, 그림
```

`inspect`는 템포, 길이, 모든 트랙(악기, 클립, 음표, 음역, 사용 마디, 이펙트, 믹서 채널), 믹서(채널, 이펙트, 센드), Beat/Bassline 파트, 컨트롤러, 오토메이션 클립을 보고한다. 작업이 어디까지 가능한지 정하는 목록 2개도 보고한다.

- `external_dependencies`: VST 악기와 이펙트, SoundFont, GIG 뱅크. 렌더하는 컴퓨터에 그 파일이 있어야 한다.
- `missing_samples`: 프로젝트가 참조하지만 찾을 수 없는 샘플 파일.

사본에서 작업한다. 사용자의 원본 파일은 건드리지 않고 결과는 새 이름으로 쓴다.

## 믿을 수 있는 것과 없는 것

다음 중 하나라도 해당하면 시작할 때 사용자에게 분명히 말한다.

- 누락된 샘플이나 플러그인: 해당 트랙이 무음이나 잘못된 소리로 렌더된다. 음표와 구조의 분석은 유효하다. 오디오 측정은 실제 곡을 설명하지 못한다. 파일을 요청하거나(샘플은 프로젝트 옆 `samples/`에 둔다) 그 트랙을 제외하고 계속하기로 합의한다.
- VST 플러그인: VST의 창 없는 렌더는 사용자 시스템에 좌우되며 자주 실패한다. 그 설정은 보존할 수는 있지만 이해하거나 고칠 수 없는 불투명 데이터다.
- 큰 프로젝트(수십 개 트랙, 여러 분): 스템 렌더에 오래 걸린다. 소요 시간을 말하고, 음표 수준의 `lint`(렌더 없음)나 구간(`render --bars`)으로 시작하는 방법을 제안한다.
- 설치된 것보다 새로운 LMMS로 만든 프로젝트는 열리지 않을 수 있다. `lmms upgrade in.mmp out.mmp`는 오래된 파일을 새 형식으로 올릴 뿐 이전 형식으로 되돌리지는 않는다.
- 피크 컨트롤러 사이드체인, DrumSynth 프리셋, 악기 노브 오토메이션을 쓰는 프로젝트는 실행마다 조금 다르게 렌더될 수 있다(lint의 `unrepeatable_*` 결과). 일부 서드 파티 이펙트 플러그인도 마찬가지다. 측정값은 0.몇 dB 이내에서 여전히 유효하다.
- plan 파일이 없으면 도구가 트랙의 이름, 악기, 음역으로 믹스 역할을 추정한다. `part_levels` 표에서 추정을 확인하고, 중요하면 트랙 이름을 바꾸거나 스크립트에서 역할을 넘겨 바로잡는다.

## 분석

- 조성과 화성: `lint`는 선언된 조성이 없으면 가장 잘 맞는 조성을 찾고(`--key "F# minor"`로 지정), 스케일 밖의 음, 충돌, 베이스 음역, 낮은 음역의 탁함을 마디 번호와 함께 보고한다.
- 편곡: `visual.arrangement`(`check`가 `fig_arrangement.png`로 그림)는 어느 트랙이 어느 마디에서 연주되는지 보여 준다. `section_density` 표에는 선언된 섹션이 필요한데 외부 프로젝트에는 없으므로, 그림에서 구조를 서술한다. 파트가 들어오는 곳, 저역이 빠지는 곳, 정점이 있는 곳을 적는다.
- 믹스: `check`는 스크립트 곡과 똑같이 음량, 피크, 스테레오, 대역 밸런스, 파트 레벨, 마스킹을 측정하고(`mixing.md`) 그림을 그린다(`visual-qa.md`).
- 음표 자세히 보기: `visual.piano_roll(project, out, start_bar, bars, tracks, scale_pitch_classes)`는 선택한 트랙을 스케일 밖의 음을 표시해 그린다.

점검 결과는 마디 번호와 함께 음악 용어로 사용자에게 보고한다("17-32마디에서 베이스와 패드가 둘 다 C3 아래에서 좁은 화음을 끌고 있어 150-400 Hz 대역이 탁하게 읽힌다").

## 조언

진술을 3가지로 나누고 표시한다.

- 측정된 결함: 클리핑, 위상 상쇄, 누락된 파일, 사용자가 말한 조성 밖의 음.
- 관례에서 벗어난 점: 대역 밸런스, 음량, 레벨 관계. 통상 범위와 함께 관찰로 제시하고 의도한 것인지 묻는다.
- 취향의 제안: 편곡 아이디어, 음색 선택. 선택지로 제시한다.

측정 가능한 모든 것의 전체 목록 대신 가장 중요한 변경 2-3개를 순서대로 준다.

## 수정

`lmmskit.project.Project`로 직접 접근한다.

```python
from lmmskit.project import Project, Note
from lmmskit import fx, sounds

project = Project.load("song.mmpz")
bass = project.track("Bass")
bass.param("vol").set(85)
for pattern in bass.patterns():                       # 원시 클립. bass.notes()는 Note 객체를 준다
    ...
fx.eq(project.mixer.fx(3), highpass=120)              # 믹서 채널 3에 이펙트 추가
lead = sounds.add(project, "New lead", "supersaw_lead", fxch=project.mixer.add_channel("Lead"))
lead.add_pattern(start_beat=64, notes=[Note(0, 1, 76), Note(1, 1, 79)])
project.automate(bass.param("vol"), [(0, 60), (16, 100)])
project.save("song_v2.mmp")
```

- 트랙: `project.tracks()`, `track(name)`, `add_instrument_track`, `add_preset_track`, `remove_track`. 트랙마다 `param("vol" | "pan")`, `plugin_param(name)`, `shaping_param("fcut")`, `fx`(트랙 자체의 이펙트 체인), `patterns()`, `notes()`, `add_pattern`, `clear_patterns`.
- 믹서: `project.mixer.channels()`, `add_channel`, `fx(n)`, `volume(n)`, `send(a, b, amount)`.
- 시간은 박 단위다. 템포는 `project.bpm`.
- `lmmskit.mix.balance`와 `master_to_loudness`는 어떤 프로젝트에도 동작한다. `balance`는 악기 트랙만 움직이고, 그대로 둔 Beat/Bassline 트랙과 샘플 트랙을 목표와의 차이와 함께 `not_adjusted` 아래에 나열한다. 사용자의 프로젝트에서는 제안으로 내놓고, 무엇이든 교체하기 전에 전후를 비교한다(`visual.compare_spectrograms`와 두 리포트).
- 외부 프로젝트를 곡 스크립트의 편의 기능(섹션, 리프, 사이드체인 오토메이션)으로 확장하려면 위처럼 `Project` 호출로 새 트랙을 쓴다. `Song`은 프로젝트를 처음부터 만들며 기존 프로젝트를 감싸지 않는다.
- 수정할 때마다 렌더하고, `check`를 돌리고, 그림을 본다. XML에서 맞아 보이는 수정이 오디오에서는 무음일 수 있다.

변경은 최소로 하고 목록으로 남긴다. 사용자가 무엇이 바뀌었는지 정확히 읽을 수 있어야 한다. 추가된 트랙, 어느 마디의 음표가 바뀌었는지, 어느 채널에 이펙트가 더해졌는지, 레벨이 몇 dB 움직였는지를 적는다.

## 내보내기 형식

| 형식 | 명령 | 담는 것 | 용도 |
|---|---|---|---|
| 오디오 | `render song.mmp -o out.ogg`(`.mp3`, `.flac`, `.wav`) 또는 `produce`가 쓰는 파일 | 믹스 | 감상, 공개. ogg, mp3, flac에는 `ffmpeg`가 필요 |
| LMMS 프로젝트 | `.mmp` 자체, 또는 `export --mmp copy.mmpz` | 전부 | LMMS에서 이어서 작업 |
| 휴대용 프로젝트 | `pack song.mmp -o song.zip` | 프로젝트, plan 파일, 쓰이는 샘플, 복사 위치 안내 | 다른 LMMS 사용자에게 보내기. 보이스뱅크는 포함되지 않는다 |
| MIDI | `export song.mmp --midi song.mid` | 템포와 음표, 파트당 트랙 하나. 드럼은 채널 10에 General MIDI 음 번호로. 부른 멜로디는 음표로 | 모든 DAW나 악보 프로그램. 음색은 실리지 않는다 |
| DAWproject | `export song.mmp --dawproject song.dawproject --stems stems/` | 템포, 음표 트랙, `--stems`가 있으면 렌더된 파트마다 오디오 트랙 하나 | Bitwig Studio, Studio One, Cubase 등 이 형식을 읽는 DAW. `xmlschema`가 설치되어 있으면 공식 스키마로 파일을 검증한다. LMMS 악기와 이펙트는 옮겨지지 않는다. 스템이 소리를 싣고, 음표로 음색을 다시 입힐 수 있다 |
| JSON | `export song.mmp --json song.json`, 되돌리기는 `import-json song.json -o song.mmp` | 프로젝트 전체, 무손실 | 비교, 버전 관리, 다른 도구의 처리 |

곡을 다른 DAW로 옮길 때는 MIDI와 스템을 둘 다 준다(또는 스템이 든 DAWproject). 신스 패치와 이펙트는 따라가지 않는다는 점을 분명히 말한다.

## 자료 들여오기

- MIDI 파일: `export.read_midi_notes(path)`가 트랙별 음표를 박 단위로 돌려준다. `add_pattern`이나 `part.notes`로 트랙에 놓고 음색을 고른다.
- 오디오(녹음된 보컬, 사용자 소유의 루프): 프로젝트 옆 `samples/` 아래에 복사하고 `song.add_audio(name, "folder/file.wav", role=...)`와 `song.place_audio(part, at, seconds)`로 배치하거나, 악기 트랙에서 `sounds.sample(path)`를 쓴다. 루프의 템포 맞춤은 자료에 달려 있다. 이 툴킷은 임의의 오디오를 타임스트레치하지 않는다.
- 다른 프로젝트의 트랙: 두 프로젝트를 불러 `<track>` 요소를 복사하거나, `track.notes()`로 스크립트에서 파트를 다시 만든다.

## 알아 둘 파일 사실

- 박당 48틱. LMMS의 키 번호는 MIDI에서 12를 뺀 값이다(툴킷이 변환한다. 이 API의 모든 음높이는 MIDI 번호이며 가온 다 = 60).
- 음표 볼륨은 0-200이며 100이 기준이다. 트랙 볼륨도 같다.
- LMMS 1.2에서 "샘플 트랙"의 오디오 클립은 믹서 채널을 거치지 않으므로 툴킷은 샘플 플레이어 악기 트랙으로 오디오를 재생한다. 외부 프로젝트의 샘플 트랙은 그대로 둔다.
- 이펙트는 입력 없이 "decay" 시간이 지나면 꺼진다. 툴킷이 그 값을 최대로 두어 딜레이와 리버브 잔향이 끝까지 울리게 한다.
- LMMS는 마지막 클립 뒤 한 마디까지 렌더한다. `Project.set_length`나 `song.tail_bars`가 잔향을 위한 여유를 더한다.
- 상대 샘플 경로는 LMMS 기본 샘플과 프로젝트 옆 `samples/`를 기준으로 해석된다.
