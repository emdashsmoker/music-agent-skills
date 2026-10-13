# 작곡: 곡을 스크립트로 쓰기

곡은 `lmmskit.compose.Song`을 쓰는 짧은 Python 스크립트다. 실행하면 보통의 LMMS 프로젝트(`.mmp`)와 그 옆에 작은 파일 3개가 생긴다. `<이름>.plan.json`(조성, 섹션, 코드, 파트 역할)이 있고, 보컬 곡에는 `<이름>.vocals.json`과 `<이름>.lyrics.txt`가 더해진다. 스크립트를 보관한다. 스크립트가 곡의 원본이며, 이후의 모든 변경은 스크립트를 고쳐 다시 실행하는 방식으로 한다.

## 목차

- 곡 스크립트의 뼈대
- 위치와 시간
- 파트와 역할
- 음표 쓰기 (5가지 표기법)
- 코드와 화성
- 움직임: 사이드체인, 스윕, 페이드, 라이저, 임팩트
- 편곡 요령
- 보컬 파트
- 휴머나이즈와 스윙
- lint가 점검하는 것

## 곡 스크립트의 뼈대

```python
import os, sys
sys.path.insert(0, "<스킬 폴더>/scripts")
from lmmskit.compose import Song

song = Song("Night Drive", 128, "A minor", "house")          # 제목, bpm, 조성, 장르 프로파일
song.structure([("intro", 8), ("verse", 16), ("drop", 16), ("outro", 8)])
chords = song.chords("drop", "Am F C G", repeats=4)          # lint용 화성을 선언하고 코드 기호를 돌려준다

kick = song.add("kick", "house_kick")
hat = song.add("hat", "909_hat")
bass = song.add("bass", "moog_bass")
pad = song.add("pad", "warm_pad")

kick.hits("drop", "x---x---x---x---", bars=16)
hat.hits("drop", "--x---x---x---x-", bars=16)
bass.riff("drop", chords, ". . R . . . R . . . R . . R . 8", octave=1)
pad.chords("drop", chords, octave=3)

song.sidechain("kick", ["bass", "music"], depth_db=6)
song.master()                                                # 마지막에 한 번 호출
print(song.save(os.path.join(os.getcwd(), "night_drive.mmp")))
```

`Song.save()`는 곡이 쓰는 드럼 원샷을 프로젝트 옆 `samples/kit/`에 설치하고(킷이 아직 없으면 이 컴퓨터에서 먼저 만든다. `setup.md` 참조), 보컬 파트를 렌더하고, 파일들을 쓴다. 섹션 이름은 겹치면 안 된다(`drop1`, `drop2`).

## 위치와 시간

무언가를 배치하는 모든 메서드는 위치 `at`을 3가지 형태 중 하나로 받는다. 섹션 이름(`"drop"`), 그 섹션의 4마디 지점을 뜻하는 튜플 `("drop", 4)`, 0부터 세는 절대 마디 번호다. 리포트와 LMMS는 마디를 1부터 세므로 리포트의 "bar 33"은 여기서 32번 마디다. 음 길이와 스텝은 박 단위다(4분음표가 1, 16분음표가 0.25).

## 파트와 역할

`song.add(name, patch, role=None, level_db=0.0, pan=0.0, sends=None, highpass=None, strip=True)`는 자기 믹서 채널을 가진 LMMS 악기 트랙 하나를 만든다.

- `patch`는 음색 라이브러리의 이름(`lmms_tool.py sounds`가 역할별로 나열)이거나 패치 딕셔너리다(`sounds-effects.md` 참조).
- `role`의 기본값은 패치의 역할이다. 역할이 버스(drums, bass, music, vocals), 표준 채널 처리(하이패스, 킥과 서브의 모노), 기본 리버브와 딜레이 센드, 자동 밸런스가 목표로 삼는 레벨을 정한다. 역할 목록: kick, snare, clap, hat, cymbal, perc, sub, bass, lead, pluck, pad, keys, fx, vocal, vocal_bg.
- `level_db`는 역할의 통상 레벨에 대한 오프셋이다. 의도를 표현할 때 쓴다("이 패드는 더 뒤에 있어야 한다": `level_db=-3`). 절대 볼륨을 손으로 정하지 않는다. 밸런스 단계가 측정해서 정한다.
- `sends`는 역할의 기본 센드를 대체한다. 예: `{"reverb": 0.4, "delay": 0.2}`.

