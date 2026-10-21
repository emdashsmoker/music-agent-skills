---
name: spectro-maestro
license: AGPL-3.0-or-later
description: 전자음악 중심의 완성곡을 코드로 작곡, 편곡, 합성, 믹싱, 마스터링하여 mp3, ogg, wav, MIDI, DAW 프로젝트로 내보내는 음악 제작 스킬 '스펙트로 마에스트로'. 사용자가 곡, 노래, 비트, 트랙, BGM, 데모곡, 루프의 작곡이나 제작을 요청하거나 하우스, 테크노, 트랜스, 드럼앤베이스, 신스웨이브, 인더스트리얼, EBM, 퓨처팝, 싸이트랜스, 개버, IDM, 힙합, 트랩 같은 장르 이름을 언급하며 음악을 만들어 달라고 할 때 반드시 사용. 가사가 있는 보컬곡 제작(TTS 목소리의 가창 변환, 사용자가 제공한 DiffSinger 보이스뱅크), 가사 전달력 점검, 믹스 검수, 기존 곡 파일 수정, MIDI 가져오기, LMMS와 DAWproject 내보내기 요청에도 사용. 작업 중 해당 단계의 참조 문서를 반드시 읽을 것 - references/planning.md(기획 질의), references/song-format.md(곡 파일 문법, 필수), references/composition.md(작곡과 편곡, lint 해설), references/genres.md(장르), references/sound.md(악기와 이펙트), references/mixing-qa.md(렌더 후 검수, 필수), references/vocals.md(보컬 전 과정, 필수), references/export.md(내보내기, LMMS 확인). Use this skill whenever the user asks to compose, produce, arrange, mix or master music, write a song with vocals, or export a track, even if they only say "make me a beat" or "노래 만들어줘".
---

# 스펙트로 마에스트로 (Spectro Maestro)

## 라이선스와 고지
- 스펙트로 마에스트로, Copyright (C) 2026 Em Dash Smoker
- 이 스킬은 GNU Affero General Public License 버전 3 또는 그 이후 버전(AGPL-3.0-or-later)으로 배포되는 자유 소프트웨어
    + 전문은 `LICENSE`, 어떤 보증도 없음
    + 스킬을 수정하거나 재배포할 때는 같은 라이선스와 저작권 표시를 유지
- 이 스킬로 만든 산출물에는 이 라이선스가 적용되지 않음
    + 곡 파일, 오디오, MIDI, 스템, 프로젝트 JSON, LMMS 프로젝트, DAWproject, 그림, 보고서는 만든 사람의 것
    + 장르 파일과 스타터 곡에서 산출물로 옮겨진 내용도 AGPL 조건 없이 사용 가능 (AGPL 버전 3의 7조에 따른 추가 허용)
    + 보컬에 쓴 목소리 모델이나 보이스뱅크의 이용 조건은 산출물에 그대로 적용됨
- 서드 파티 고지
    + 스킬에 포함된 외부 자료는 DAWproject 스키마 파일 2개(Copyright (c) 2020 Bitwig, MIT)와 OpenUtau에서 옮긴 G2P 표(`scripts/foundry/g2p.py`, Copyright (c) 2014 StAkira, MIT)
    + 실행할 때 쓰는 패키지와 모델은 스킬에 들어 있지 않으며 각자의 라이선스를 따름
    + 주요 항목 : NumPy와 SciPy(BSD-3-Clause), pyworld와 ONNX Runtime과 faster-whisper(MIT), Kokoro-82M 모델(Apache-2.0), piper-tts와 phonemizer와 cmudict(GPL-3.0-or-later)
    + 전체 목록과 조건은 `THIRD-PARTY-NOTICES.md`
- 사용자가 라이선스를 물으면 이 절과 두 파일을 근거로 답함

## 스킬의 역할
- 곡 한 개를 YAML 곡 파일로 작성하고 명령줄 도구로 렌더하는 제작 환경
    + 작곡가는 곡 파일을 쓰고, 도구가 합성과 믹싱과 마스터링과 검수 자료 생성을 담당
    + 소리를 들을 수 없는 작업자를 전제로 설계되어 모든 판단 근거가 수치와 그림으로 제공됨
- 결과물은 처음부터 끝까지 완결된 곡
    + 팝과 보컬곡 3-4분, 클럽 장르 5-8분, 업리프팅 트랜스 7-15분
    + 도입, 전개, 절정, 마무리가 있는 구성
