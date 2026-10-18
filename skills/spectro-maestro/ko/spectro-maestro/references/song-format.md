# 곡 파일 문법

## 파일의 역할
- 곡 한 개는 YAML 파일 한 개로 작성
    + 작곡 단계의 모든 결정(조, 템포, 코드, 패턴, 구성, 가사, 믹스 설정)을 이 파일에 기록
    + `render`가 이 파일을 평탄화한 `*.project.json`을 함께 저장하므로 같은 결과를 언제든 재현 가능
- YAML 불리언은 `true`와 `false`만 인식
    + `on`, `off`, `yes`, `no`는 문자열로 읽히므로 파트 이름으로 사용 가능
- 오류는 위치와 함께 한 줄로 보고됨
    + 예시 메시지 : `tracks.vox.parts.v1.lyrics[1]: bar line reached at beat 4.5`

## 최상위 키
| 키 | 필수 | 내용 |
|---|---|---|
| `title`, `artist`, `notes` | 선택 | 메타 정보, `notes`에 기획 의도 기록 |
| `genre` | 권장 | 장르 id, 해당 장르의 믹스 프로필과 QA 기준이 적용됨 |
| `bpm` | 필수 | 고정 템포 (곡 중간 템포 변경은 미지원) |
| `key` | 필수 | `A minor`, `F# dorian` 형식 |
| `meter` | 선택 | 한 마디의 박 수, 기본 4 |
| `seed` | 선택 | 난수 기준값, 같은 값이면 같은 결과 |
| `swing`, `swing_step` | 선택 | 짝수 번째 스텝을 늦추는 양(스텝 길이 대비 비율), 스텝 길이 기본 0.25박 |
| `humanize` | 선택 | `{timing_ms: 6, velocity: 0.04}` 형식의 미세 흔들림 |
| `ending` | 권장 | 곡의 끝 처리, `hit` 또는 `fade` (아래 항목 참조) |
| `chords` | 권장 | 이름 붙인 코드 진행 모음 |
| `tracks` | 필수 | 트랙 정의 |
| `sections` | 필수 | 곡 구성, 위에서 아래 순서로 연주 |
| `patches` | 선택 | 곡 전용 악기 정의 |
| `mix`, `master` | 선택 | 리턴 이펙트 설정과 마스터 설정 |

- 사용 가능한 선법 : major, minor, dorian, phrygian, lydian, mixolydian, locrian, harmonic_minor, melodic_minor, phrygian_dominant

## 코드 진행
- 마디는 `|`로 구분
    + `Am | F | C G | %` : 한 마디에 코드가 2개면 마디를 균등 분할, `%`는 직전 마디 반복
    + `Am:3 G:1` : 박 수를 직접 지정
- 절대 표기와 로마 숫자 표기를 모두 지원
    + 절대 표기 : `Am7`, `F#m/C#`, `Csus4`, `Gadd9`
    + 로마 숫자 : `i | VI | III | VII`, 소문자는 단화음
    + 임시표 없는 로마 숫자는 곡의 음계를 따름 (A minor의 `VI`는 F)
    + 임시표 있는 로마 숫자는 장음계 기준으로 읽음 (A minor의 `bVI`도 F)
- 로마 숫자로 쓰면 `key` 한 줄만 바꿔 곡 전체를 이조 가능
- 지원 코드 종류 : maj, m, 5, dim, aug, sus2, sus4, 6, m6, 7, maj7, m7, mmaj7, dim7, m7b5, 7sus4, add9, madd9, 9, maj9, m9, 11, m11

## 트랙
```yaml
tracks:
  bass:
    inst: bass_fm          # 악기 이름, 또는 {base: bass_fm, filter: {cutoff: 900}} 형식의 수정본
    role: bass             # 믹스 역할
    octave: 2              # 선택, 파트에서 재지정 가능
    mix: {gain_db: -2}     # 선택
    parts:
      main: {grid: "1 . 1 . 1' . 1 ."}
```
- `role`이 음량, 버스, 리버브 양, 사이드체인 깊이를 결정
    + 드럼 계열 : kick, snare, hat, perc
    + 저역 계열 : bass, sub
    + 선율 계열 : lead, pluck, arp
    + 화성 계열 : pad, chord, keys
    + 기타 : fx, vocal, backing
- `parts`에 이름 붙인 패턴을 여러 개 정의한 뒤 섹션에서 골라 연주
- 파트 공통 옵션
    + `vel` : 파트 전체 세기 배율
    + `gate` : 음 길이 비율, 기본 0.9
    + `octave`, `transpose` : 음역 이동
    + `step` : 스텝 길이(박), 기본 0.25 (16분음표)
    + `loop: false` : 섹션 시작에서 한 번만 연주
    + `swing` : 파트별 스윙

## 드럼 표기 (hits)
- 문자 하나가 스텝 하나
    + `x` 보통, `X` 강하게, `o` 약하게, `.` 쉼
    + `r` 2연타, `t` 3연타