역할은 믹스 결정이므로 기능에 따라 준다. 훅을 맡은 아르페지오는 `role="lead"`로 둘 수 있다. 높은 음역에서 연주하는 두 번째 베이스 라인은 `bass`보다 `lead`나 `pluck`이 낫다.

## 음표 쓰기 (5가지 표기법)

| 메서드 | 용도 | 예 |
|---|---|---|
| `part.hits(at, grid, bars, pitch=None, step=0.25, vol=100, swing=0.0)` | 드럼 | `"x---x---x---x---"`: `x` 타격, `X` 악센트, `o` 고스트, `-` 쉼. 그리드는 `bars`를 채울 때까지 반복된다. |
| `part.seq(at, text, bars=None, step=0.25, octave=3, gate=1.0, vol=100)` | 음이름으로 쓰는 멜로디와 베이스 라인 | `"A2 . . C3 _ _ . E3"`: 음이름은 연주, `.` 쉼, `_` 유지, `[A2 C3 E3]`는 화음, 마디선은 선택. |
| `part.riff(at, symbols, pattern, bars_each=1.0, step=0.25, octave=2, gate=1.0)` | 코드를 따라가는 하나의 패턴 | `"R . R 5 8 _ 5 ."`: `R` 근음, `3`, `5`, `7`, `8`(옥타브), 접미사 `+`/`-`는 옥타브 이동, `!` 악센트, `?` 고스트. |
| `part.chords(at, symbols, bars_each=1.0, octave=3, rhythm=None, gate=0.95)` | 패드, 스탭, 건반 | `rhythm=None`은 코드를 길게 유지한다. `rhythm="x--x--x---x--x--"`는 스탭으로 친다. 보이싱은 코드에서 코드로 매끄럽게 이어진다. |
| `part.notes(at, [Note(start, length, pitch, vol)])` | 그 밖의 모든 것 | `Note`는 `lmmskit.project`에 있다. start는 클립 시작부터의 박이다. `theory.note("E5")`가 음높이 번호를 준다. |

추가로 `part.roll(at, bars)`는 점점 촘촘해지고 커지는 빌드업 롤을 쓰고, `part.loop(at, notes, bars, unit_bars)`는 프레이즈를 이어 붙인다.

베이스와 서브 리프는 E1(41 Hz) 아래로 내려가지 않는다. 근음이 그보다 낮아질 코드는 한 옥타브 위로 연주한다. 더 낮은 기음은 대부분의 스피커에서 사라지기 때문이다. 의도적으로 바꾸려면 `floor=`를 넘긴다.

드럼 원샷은 샘플 전체 길이만큼 자동으로 유지된다.

## 코드와 화성

- `song.chords(at, "Am F C G", bars_each=1.0, repeats=1)`은 화성이 무엇인지 선언한다. lint가 이를 써서 베이스 음과 긴 멜로디 음을 점검한다. 전체 구간(진행 × `repeats`)에 대해 코드마다 기호 하나를 돌려주며, 파트의 `riff`와 `chords`가 이 형태를 받는다.
- 조성과 함께 로마 숫자를 쓸 수 있다. `theory.progression("i VI III VII", "A minor")`는 `["Am", "F", "C", "G"]`를 준다.
- 코드 기호: 장3화음, `m`, `7`, `maj7`, `m7`, `dim`, `aug`, `sus2`, `sus4`, `add9`, `m9`, `9`, 슬래시 베이스(`C/E`).
- 선법도 조성으로 받는다: `"A phrygian"`, `"D dorian"`, `"E harmonic minor"`.