- 음원은 전부 내장 신시사이저와 드럼 머신 모델로 합성
    + 외부 샘플 없이 909, 808, 303 계열을 포함한 드럼 47종과 신스 49종 제공
    + 관현악 음색은 보조 수단

## 도구 위치
- 모든 명령은 이 스킬 폴더의 `scripts/studio.py`로 실행
    + 아래의 `studio`는 `python <스킬 폴더>/scripts/studio.py`를 뜻함
    + `python`은 환경에 따라 `python3` 또는 `py`, 경로에 공백이 있으면 따옴표로 감쌈
- 명령 요약
    + `doctor` : 실행 환경 보고 (패키지, 외부 도구, 설정, 누락 항목)
    + `genres [id]` : 장르 목록, 장르 관습
    + `new <장르> -o song.yaml` : 스타터 곡 생성
    + `instruments`, `audition <악기>` : 악기 목록, 단독 시청 그림
    + `lint song.yaml` : 화성, 음역, 구성, 가사 점검
    + `voices`, `vocal-check`, `vocal-try`, `diffsinger-inspect` : 보컬 관련
    + `render song.yaml` : 오디오, MIDI, 검수 보고, 그림 생성
    + `plot` : 추가 그림
    + `export --to json,midi,lmms,dawproject`, `import-midi` : 내보내기와 가져오기
    + `lmms-check` : 내보낸 LMMS 프로젝트를 LMMS로 다시 렌더하여 확인 (LMMS가 있을 때만, 선택)
- 각 명령의 옵션은 `studio <명령> -h`로 확인

## 시작 전 준비
- 가장 먼저 `studio doctor` 실행
    + 패키지가 하나도 없어도 동작하며 아무것도 설치하거나 내려받거나 바꾸지 않음
    + 운영체제, 파이썬의 종류, 누락 패키지, 외부 도구, 설정값과 그 출처를 보고
- 실행 환경의 성격을 먼저 판단
    + 일회용 환경(컨테이너, 샌드박스, CI) : 묻지 않고 바로 설치하여 진행
    + 사용자의 개인 컴퓨터 : 설치와 내려받기 전에 무엇을 어디에 얼마나 받는지 알리고 동의를 받음
    + 판단이 서지 않으면 개인 컴퓨터로 간주
- 패키지 설치 원칙
    + 기악곡은 `requirements.txt`만 필요, `requirements-vocal.txt`는 보컬곡일 때만 설치
    + 개인 컴퓨터에서는 격리된 환경에 설치 (venv, conda, uv 등 사용자가 이미 쓰는 방식을 따름)
    + 운영체제가 관리하는 파이썬에 강제로 설치하지 않음 (`--break-system-packages`, `sudo pip`), 일회용 환경만 예외
    + 관리자 권한이 필요한 작업은 직접 실행하지 않고 사용자에게 명령을 안내
    + pyworld 불러오기가 `No module named 'pkg_resources'`로 실패하면 같은 환경에 `setuptools<82` 설치 (pyworld 0.3.5 기준 setuptools가 없거나 82 이상인 환경에서 발생, doctor에 오류 표시)
    + 설치가 끝나기 전에는 작곡 단계로 넘어가지 않음
- 설정은 스크립트를 고치지 않고 바깥에서 지정
    + 우선순위 : 명령 옵션, 환경 변수 `SPECTRO_MAESTRO_<이름>`, JSON 설정 파일, 운영체제별 기본값
    + 설정 파일 : `--config <파일>`(명령 이름 앞에 둠), 작업 폴더의 `spectro-maestro.json`, 사용자 설정 폴더의 `spectro-maestro/config.json` 순으로 탐색
    + 항목 : `cache_dir`, `models_dir`, `offline`, `download_timeout_s`, `native`, `compiler`, `ffmpeg`, `lmms`, `asr_model`, `kokoro_revision`
    + 현재 값, 출처, 탐색한 설정 파일 경로는 `doctor`가 표시
    + 예시 : `{"models_dir": "D:/music-models", "offline": true}`
