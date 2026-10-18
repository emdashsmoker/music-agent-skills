# 내보내기와 가져오기

## 오디오와 MIDI
- `render --formats wav,mp3,ogg,flac,mid`로 한 번에 생성
    + `wav` : 16비트, 고정 시드 디더
    + `flac` : 24비트
    + `ogg` : Vorbis
    + `mp3` : libsndfile 1.1 이상 또는 ffmpeg 필요
    + `mid` : 트랙별 채널, 드럼은 10번 채널의 General MIDI 건반, 가사는 가사 이벤트로 포함
- 기본값은 `wav,ogg,mp3,mid`
- `render --stems`는 트랙별 스템을 `stems/<트랙>.flac`으로 저장
    + 버스 스템(`bus_drums.flac` 등)은 항상 저장됨
    + 스템을 모두 더하면 마스터 이전 믹스와 같은 균형

## 프로젝트 JSON
- `render`와 `export --to json`이 `<곡>.project.json`을 저장
    + 모든 음, 코드, 섹션, 믹스 설정이 풀어 적힌 평탄한 형식
    + 곡 파일 없이 이 JSON만으로 다시 렌더 가능
- 가져오기 : `python scripts/studio.py render song.project.json`
    + `lint`, `export`, `plot`, `vocal-check`도 JSON을 그대로 받음
- JSON을 직접 고쳐 음 하나 단위로 수정 가능
    + 트랙의 `notes` 항목 : `[시작 박, 길이 박, MIDI 음높이, 세기]`

## LMMS 프로젝트
- `python scripts/studio.py export song.yaml --to lmms`
    + 결과 : `lmms/<곡>.mmp`, `lmms/samples/<곡>/`, `lmms/HOW_TO_OPEN.txt`
- 변환 방식
    + 드럼 트랙 : 같은 드럼 소리를 원샷 샘플로 담은 샘플러 트랙, 타점 편집 가능
    + 음정 트랙 : 패치를 근사한 Triple Oscillator 트랙, 음 편집 가능
    + 보컬과 전환 효과 : 렌더된 스템을 담은 샘플 트랙
- 보컬과 전환 효과를 포함하려면 먼저 `render --stems` 실행
- LMMS에서 다시 렌더한 소리는 원본과 다름
    + 음표, 구성, 드럼 소리는 동일
    + 신스 음색은 근사치
    + 버스 처리, 리턴 이펙트, 마스터링은 포함되지 않음
    + 자동화(필터 변화, 음량 변화, 곡 끝의 페이드)는 포함되지 않으므로 LMMS에서 다시 그려 넣음
    + 클리핑 방지를 위해 전체 트랙 음량을 6 dB 낮춰 내보냄
- 샘플 경로는 LMMS 샘플 폴더 기준 상대 경로(`<곡>/<파일>.wav`)로 기록
    + 프로젝트를 열려면 `samples/<곡>/` 폴더를 LMMS 샘플 폴더에 복사, `HOW_TO_OPEN.txt`에도 같은 안내 수록
    + 복사 후에는 어느 컴퓨터에서든 프로젝트가 열림
- 프로젝트 파일은 LMMS 1.2 형식

## LMMS로 확인하기
- LMMS는 선택 사항인 외부 프로그램
    + 내보내기는 LMMS 없이 동작
    + 사용자가 LMMS 프로젝트를 요청하지 않았으면 LMMS를 찾거나 설치하지 않음
    + 사용자가 LMMS를 쓰지 않으면 DAWproject 또는 MIDI와 스템을 제안
- 확인 명령 : `python scripts/studio.py lmms-check song.yaml`
    + 찾은 LMMS로 프로젝트를 다시 렌더하여 길이, 최대 피크, 클리핑된 샘플 수를 출력
    + 화면이 없는 환경, 관리자 계정, AppImage, Flatpak에 필요한 실행 옵션은 명령이 알아서 붙임
    + LMMS가 없으면 그 사실만 알리고 종료 코드 3으로 끝남, 내보낸 파일에는 영향 없음
