# 예제 곡

## 수록곡

| 폴더 | 곡 | 장르 | 보컬 | 길이 |
|---|---|---|---|---|
| `first_light/` | First Light | 업리프팅 트랜스, 138 bpm, F# minor | 없음 | 7:16 |
| `signal_fires/` | Signal Fires | 퓨처팝, 128 bpm, A minor | Kokoro `af_heart` | 3:50 |
| `last_tram/` | Last Tram | 두머, 156 bpm, E minor | Kokoro `am_michael` | 3:04 |
| `silver_box/` | Silver Box | 애시드 하우스, 124 bpm, G minor | 없음 | 4:12 |

- 폴더마다 곡 파일(`.yaml`)과 MIDI 수록
    + 보컬곡은 가사(`lyrics.txt`) 포함
- 음원은 싣지 않았으며 곡 파일을 렌더하면 같은 소리가 나옴
- 모든 악기 소리는 이 스킬이 합성하며 샘플을 쓰지 않음

## 다시 렌더하기
- 출력 폴더를 스킬 밖으로 지정
    + `python scripts/studio.py render examples/silver_box/silver_box.yaml -o <작업 폴더>/silver_box_out`
- 보컬곡은 보컬 패키지와 Kokoro 모델이 필요
- 같은 곡 파일은 같은 소리를 냄

## 저작권과 라이선스
- 음악, 가사, 곡 파일 : Copyright (C) 2026 Em Dash Smoker
- 이 스킬의 일부로서 AGPL-3.0-or-later로 제공 (`../LICENSE`)
- Signal Fires와 Last Tram의 보컬은 렌더할 때 Kokoro-82M TTS 모델(Apache-2.0)로 합성됨
- 자세한 고지는 `../THIRD-PARTY-NOTICES.md`