- 보컬 모델은 첫 사용 시 `models_dir`에 내려받음 (목소리와 음성 인식 모델을 합쳐 약 1 GB)
    + 기본 위치는 운영체제의 사용자 캐시 폴더 아래이며 `--models` 또는 설정으로 변경
    + 내려받기에 실패하면 오류 메시지가 파일 주소와 놓을 경로를 알려주므로 사용자가 직접 넣을 수 있음
    + `offline`을 켜면 내려받기를 시도하지 않음
    + Kokoro는 스킬을 검증한 리비전으로 내려받음. `kokoro_revision`으로 다른 리비전을 지정: 렌더를 그대로 되풀이하려면 커밋 id, 최신본은 `main`. 다른 리비전은 별도 폴더에 두고 노래 캐시도 따로 씀. `main`은 한 번만 내려받으므로 더 새것을 받으려면 `models_dir` 아래 `kokoro/main`을 지움
    + LMMS(이 스킬에서는 선택 도구)는 `lmms` 설정이 가리키는 것을 쓰므로 더 새 버전도 지정 가능
    + 모델을 구할 수 없으면 사용자에게 알리고 기악곡으로 진행하거나 모델 파일 제공을 요청
- 외부 도구는 모두 선택 사항
    + C 컴파일러 : 있으면 필터 가속 코드를 `cache_dir`에 한 번 빌드, 없으면 같은 결과를 내는 느린 경로로 동작 (`native: off`로 끌 수 있음)
    + ffmpeg : 오디오 라이브러리가 mp3를 직접 쓰지 못할 때만 사용, 둘 다 없으면 ogg, flac, wav로 전달
    + LMMS : 내보낸 LMMS 프로젝트를 열거나 다시 렌더해 볼 때만 필요, 사용자가 원할 때만 다룸 (`references/export.md`)
    + 없는 도구를 이유로 작업을 멈추지 않고 가능한 범위로 진행한 뒤 보고에 기록
- 출력은 곡 파일 옆의 `<곡이름>_out/` 폴더에 모임
    + 최종 오디오와 MIDI, `report.json`, `qa/` 그림, `stems/`, `vocals/`, `build/`(캐시)
    + 도구가 파일을 쓰는 곳은 명령에 지정한 출력 경로, `cache_dir`, `models_dir`뿐

## 작업 흐름
- 1단계 : 기획 (사용자와 합의)
- 2단계 : 뼈대 작성 (구성, 코드, 리듬)
- 3단계 : 선율과 편곡
- 4단계 : 보컬 (가사가 있는 곡)
- 5단계 : 렌더와 검수
- 6단계 : 수정 반복
- 7단계 : 내보내기와 보고
- 각 단계는 확인 가능한 산출물로 끝남
    + 기획 요약, lint 통과, 보컬 확인표, 검수 수치와 그림
    + 앞 단계의 확인을 건너뛰면 뒤 단계에서 고칠 범위가 커짐

## 1단계 기획
- 장르, 분위기, 템포, 조, 길이, 구성, 보컬 유무, 믹스 스타일, 음량 목표, 전달 형식을 사용자와 합의
    + 항목마다 기본값을 제시하고 사용자가 바꿀 것만 답하게 함
    + 질의 항목과 기본값, 요약 양식은 `references/planning.md`
- `studio genres <id>`로 장르 관습을 읽고 시작
    + 목록에 없는 장르의 처리는 `references/genres.md`
- 사용자가 준 가사, 선율, 레퍼런스는 그대로 존중
    + 문제가 보이면 위치와 대안을 제시하고 선택을 받음
    + 가사는 고른 목소리의 역량 기준으로도 검토 (`references/vocals.md`)
    + 임의로 고쳐서 진행하지 않음
- 기획이나 가사가 품질을 크게 해칠 내용이면 진행 전에 알림
    + 문제 설명, 대안 제시, 사용자 선택의 순서
    + 사용자가 원안을 고수하면 원안대로 진행하고 예상되는 품질 저하를 명확히 고지
- 보컬곡이면 엔진과 목소리를 이 단계에서 결정
    + `studio voices`의 목록과 이용 조건 안내를 사용자에게 전달
    + 가창 보이스뱅크는 사용자가 제공한 것만 사용, 찾아주거나 대신 내려받지 않음
    + 가사는 한 줄이라도 부르기 전에 전문을 보여 주고 확인을 받음 (새로 쓴 가사는 기획 요약과 함께 확인)

## 2단계 뼈대 작성
- `studio new <장르> -o song.yaml --title ... --bpm ... --key ...`로 스타터 생성
    + 스타터는 그 장르의 표준 악기와 패턴이 들어 있는 완결된 곡
- 스타터를 기획에 맞게 다시 작성
    + 섹션 목록과 마디 수를 기획의 길이에 맞춤
    + 코드 진행을 곡의 성격에 맞게 교체
    + 드럼과 베이스 패턴에 변주와 필인 추가
    + 곡의 끝 처리를 정함 (`ending: hit` 또는 `ending: fade`, 또는 끝맺음 섹션)