- LMMS를 찾는 순서
    + 설정 `lmms` (`--lmms`, 환경 변수 `SPECTRO_MAESTRO_LMMS`, 설정 파일) : 실행 파일 경로 또는 `flatpak run io.lmms.LMMS` 같은 명령
    + PATH의 `lmms`
    + Flatpak으로 설치된 LMMS
    + `cache_dir`의 `tools/` 폴더에 둔 `lmms*.AppImage`, Snap
    + macOS의 응용 프로그램 폴더, Windows의 Program Files
- LMMS가 없는데 사용자가 확인을 원할 때
    + `doctor`로 운영체제와 환경을 확인한 뒤 그 환경에 맞는 배포 형태를 고름
    + 배포 형태, 최신 버전, 내려받기 주소는 LMMS 공식 내려받기 페이지와 공식 저장소의 릴리스에서 직접 확인
    + 공식 저장소는 GitHub `LMMS/lmms`. 세션에 GitHub 저장소를 연결하는 도구가 실행 환경에 있으면 릴리스 확인 전에 호출. 인자는 소유자 `LMMS`, 저장소 이름 `lmms`를 각각 따로 전달. 도구 응답이 안내하는 접근 경로를 따름. 도구가 없거나 호출이 거부되면 이 단계를 건너뜀
    + 기억에 의존해 주소나 버전을 단정하지 않음
    + 개인 컴퓨터에서는 설치 전에 사용자 동의를 받음
| 환경 | 먼저 검토할 형태 | 유의점 |
|---|---|---|
| Linux 데스크톱 | Flatpak(사용자 범위 설치), AppImage, 배포판 패키지 | 배포판 패키지는 관리자 권한이 필요하므로 명령을 사용자에게 안내 |
| Linux 컨테이너, 권한이 없는 환경 | AppImage | 관리자 권한 불필요, `cache_dir`의 `tools/`에 두면 자동 인식 |
| macOS | 공식 디스크 이미지, Homebrew | 응용 프로그램 폴더에 두면 자동 인식 |
| Windows | 공식 설치 파일, winget 같은 패키지 관리자 | 기본 설치 위치면 자동 인식 |
- 사용자가 이미 쓰는 패키지 관리 방식이 있으면 그 방식을 따름
- 다른 위치에 설치했으면 설정 `lmms`에 경로를 지정
- 설치할 수 없거나 사용자가 원하지 않으면 확인을 생략
    + 보고에 LMMS 재렌더 확인을 하지 않았다고 기록

## DAWproject
- `python scripts/studio.py export song.yaml --to dawproject`
    + 결과 : `<곡>.dawproject` (Bitwig Studio, Studio One, Cubase 등이 읽는 공개 교환 형식)
- 변환 방식
    + 음이 있는 트랙 : 노트 트랙, 섹션마다 클립 하나
    + 보컬과 전환 효과 : 스템이 있으면 오디오 클립으로 포함 (`render --stems` 선행)
    + 템포, 박자, 섹션 마커, 트랙 음량과 팬 포함
- 악기 음색은 포함되지 않음
    + 받는 DAW에서 트랙마다 악기를 지정
- 자동화(필터 변화, 음량 변화, 곡 끝의 페이드)는 포함되지 않음
    + 받는 DAW에서 다시 그려 넣음
- 내보낸 XML은 형식의 스키마로 검사됨 (lxml 설치 시)

## MIDI 가져오기
- `python scripts/studio.py import-midi input.mid -o song.yaml --key "A minor"`
    + 음높이와 리듬을 유지한 곡 파일 초안 생성
    + 악기와 역할은 음역으로 추정한 값이므로 직접 검토 후 수정
    + 드럼은 16분 단위, 나머지는 48분의 1박 단위로 정렬
- 가져온 곡은 섹션 하나로 들어옴
    + 구성을 나누고 믹스 역할을 지정한 뒤 렌더

## 전달물 구성
- 기본 전달물
    + 완성 오디오 (`ogg`와 `mp3` 또는 사용자가 지정한 형식)
    + MIDI
    + 곡 파일 (`.yaml`)과 프로젝트 JSON
- 요청 시 추가
    + 스템, LMMS 프로젝트, DAWproject
    + 가사 파일, QA 그림
