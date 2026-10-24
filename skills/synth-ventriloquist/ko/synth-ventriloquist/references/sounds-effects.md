# 음색과 이펙트

모든 소리는 설정값을 가진 LMMS 악기("패치")다. 라이브러리에는 약 130개의 패치가 있다. 패치는 출발점이다. 곡에 다른 것이 필요하면 하나를 복사해 바꾼다.

## 목차

- 음색 찾기와 오디션
- 라이브러리의 드럼머신
- 역할별 신스 패치
- 패치 바꾸기
- 패치를 처음부터 만들기
- LMMS 프리셋, 샘플, SoundFont 쓰기
- 이펙트
- 오토메이션 대상
- 음색의 재현성 규칙

## 음색 찾기와 오디션

```bash
python scripts/lmms_tool.py sounds                       # 역할별 이름
python scripts/lmms_tool.py sounds moog_bass acid_bass reese_bass --out work/audition
```

두 번째 형태는 지정한 패치를 하나씩 따로 렌더하고, 표(음량, 길이, 밝기, 주 주파수)를 출력하고, 작은 스펙트로그램을 모은 `sounds.png`를 쓴다. 후보 중에서 고를 때와 패치를 바꾼 뒤에 쓴다. 숫자와 그림으로 소리를 "듣는" 방법이다. `sounds all`은 라이브러리 전체를 측정한다.

## 라이브러리의 드럼머신

머신 킷은 LMMS 자체 드럼 합성의 원샷 녹음이고, 이름이 붙은 킥은 깨끗하게 합성한 원샷(피치가 떨어지는 사인파와 짧은 클릭)이다. 스킬은 이들을 오디오로 싣지 않는다. 킷은 곡이 처음 필요로 할 때 이 컴퓨터에서 만들어(`lmms_tool.py kit`으로 확인, `kit --build`로 즉시 생성) 킷 폴더에 보관하므로, 이후 이 컴퓨터의 모든 렌더에서 드럼이 같은 소리를 낸다. 이름이 붙은 킥은 모든 컴퓨터에서 동일하다. 노이즈가 섞인 녹음 타격(스네어, 햇, 클랩)은 같은 드럼머신의 두 테이크처럼 컴퓨터마다 조금 다르다. 접두어가 없는 타격(`kick_acoustic`, `kick_hardcore`, `snare_harsh`, `clap`, `ohat`, `ride` 등)은 설치된 LMMS에 기본으로 들어 있는 샘플을 바로 재생한다.

| 접두어 | 성격 | 대표 장르 |
|---|---|---|
| `909_` | 펀치 있는 킥, 밝은 햇, 날카로운 클랩과 스네어 (Roland TR-909 계열) | 하우스, 테크노, 트랜스, 퓨처팝, 개버 |
| `808_` | 깊고 긴 킥, 탄력 있는 스네어, 카우벨, 클라베, 탐 (TR-808 계열) | 힙합, 트랩, 일렉트로, 신스팝 |
| `606_` | 얇고 건조하고 타이트함 (TR-606 계열) | 애시드, IDM, 일렉트로 |
| `linn_` | 자연스러운 80년대 드럼과 탐, 카바사, 탬버린 (LinnDrum 계열) | 신스팝, 신스웨이브, 두머와 포스트펑크 |
| `cr78_` | 부드러운 빈티지 프리셋 리듬 박스 (CR-78 계열) | 콜드웨이브, 로파이, 다운템포 |
| `electro_`, `8bit_`, `jazz_`, `amen_`, `reverb_` | 일렉트로 킷, 칩 사운드, 어쿠스틱 느낌의 타격, 게이트 리버브 타격 | 일렉트로, 칩튠, 브레이크비트, 80년대 스타일 |
| 이름이 붙은 킥 | `trance_kick`, `house_kick`, `techno_kick`, `hard_kick`, `industrial_kick`, `psy_kick`, `dnb_kick`, `boom_kick` | 이름에 있는 장르 |
| 접두어 없는 타격 (LMMS 기본 샘플) | `kick_acoustic`, `kick_hardcore`, `kick_distorted`, `kick_hiphop`, `snare_acoustic`, `snare_harsh`, `clap`, `hat`, `ohat`, `ride`, `crash`, `tom_low` 등 | 브레이크비트, 하드코어, 인더스트리얼, 힙합 |