- `|`로 마디를 나누면 스텝 수가 검사됨
```yaml
kick:  {hits: "x...x...x...x..."}
snare: {hits: "....x.......x...|....x.......x.xx"}   # 2마디 패턴, 둘째 마디 끝에 필인
```
- 패턴은 섹션 길이만큼 반복됨
    + 8마디 섹션의 마지막 마디에만 필인을 넣으려면 8마디 길이 패턴으로 작성
- `note: E4` 옵션으로 드럼 음높이 이동 가능
    + C4가 원래 음높이, 반음 단위로 위아래 이동

## 코드 기준 표기 (grid)
- 스텝마다 토큰 하나, 숫자는 현재 코드의 구성음 차수
    + `1 3 5 7` : 코드의 근음, 3음, 5음, 7음
    + `2 4 6` : 코드 근음 위의 음계음
    + `b3`, `b7`, `#4` : 임시표가 붙은 차수는 코드 근음 위 장음계 기준
    + `c` : 코드 전체를 부드러운 성부 진행으로 보이싱
- 꾸밈 기호
    + `'` 한 옥타브 위, `,` 한 옥타브 아래
    + `!` 악센트, `?` 고스트
    + `-` 앞 음 연장, `.` 쉼
    + `~` 다음 음으로 슬라이드 (모노 신스), `-~` 연장 후 슬라이드
```yaml
bass: {grid: ". 1 1 1 . 1 1 1 . 1 1 1 . 1 1 1"}          # 킥 자리를 비운 롤링 베이스
acid: {grid: "1 1' 1~ b3 1 . 1'! 1 5~ 5 1 1'! . b3 1 b7,!"}
pad:  {grid: "c - - - - - - - - - - - - - - -"}          # 한 마디 동안 코드 유지
```
- 코드가 바뀌면 같은 패턴이 새 코드를 따라감
    + 베이스 역할의 `1`은 슬래시 코드의 베이스음을 따름
- 베이스 역할은 `octave`를 생략하면 근음을 E1 이상 가장 낮은 자리에 배치

## 선율 표기 (line)
- `음:박수` 형식의 토큰을 나열
    + 음이름 : `C4`, `F#3`, `Bb4` (대문자만 음이름으로 인식)
    + 차수 : `5`, `b3`, `1'`, `7,` (곡의 음계 기준, 임시표가 붙으면 장음계 기준, `'`는 한 옥타브 위, `,`는 한 옥타브 아래)
    + 쉼표 : `r:1`
    + 화음 : `[C4 E4 G4]:2`
    + 박수 생략 시 직전 값을 사용
- `|`는 마디 검사선
    + 마디 경계가 맞지 않으면 오류로 보고되므로 박 계산 실수를 즉시 발견 가능
- `~`로 앞뒤 음을 이음 (예시 : `E4:1~D4:1`)
    + 보컬에서는 이은 음들을 한 음절로 부름
- 음 뒤에 `!`를 붙이면 강하게(악센트), `?`를 붙이면 약하게(고스트) 연주
```yaml
lead: {line: "5:1.5 3:.5 5:1 1':1 | 1':1.5 7:.5 6:2", octave: 4}
```

## 가사 파트 (lyrics)
```yaml
vox:
  role: vocal
  vocal: {engine: kokoro, voice: af_heart}
  layers:
    - {type: double, sections: [chorus]}
    - {type: harmony, steps: 2, sections: [chorus]}
  parts:
    verse:
      octave: 4
      lyrics:
        - {bar: 1, text: "Cold light upon the station wall", notes: "r:.5 E4:.5 E4:.5 D4:.5 E4:.5 D4:.5 C4:.5 D4:.5 | C4:3 r:1"}
        - {bar: 3, text: "I count the trains that never slow", notes: "r:.5 E4:.5 G4:.5 E4:.5 E4:.5 D4:.5 E4:.5 D4:.5 | D4:3 r:1"}
```
- 한 항목이 가사 한 줄
    + `bar`, `beat` : 섹션 안에서 줄이 시작하는 위치
    + `text` : 가사
    + `notes` : 선율 표기, 음 하나가 음절 하나
    + `phonemes` : 엔진의 발음 기호를 직접 지정 (선택)
- 음절 수와 음 수가 다르면 `lint`가 단어별 음절 수와 함께 보고
- 한 음절을 여러 음으로 부르려면 음 사이를 `~`로 이음
- 보컬 설정과 가사 작성 규칙은 `vocals.md` 참조