멜로디는 코드에 맞춰 쓴다. 긴 음과 강박의 음은 코드 구성음이어야 하고, 경과음은 약박에 둔다. lint가 예외를 마디 번호와 함께 보고한다.

## 움직임: 사이드체인, 스윕, 페이드, 라이저, 임팩트

- `song.sidechain(source="kick", targets=["bass", "music"], depth_db=6.0, hold_beats=0.05, release_beats=0.4)`는 소스가 칠 때마다 대상(버스나 파트 이름)을 눌러 준다. 소스의 음표에서 뽑은 볼륨 오토메이션으로 쓰이므로 모든 렌더가 동일하다. `song.pump(at, grid, bars)`는 킥이 없는 곳에 더킹을 더해 브레이크다운의 패드가 계속 숨 쉬게 한다.
- `song.sweep(target, at, bars, start_hz, end_hz, kind="lowpass", resonance=0.9, rest_hz=None)`은 파트나 버스의 필터를 오토메이션한다. 빌드업 동안 로우패스를 여는 것과 아웃트로로 닫는 것이 표준 용법 2가지다.
- `song.fade(target, at, bars, start_db, end_db, rest_db=0.0)`은 파트나 버스의 레벨을 서서히 바꾼 뒤 `rest_db`로 건너뛴다. 곡 끝의 페이드아웃에는 `rest_db=-60`을 넘긴다.
- `song.riser(at, bars, level_db=0.0)`은 `at + bars`에서 끝나는 필터드 노이즈 라이저를 놓는다. `song.impact(at, level_db=0.0)`은 첫 박에 크래시와 서브 드롭을 놓는다. 모든 라이저는 트랙 1개를, 모든 임팩트는 트랙 2개를 공유한다.
- `song.automate(param, [(bar, value), ...])`는 파라미터를 오토메이션한다. 이펙트 컨트롤(`fx.control(effect, "name")`), 트랙 볼륨이나 팬, 트랙 필터가 대상이다. 악기 자체의 노브도 오토메이션할 수 있지만 매번 같게 렌더되지 않는다(`sounds-effects.md`에 대상 목록이 있다).
- `song.tail_bars`(기본 2)는 리버브와 딜레이 잔향을 위해 마지막 마디 뒤에 남기는 여유다.

## 편곡 요령

아래 습관이 완성 트랙과 루프를 가른다. 판단의 출발점이 되는 기본값이며, 사용자의 취향이 어느 항목보다 우선한다.

- 8마디와 16마디 프레이즈로 생각한다. 프레이즈 경계마다 무언가 바뀌어야 한다. 파트가 들어오거나 나가고, 필터가 열리고, 필인이 나온다.
- 어느 순간이든 1-2개 파트가 전면을 맡는다. 나머지는 받쳐 준다. 보컬이 노래할 때 리드는 쉬거나 빈 곳에서 응답한다.
- 에너지에는 모양이 있다. 가장 크고 촘촘한 섹션은 뒤쪽에 온다(마지막 코러스, 클라이맥스). 브레이크다운은 킥과 베이스를 빼서 돌아올 때 무게가 실리게 한다.
- 전환을 표시한다. 마지막 마디의 필인이나 롤, 새 섹션으로 들어가는 라이저, 첫 박의 임팩트, 장르가 극적인 연출을 좋아하면 드롭 직전의 짧은 침묵을 쓴다.
- 저역에는 순간마다 주인을 하나만 둔다. 킥과 베이스는 사이드체인이나 리듬(킥 사이의 베이스 음)으로 저역을 나눠 쓴다.
- 반복에는 4마디나 8마디마다 변주가 필요하다. 고스트 노트 추가, 옥타브 도약, 오픈 햇, 달라진 마지막 마디가 그 예다. lint가 긴 구간을 변화 없이 반복하는 파트를 보고한다.
- 클럽 장르의 인트로와 아웃트로는 드럼 중심이고 16-32마디다. DJ가 믹스할 수 있게 하기 위해서다. 감상용 곡은 4-8마디 안에 훅으로 시작해도 된다.