별도의 707 킷은 없다. 909와 Linn 킷이 그 영역을 맡는다. TB-303 계열 베이스 라인은 `acid_bass`와 `acid_square` 패치(LMMS의 LB302)다. 겹치는 음은 슬라이드가 되고, 악센트는 더 큰 음이다.

## 역할별 신스 패치

| 역할 | 패치 |
|---|---|
| bass | `808_bass`, `acid_bass`, `acid_square`, `ebm_bass`, `fm_bass`, `moog_bass`, `offbeat_bass`, `pick_bass`, `reese_bass`, `rolling_bass`, `wobble_bass` |
| sub | `sub_bass` |
| lead | `acid_lead`, `chip_lead`, `rave_stab`, `saw_lead`, `square_lead`, `supersaw_lead`, `supersaw_high` |
| pluck | `bell`, `jangle_pluck`, `pluck`, `trance_pluck` |
| keys | `chord_stab`, `epiano`, `organ` |
| pad | `cold_pad`, `dark_pad`, `string_pad`, `warm_pad` |
| fx | `reverse_crash`, `sub_drop`, `white_noise`, `zap` |

`python scripts/lmms_tool.py genres <이름>`은 장르 프로파일이 추천하는 킷을 보여 주고, `genres.md`는 스타일마다 어울리는 패치를 든다.

## 패치 바꾸기

```python
from lmmskit import sounds
darker = sounds.get("supersaw_lead", filter=(2500, 0.4, sounds.FILTER_LP24),
                    env={"attack": 0.02, "decay": 0.4, "sustain": 0.6, "release": 0.5})
lead = song.add("lead", darker)
```

패치의 최상위 키:

- `plugin`과 `attrs`: LMMS 악기와 그 원시 설정값. `sounds.get(name, attrs={...})`는 기존 설정에 변경을 합친다.
- `env`: 초 단위 볼륨 엔벨로프(`attack`, `hold`, `decay`, `release`)와 0-1 범위의 `sustain`.
- `filter`: `(컷오프 Hz, 레조넌스, 종류)`. 종류 상수는 `FILTER_LP`, `FILTER_HP`, `FILTER_BP`, `FILTER_NOTCH`, `FILTER_MOOG`, `FILTER_LP24`. `cut_env`는 필터 엔벨로프(`env`와 같은 키에 `amount` 추가)를, `cut_lfo`는 템포에 동기된 필터 흔들림(`{"beats": 0.5, "amount": 0.5}`)을 더한다.
- `fx`: 소리 자체에 속하는 이펙트(패드의 코러스, 베이스의 새츄레이션). 아래 이펙트 빌더를 써서 `[("chorus", {...}), ...]` 형태로 쓴다.
- `role`: 기본 믹스 역할.

## 패치를 처음부터 만들기

대부분의 전자음악 소리를 맡는 악기들의 `attrs`를 만들어 주는 보조 함수가 있다.

- `sounds.osc3(waves, vols, coarse, fine, pan, spread, phase, mod)`: TripleOscillator용. 파형(상수 `SINE`, `TRIANGLE`, `SAW`, `SQUARE`, `MOOG_SAW`, `EXPONENTIAL`, `NOISE`), 반음과 센트 단위 디튠, 오실레이터 사이의 혼합 방식(`MOD_MIX`, `MOD_FM`, `MOD_PM`, `MOD_AM`, `MOD_SYNC`)을 가진 오실레이터 3개다. 디튠한 소우는 슈퍼소우와 패드가 되고, 사인과 스퀘어는 오르간이 되고, FM은 벨이나 금속성 베이스가 된다.
- `sounds.acid(cutoff, resonance, env_mod, decay, dist, square)`: LB302 애시드 신스용.
- `sounds.kicker(start, end, decay_ms, ...)`: 합성 킥용. `start` Hz에서 `end` Hz로 스윕하는 사인파다. `noise` 노브는 0으로 둔다. 노이즈가 킥 길이만큼 지속되어 매 박에 히스로 들린다. 클릭이 있는 킥이 필요하면 라이브러리 킥에서 출발하거나 `scripts/lmmskit/kit.py`의 `KICKS` 표를 고치고 `lmms_tool.py kit --rebuild`를 실행한다.
- `sounds.sample(path, loop=False, reversed_=False)`: 오디오 파일을 재생한다.

새 패치의 예:

