# 음색 선택

## 악기 확인 방법
- 이름 목록 : `python scripts/studio.py instruments`
- 단독 시청 : `python scripts/studio.py audition bass_303 --notes A1,A2,C2 --beats 1`
    + 파형과 스펙트럼 그림(`audition/<이름>.png`)과 수치(중심 주파수, 최대 성분 주파수, 지속 시간)를 출력
    + 소리를 들을 수 없으므로 그림과 수치로 음색을 확인
- 패치 수정 시청 : `--patch '{filter: {cutoff: 900, res: 0.6}}'`

## 드럼 악기
| 분류 | 이름 |
|---|---|
| 킥 | kick_909, kick_808, kick_house, kick_techno, kick_trance, kick_psy, kick_gabber, kick_hardstyle, kick_dnb, kick_linn, kick_lofi, kick_industrial, kick_break |
| 스네어 | snare_909, snare_808, snare_linn, snare_dnb, snare_trap, snare_break, snare_industrial, snare_lofi |
| 클랩 | clap_909, clap_808, clap_big, snap |
| 하이햇 | hat_closed_909, hat_open_909, hat_closed_808, hat_open_808, hat_closed_lofi, hat_pedal |
| 심벌 | ride_909, crash_909, splash |
| 퍼커션 | tom_low, tom_mid, tom_high, conga, timpani, rim_808, clave, cowbell_808, shaker, tambourine, metal_hit, anvil |
- 닫힌 하이햇이 울리면 같은 계열의 열린 하이햇이 자동으로 끊김
- 드럼 파라미터 수정 예시 : `inst: {base: kick_909, decay: 0.6, drive: 0.4}`
    + 킥 : `tune_hz`(몸통 음높이), `start_hz`, `sweep`(음높이 하강 시간), `decay`, `click`, `drive`
    + 스네어 : `tune_hz`, `tone`, `snappy`, `noise_decay`
    + 하이햇 : `decay`, `band_hz`, `metal`

## 전환 효과
- 섹션의 `rise`와 `hit`으로 사용
    + 상승 : riser, noise_sweep, reverse_crash, snare_roll
    + 타격 : impact, crash, downlifter, sub_drop

## 신스 악기
| 분류 | 이름 | 성격 |
|---|---|---|
| 베이스 | bass_303, bass_303_square | 슬라이드와 악센트에 반응하는 애시드 베이스 |
| 베이스 | bass_sub, bass_808 | 순수 저역, 808은 긴 꼬리 |
| 베이스 | bass_reese, bass_wobble, bass_hoover | 디튠된 중저역, 드럼앤베이스와 덥스텝용 |
| 베이스 | bass_moog, bass_fm, bass_pluck, bass_organ | 단단한 시퀀스 베이스 |
| 베이스 | bass_offbeat, bass_rolling | 트랜스 계열 뒷박 베이스와 롤링 베이스 |
| 베이스 | bass_picked, bass_saw_dist | 피크 베이스 기타 느낌, 왜곡된 톱니파 |
| 리드 | lead_supersaw, lead_saw, lead_square, lead_sine | 기본 리드 |
| 리드 | lead_acid, lead_psy, lead_hoover, lead_chip | 장르 특화 리드 |
| 리드 | lead_guitar, lead_guitar_dist, lead_fm_bell | 뜯는 현 느낌, 벨 |
| 플럭 | pluck_saw, pluck_square, pluck_supersaw, pluck_fm, pluck_string, arp_pulse | 짧은 감쇠음 |
| 패드 | pad_warm, pad_supersaw, pad_strings, pad_pwm, pad_dark, pad_glass, pad_choir, drone | 지속음 |
| 코드 | chord_stab, chord_supersaw, chord_rave | 짧은 화음 타격 |
| 건반 | keys_piano, keys_ep, keys_organ | FM 피아노, 일렉트릭 피아노, 오르간 |
| 기타 | brass_synth, strings_orch, bell_tubular | 관현악 보조 음색 (합성음) |
- 관현악 음색은 신스로 흉내 낸 보조 수단
    + 실제 악기 수준의 사실감은 기대하지 않음

## 패치 구조
- 엔진 5종
    + `sub` : 오실레이터 여러 개와 필터 (대부분의 음색)
    + `mono` : 단음, 슬라이드와 악센트 지원 (303 계열, 리스 베이스)
    + `fm` : 주파수 변조 (벨, 피아노, 금속성 베이스)
    + `pluck` : 뜯는 현 모델
    + `organ` : 배음 합산
