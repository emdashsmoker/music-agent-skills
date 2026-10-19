# 환경 준비

모든 작업은 에이전트가 일하는 컴퓨터에서 이루어진다. LMMS는 창을 열지 않고 렌더하고, `scripts/`의 Python 툴킷이 LMMS를 조종한다. GPU는 필요 없다. 컴퓨터마다 사정이 크게 다르므로 이 문서는 판단 방법과 예시를 주고, 정확한 명령은 그 컴퓨터가 제공하는 수단에 맡긴다.

## 목차

- 먼저 살펴보기
- 누구의 컴퓨터인가
- LMMS 구하기
- ffmpeg 구하기
- 드럼 킷
- Python 패키지
- 설정
- 렌더 방식: 사용자의 선택
- 모델 다운로드
- 시험한 범위
- 문제 해결
- 자가 시험

## 먼저 살펴보기

```bash
python scripts/lmms_tool.py doctor
```

`doctor`는 아무것도 바꾸지 않는다. 다음을 보고한다.

- `environment`: 운영체제, Python 버전, Python이 격리된 환경인지, 프로세스에 관리자 권한이 있는지, 컨테이너로 보이는지, 디스플레이가 있는지, PATH에 있는 패키지 관리자.
- `lmms`: 사용할 실행 방법, 발견 경로(설정, PATH, 알려진 폴더, Flatpak), 버전, 샌드박스 안에서 도는지, 발견된 다른 LMMS 전부.
- `ffmpeg`, `python_packages`: 있는 것과, 빠진 항목마다 쓸 수 없게 되는 기능.
- `settings`: 현재 적용되는 설정값.

과제에 필요한 것만 설치한다. 연주곡에는 LMMS와 Python 패키지 4개면 된다. `doctor`가 동작하는 LMMS를 이미 보여 주면 그것을 쓴다. 두 번째 LMMS를 설치하지 않고, 사용자의 LMMS를 업그레이드, 다운그레이드, 삭제하지 않는다.

## 누구의 컴퓨터인가

같은 항목이 빠져 있어도 에이전트가 도는 곳에 따라 행동이 달라진다. `environment`를 읽고 판단한다.

| 상황 | 징후 | 진행 방법 |
|---|---|---|
| 일회성 컨테이너나 클라우드 샌드박스 | `looks_like_container`나 `administrator`가 true, 디스플레이 없음, 디스크에 사용자 자료 없음 | 묻느라 멈추지 말고 시스템 패키지 관리자로 빠진 것을 설치한다. 설치한 내용을 사후에 보고한다. 아무것도 유지되지 않으므로 설정은 환경 변수로 한다 |
| 사람이 쓰는 데스크톱이나 노트북 | 디스플레이, 일반 사용자 계정, 사용자 파일이 있는 홈 폴더 | 빠진 것, 용량, 제안하는 설치 방법을 말하고 답을 기다린다. 관리자 권한이 필요 없고 홈 폴더 밖을 건드리지 않는 방법을 우선한다. 관리자 권한 명령은 직접 실행하지 않는다. 사용자가 그 방법을 택하면 실행할 명령을 알려 준다 |
| 공용 서버나 관리되는 업무용 컴퓨터 | 관리자 권한 없음, 정책을 알 수 없음 | 사용자 수준 설치만 한다(AppImage, 가상 환경). 모든 다운로드 전에 묻는다 |

일회성이 아닌 모든 컴퓨터에서 지킬 사항:

- Python 패키지는 격리된 환경(가상 환경, 또는 conda나 uv 같은 프로젝트 자체의 환경 관리자)에 설치한다. 시스템 Python에 설치하지 않는다.
- 셸 시작 파일, 시스템 경로, 사용자의 LMMS 설정을 고치지 않는다. 툴킷은 자체 임시 설정 파일로 LMMS를 시작하므로 사용자의 LMMS 설정, 최근 파일, 작업 폴더를 읽지도 바꾸지도 않는다.
- 렌더는 지정한 출력 폴더에만 쓰고, 임시 폴더는 렌더마다 지운다.
- 직접 만들지 않은 것은 지우지 않는다.

