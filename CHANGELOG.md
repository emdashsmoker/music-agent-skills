# Changelog

Dates are in UTC.

날짜는 UTC 기준으로 표기

<!--
Changelog rules
- (Timing) Record each pull request right after it is merged into main.
- (Scope) Check all main history since the last commit that changed CHANGELOG.md and record every merge that is still missing.
- (History command) TZ=UTC git log --first-parent --date=format-local:%Y-%m-%d origin/main
- (Date) Use the UTC date of the merge commit in YYYY-MM-DD format.
- (Date order) Keep the newest date at the top.
- (Entry unit) Write one entry for each change that users can notice.
- (Grouping) Combine same-day pull requests on the same topic into one entry and list every pull request number.
- (Splitting) Split a pull request that contains unrelated changes into separate entries.
- (Skill tag) Use the folder name under skills/. Join two names with "and" in English and "및" in Korean. Separate three or more names with commas. Use (common) in English and (공통) in Korean for repository-wide changes.
- (Entry order) Put repository-wide entries first and sort the rest by skill folder name.
- (English entries) List the English entries first under each date with the "-" bullet.
- (Korean entries) Leave one blank line after the English entries and list the same changes in the same order with the "*" bullet so that they render as a separate list.
- (English format) - (skill tag) Description that starts with the change type verb (#PR number)
- (Korean format) * (skill tag) Korean noun-ending description that ends with the change type word (#PR number)
- (Change types) Added (추가), Changed (변경), Fixed (수정), Removed (삭제), Action needed (필요)
- (Include) Changes to skill outputs, usage steps, or installation.
- (Exclude) Typo and wording fixes, demo image replacements, README changes unrelated to installation, internal refactoring without behavior changes, and commits that only change CHANGELOG.md.
- (Push) Commit on top of the latest main and push directly to main.
-->

## 2026-10-20
- (spectro-maestro) Fixed cut model downloads that were kept and reused as broken files (#68)
- (spectro-maestro) Fixed the exposed-note lyric rules that read bright consonant counts as beat weights (#69)
- (spectro-maestro and synth-ventriloquist) Changed Kokoro downloads to a pinned commit that the kokoro_revision setting can replace (#68)
- (spectro-maestro and synth-ventriloquist) Added a planning question that sets the reading speed of speech voices to agent-decided, melody-matched or fixed (#69)
- (spectro-maestro and synth-ventriloquist) Fixed the lyric lint warning on stressed reduced vowels (#69)
- (spectro-maestro and synth-ventriloquist) Changed syllable counting outside English to join vowels until a line fits its notes (#71)
- (spectro-maestro and synth-ventriloquist) Removed the built-in per-language pronunciation tables and non-English carrier words so that the agent supplies the language knowledge (#71)
- (spectro-maestro and synth-ventriloquist) Changed the flexible mix style adherence to switch styles without asking, with the ask-first behavior moved to a new flexible-HITL option (#73)
- (synth-ventriloquist) Changed speech-voice lines to read at the pace of their melody (#69)
- (synth-ventriloquist) Added a phonemes option that sings a line from given IPA or voicebank symbols (#71)

* (spectro-maestro) 끊긴 모델 다운로드 파일을 보관하여 손상된 파일을 계속 사용하는 오류 수정 (#68)
* (spectro-maestro) 노출 음표 가사 규칙이 강한 자음 개수를 박 강세로 읽는 오류 수정 (#69)
* (spectro-maestro 및 synth-ventriloquist) Kokoro 다운로드를 kokoro_revision 설정으로 바꿀 수 있는 고정 커밋 기준으로 변경 (#68)
* (spectro-maestro 및 synth-ventriloquist) TTS 목소리의 읽기 속도를 에이전트 판단, 멜로디 맞춤, 고정 속도 중에서 고르는 기획 질문 추가 (#69)
* (spectro-maestro 및 synth-ventriloquist) 강세가 있는 약화 모음에도 가사 린트 경고가 표시되는 오류 수정 (#69)
* (spectro-maestro 및 synth-ventriloquist) 영어 외 언어의 음절을 라인의 음표 수에 맞을 때까지 모음을 합쳐 세도록 변경 (#71)
* (spectro-maestro 및 synth-ventriloquist) 언어 지식을 에이전트가 제공하도록 내장 언어별 발음 표 및 영어 외 캐리어 단어 삭제 (#71)
* (spectro-maestro 및 synth-ventriloquist) 먼저 묻는 동작을 유연-HITL 옵션으로 분리하여 유연 준수가 묻지 않고 믹스 스타일을 바꾸도록 변경 (#73)
* (synth-ventriloquist) TTS 목소리 라인을 멜로디 속도에 맞춰 읽도록 변경 (#69)
* (synth-ventriloquist) 지정한 IPA 또는 보이스뱅크 기호로 라인을 부르는 phonemes 옵션 추가 (#71)

## 2026-10-19
- (spectro-maestro) Fixed voicebanks whose pitch or variance model lists fewer speakers than the acoustic model (#63)
- (spectro-maestro) Fixed lines whose phonemes entry was written for another engine, which collapsed into one syllable and stopped the render (#66)
- (spectro-maestro) Fixed vocal-try wordings typed in decomposed form that lost their accents (#67)
- (spectro-maestro and synth-ventriloquist) Added a mix style question to the plan with the forward, balanced, blended, vocal and backbeat presets and an adherence setting (#63)
- (spectro-maestro and synth-ventriloquist) Fixed newer DiffSinger exports that stopped at the first line with a missing duration model input (#63)
- (spectro-maestro and synth-ventriloquist) Added singing of German, French, Spanish, Italian, Portuguese and Russian words on DiffSinger voicebanks (#67)
- (spectro-maestro and synth-ventriloquist) Added a planning question for the recognition model of the vocal checks (#67)
- (spectro-maestro and synth-ventriloquist) Added a warning when the opening consonants of a line fall before the song start (#67)
- (spectro-maestro and synth-ventriloquist) Fixed European lyrics sung with wrong syllable counts and Brazilian Kokoro voices that read European Portuguese (#67)

* (spectro-maestro) 피치 또는 분산 모델의 화자 수가 음향 모델보다 적은 보이스뱅크를 사용할 수 없는 오류 수정 (#63)
* (spectro-maestro) 다른 엔진 기호로 작성된 phonemes 항목 때문에 라인이 한 음절로 합쳐져 렌더링이 중단되는 오류 수정 (#66)
* (spectro-maestro) 분해형으로 입력한 vocal-try 문구의 악센트가 사라지는 오류 수정 (#67)
* (spectro-maestro 및 synth-ventriloquist) 전면, 균형, 융합, 보컬 전면, 백비트 전면 프리셋 및 준수 수준 설정을 갖춘 믹스 스타일 기획 질문 추가 (#63)
* (spectro-maestro 및 synth-ventriloquist) 최신 DiffSinger 내보내기 모델이 길이 모델 입력 누락으로 첫 라인에서 중단되는 오류 수정 (#63)
* (spectro-maestro 및 synth-ventriloquist) DiffSinger 보이스뱅크의 독일어, 프랑스어, 스페인어, 이탈리아어, 포르투갈어, 러시아어 가창 추가 (#67)
* (spectro-maestro 및 synth-ventriloquist) 보컬 검사용 음성 인식 모델을 묻는 기획 질문 추가 (#67)
* (spectro-maestro 및 synth-ventriloquist) 라인 첫 자음이 곡 시작 전에 놓일 때의 경고 추가 (#67)
* (spectro-maestro 및 synth-ventriloquist) 유럽 언어 가사의 음절 수 오류 및 브라질 Kokoro 목소리의 유럽 포르투갈어 발음 수정 (#67)

## 2026-10-18
- (spectro-maestro) Added a step that confirms the full lyrics before any line is sung (#50)
- (spectro-maestro) Changed the planning defaults to list the song file and project JSON as deliverables (#52)
- (spectro-maestro) Changed the default render formats to include ogg (#55)
- (spectro-maestro and synth-ventriloquist) Fixed API names, defaults and figures in the skill documents that did not match the toolkit code (#41, #42)
- (spectro-maestro and synth-ventriloquist) Added a lyric step that plans new lyrics and reviews user-written lyrics against what the chosen voice sings well (#45, #47)
- (spectro-maestro and synth-ventriloquist) Added a lyric tip on short function words that blur on off-beat notes while the match score passes them (#52)
- (spectro-maestro and synth-ventriloquist) Added a lyric review from several seats where the rules are silent (#53)
- (spectro-maestro and synth-ventriloquist) Added a step that attaches GitHub repositories before using a voicebank repository or downloading the LMMS AppImage (#54)
- (spectro-maestro and synth-ventriloquist) Changed voicebank downloads, unpacking and terms-of-use lookup to agent steps so that terms files under any name are found (#54)
- (spectro-maestro and synth-ventriloquist) Added the default of the expressiveness setting of the voicebank pitch model with guidance on when to lower it (#56)
- (spectro-maestro and synth-ventriloquist) Added lint warnings for clipped line endings and rushed lines with guidance that takes vocal rhythm from speech (#57)
- (spectro-maestro and synth-ventriloquist) Fixed Korean, Japanese, Chinese and Russian lyrics that broke at the text level and vocal checks that scored non-English lines as weak (#58, #59)
- (spectro-maestro and synth-ventriloquist) Fixed doctor stopping before its report on machines without the core packages (#60)
- (synth-ventriloquist) Changed planning to go ahead with a plan that the user keeps after stating the expected loss of quality once (#48)
- (synth-ventriloquist) Removed the planning rule that declined lyrics the skill would not write in other contexts (#48)
- (synth-ventriloquist) Changed the voices offered at planning to the default Kokoro voices af_heart and am_michael (#51)
- (synth-ventriloquist) Changed the encoder for ogg, mp3 and flac from ffmpeg to soundfile (#55)
- (synth-ventriloquist) Fixed sung syllables that landed off the beat (#56)
- (synth-ventriloquist) Fixed hiss that was resynthesized as pitched noise (#56)
- (synth-ventriloquist) Fixed voicebank renders of the same line that differed within one run (#58)

* (spectro-maestro) 라인을 부르기 전 전체 가사를 확인받는 단계 추가 (#50)
* (spectro-maestro) 기획 단계 기본 산출물에 곡 파일 및 프로젝트 JSON을 포함하도록 변경 (#52)
* (spectro-maestro) 기본 렌더링 형식에 ogg를 포함하도록 변경 (#55)
* (spectro-maestro 및 synth-ventriloquist) 툴킷 코드와 맞지 않던 스킬 문서의 API 이름, 기본값, 수치 수정 (#41, #42)
* (spectro-maestro 및 synth-ventriloquist) 선택한 목소리가 잘 부르는 표현을 기준으로 새 가사를 기획하거나 사용자 가사를 검토하는 단계 추가 (#45, #47)
* (spectro-maestro 및 synth-ventriloquist) 약박 음표의 짧은 기능어가 뭉개져도 일치 점수를 통과하는 사례를 다룬 가사 작성 팁 추가 (#52)
* (spectro-maestro 및 synth-ventriloquist) 규칙이 다루지 않는 부분을 여러 관점에서 살피는 가사 검토 단계 추가 (#53)
* (spectro-maestro 및 synth-ventriloquist) 보이스뱅크 저장소 사용 또는 LMMS AppImage 다운로드 전 GitHub 저장소 연결 단계 추가 (#54)
* (spectro-maestro 및 synth-ventriloquist) 파일 이름과 무관하게 이용 약관 문서를 찾도록 보이스뱅크 다운로드, 압축 해제, 약관 확인을 에이전트 단계로 변경 (#54)
* (spectro-maestro 및 synth-ventriloquist) 보이스뱅크 피치 모델의 expressiveness 기본값 및 값을 낮출 시점 안내 추가 (#56)
* (spectro-maestro 및 synth-ventriloquist) 말의 리듬을 따르는 보컬 리듬 지침과 함께 끝 단어가 잘리는 라인 및 서두르는 라인의 린트 경고 추가 (#57)
* (spectro-maestro 및 synth-ventriloquist) 한국어, 일본어, 중국어, 러시아어 가사의 텍스트 처리 오류 및 영어 외 라인의 보컬 검사 오판정 수정 (#58, #59)
* (spectro-maestro 및 synth-ventriloquist) 핵심 패키지가 없는 컴퓨터에서 doctor가 보고 전에 중단되는 오류 수정 (#60)
* (synth-ventriloquist) 사용자가 기존 기획을 유지하면 예상 품질 저하를 한 번 고지한 뒤 기획대로 진행하도록 변경 (#48)
* (synth-ventriloquist) 다른 상황에서 쓰지 않을 가사를 거절하는 기획 단계 규칙 삭제 (#48)
* (synth-ventriloquist) 기획 단계에서 소개하는 목소리를 Kokoro 기본 목소리 af_heart 및 am_michael로 변경 (#51)
* (synth-ventriloquist) ogg, mp3, flac 인코딩 도구를 ffmpeg에서 soundfile로 변경 (#55)
* (synth-ventriloquist) 가창 음절이 박자에서 어긋나는 오류 수정 (#56)
* (synth-ventriloquist) 마찰음이 음정 있는 잡음으로 재합성되는 오류 수정 (#56)
* (synth-ventriloquist) 같은 실행 안에서 같은 라인의 보이스뱅크 렌더링 결과가 달라지는 오류 수정 (#58)

## 2026-10-17
- (common) Added SHA256SUMS.txt files with the checksums of the install packages to each skill folder (#29, #30, #31)
- (common) Added a README note on building a dependency skill with offline-deps-builder where network access is blocked (#34, #35)
- (spectro-maestro and synth-ventriloquist) Added lyric writing guidance for bright consonants, held ee vowels and weak words on exposed notes (#22, #23, #27, #33, #38)
- (spectro-maestro and synth-ventriloquist) Added an opt-in body fill for held ee vowels (Style vowel_body) (#24)
- (spectro-maestro and synth-ventriloquist) Added a lyric lint for bright consonants, held ee vowels and reduced vowels on exposed notes that runs on every lead line while drafting (#25, #26, #27, #28, #30)
- (spectro-maestro and synth-ventriloquist) Fixed DiffSinger voicebanks whose acoustic export takes an integer shallow-diffusion depth (#36, #37)
- (synth-ventriloquist) Added vocal checks for off-pitch lines, rough or swallowed vowels, stress on weak beats and line endings that still die after repair, covering backing vocals too (#15, #16, #18, #21)
- (synth-ventriloquist) Changed the vocal strip to drop the de-esser and narrow the duck dip so that speech-voice leads sound brighter (#18)
- (synth-ventriloquist) Added opt-in settings for a de-esser, bright consonant taming and the width of the duck dip (#19, #20)
- (synth-ventriloquist) Fixed vocal margin checks that misread the mix and recognition scores that changed between near-identical renders (#19)
- (synth-ventriloquist) Fixed doubled vocal takes leveled as a second lead when mix roles are guessed from track names (#20)
- (synth-ventriloquist) Changed vocal timing to follow vowel periodicity so that held words no longer start as a long hiss (#28, #37)

* (공통) 스킬 폴더별 설치용 패키지의 체크섬을 담은 SHA256SUMS.txt 파일 추가 (#29, #30, #31)
* (공통) 네트워크 접근이 차단된 환경에서 offline-deps-builder로 의존성 스킬을 만드는 README 안내 추가 (#34, #35)
* (spectro-maestro 및 synth-ventriloquist) 노출된 음표 위의 강한 자음, 길게 끄는 ee 모음, 약한 단어를 다루는 가사 작성 지침 추가 (#22, #23, #27, #33, #38)
* (spectro-maestro 및 synth-ventriloquist) 길게 끄는 ee 모음의 몸통 대역을 보강하는 선택형 설정(Style vowel_body) 추가 (#24)
* (spectro-maestro 및 synth-ventriloquist) 강한 자음, 길게 끄는 ee 모음, 노출된 음표 위의 약화 모음을 가사 초안 단계에서 모든 리드 라인에 대해 검사하는 가사 린트 추가 (#25, #26, #27, #28, #30)
* (spectro-maestro 및 synth-ventriloquist) 음향 모델이 정수형 얕은 확산 깊이를 받는 DiffSinger 보이스뱅크의 렌더링 실패 수정 (#36, #37)
* (synth-ventriloquist) 음정 이탈, 거칠거나 묻힌 모음, 약박에 놓인 강세, 보정 후에도 사라지는 라인 끝을 백킹 보컬까지 확인하는 보컬 검사 추가 (#15, #16, #18, #21)
* (synth-ventriloquist) TTS 목소리 리드가 밝게 들리도록 디에서를 뺀 보컬 체인 및 좁힌 더킹 대역으로 변경 (#18)
* (synth-ventriloquist) 디에서, 강한 자음 억제, 더킹 대역 폭을 선택할 수 있는 설정 추가 (#19, #20)
* (synth-ventriloquist) 보컬 여유 검사의 믹스 판독 오류 및 거의 같은 렌더링에서 달라지는 인식 점수 수정 (#19)
* (synth-ventriloquist) 트랙 이름으로 믹스 역할을 추정할 때 더블 보컬 테이크를 두 번째 리드로 맞추는 오류 수정 (#20)
* (synth-ventriloquist) 길게 끄는 단어가 긴 마찰음으로 시작하지 않도록 모음 주기성 기준으로 라인 타이밍을 맞추도록 변경 (#28, #37)

## 2026-10-16
- (synth-ventriloquist) Changed songs with vocals to duck the music under sung lead lines by default (#13)
- (synth-ventriloquist) Changed the vocal ceiling check to judge each section (#13)

* (synth-ventriloquist) 보컬이 있는 곡에서 리드 보컬 구간의 음악 레벨을 기본으로 낮추도록 변경 (#13)
* (synth-ventriloquist) 보컬 상한 검사를 섹션별로 판정하도록 변경 (#13)

## 2026-10-14
- (spectro-maestro and synth-ventriloquist) Changed the English edition skill names to the Korean edition names (#9)
- (synth-ventriloquist) Added the GPL license text and DrumSynth preset sources to kit folders, project folders and packs that carry recorded drum hits (#7)
- (synth-ventriloquist) Added fallbacks for drum kits that the installed LMMS cannot record (#8)
- (synth-ventriloquist) Fixed the LMMS version read from the official AppImage (#8)

* (spectro-maestro 및 synth-ventriloquist) 영어판 스킬 이름을 한국어판 스킬 이름과 같게 변경 (#9)
* (synth-ventriloquist) 녹음한 드럼 타격을 담은 킷 폴더, 프로젝트 폴더, 팩에 GPL 라이선스 전문 및 DrumSynth 프리셋 원본 추가 (#7)
* (synth-ventriloquist) 설치된 LMMS로 드럼 킷을 녹음할 수 없을 때의 대체 절차 추가 (#8)
* (synth-ventriloquist) 공식 AppImage에서 LMMS 버전을 잘못 읽는 오류 수정 (#8)

## 2026-10-13
- (common) Added the first public release with the Korean and English editions of spectro-maestro and synth-ventriloquist

* (공통) spectro-maestro 및 synth-ventriloquist 스킬의 한국어판 및 영어판을 담은 최초 공개 버전 추가