- 공통 키
    + `amp: [attack, decay, sustain, release]` : 음량 엔벨로프(초, sustain은 0에서 1)
    + `drive` : 왜곡 양
    + `fx` : 패치 전용 이펙트 체인
    + `vibrato: {rate, depth, delay}` : depth는 센트
    + `pitch_env: {semis, time}` : 시작 음높이를 올렸다 떨어뜨림
- `sub`와 `mono`의 오실레이터 (`osc` 리스트)
    + `wave` : saw, square, pulse, tri, sine, noise
    + `voices`, `spread` : 유니즌 수와 퍼짐(센트)
    + `octave`, `semi`, `detune`, `level`
    + `pw`, `pwm_rate`, `pwm_depth` : 펄스 폭과 변조
- 필터 (`filter`)
    + `type` : lp, hp, bp
    + `cutoff`(Hz), `res`(0에서 1), `poles`(2 또는 4)
    + `env` : 필터 엔벨로프 깊이(옥타브), `fenv: [a, d, s, r]`
    + `track` : 음높이 추종, `vel` : 세기 추종
    + `lfo_rate`, `lfo_depth` : 느린 흔들림, rate에 `1/4` 같은 음표 값 사용 가능
- `mono` 전용
    + `glide` : 슬라이드 시간, `accent` : 악센트 때 필터가 더 열리는 양, `fenv_decay`
- `fm`의 연산자 (`ops` 리스트)
    + `ratio`, `mod_ratio`, `index`, `index_env`, `level`, `detune`
- `pluck` 전용
    + `decay`, `damp`, `pick`, `body`(기음 보강)

## 이펙트
| 이름 | 주요 파라미터 | 용도 |
|---|---|---|
| `eq` | `bands: [[peak, 3000, 2.5, 1.0], [highshelf, 9000, 3]]` | 밴드마다 [종류, 주파수(Hz), 이득(dB), Q], 이득을 생략하면 0, Q를 생략하면 0.707, 종류 : peak, lowshelf, highshelf, hp, lp, notch |
| `hpf`, `lpf` | `freq`, `poles` | 대역 정리 |
| `tilt` | `db_per_octave`, `pivot` | 전체 밝기 |
| `comp` | `threshold`, `ratio`, `attack`, `release`, `makeup`, `mix` | 음량 고르기 |
| `gate` | `threshold`, `release` | 잔향 자르기 |
| `soft_clip` | `drive_db` | 부드러운 포화 |
| `dist` | `drive`, `tone`, `mix`, `kind` | 왜곡 |
| `crush` | `bits`, `rate`, `mix` | 비트 감소 |
| `chorus`, `flanger`, `phaser` | `rate`, `mix` 외 | 움직임과 폭 |
| `tremolo` | `rate`, `depth` | 음량 흔들림 |
| `width` | `amount`, `mono_below` | 스테레오 폭 |
| `lofi` | `wow`, `noise_db`, `top` | 테이프 질감 |
| `delay` | `time`, `feedback`, `mix`, `pingpong` | 트랙 전용 딜레이 |
| `reverb`, `gated_reverb` | `decay`, `mix` | 트랙 전용 리버브 |
- 공간계는 트랙의 `reverb`와 `delay` 센드 사용이 기본
    + 인서트 리버브는 게이트 스네어처럼 그 트랙만의 효과가 필요할 때 사용
- 이펙트 체인의 주파수 응답 그림 : `python scripts/studio.py plot song.yaml --chain <트랙>`

## 음색 선택 지침
- 장르 파일의 스타터 곡이 그 장르의 기본 악기 조합
    + 같은 역할의 다른 악기로 바꿀 때는 `audition`으로 음역과 지속 시간을 먼저 비교
- 저역은 한 번에 하나
    + 킥과 베이스의 기음이 같은 대역에 오래 겹치지 않도록 킥의 `tune_hz`와 베이스 음역을 확인
- 같은 음역의 지속음은 두 개까지
    + 패드, 스트링, 슈퍼소 코드가 한 섹션에 모두 울리면 중역이 뭉침
- 필터 움직임이 선율을 대신하는 장르(애시드, 테크노 등)는 섹션의 `auto`로 `lpf`를 움직여 전개를 만듦