## LMMS 구하기

툴킷은 LMMS 1.2.x를 기준으로 작성했다(시험한 범위 참조). LMMS는 여러 방식으로 배포되며, 그 컴퓨터에 맞는 방식이 가장 좋은 방식이다. 가정하지 말고 무엇을 쓸 수 있는지 찾아본다.

- 배포판 패키지. `doctor`가 보여 준 패키지 관리자에서 찾는다(`apt-cache policy lmms`, `dnf info lmms`, `pacman -Si lmms`, `zypper info lmms`, `apk search lmms`, `nix-env -qaP lmms` 등). 컨테이너에서 가장 간단하다. 보통 LADSPA 이펙트 플러그인과 기본 샘플이 함께 온다. 관리자 권한이 필요하다.
- LMMS 다운로드 페이지(https://lmms.io/download)의 AppImage. 파일 하나이고, 관리자 권한이 필요 없고, 시스템 전체에 설치되는 것이 없다. `~/Applications` 같은 폴더에 두고 실행 권한을 주면 `doctor`가 찾는다. 사람이 쓰는 리눅스 데스크톱의 좋은 기본 선택이다.
- Flatpak(`flatpak search lmms`). `flatpak install --user`로 사용자 단위 설치가 된다. `doctor`는 id에 "lmms"가 들어간 설치된 Flatpak 앱을 찾는다.
- Snap(`snap find lmms`). PATH에 들어온다.
- macOS: 다운로드 페이지의 디스크 이미지나 패키지 관리자(`brew search lmms`). `/Applications`나 `~/Applications`의 앱 번들은 자동으로 발견된다.
- Windows: 다운로드 페이지의 설치 프로그램이나 패키지 관리자(`winget search lmms`, `choco search lmms`, `scoop search lmms`). 통상의 설치 폴더를 탐색한다.
- 사용자가 직접 빌드한 LMMS는 위치와 무관하게 `lmms_command` 설정으로 지정한다.

설치 전에 그 배포처가 제공하는 버전을 확인한다. 배포처가 여럿이면 이미 설치된 LMMS, 사용자 수준의 1.2.x(AppImage나 Flatpak), 시스템 패키지 순으로 우선한다.

특이한 위치에 있거나 감싸는 명령이 필요한 LMMS는 한 번 설정해 둔다.

```bash
python scripts/lmms_tool.py configure --set lmms_command=/path/to/lmms-1.2.2-linux-x86_64.AppImage
python scripts/lmms_tool.py configure --set 'lmms_command=["flatpak", "run", "--command=lmms", "{grants}", "<flatpak list --app 이 보여 주는 앱 id>"]'
```

목록으로 쓴 명령에는 `{grants}`를 넣을 수 있다. Flatpak에서는 이 자리가 한 번의 렌더에 필요한 폴더(프로젝트 폴더, 출력 폴더, 임시 폴더)에 대한 권한으로 바뀌며 그 실행에만 유효하다. Flatpak에 저장된 권한은 바뀌지 않는다.

## ffmpeg 구하기

ffmpeg는 선택 사항이다. ogg, mp3, flac은 soundfile이 직접 쓴다. ffmpeg는 soundfile에 든 libsndfile이 1.1보다 오래되어 mp3를 쓰지 못할 때만 mp3 인코딩에 쓰인다. 둘 다 없으면 `produce`는 mp3를 건너뛰고 ogg와 WAV를 전달하며 그 사실을 알린다. 이때는 soundfile을 새 판으로 올리는 것이 가장 간단하다. ffmpeg를 구하는 방법은 위와 같은 논리를 따른다. 시스템 패키지 관리자, 홈 폴더에 둔 정적 빌드와 그 경로를 가리키는 `ffmpeg` 설정, 또는 Python 패키지 `imageio-ffmpeg`가 있다. `imageio-ffmpeg`는 관리자 권한 없이 Python 환경 안에 ffmpeg 실행 파일을 가져오며 자동으로 인식된다.

## 드럼 킷

스킬에는 오디오가 들어 있지 않다. 드럼이 있는 곡을 처음 저장할 때(또는 자가 시험을 돌릴 때) 툴킷이 이 컴퓨터에서 드럼 킷을 만든다. 이름이 붙은 킥과 노이즈 루프를 계산하고, 설치된 LMMS의 DrumSynth 프리셋에서 드럼머신 타격을 짧은 렌더 한 번으로 녹음한다. 몇 초가 걸리고, 기본 샘플을 갖춘 동작하는 LMMS가 필요하고, 아무것도 내려받지 않으며, 킷 폴더(`kit_dir`, 기본값은 캐시 폴더 아래 `kit` 폴더)에만 쓴다.

```bash
python scripts/lmms_tool.py kit            # 현재 상태
python scripts/lmms_tool.py kit --build    # 지금 만들기
```

- 사람이 쓰는 컴퓨터에서는 킷을 한 번 만들어 계속 쓴다. 일회성 컨테이너에서는 새 컨테이너마다 다시 만들며 몇 초가 든다.
- 한 컴퓨터에서는 곡이 렌더마다 같은 소리를 낸다. 컴퓨터 사이에서는 노이즈 기반 타격이 조금 다르므로, 다른 곳에서 렌더한 곡은 여기서 렌더한 같은 곡과 샘플 단위로 동일하지 않다. 똑같은 드럼을 다른 컴퓨터로 가져가려면 킷 폴더를 복사하거나, 곡이 쓰는 사운드를 담는 프로젝트 묶음을 쓴다.
- `kit --rebuild`는 타격을 새로 녹음하므로 기존 곡의 렌더 결과가 바뀐다. 의도한 경우에만 쓴다.

### 이 LMMS로 킷을 만들 수 없을 때

드럼머신 타격은 LMMS 1.2.x에 들어 있는 DrumSynth 프리셋에서 녹음한다. 이후 버전의 LMMS는 이 프리셋을 옮기거나, 이름을 바꾸거나, 뺄 수 있다. 프리셋 없이 나온 빌드도 있을 수 있다. 이때 킷 생성은 "LMMS rendered no sound for ... DrumSynth presets" 오류로 멈추고, 드럼이 있는 곡을 저장할 수 없다. 해결 방법은 사용자의 LMMS 옆에 LMMS 1.2.2를 따로 두고 킷을 한 번만 녹음하는 것이다. LMMS 1.2.2는 킷 녹음에만 쓴다. 곡 렌더는 사용자가 원래 쓰던 LMMS로 계속하며, 그 LMMS는 그대로 둔다.

- 이 문서의 다른 설치와 달리 일회성 컨테이너를 포함한 모든 환경에서 사용자에게 먼저 묻는다. 사용자가 고른 LMMS 옆에 LMMS를 하나 더 두는 일이기 때문이다. 이유(설치된 LMMS로 드럼머신 타격을 녹음할 수 없음), 받을 대상(https://github.com/LMMS/lmms/releases/tag/v1.2.2 의 LMMS 1.2.2), 사용자의 LMMS는 건드리지 않는다는 점을 함께 말한다. 사용자가 거절하면 문제 해결에 있는 다른 방법을 제안한다.
- Linux: 사용자가 동의하면 위 페이지의 AppImage를 툴킷 전용 폴더(예를 들어 캐시 폴더)에 내려받아 실행 권한을 준다. 그다음 이 명령 한 번에만 그 AppImage를 지정해 킷을 녹음한다. AppImage가 실행되지 않으면 문제 해결을 본다. 내려받기 전에 세션에 GitHub 저장소를 연결하는 도구가 실행 환경에 있으면 호출한다. 인자는 소유자 `LMMS`, 저장소 이름 `lmms`를 각각 따로 전달한다. 도구 응답이 안내하는 접근 경로를 따른다. 도구가 없거나 호출이 거부되면 이 단계를 건너뛴다.

```bash
LMMS_BIN=/path/to/lmms-1.2.2-linux-x86_64.AppImage python scripts/lmms_tool.py kit --build
```

- Windows와 macOS: 직접 내려받거나 설치하지 않는다. 절차를 설명하고 사용자가 진행하게 한다. 사용자는 같은 페이지에서 LMMS 1.2.2를 내려받아 지금 쓰는 LMMS를 덮어쓰지 않도록 별도 사본으로 설치한다. Windows에서는 전용 폴더에 설치하고, macOS에서는 두 앱을 다른 이름으로 함께 둔다. 그다음 환경 변수 `LMMS_BIN`을 1.2.2 프로그램으로 지정한 채 `kit --build`를 한 번 실행한다.
- 녹음이 끝나면 `kit`의 출력에 `"lmms": "LMMS 1.2.2"`가 나온다. 이 사실을 전달 노트에 적는다. 킷은 보관되므로 이 작업은 컴퓨터마다, 또는 컨테이너마다 한 번이면 된다.
- Linux에서 공식 1.2.2 AppImage로 시험했다. 컨테이너에 FUSE가 없어 압축을 풀어 썼다(`LMMS_BIN`을 `squashfs-root/AppRun`으로 지정). 결과는 자가 시험으로 확인한다.
- 어떤 LMMS로도 킷을 만들 수 없으면 킷 없이 드럼을 만든다. 원샷은 곡 스크립트가 numpy로 합성해 프로젝트 옆 `samples/`에 저장한 뒤 `sounds.sample(...)`로 연주한다(`sounds-effects.md` 참고). 킥은 그 컴퓨터에서 동작하는 쪽을 쓴다. LMMS의 Kicker인 `sounds.kicker(...)`를 쓰거나 numpy로 만든다. numpy로 만들 때는 `kit.synthesize_kick(*kit.KICKS["techno_kick"])`가 킷을 만들지 않고 이름 붙은 킥을 돌려준다. 킷 소리를 쓰지 않는 곡은 킷을 만들지 않는다.

## Python 패키지

`doctor`는 패키지마다 설치할 이름으로 보여 준다. 그 환경에 속한 설치 도구(pip, uv, conda, poetry)를 쓴다.

| 묶음 | 패키지 | 용도 |
|---|---|---|
| 핵심 | numpy, scipy, soundfile, matplotlib | 측정, 믹싱, 점검, 그림. 연주곡은 이것으로 충분 |
| 보컬 | onnxruntime, kokoro-onnx, pyworld, onnx | Kokoro 목소리의 가창 |
| 추가 목소리 | piper-tts | Piper 목소리 |
| 가사 점검 | faster-whisper | 부른 가사 줄의 인식 점수 |
| 보이스뱅크 | pyyaml | 사용자가 제공하는 가수 보이스뱅크 |
| 선택 | xmlschema, imageio-ffmpeg | DAWproject 검증, 관리자 권한 없는 ffmpeg |

## 설정

모든 설정은 환경 변수, 설정 파일, 컴퓨터에서의 탐색 순으로 찾는다. `python scripts/lmms_tool.py configure`는 전체 설정과 뜻, 읽는 파일을 출력한다.

| 설정 | 환경 변수 | 뜻 |
|---|---|---|
| `lmms_command` | `LMMS_BIN` | LMMS 실행 방법. 경로, 또는 JSON 목록으로 쓴 명령 |
| `lmms_data_dir` | `LMMS_DATA_DIR` | LMMS 기본 `samples/`와 `presets/`가 있는 폴더 |
| `ffmpeg` | `LMMSKIT_FFMPEG` | ffmpeg 실행 파일 경로 |
| `cache_dir` | `LMMSKIT_CACHE` | 내려받은 TTS 모델과 보컬 캐시 위치. 기본값은 운영체제의 사용자 캐시 폴더 |
| `kit_dir` | `LMMSKIT_KIT_DIR` | 이 컴퓨터에서 만든 드럼 킷의 보관 위치. 기본값은 `cache_dir` 아래 `kit` |
| `scratch_dir` | `LMMSKIT_SCRATCH` | 임시 렌더 폴더를 만드는 위치. 기본값은 시스템 임시 폴더이며, 샌드박스 안의 LMMS에는 프로젝트 옆 |
| `pin_cpu` | `LMMSKIT_PIN_CPU` | LMMS 프로세스를 CPU 코어 1개에 묶기: `auto`, `on`, `off` |
| `stem_workers` | `LMMSKIT_STEM_WORKERS` | 스템을 병렬로 렌더하는 LMMS 수. 0은 CPU 코어당 1개. 사용자가 작업 중인 컴퓨터에서는 낮춘다 |
| `render_timeout_s` | `LMMSKIT_RENDER_TIMEOUT` | 렌더 한 번의 최대 허용 시간 |
| `qt_platform` | `QT_QPA_PLATFORM` | 렌더용 Qt 플랫폼 플러그인. 기본값 `offscreen` |
| `figure_fonts` | `LMMSKIT_FONTS` | 그림에 순서대로 시도할 글꼴 |

- 컨테이너에서는 환경 변수를 쓴다. 파일을 쓸 필요가 없다.
- 데스크톱에서는 `configure --set KEY=VALUE`가 사용자 설정 파일(운영체제의 설정 폴더 아래)에 값을 저장한다. `configure --here --set ...`는 프로젝트 하나를 위해 현재 폴더에 `lmmskit.json`을 쓴다. `configure --unset KEY`는 값을 지운다. `LMMSKIT_CONFIG`로 추가 설정 파일을 지정한다.
- 지정한 폴더 밖에 툴킷이 쓰는 것은 설정 파일(`configure`를 통해서만), 드럼 킷, 모델 캐시뿐이다.

## 렌더 방식: 사용자의 선택

LMMS가 CPU를 쓰는 방식에 따라 정확한 재현성, 속도, 렌더 중 컴퓨터의 여유가 서로 맞바뀐다. 사용자의 컴퓨터와 시간이 걸린 문제이므로 기획 단계에서 3가지 방식을 각각의 비용과 함께 제시하고 답을 적용한다. 물어볼 사람이 없으면 첫 번째를 쓴다.

| 방식 | 설정 | 사용자가 얻는 것 | 비용 |
|---|---|---|---|
| 재현성 우선 (기본) | `pin_cpu=auto`, `stem_workers=0` | 같은 곡을 렌더할 때마다 같은 파일이 나오고, `produce`가 두 번 렌더해 이를 증명한다. 스템은 모든 코어에서 나란히 렌더된다 | LMMS 프로세스마다 코어 1개에 묶이므로 `produce`의 전체 믹스 렌더 3-4회가 더 느리다 |
| 속도 우선 | `pin_cpu=off` | 전체 믹스 렌더가 더 빨리 끝난다. 코어 2개에서 3분 41초 곡으로 측정한 렌더당 시간은 재현성 우선 40초, 속도 우선 30초다 | 타이밍에 좌우되는 음원(노이즈를 쓰는 Kicker 트랙 여러 개, 악기 노브 오토메이션)이 있는 곡은 렌더마다 조금 달라질 수 있고, 그때 `produce`가 `not_repeatable`을 보고한다. 시험 곡은 두 방식에서 동일하게 렌더되었다. 스템 단계에 미치는 영향은 측정하지 않았다 |
| 컴퓨터 여유 우선 | `stem_workers=1` 또는 `2` | 곡을 렌더하는 동안 컴퓨터로 다른 일을 할 수 있다 | `produce`에서 가장 긴 스템 단계가 그만큼 오래 걸린다 |

- LMMS를 코어 1개에 묶는 기능은 Linux에만 있다. macOS와 Windows에서는 LMMS가 항상 자유롭게 돌기 때문에 동시 렌더 수만 선택 사항이며, 곡이 두 번 같게 나왔는지는 `produce`의 반복 점검이 알려 준다.
- 속도 우선과 컴퓨터 여유 우선은 함께 쓸 수 있다.
- 선택은 한 세션에 한해 환경 변수(`LMMSKIT_PIN_CPU=off`, `LMMSKIT_STEM_WORKERS=2`)로 적용하거나 `configure --set`으로 저장한다. 전달 노트에 사용한 방식을 적는다.

## 모델 다운로드

TTS 모델과 인식 모델은 처음 쓸 때 `cache_dir`와 Hugging Face 캐시에 내려받는다.

- 타이밍 출력이 있는 Kokoro TTS 모델(고정 리비전): 약 330 MB, 목소리마다 1 MB 미만 추가.
- Piper 목소리: 각 60-115 MB.
- 인식 모델(`base.en`, 다른 언어는 `base`): 약 140 MB.
- OpenUtau G2P 언어 팩(가수 보이스뱅크가 사전에 없는 독일어, 프랑스어, 스페인어, 이탈리아어, 포르투갈어, 러시아어 단어를 부를 때): 언어마다 1.7-2.6 MB, OpenUtau GitHub 저장소의 고정 커밋에서 받고 SHA-256으로 확인.

첫 보컬 렌더 전에 이 다운로드가 있음을 사용자에게 알린다. 다운로드 호스트가 막혀 있으면 오류 메시지가 파일 이름과 직접 둘 위치를 알려 준다. 가수 보이스뱅크는 툴킷이 내려받지 않는다. 사용자가 제공한다(`vocals.md` 참조).

## 시험한 범위

- 시험함: Linux, Python 3.13, Debian 패키지의 LMMS 1.2.2, numpy 2.5, scipy 1.18, onnxruntime 1.30, kokoro-onnx 0.6, piper-tts 1.8, faster-whisper 1.2, pyworld 0.3.5. 공식 LMMS 1.2.2 AppImage는 압축을 풀어(컨테이너에 FUSE 없음) `LMMS_BIN`으로 지정한 상태에서 자가 시험을 통과했다. 파일 이름으로 AppImage를 찾는 경로와 Flatpak 명령 경로는 그 실행 방법을 흉내 낸 대역으로 시험했다.
- 시험하지 못함: LMMS Flatpak, Snap, macOS, Windows, 1.2.2 이외의 LMMS 버전. 탐색 코드는 이들을 다루며, 특정 컴퓨터에서의 동작은 아래 자가 시험이 증명한다. 이런 환경에서 작업할 때는 사용자에게 이 사실을 말한다.
- LMMS를 CPU 코어 1개에 묶는 기능은 운영체제가 제공하는 곳(Linux)에만 있다. 그 밖의 환경에서는 LMMS가 제한 없이 돌고, 렌더가 실행마다 조금 달라질 수 있으며, `produce`의 반복 점검이 이를 보고한다.
- 1.2 이후의 LMMS는 프로젝트 형식과 일부 악기가 달라졌다. 버전이 1.2.x가 아니면 `doctor`가 안내를 붙인다. 자가 시험을 돌리고, 실패하면 사용자의 버전 옆에 1.2.x AppImage를 두는 방법을 제안한다.

## 문제 해결

- LMMS가 관리자 계정으로 실행을 거부한다: 필요할 때 툴킷이 `--allowroot`를 직접 붙인다.
- AppImage가 시작되지 않는다(FUSE 없음, 컨테이너에서 흔함): 자기 폴더에서 `--appimage-extract`로 한 번 풀고 `lmms_command`를 그 안의 `squashfs-root/AppRun`으로 지정한다.
- 샌드박스 안의 LMMS(Flatpak, Snap)가 아무것도 렌더하지 않는다: 폴더가 보이지 않는 상태다. 프로젝트와 출력 폴더를 사용자 홈 폴더 안(최상위 숨김 폴더 제외)에 두고, `scratch_dir`를 비워 두어 임시 폴더가 프로젝트 옆에 만들어지게 한다.
- LMMS가 Qt 플랫폼 오류로 실패한다: 그 빌드에 `offscreen` 플러그인이 없다. `configure --set qt_platform=minimal`을 시도하거나, 디스플레이가 있는 컴퓨터에서는 `qt_platform=xcb`(Linux), `cocoa`(macOS), `windows`로 시스템의 것을 쓴다.
- 킷을 만들 수 없다("LMMS rendered no sound for ... DrumSynth presets"): 이 LMMS에 기본 샘플이 없거나 배치가 다르다. 데이터 폴더에 `samples/drumsynth`가 있는지 확인하고, 온전한 빌드를 쓰거나, 다른 컴퓨터의 킷 폴더를 복사해 `kit_dir`로 지정한다. 숨김 폴더를 볼 수 없는 Snap에서는 `kit_dir`를 홈 폴더의 보이는 폴더로 둔다. 이 LMMS가 프리셋이 달라진 이후 버전이면 드럼 킷의 "이 LMMS로 킷을 만들 수 없을 때"를 본다.
- 렌더 결과가 무음이거나 파일이 아주 작다: `inspect` 출력의 `missing_samples`를 본다. 드럼 사운드는 프로젝트 옆 `samples/kit/`에 있다. `Song.save()`가 거기에 넣으며, `samples/` 폴더 없이 옮긴 프로젝트는 드럼을 잃는다.
- LADSPA 이펙트가 효과를 내지 않는다: 그 LMMS 빌드에 플러그인이 없다. `fx.catalog()`가 툴킷이 기대하는 목록을 보여 준다. 배포판 패키지와 공식 빌드에는 들어 있다.
- 렌더가 매우 오래 걸린다: 곡 길이와 파트 수를 확인하고 먼저 `render --bars 1:16`을 시도한다. LMMS는 한 번에 실시간의 약 5배 속도로 렌더하고, `produce`는 파트마다 짧은 렌더 1회와 전체 렌더 3-4회가 필요하다.
- 렌더 중 컴퓨터가 느려진다: `stem_workers`를 1이나 2로 둔다.
- 그림의 글자가 네모로 나온다: `figure_fonts`의 글꼴이 하나도 설치되어 있지 않다. 컴퓨터에 있는 글꼴 이름을 설정에 추가한다.
- `pyworld`가 `pkg_resources` 오류로 import에 실패한다: 툴킷이 우회한다. 그래도 실패하면 환경에 `setuptools`를 설치한다.

## 자가 시험

```bash
python scripts/lmms_tool.py selftest            # 연주곡 파이프라인, 1분 이내
python scripts/lmms_tool.py selftest --vocal    # 기본 TTS 목소리로 한 줄 가창 추가 (처음에는 모델을 내려받음)
```

자가 시험은 드럼 킷이 없으면 만들고, 임시 폴더에 8마디 곡을 만들고, 두 번 렌더하고, 두 렌더가 동일한지, lint와 믹스 점검이 도는지, MIDI, JSON, DAWproject 내보내기가 쓰이고 다시 읽히는지 확인한다. 점검마다 한 줄을 출력하고 `self-test passed` 또는 실패 목록으로 끝난다. 설치 후, 시험하지 못함으로 적힌 실행 방법이나 플랫폼에서, 렌더가 이상하게 동작할 때마다 돌린다.
