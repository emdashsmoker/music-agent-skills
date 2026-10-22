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
- (Skill header) Group the entries of each date under ### headers named after the folders under skills/. Use ### Common for repository-wide changes and changes that apply to every skill. Repeat a change that applies to several skills under each of their headers.
- (Entry order) Put the Common header first and sort the other headers by skill folder name. List the entries under each header in pull request order.
- (English entries) List the English entries first under each header with the "-" bullet.
- (Korean entries) Leave one blank line after the English entries and list the same changes in the same order with the "*" bullet so that they render as a separate list.
- (English format) - Description that starts with the change type verb (#PR number)
- (Korean format) * Korean noun-ending description that ends with the change type word (#PR number)
- (Korean style) Write each Korean entry in formal note style as a simple sentence (단문) with a noun ending. Keep one subject-predicate relation per entry, turn other clauses into noun phrases, and split an entry that carries two messages. Avoid colloquial expressions and placeholder nouns such as 것, 곳, 거, 셈 and 부분.
- (Change types) Added (추가), Changed (변경), Fixed (수정), Removed (삭제), Action needed (필요)
- (Include) Changes to skill outputs, usage steps, or installation.
- (Exclude) Typo and wording fixes, demo image replacements, README changes unrelated to installation, internal refactoring without behavior changes, and commits that only change CHANGELOG.md.
- (Push) Commit on top of the latest main and push directly to main.
-->

## 2026-10-22

### Common
- Changed the description of each skill to state its purpose without limiting it to electronic music (#80)

* 전자음악 한정 없이 각 스킬의 용도를 설명하도록 description 문구 변경 (#80)

## 2026-10-21

### spectro-maestro
- Fixed the pyworld import that failed without pkg_resources (setuptools 82 or later, or none) and stopped vocal rendering (#76)
- Fixed vocal-check and vocal-try letting a multilingual recognition model guess the language of a track without lang (#76)
- Changed doctor to show the import error of each missing package so that a broken install and an absent one read differently (#78)
- Action needed: install setuptools below 82 where pyworld fails to import with No module named 'pkg_resources' (#78)

* pkg_resources가 없는 환경(setuptools 82 이상 또는 미설치)의 pyworld 불러오기 실패로 보컬 렌더가 중단되는 오류 수정 (#76)
* lang이 없는 트랙의 vocal-check와 vocal-try에서 다국어 인식 모델이 언어를 추정하는 오류 수정 (#76)
* 누락 패키지마다 불러오기 오류 문구를 함께 표시하도록 doctor 출력 변경 (#78)
* pyworld 불러오기가 No module named 'pkg_resources'로 실패하는 환경의 setuptools 82 미만 설치 필요 (#78)

### synth-ventriloquist
- Changed doctor to show the import error of each missing package so that a broken install and an absent one read differently (#78)
- Action needed: install setuptools below 82 where pyworld fails to import with No module named 'pkg_resources' (#78)

* 누락 패키지마다 불러오기 오류 문구를 함께 표시하도록 doctor 출력 변경 (#78)
* pyworld 불러오기가 No module named 'pkg_resources'로 실패하는 환경의 setuptools 82 미만 설치 필요 (#78)

## 2026-10-20

### Common
- Changed Kokoro downloads to a pinned commit that the kokoro_revision setting can replace (#68)
- Added a planning question that sets the reading speed of speech voices to agent-decided, melody-matched or fixed (#69)
- Fixed the lyric lint warning on stressed reduced vowels (#69)
- Fixed three German words (wir, wich, verbums) that the pinned OpenUtau German pack writes with English sounds or cut short (#70)
- Fixed low scores of Japanese and Chinese lines that the recogniser writes in another script (#70)
- Changed syllable counting outside English to join vowels until a line fits its notes (#71)
- Removed the built-in per-language pronunciation tables and non-English carrier words so that the agent supplies the language knowledge (#71)
- Changed the flexible mix style adherence to switch styles without asking (#73)
- Added a flexible-HITL option that asks before switching the mix style (#73)

* kokoro_revision 설정으로 리비전을 선택할 수 있는 Kokoro 고정 커밋 다운로드로 변경 (#68)
* TTS 목소리의 읽기 속도를 에이전트 판단, 멜로디 맞춤, 고정 속도 중에서 선택하는 기획 질문 추가 (#69)
* 강세 위치의 약화 모음에도 가사 린트 경고가 표시되는 오류 수정 (#69)
* 고정 OpenUtau 독일어 팩의 독일어 단어 3개(wir, wich, verbums) 발음 오류 수정 (#70)
* 인식기의 다른 문자 표기로 일본어와 중국어 라인 점수가 낮게 나오는 오류 수정 (#70)
* 영어 외 언어의 음절 수 산정 방식을 라인 음표 수 기준의 인접 모음 병합으로 변경 (#71)
* 언어 지식을 에이전트가 제공하도록 내장 언어별 발음 표 및 영어 외 캐리어 단어 삭제 (#71)
* 유연 준수에서 사용자 확인 없이 믹스 스타일을 전환하도록 변경 (#73)
* 믹스 스타일 전환 전 사용자에게 확인하는 유연-HITL 옵션 추가 (#73)

### spectro-maestro
- Fixed cut model downloads that were kept and reused as broken files (#68)
- Fixed the exposed-note lyric rules that read bright consonant counts as beat weights (#69)

* 다운로드 중단 모델 파일의 보존으로 손상 파일을 반복 사용하는 오류 수정 (#68)
* 노출 음표 가사 규칙이 강한 자음 개수를 박 강세로 해석하는 오류 수정 (#69)

### synth-ventriloquist
- Changed speech-voice lines to read at the pace of their melody (#69)
- Added a phonemes option that sings a line from given IPA or voicebank symbols (#71)

* TTS 목소리 라인의 읽기 속도를 멜로디 속도에 맞추도록 변경 (#69)
* 사용자 지정 IPA 또는 보이스뱅크 기호로 라인을 가창하는 phonemes 옵션 추가 (#71)

## 2026-10-19

### Common
- Added a mix style question to the plan with the forward, balanced, blended, vocal and backbeat presets and an adherence setting (#63)
- Fixed newer DiffSinger exports that stopped at the first line with a missing duration model input (#63)
- Added singing of German, French, Spanish, Italian, Portuguese and Russian words on DiffSinger voicebanks (#67)
- Added a planning question for the recognition model of the vocal checks (#67)
- Added a warning when the opening consonants of a line fall before the song start (#67)
- Fixed European lyrics sung with wrong syllable counts (#67)
- Fixed Brazilian Kokoro voices that read European Portuguese (#67)

* 전면, 균형, 융합, 보컬 전면, 백비트 전면 프리셋 및 준수 수준 설정을 갖춘 믹스 스타일 기획 질문 추가 (#63)
* 최신 DiffSinger 내보내기 모델이 길이 모델 입력 누락으로 첫 라인에서 중단되는 오류 수정 (#63)
* DiffSinger 보이스뱅크의 독일어, 프랑스어, 스페인어, 이탈리아어, 포르투갈어, 러시아어 가창 추가 (#67)
* 보컬 검사용 음성 인식 모델을 묻는 기획 질문 추가 (#67)
* 라인 첫 자음이 곡 시작 전에 놓일 때의 경고 추가 (#67)
* 유럽 언어 가사의 음절 수 오류 수정 (#67)
* 브라질 Kokoro 목소리가 유럽 포르투갈어로 발음하는 오류 수정 (#67)

### spectro-maestro
- Fixed voicebanks whose pitch or variance model lists fewer speakers than the acoustic model (#63)
- Fixed lines whose phonemes entry was written for another engine, which collapsed into one syllable and stopped the render (#66)
- Fixed vocal-try wordings typed in decomposed form that lost their accents (#67)

* 음향 모델보다 피치 또는 분산 모델의 화자 수가 적은 보이스뱅크의 사용 불가 오류 수정 (#63)
* 다른 엔진 기호의 phonemes 항목에 따른 단일 음절 처리로 렌더링이 중단되는 오류 수정 (#66)
* 분해형 입력 vocal-try 문구의 악센트가 누락되는 오류 수정 (#67)

## 2026-10-18

### Common
- Fixed API names, defaults and figures in the skill documents that did not match the toolkit code (#41, #42)
- Added a lyric step that plans new lyrics and reviews user-written lyrics against what the chosen voice sings well (#45, #47)
- Added a lyric tip on short function words that blur on off-beat notes while the match score passes them (#52)
- Added a lyric review from several seats where the rules are silent (#53)
- Added a step that attaches GitHub repositories before using a voicebank repository or downloading the LMMS AppImage (#54)
- Changed voicebank downloads, unpacking and terms-of-use lookup to agent steps so that terms files under any name are found (#54)
- Added the default of the expressiveness setting of the voicebank pitch model with guidance on when to lower it (#56)
- Added lint warnings for clipped line endings and rushed lines (#57)
- Added guidance that takes vocal rhythm from spoken stress (#57)
- Fixed Korean, Japanese, Chinese and Russian lyrics that broke at the text level (#58)
- Fixed doctor stopping before its report on machines without the core packages (#60)

* 툴킷 코드와 맞지 않던 스킬 문서의 API 이름, 기본값, 수치 수정 (#41, #42)
* 목소리별 가창 적합성 기준의 신규 가사 기획 및 사용자 가사 검토 단계 추가 (#45, #47)
* 약박 음표에서 짧은 기능어의 불명확한 발음이 일치 점수를 통과하는 사례의 가사 작성 지침 추가 (#52)
* 규칙 범위 밖의 가사 문제를 여러 관점에서 점검하는 검토 단계 추가 (#53)
* 보이스뱅크 저장소 사용 또는 LMMS AppImage 다운로드 전 GitHub 저장소 연결 단계 추가 (#54)
* 파일 이름과 무관하게 이용 약관 문서를 찾도록 보이스뱅크 다운로드, 압축 해제, 약관 확인을 에이전트 단계로 변경 (#54)
* 보이스뱅크 피치 모델의 expressiveness 기본값 및 하향 조정 시점 안내 추가 (#56)
* 라인 끝 단어 단축 및 음절 과밀의 린트 경고 추가 (#57)
* 말의 강세를 기준으로 보컬 리듬을 정하는 지침 추가 (#57)
* 한국어, 일본어, 중국어, 러시아어 가사의 텍스트 처리 오류 수정 (#58)
* 핵심 패키지 미설치 컴퓨터에서 doctor가 보고 전에 중단되는 오류 수정 (#60)

### spectro-maestro
- Added a step that confirms the full lyrics before any line is sung (#50)
- Changed the planning defaults to list the song file and project JSON as deliverables (#52)
- Changed the default render formats to include ogg (#55)
- Fixed vocal checks that scored non-English lines as weak (#59)

* 가창 렌더링 전 전체 가사의 사용자 승인 단계 추가 (#50)
* 기획 단계 기본 산출물에 곡 파일 및 프로젝트 JSON을 포함하도록 변경 (#52)
* 기본 렌더링 형식에 ogg를 포함하도록 변경 (#55)
* 영어 외 라인을 보컬 검사에서 약한 라인으로 판정하는 오류 수정 (#59)

### synth-ventriloquist
- Changed planning to go ahead with a plan that the user keeps after stating the expected loss of quality once (#48)
- Removed the planning rule that declined lyrics the skill would not write in other contexts (#48)
- Changed the voices offered at planning to the default Kokoro voices af_heart and am_michael (#51)
- Changed the encoder for ogg, mp3 and flac from ffmpeg to soundfile (#55)
- Fixed sung syllables that landed off the beat (#56)
- Fixed hiss that was resynthesized as pitched noise (#56)
- Fixed voicebank renders of the same line that differed within one run (#58)

* 사용자의 기존 기획 유지 시 예상 품질 저하의 1회 고지 후 기획대로 진행하도록 변경 (#48)
* 기획 단계의 가사 내용 거절 규칙 삭제 (#48)
* 기획 단계에서 소개하는 목소리를 Kokoro 기본 목소리 af_heart 및 am_michael로 변경 (#51)
* ogg, mp3, flac 인코딩 도구를 ffmpeg에서 soundfile로 변경 (#55)
* 가창 음절이 박자 위치에서 벗어나는 오류 수정 (#56)
* 마찰음이 유성 잡음으로 재합성되는 오류 수정 (#56)
* 같은 실행 안에서 같은 라인의 보이스뱅크 렌더링 결과가 달라지는 오류 수정 (#58)

## 2026-10-17

### Common
- Added lyric writing guidance for bright consonants, held ee vowels and weak words on exposed notes (#22, #23, #27, #33, #38)
- Added an opt-in body fill for held ee vowels (Style vowel_body) (#24)
- Added a lyric lint for bright consonants, held ee vowels and reduced vowels on exposed notes that runs on every lead line while drafting (#25, #26, #27, #28, #30)
- Added SHA256SUMS.txt files with the checksums of the install packages to each skill folder (#29, #30, #31)
- Added a README note on building a dependency skill with offline-deps-builder where network access is blocked (#34, #35)
- Fixed DiffSinger voicebanks whose acoustic export takes an integer shallow-diffusion depth (#36, #37)

* 노출 음표 위의 강한 자음, 장음 ee 모음, 약한 단어를 다루는 가사 작성 지침 추가 (#22, #23, #27, #33, #38)
* 장음 ee 모음의 중역대를 보강하는 선택형 설정(Style vowel_body) 추가 (#24)
* 강한 자음, 장음 ee 모음, 노출 음표 위의 약화 모음을 가사 초안 단계의 모든 리드 라인에서 검사하는 가사 린트 추가 (#25, #26, #27, #28, #30)
* 스킬 폴더별 설치용 패키지의 체크섬을 담은 SHA256SUMS.txt 파일 추가 (#29, #30, #31)
* 네트워크 차단 환경에서 offline-deps-builder로 의존성 스킬을 생성하는 README 안내 추가 (#34, #35)
* 음향 모델이 정수형 얕은 확산 깊이를 받는 DiffSinger 보이스뱅크의 렌더링 실패 수정 (#36, #37)

### synth-ventriloquist
- Added vocal checks for off-pitch lines, rough or swallowed vowels, stress on weak beats and line endings that still die after repair, covering backing vocals too (#15, #16, #18, #21)
- Changed the vocal strip to drop the de-esser and narrow the duck dip so that speech-voice leads sound brighter (#18)
- Added opt-in settings for a de-esser, bright consonant taming and the width of the duck dip (#19, #20)
- Fixed vocal margin checks that misread the mix (#19)
- Fixed recognition scores that changed between near-identical renders (#19)
- Fixed doubled vocal takes leveled as a second lead when mix roles are guessed from track names (#20)
- Changed vocal timing to follow vowel periodicity so that held words no longer start as a long hiss (#28, #37)

* 음정 이탈, 모음 잡음화, 모음 묻힘, 약박 강세, 보정 후 라인 끝 소실을 백킹 보컬까지 확인하는 보컬 검사 추가 (#15, #16, #18, #21)
* TTS 목소리 리드의 고음역 유지를 위해 기본 보컬 처리를 디에서 제외 및 더킹 대역 축소로 변경 (#18)
* 디에서, 강한 자음 억제, 더킹 대역 폭을 선택할 수 있는 설정 추가 (#19, #20)
* 보컬 여유 검사의 믹스 판독 오류 수정 (#19)
* 거의 같은 렌더링에서 인식 점수가 달라지는 오류 수정 (#19)
* 트랙 이름에 따른 믹스 역할 추정 시 더블 보컬 테이크를 두 번째 리드 레벨로 조정하는 오류 수정 (#20)
* 장음 단어의 긴 마찰음 시작 방지를 위해 라인 타이밍 정렬 기준을 모음 주기성으로 변경 (#28, #37)

## 2026-10-16

### synth-ventriloquist
- Changed songs with vocals to duck the music under sung lead lines by default (#13)
- Changed the vocal ceiling check to judge each section (#13)

* 보컬 포함 곡에서 리드 보컬 구간의 음악 레벨 감쇠를 기본 적용하도록 변경 (#13)
* 보컬 상한 검사를 섹션별로 판정하도록 변경 (#13)

## 2026-10-14

### Common
- Changed the English edition skill names to the Korean edition names (#9)

* 영어판 스킬 이름을 한국어판 스킬 이름과 동일하게 변경 (#9)

### synth-ventriloquist
- Added the GPL license text and DrumSynth preset sources to kit folders, project folders and packs that carry recorded drum hits (#7)
- Added fallbacks for drum kits that the installed LMMS cannot record (#8)
- Fixed the LMMS version read from the official AppImage (#8)

* 녹음 드럼 타격을 담은 킷 폴더, 프로젝트 폴더, 팩에 GPL 라이선스 전문 및 DrumSynth 프리셋 원본 추가 (#7)
* 기존 설치 LMMS의 드럼 킷 녹음 불가 시 대체 절차 추가 (#8)
* 공식 AppImage에서 LMMS 버전을 잘못 인식하는 오류 수정 (#8)

## 2026-10-13

### Common
- Added the first public release with the Korean and English editions of the skills

* 한국어판 및 영어판 스킬을 담은 최초 공개 버전 추가
