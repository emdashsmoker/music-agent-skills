# 예제 곡

툴킷으로 쓴 완성곡 4개다. 폴더마다 곡 스크립트, 완성곡의 MIDI 파일, 보컬 곡의 가사가 들어 있다. 렌더된 오디오는 들어 있지 않다. 곡을 들으려면 스크립트와 `produce`를 실행한다. 예제는 스킬의 일부이며 스킬의 라이선스가 적용된다. 직접 쓴 곡은 쓴 사람의 저작물이다.

| 폴더 | 곡 | 보여 주는 것 |
|---|---|---|
| `first_light_uplifting_trance/` | First Light, 138 BPM, A단조, 256마디, 연주곡 | 브레이크다운 2개와 클라이맥스가 있는 긴 클럽 형식, 파트를 더하고 빼서 만드는 에너지 곡선, 필터 스윕과 페이드, 높은 옥타브를 겹친 슈퍼소우 리드, 구르는 엇박 베이스, 공용 라이저와 임팩트 트랙 |
| `rubber_line_acid_techno/` | Rubber Line, 130 BPM, A 프리지안, 120마디, 연주곡 | 슬라이드와 악센트가 있는 303 계열 베이스 라인, 노브 오토메이션(재현되지 않음) 대신 곡 전체에서 움직이는 채널 레조넌스 필터, 909 킷, 새츄레이션 |
| `signal_fires_futurepop/` | Signal Fires, 132 BPM, A단조, 104마디, 가창 | 벌스, 프리코러스, 코러스, 브리지의 노래 형식, 코러스에 하모니와 더블이 붙는 리드 가창, 보컬 더킹, 밝기 점검에서 정한 보컬 EQ, 스크립트 하나에서 나오는 드럼 편곡 2가지: `trance`(부드러운 킥, 클랩 백비트)와 `hard`(펀치 있는 킥, 스네어 백비트, 림, 필인, 킥 픽업) |
| `grey_light_doomer/` | Grey Light, 124 BPM, E단조, 112마디, 가창 | 의도적으로 유지한 어둡고 느리게 움직이는 믹스, 낮고 무표정한 보컬 스타일, 전달력을 위해 2마디 줄로 쓴 코러스, 기타 같은 플럭 리프, Linn 계열 드럼 |

## 실행하기

프로젝트가 현재 폴더에 쓰이므로 자기 작업 폴더에서 실행한다.

```bash
mkdir work && cd work
python <스킬>/examples/first_light_uplifting_trance/song.py
python <스킬>/scripts/lmms_tool.py produce first_light.mmp -o out

python <스킬>/examples/signal_fires_futurepop/song.py kokoro:af_heart signal_fires hard
python <스킬>/scripts/lmms_tool.py produce signal_fires.mmp -o out_signal_fires
```

보컬 곡은 첫 인자로 목소리를 받으며(선택지는 `references/vocals.md`) 처음 쓸 때 음성 모델을 내려받는다. CPU 코어 2개에서 트랜스 곡의 produce는 약 15분, 나머지는 5-10분 걸린다.

## 본보기로 쓰기

- 음표 대신 구조를 가져온다. 섹션을 선언하는 방법, 섹션을 도는 루프 하나가 드럼과 베이스를 놓는 방법, 목소리가 받기 전에 악기가 훅을 제시하는 방법을 본다.
- 주석은 값을 고른 이유를 말한다. 그중 여럿은 리포트의 측정(레벨, 필터, EQ)을 기록한 것이다.
- 퓨처팝 스크립트는 매개변수 하나로 두 편곡을 한 원본에 유지하는 방법을 보여 준다. 곡을 둘로 가르지 않고 사용자에게 대안을 제시하는 방법이다.