## 보컬 파트

```python
vocal = song.vocal("lead vocal", "kokoro:af_heart")           # 또는 piper:<목소리>, diffsinger:<폴더>[#음색]
vocal.line(("verse", 0), "Empty roads below a paper sky", "E4/0.5 E4/0.5 G4/0.5 G4/0.5 A4/2 A4/0.5 G4/0.5 F4/0.5 E4/2")
vocal.harmony("harmony vocal", steps=2, only_kind="chorus", pan=20)
vocal.double("double vocal", only_kind="chorus", pan=-20)
song.duck_for_vocals(1.5, presence_db=3.0)
```

멜로디는 부르는 음절마다 토큰 하나를 가진다. 목소리, 표기법, 가사 쓰기, 점검에 관한 모든 내용은 `vocals.md`에 있다. 가사를 쓰기 전에 읽는다.

## 휴머나이즈와 스윙

`hits(..., swing=0.33)`은 16분음표를 하나 걸러 스텝의 3분의 1만큼 늦춘다. `theory.humanize(notes, seed, timing=0.01, volume=6)`은 시드가 고정된 작은 어긋남을 더한다. 항상 고정 시드를 넘긴다. 같은 스크립트는 같은 곡을 만들어야 한다.

## lint가 점검하는 것

`python scripts/lmms_tool.py lint song.mmp`는 음표와 plan 파일을 읽고 점검 결과를 마디 번호와 함께 보고한다. `ERROR`와 `WARN`은 컴파일러 메시지처럼 다룬다. 스크립트를 고쳐 다시 실행하거나, 의도한 것으로 판단하고 사용자 보고에 그렇게 적는다.

| 점검 결과 | 뜻 | 통상의 조치 |
|---|---|---|
| `out_of_scale`, `key_mismatch` | 선언한 조성 밖의 음이 있거나 다른 조성이 더 잘 맞는다 | 음을 고치거나 실제 조성이나 선법을 선언한다 |
| `bass_off_chord` | 코드가 바뀔 때 베이스가 코드 구성음에 놓이지 않는다 | 마디를 근음(또는 슬래시 베이스)으로 시작한다 |
| `avoid_note` | 강박의 긴 음이 코드 구성음의 반음 위에 있다 | 코드 구성음으로 옮기거나 짧게 줄여 경과음으로 만든다 |
| `semitone_clash` | 두 파트가 반음(또는 단9도) 간격의 음을 길게 낸다 | 둘 중 한 음을 바꾼다. 하모니 보컬은 자동으로 코드와의 충돌을 피한다 |
| `low_mud` | 약 C3 아래의 좁은 음정 | 그 음역에서는 단음이나 옥타브를 쓰고 화음은 위로 올린다 |
| `bass_too_low`, `bass_too_high`, `bass_polyphony`, `range` | 역할의 유효 음역을 벗어난 음 | 옥타브를 옮긴다 |
| `silent_bars`, `empty_tracks` | 아무것도 연주되지 않는 마디, 음표가 없는 트랙 | 대개 위치 지정 실수다. 드롭 직전의 의도된 침묵은 괜찮다 |
| `monotony` | 한 파트가 긴 구간을 변화 없이 반복한다 | 4마디나 8마디마다 변주를 넣거나 필터를 오토메이션한다 |
| `unrepeatable_automation`, `unrepeatable_peak_controller`, `unrepeatable_drumsynth`, 그리고 코어 1개 렌더가 안 되는 시스템의 `unrepeatable_kicker_noise` | LMMS가 실행마다 다르게 렌더하는 요소 | 메시지가 알려 주는 재현 가능한 대안을 쓴다(`sounds-effects.md` 참조) |
| `section_density` (info) | 섹션마다 연주되는 파트 수 | 의도한 에너지 곡선과 비교한다 |