```python
hoover = {"plugin": "tripleoscillator", "role": "lead",
          "attrs": sounds.osc3(waves=(sounds.SAW, sounds.SAW, sounds.SQUARE), vols=(40, 40, 30), coarse=(0, -12, 0),
                               fine=((-18, 14), (12, -16), (0, 0))),
          "env": {"attack": 0.01, "decay": 0.3, "sustain": 0.8, "release": 0.2},
          "filter": (5000, 0.4, sounds.FILTER_LP24),
          "fx": [("chorus", {"rate_hz": 0.6, "depth_ms": 4.0, "wet": 0.6})]}
```

새 패치는 쓰기 전에 오디션한다. 그럴듯하게 읽히는 패치도 무음이거나, 너무 작거나, 거칠 수 있으며, 오디션 표가 몇 초 만에 이를 보여 준다. `sounds.set_cutoff_lfo(project, track, beats, amount)`는 템포에 동기된 필터 흔들림을 더한다.

## LMMS 프리셋, 샘플, SoundFont 쓰기

- `Project.add_preset_track(name, preset_path)`는 LMMS 프리셋 파일(`.xpf`)을 불러온다. LMMS 데이터 폴더(`lmms_tool.py doctor`가 출력)에 악기별 프리셋이 들어 있다.
- `sounds.sample("drums/kick01.ogg")`는 LMMS 기본 샘플 폴더나 프로젝트 옆 `samples/`의 파일을 재생한다. 사용자의 샘플은 프로젝트 옆 `samples/`에 넣어 프로젝트를 옮길 수 있게 유지한다.
- 기존 프로젝트의 SoundFont(`sf2player`)와 VST 악기는 가리키는 파일이 렌더하는 컴퓨터에 있는 한 계속 동작한다. 이 툴킷은 그것들을 만들거나 내장하지 않는다.

## 이펙트

`lmmskit.fx`의 빌더는 체인에 이펙트를 더하고 그 이펙트를 돌려준다. 파트의 믹스 체인은 `part.chain`, 버스 체인은 `song.mixer.fx(song.bus("music"))`, 마스터는 `song.mixer.fx(0)`이다.

| 빌더 | 용도 |
|---|---|
| `fx.eq(chain, highpass, lowpass, low_shelf, high_shelf, peaks, slope)` | 음색. 셸프는 `(Hz, dB)`. 피크는 최대 4개의 `(Hz, dB, 옥타브)`. |
| `fx.compressor(chain, threshold_db, ratio, attack_ms, release_ms, makeup_db)` | 레벨 제어와 펀치 |
| `fx.limiter(chain, ceiling_db, input_gain_db)` | 브릭월. 마스터의 마지막(`song.master()`가 추가) |
| `fx.saturator(chain, drive, character)`, `fx.distortion(chain, drive)`, `fx.bitcrush` | 배음과 거친 질감: 베이스, 드럼, 개버 킥, 인더스트리얼, 로파이. `drive`는 10까지 |
| `fx.reverb(chain, decay_s, room, damp_hz, predelay_ms)` | 공간. 센드 버스용으로 기본값은 완전 웻 |
| `fx.delay(chain, bpm, left_16ths, right_16ths, feedback)` | 템포에 동기된 에코 |
| `fx.chorus`, `fx.phaser`, `fx.flanger` | 폭과 움직임 |
| `fx.deesser`, `fx.exciter`, `fx.bass_boost` | 보컬 치찰음, 합성 고역, 저역 보강. LMMS 1.2의 디에서(de-esser)는 임계값과 무관하게 분할 주파수 위를 고정으로 깎으므로 기본 보컬 스트립에 없다. 사용자가 명시적으로 요청할 때만 `song.vocal(..., deesser={})`로 켜고 스템 스펙트럼을 확인한다 |
| `fx.stereo_width`, `fx.mono` | 넓히기, 또는 모노로 모으기(킥과 서브) |
| `fx.filter_sweep(chain, cutoff, resonance, kind)` | 오토메이션용 필터 |
| `fx.ladspa(chain, "file:Label", {"포트 이름": 값})` | 내장 LADSPA 플러그인 225개 중 아무것이나. `fx.catalog()`가 포트 이름, 범위, 기본값과 함께 나열한다 |