- 곡 파일 문법은 `references/song-format.md`
    + 처음 쓰기 전에 한 번 통독
- `studio lint song.yaml`로 확인
    + 오류는 위치와 함께 보고되므로 바로 수정

## 3단계 선율과 편곡
- 주선율과 훅을 직접 작곡
    + 스타터의 선율을 그대로 쓰지 않음
    + 강박에 코드음, 순차 진행 위주, 프레이즈 끝의 해결
- 섹션마다 에너지를 설계
    + 성부 수, 필터, 음역, 리듬 밀도로 오르내림을 만듦
    + 전환 장치(라이저, 스네어 롤, 임팩트, 킥 비우기)로 경계를 표시
- 작곡과 편곡 지침, lint 항목 해설은 `references/composition.md`
- 악기 선택과 패치 수정은 `references/sound.md`
    + 낯선 악기는 `studio audition <악기>`의 그림과 수치로 확인
- `lint`의 경고는 하나씩 판단
    + 의도한 것은 유지하고 이유를 `notes`에 기록

## 4단계 보컬
- 가사 작성 규칙을 먼저 읽음 : `references/vocals.md`
- 순서
    + 고른 엔진과 목소리의 강점과 약점을 확인하고 그에 맞는 단어와 문장 구조 선택
    + 선율의 리듬 확정, 가사 작성, `lint`로 음절 수와 강세 확인
    + `studio vocal-check song.yaml` : 믹스 전에 보컬만 불러서 줄별 인식 일치율, 거친 음절(`ROUGH`), 음정 오차 확인
    + 약한 줄과 `ROUGH` 표시가 있는 줄은 그림과 단독 클립 확인
    + `studio vocal-try song.yaml --line N --text "후보"` : 같은 음절 수의 후보 비교
- 일치율은 들어볼 줄을 고르는 탐지기
    + 합격 여부는 사람의 청취로 결정
    + 사용자가 쓰거나 승인한 가사는 경고만으로 바꾸지 않고 원본과 후보 클립을 제시하여 선택을 받음
- DiffSinger 보이스뱅크를 받으면 `studio diffsinger-inspect <폴더>`부터 실행
    + `references/vocals.md`의 가사 규칙 가운데 가창 요령과 모델 목소리의 습성만 보이스뱅크에 적용
    + `lint`도 보이스뱅크의 줄에 이 두 가지를 검사
    + 이용 조건 파일을 읽고 사용자에게 요약 고지
- 목소리를 바꾸면 보컬 확인과 믹스 수치를 다시 확인

## 5단계 렌더와 검수
- 부분 렌더로 먼저 확인
    + `studio render song.yaml --sections chorus1` : 한 섹션의 음색과 균형
- 전체 렌더
    + `studio render song.yaml --formats wav,mp3,ogg,mid`
    + 3-4분 곡 기준 2코어 CPU에서 2-3분, 7분 곡은 4분 안팎, 보컬 합성은 별도 시간
    + 실행 시간 제한이 있는 환경에서는 백그라운드로 실행하고 로그를 확인
- 검수는 세 가지를 모두 수행
    + 수치와 발견 사항 (`== metrics ==`, `== findings ==`)
    + 섹션 표 (`== sections ==`)
    + `qa/` 폴더의 그림 6장
- 그림 확인은 정식 단계
    + overview, spectrogram, spectrum, arrangement, pianoroll, stereo를 직접 열어 확인
    + 수치 기준에 걸리지 않는 이상이 그림에서 드러남 (빈 대역, 계속되는 띠, 쏠림, 예상 밖의 무음)
    + 규칙에 없는 이상을 보면 추가 그림과 트랙 단독 렌더로 원인을 추적
- 곡의 시작과 끝을 따로 확인
    + overview 파형의 끝이 서서히 가늘어지는지, `ending_drop_db` 발견 사항이 없는지 확인
- 반드시 지킬 균형
    + 비트가 묻히지 않을 것, 비트가 믹스를 삼키지 않을 것 (`drums_vs_rest_db`)
    + 보컬과 반주 어느 쪽도 묻히지 않을 것 (`vocal_body_db`, `vocal_consonant_db`)
- 수치 해설, 그림 보는 법, 증상별 처방은 `references/mixing-qa.md`
- 그림을 볼 수 없는 실행 환경이면 그 사실을 보고에 적고 수치와 섹션 표만으로 판단