## 섹션
```yaml
sections:
  - name: chorus1
    type: chorus            # intro verse prechorus build drop chorus break bridge outro
    bars: 16
    chords: chorus          # 진행 이름 또는 진행 문자열
    energy: 0.9             # 선택, 0-1의 기획 에너지
    play: {kick: four, bass: oct, pad: hold, vox: chorus, piano: [theme, chords]}
    rise: {riser: 4, snare_roll: 2}     # 섹션 끝으로 향하는 효과, 숫자는 마디 수
    hit: [impact, crash]                # 섹션 첫 박의 효과
    gap: {kick: 4}                      # 섹션 마지막 N박 동안 해당 트랙 비움
    auto: {pad: {lpf: [600, 9000]}, master: {volume: [0, -12]}}
    vel: {pad: 0.7}                     # 이 섹션에서만 세기 배율
    transpose: 2                        # 이 섹션만 반음 단위 이조
```
- `play`에 적은 트랙만 그 섹션에서 연주
    + 한 트랙에 파트 여러 개를 리스트로 겹칠 수 있음
- `rise` 종류 : riser, snare_roll, reverse_crash, noise_sweep
- `hit` 종류 : impact, crash, downlifter, sub_drop
- `auto`는 섹션 시작값에서 끝값으로 직선 이동
    + 대상 파라미터 : `lpf`(Hz), `hpf`(Hz), `volume`(dB)
    + `master`를 대상으로 지정하면 전체 믹스에 적용
    + 구간이 끝난 뒤에도 끝값이 그 트랙의 다음 음이 시작될 때까지 유지됨 (닫힌 필터가 잔향에서 다시 열리지 않음)
- `energy`는 QA에서 실제 섹션 음량 순위와 비교됨

## 곡의 끝 처리
- `ending: hit` : 마지막 섹션 뒤에 2마디짜리 끝맺음을 자동으로 붙임
    + 으뜸화음의 첫 박을 킥, 베이스, 패드, 크래시로 한 번 치고 2마디에 걸쳐 감쇠
    + 곡에서 이미 쓰고 있는 트랙만 사용
    + 마지막 섹션이 으뜸화음이 아닌 코드로 끝나는 곡에 적합
- `ending: fade` : 마지막 4마디를 페이드아웃
    + 반복형 아웃트로에 적합
- 길이 지정 : `ending: {type: fade, bars: 8}`
- 직접 끝맺음 섹션을 쓰는 경우는 `ending`을 생략
    + 마지막 화음은 `auto: {master: {volume: [0, -36]}}`로 감쇠시키면 자연스러움
- 아무 처리 없이 마지막 마디까지 가득 연주하면 곡이 뚝 끊김
    + `lint`의 `structure.no_ending`과 QA의 `ending_drop_db`가 이 경우를 알림
- 마지막 마디 뒤의 잔향은 `master.tail` 초 동안 서서히 줄어들며 소리가 끝난 뒤 0.4초에서 파일이 끝남

## 트랙별 믹스 설정
| 키 | 내용 |
|---|---|
| `gain_db` | 역할 기본 음량에서 가감 (가장 자주 쓰는 손잡이) |
| `level` | 역할 기본 음량 자체를 교체 |
| `pan`, `width` | 좌우 위치(-1에서 1), 스테레오 폭(0에서 1) |
| `reverb`, `delay` | 리턴으로 보내는 양 (0에서 1) |
| `duck` | 킥에 맞춘 사이드체인 깊이(dB, 음수) |
| `hpf`, `lpf` | 트랙 필터 (Hz) |
| `mono` | 모노로 고정 |
| `inserts` | 이펙트 체인, 예시 `[{fx: dist, drive: 0.4}, {fx: chorus, mix: 0.4}]` |
| `mute` | 트랙 끄기 |
| `dry` | 보컬 전용, 기본 보컬 체인 생략 |

## 곡 전체 믹스 설정
```yaml
mix:
  returns:
    reverb: {decay: 2.6, damp: 5000}
    delay: {time: 1/8d, feedback: 0.4}
    vox_reverb: {decay: 2.2}
  sidechain_source: kick      # 선택, 사이드체인 기준 트랙
master:
  lufs: -10                   # 목표 음량
  ceiling: -1                 # 트루 피크 상한 (dBTP)
  eq: [[highshelf, 9000, 1.5]] # 밴드 표기는 sound.md의 eq 참조
  vocal_carve: -2.5           # 보컬이 있을 때 반주의 1.3-5 kHz를 덜어내는 양
  fade_out: 8                 # 곡 끝 페이드 길이(박)
  tail: 3                     # 곡 끝 잔향 여유(초)
```
- 시간 값은 초 단위 숫자 또는 음표 값으로 지정
    + `1/4`, `1/8`, `1/16` : 음표 길이
    + `1/8d` : 점음표, `1/8t` : 셋잇단

## 곡 전용 악기
```yaml
patches:
  my_bass: {base: bass_reese, filter: {cutoff: 500}, drive: 0.5}
tracks:
  bass: {inst: my_bass, role: bass, parts: {...}}
```
- 악기 목록과 패치 파라미터는 `sound.md` 참조

## 부분 렌더
- `render --sections chorus1,verse2` : 지정 섹션만 렌더
- `render --only kick,bass` : 지정 트랙만 렌더
- 전체 렌더 전에 한 섹션으로 음색과 균형을 먼저 확인하면 반복 시간이 크게 감소
