# 장르 라이브러리

## 사용 방법
- 목록 : `python scripts/studio.py genres`
- 장르 관습 열람 : `python scripts/studio.py genres uplifting_trance`
    + 리듬, 베이스, 화성, 선율, 편곡, 믹스 순서로 그 장르의 관습을 서술
    + 작곡 전에 반드시 읽고 시작
- 스타터 곡 생성 : `python scripts/studio.py new futurepop -o song.yaml --title "..." --bpm 128 --key "A minor"`
    + 장르의 표준 악기, 패턴, 구성이 들어 있는 완결된 곡 파일
    + 코드와 선율이 로마 숫자와 차수로 적혀 있어 어떤 조에서도 동작
- 스타터는 출발점
    + 그대로 전달하면 모든 곡이 같아지므로 선율, 진행, 구성, 필인을 곡의 기획에 맞게 다시 작성
    + 길이도 기획에 맞게 섹션을 추가하여 확장
- 곡 파일의 `genre` 값이 믹스 프로필과 QA 기준을 결정
    + 스타터를 쓰지 않고 처음부터 작성해도 `genre`는 지정

## 수록 장르

| 계열 | 장르 id (기본 bpm) |
|---|---|
| 하우스 | house (124), deep_house (120), tech_house (126), progressive_house (126), acid_house (122), electro_house (128), big_room (128), disco (118), uk_garage (132) |
| 테크노 | techno (132), acid_techno (140), dub_techno (122), industrial_techno (142) |
| 트랜스 | trance (138), uplifting_trance (138), psytrance (145), dark_psy (150), eurodance (138) |
| 브레이크비트 | breakbeat (132), big_beat (126), dnb (174), liquid_dnb (174), neurofunk (174), jungle (165) |
| 베이스 뮤직 | dubstep (140), future_bass (150) |
| 하드코어 | gabber (180), hardstyle (150), happy_hardcore (170) |
| 인더스트리얼 | ebm (120), industrial (110) |
| 팝 | synthpop (118), futurepop (128) |
| 레트로 | synthwave (100), darksynth (115), italo_disco (120), electro (128), doomer (156), chiptune (150), vaporwave (80) |
| 힙합 | hiphop (90), lofi_hiphop (78), trap (140), trip_hop (84) |
| 실험 | idm (140), ambient (70) |
| 관현악 보조 | cinematic (110) |

## 목록에 없는 장르
- 가장 가까운 장르에서 출발
    + 템포, 드럼 패턴, 베이스 방식이 가장 비슷한 장르를 고름
    + 그 장르의 스타터를 만든 뒤 차이 나는 요소를 수정
- 두 장르의 혼합 요청은 뼈대 장르 하나를 정하고 다른 장르의 특징 요소를 얹음
    + 뼈대 : 드럼, 베이스, 템포
    + 얹는 요소 : 리드 음색, 화성, 구성
- 장르 관습을 모르면 추측하지 않음
    + 사용자에게 레퍼런스 곡이나 특징을 질의
    + 웹 검색이 허용된 환경이면 템포, 리듬, 대표 음색, 구성을 조사한 뒤 진행

## 장르 파일 구조
```yaml
name: Futurepop
family: pop
summary: 한 줄 요약
bpm: [122, 136, 128]          # 최소, 최대, 기본
keys: [A minor, D minor]      # 자주 쓰는 조
about: |                      # 장르 관습 서술
  Rhythm: ...
profile:                      # 믹스 프로필
  master: {lufs: -9.5}
  roles: {pad: {duck: -6}, vocal: {reverb: 0.2}}
  returns: {reverb: {decay: 2.4}}
  buses: {music: [{fx: lofi, wow: 0.25}]}
  qa: {slope_db_per_octave: [-5.5, -0.7]}
song:                         # 스타터 곡 (곡 파일과 같은 문법)
  chords: {...}
  tracks: {...}
  sections: [...]
```
- `extends: house`처럼 부모 장르를 지정하면 부모 장르와 다른 부분만 작성
- 새 장르를 추가하려면 `assets/genres/`에 같은 구조의 파일을 추가
    + 추가 후 `new`로 스타터를 만들고 `lint`와 `render`로 검증