## 6단계 수정 반복
- 한 번에 한 가지를 바꾸고 다시 확인
    + 문제 섹션만 부분 렌더하여 수치 변화를 본 뒤 전체 렌더
- 조정 순서
    + 편곡 (성부 제거, 음역 이동), 트랙 `gain_db`, 섹션 `vel`, 센드와 필터, 인서트 EQ, 마스터 EQ
- 발견 사항이 의도한 연출이면 그대로 두고 이유를 보고에 기록
- 캐시가 있으므로 바뀐 트랙만 다시 계산됨

## 7단계 내보내기와 보고
- 기본 전달물 : 완성 오디오(ogg, mp3), MIDI, 곡 파일, 프로젝트 JSON
    + 요청 시 스템, LMMS 프로젝트, DAWproject, 가사 파일, 검수 그림
    + 형식별 내용과 한계는 `references/export.md`
- 보고에 담을 내용
    + 기획 요약과 진행 중 바뀐 점
    + 최종 수치 (음량, 트루 피크, 주요 균형 수치)와 남은 발견 사항
    + 그림에서 확인한 것
    + 보컬곡이면 줄별 일치율 요약, 약한 줄과 조치, 기능어 경고가 남아 청취로 확인할 줄
    + 확인하지 못한 것과 알려진 한계
    + 이용 조건이 붙은 목소리를 썼다면 표기 의무 등 조건
- 사용자의 청취 의견을 받아 6단계로 돌아감
    + 최종 판단은 사용자의 귀

## 판단 원칙
- 규칙과 임계값은 출발점
    + 장르와 의도에 따라 벗어날 수 있음
    + 벗어날 때는 근거를 남김
- 수치는 탐지기, 그림은 관찰 도구
    + 둘 다 통과해도 사용자의 청취 의견이 우선
- 확인하지 않은 것을 확인했다고 보고하지 않음
    + 소리를 직접 듣지 못했다는 전제를 보고에 유지
- 재현성 유지
    + 같은 곡 파일과 `seed`는 같은 소리를 냄
    + 결과가 달라져야 하면 `seed`를 바꿈

## 예제 곡
- `examples/`에 이 스킬로 만든 완성곡 4개 수록
| 폴더 | 곡 | 볼 만한 점 |
|---|---|---|
| `examples/first_light/` | First Light, 업리프팅 트랜스 138 bpm, 7분 16초 | 긴 구성, 주제 선율의 재사용, 브레이크와 클라이맥스 |
| `examples/signal_fires/` | Signal Fires, 퓨처팝 128 bpm, 3분 50초 | 보컬곡(Kokoro `af_heart`), 더블과 화음, `ending: hit` |
| `examples/last_tram/` | Last Tram, 두머 156 bpm, 3분 4초 | 보컬곡(Kokoro `am_michael`), 한 박에 한 음절인 가사, `ending: fade` |
| `examples/silver_box/` | Silver Box, 애시드 하우스 124 bpm, 4분 12초 | 필터 자동화로 전개하는 기악곡 |
- 폴더마다 곡 파일(`.yaml`)과 MIDI 수록, 보컬곡은 가사(`lyrics.txt`) 포함
    + 음원은 싣지 않았으며 곡 파일을 렌더하면 같은 소리가 나옴
- 용도
    + 곡 파일 문법, 구성, 가사 표기의 실제 예
    + 설치 확인용 렌더 대상
- 다시 렌더할 때는 출력 폴더를 스킬 밖으로 지정
    + `studio render <스킬 폴더>/examples/silver_box/silver_box.yaml -o <작업 폴더>/silver_box_out`
- 예제의 선율, 가사, 코드 진행을 새 곡에 그대로 옮기지 않음
    + 새 곡은 기획에 맞춰 새로 작곡

## 참조 문서
| 문서 | 읽을 때 |
|---|---|
| `references/planning.md` | 기획 질의, 사용자 입력 처리, 무리한 요청 대응 |
| `references/song-format.md` | 곡 파일을 쓰기 전 (필수) |
| `references/composition.md` | 코드, 선율, 편곡을 짤 때와 lint 결과를 해석할 때 |
| `references/genres.md` | 장르 선택, 목록에 없는 장르, 장르 파일 추가 |
| `references/sound.md` | 악기 선택, 패치 수정, 이펙트 |
| `references/mixing-qa.md` | 렌더 후 검수와 믹스 수정 (필수) |
| `references/vocals.md` | 보컬곡 전 과정 (필수) |
| `references/export.md` | 내보내기와 가져오기, LMMS로 확인하기 |