리버브와 딜레이는 보통 공용 센드 버스에 둔다(파트의 `sends={"reverb": 0.3}`). 곡 전체가 하나의 공간을 쓰게 되고, 파트마다 리버브를 두는 것보다 CPU가 덜 든다.

## 오토메이션 대상

`song.automate(param, [(bar, value), ...])`에 파라미터를 넘긴다.

- 이펙트 컨트롤: `fx.control(effect, "name")`. LADSPA 이펙트는 포트 이름(`"Input gain (dB)"`), 네이티브 이펙트는 속성 이름(`"cut1"`)을 쓴다. `song.sweep`과 `song.fade`가 이것을 쓴다.
- 트랙 볼륨과 팬: `part.track.param("vol")`, `part.track.param("pan")`.
- 트랙 자체의 필터: `part.track.shaping_param("fcut")`(Hz)와 `"fres"`. 이 필터는 TripleOscillator와 샘플 플레이어 같은 음표 기반 악기에 있다. LB302는 이 필터를 거치지 않는다.
- 악기 자체의 노브(LB302의 `part.track.plugin_param("vcf_cut")`, TripleOscillator의 오실레이터 볼륨)는 자유롭게 값을 정할 수 있다. 다만 노브의 오토메이션은 안정적으로 재현되지 않으며(아래 참조) lint가 경고한다. 움직이는 애시드 라인에는 LB302 노브를 고정하고 그 채널에서 레조넌스 필터를 스윕한다: `song.sweep("acid", at, bars, 300, 9000, resonance=3.0, rest_hz=9000)`.

## 음색의 재현성 규칙

같은 스크립트는 매번 같은 오디오를 렌더해야 한다. 같은 프로젝트를 반복 렌더해서 확인한 내용은 다음과 같다.

- LMMS의 일부 동작은 스레드 사이의 타이밍에 좌우된다. 그래서 툴킷은 운영체제가 허용하는 곳(Linux)에서 LMMS를 CPU 코어 1개로 시작하며, 시험에서 아래의 타이밍 의존 사례가 이 방법으로 재현 가능해졌다. 다른 시스템에서는 달라질 수 있다.
- DrumSynth 드럼 프리셋(`.ds` 파일)은 어떤 시스템에서든 렌더마다 새 무작위 노이즈로 합성된다. 그래서 라이브러리는 컴퓨터마다 한 번 만든 그 프리셋의 녹음(킷 폴더)을 재생한다.
- 피크 컨트롤러 사이드체인은 어떤 시스템에서든 렌더마다 다르다. `song.sidechain()`은 같은 더킹을 오토메이션으로 쓴다.
- 악기 자체 노브의 오토메이션은 여러 코어에서 렌더마다 달랐다. 코어 1개에서는 대부분의 렌더가 동일했지만, 완성곡 하나가 두 번째 렌더에서 다르게 나온 적이 있다. 재현 불가능한 것으로 취급한다.
- 타이밍 의존: Kicker 트랙 여러 개가 연주될 때의 Kicker 노이즈 노브.
- 일부 LADSPA 플러그인은 실행마다 다르게 시작한다. Calf Saturator와 TAP TubeWarmth는 부하가 걸린 컴퓨터에서 그랬고, Chebyshev 디스토션은 매번 그랬다. `fx`의 빌더는 부하 상태의 반복 렌더 시험을 통과한 플러그인만 쓴다. `fx.ladspa`로 더한 플러그인은 이 시험을 거치지 않았으므로 `produce`의 반복 점검으로 판정한다.
- 303 계열 신스 LB302는 가끔 조금 다른 내부 상태로 렌더를 시작한다. 그 신스를 쓰는 곡의 두 렌더는 믹스보다 65-72 dB 낮은 저역 잔차만큼 차이가 난다. 들리지 않는 수준이며 `produce`는 `nearly_repeatable`로 보고한다.
- 스크립트 안의 무작위 요소에는 모두 고정 시드가 필요하다.

`produce`는 완성된 프로젝트를 한 번 더 렌더해 두 파일이 동일한지 보고한다(`repeatable` 또는 `not_repeatable`). `lint`는 프로젝트에서 볼 수 있는 원인을 짚는다(`unrepeatable_*` 결과).

사용자가 제공한 프로젝트에 그런 음원이 있으면 렌더가 실행마다 조금 달라질 수 있다. 보고에 그 사실을 적고 해당 트랙을 오디오로 고정하는 방법을 제안한다.
