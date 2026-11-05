# 데모 영상 직접 촬영 가이드

> **3분 시연 영상의 컷 구성과 내레이션 스크립트**: `../presentation/demo_video_script.md` (과제 필수 요소 5가지를 모두 포함한 타임라인).
> 이 문서는 실행 방법과 조작법.

`live_demo.py`는 평가(`run_episode.py`)와 **완전히 같은 정책**을 MuJoCo 대화형 뷰어 창에서 실시간으로 보여 준다.
창을 화면 녹화하면서 직접 설명하면 된다. (시작 시 일시정지 상태 → 카메라·녹화 준비 후 Space로 시작)

## 1. 준비 (본인 PC, 1회)

```bash
cd code
uv venv .venv --python 3.12                     # 또는 python -m venv .venv (Python 3.12)
uv pip install --python .venv/bin/python -r requirements.txt   # Windows: .venv\Scripts\python.exe
```

* venv는 **영문 경로**에 둘 것 (MuJoCo는 한글 경로의 파일을 못 연다. 프로젝트 폴더 이름은 상관없음).
* Windows / Linux는 `python`, **macOS는 `mjpython`** 으로 실행 (MuJoCo 뷰어 요구사항).
* 처음 실행할 때 장식용 스캔 메쉬를 so101-nexus가 내려받으므로 인터넷 연결 필요.

## 2. 실행

```bash
python live_demo.py --device tv_remote --seed 5                 # 실시간, 일시정지로 시작
python live_demo.py --device light_remote --seed 15 --speed 0.5  # 0.5배속(슬로모션)
python live_demo.py --device ac_remote --seed 5 --pause-stages  # 단계가 끝날 때마다 자동 일시정지
python live_demo.py --device stb_remote --seed 9 --cam free --clean   # 마우스로 시점 조작, 옆 패널 숨김
python live_demo.py --device tv_remote --seed 5 --mode no_tool       # 대조실험: 그냥 뒤집기 → 건전지 안 빠짐
python live_demo.py --device tv_remote --seed 5 --mode push_only     # 대조실험: 스프링 쪽으로 밀기만 → 안 빠짐
```

| 키 (뷰어 창에서) | 동작 |
|---|---|
| Space | 일시정지 / 재개 |
| `=` 또는 키패드 `+` / `-` | 2배 빠르게 / 느리게 (0.125x ~ 4x) |
| `[` / `]` | 이전 / 다음 고정 카메라, Esc = 자유 카메라 (왼쪽 패널 Rendering → Camera 에서도 선택 가능) |
| 마우스 (자유 카메라) | 왼쪽 드래그 회전, 오른쪽 드래그 이동, 휠 확대 |
| Tab / Shift+Tab | 왼쪽 / 오른쪽 UI 패널 표시·숨김 |

* 화면 왼쪽 위: 시뮬레이션 시간·배속, 왼쪽 아래: 끝난 단계 목록(OK/FAIL)과 pry 세부 단계. 터미널에는 모든 동작 로그가 나온다.
* 끝나면 `DONE - SUCCESS`가 표시되고, 창을 닫을 때까지 마지막 장면이 유지된다.
* 고정 카메라: `hero`(기본, 작업대 정면), `overview`, `operator`, `wide`, `closeup`(리모컨 근접), `top`, `side`,
  `bincam`(폐건전지 수거함), `slotcam`(pry notch 근접).
* 한 에피소드는 시뮬레이션 시간 약 60~80 초 (실시간 1배 기준 같은 시간 + 일시정지 시간).

## 3. 화면 녹화

* **Windows**: OBS Studio(무료) → 소스 "윈도우 캡처"로 MuJoCo 창 선택 + "오디오 입력 캡처"로 마이크. 또는 Xbox Game Bar
  (`Win+Alt+R` 녹화 시작/종료, `Win+G`에서 마이크 켜기) — 활성 창만 녹화된다.
* **macOS**: `Cmd+Shift+5` → "선택 부분 기록" → 옵션에서 마이크 선택. 또는 OBS.
* 뷰어 창을 최대화(또는 1920×1080)한 뒤 녹화. 깔끔한 화면이 필요하면 `--clean`.

## 4. 추천 촬영 순서 (설명 포인트)

| 순서 | 단계 (화면 왼쪽 아래 표시) | 카메라 추천 | 설명할 내용 |
|---|---|---|---|
| 0 | (일시정지 상태) | `wide` → `hero` | 작업대 구성: 팔 R(주 팔, 리모컨 조작), 팔 L(공구 팔), 지그, 공구 거치대, 빨간 폐건전지 수거함, 파란 소형 폐가전 상자 |
| 1 | push the remote against the jig fence | `hero` | 리모컨을 지그 펜스에 밀어 위치 고정 |
| 2 | pick the pry tool / press + slide the cover off | `closeup` | L은 거치대에서 얇은 공구(스패너형 pry tool)를 집고, R은 커버 걸쇠를 누른 채 밀어서 연다 (누르면서 밀어야만 열림) |
| 3 | hold the remote on the jig | `closeup` | R이 리모컨 옆면을 잡아 지그에 고정 (사람의 다른 손 역할) |
| 4 | push cells into springs, lever + ends over the lips | `slotcam`, `--speed 0.5` 권장 | **핵심.** 공구를 notch에 수직으로 넣고 → 두 셀을 스프링 쪽으로 밀어 + 끝이 고정 립을 지나게 하고 → + 끝을 들어 립 위로 올림 → 스프링이 셀을 립 위에 얹음. 실제 리모컨처럼 밀기만/뒤집기만으로는 안 빠지는 구조 |
| 5 | re-grasp and lift / turn over the battery bin and shake | `bincam` | L이 물러나고 R이 다시 잡아 수거함 위에서 뒤집고 흔들어 셀을 떨어뜨림 (동시에 L은 공구를 거치대로) |
| 6 | drop the empty body into the crate | `overview` | 빈 본체를 소형 폐가전 상자에 넣음 → `DONE - SUCCESS` |
| 7 | (대조실험) `--mode no_tool`, `--mode push_only` | `bincam` / `slotcam` | 공구 없이 뒤집기만, 또는 밀기만 하면 셀이 립에 걸려 빠지지 않음 → 구조가 실제와 같다는 근거 |

팁: `--pause-stages`로 단계마다 멈추고 설명한 뒤 Space로 넘기면 편하다. 한 번 리허설해 보고 찍을 것.

## 5. 추천 seed (평가에서 재시도 없이 깔끔하게 성공한 경우)

최종 평가(eval20, 80/80)에서 모두 성공했고, 아래는 가장 빨리(재시도 없이) 끝나고 공구 반납까지 성공한 seed.

| 기기 | 추천 seed | 소요(시뮬레이션 시간) |
|---|---|---|
| TV 리모컨 `tv_remote` | 5 (또는 14, 15) | 68.8 s |
| 셋톱박스 리모컨 `stb_remote` (AAA) | 9 (또는 13, 7) | 66.3 s |
| 에어컨 리모컨 `ac_remote` | 5 (또는 10, 14) | 68.0 s |
| 조명 리모컨 `light_remote` (AAA) | 15 (또는 9, 13) | 66.1 s |

**실패 케이스**(과제 요구: 영상에 성공과 실패 모두): 최종 정책은 80/80이므로 대조실험으로 보여 준다.
`python live_demo.py --device tv_remote --seed 5 --mode no_tool` (뒤집어도 셀이 립에 걸려 안 떨어짐) 또는
`--mode push_only` (밀기만 하면 스프링이 셀을 다시 립 밑으로 밀어 넣음). 결과 화면에 `DONE - FAILED`.

**3분 제한**: 에피소드 하나가 약 70 s(1배속)이므로, 전체 롤아웃 1개(pry 부분만 `-`로 0.5배속) + 대조실험은
뒤집는 부분만(필요하면 `=`로 2배속) + 나머지는 설명 위주로 구성하면 3분 안에 들어간다.

## 6. (선택) 녹화 대신 mp4로 뽑아서 나중에 내레이션 입히기

```bash
python run_episode.py --seeds 5 --device tv_remote --video --cam closeup   # videos/ 에 mp4 (OSMesa/EGL 등 GL 필요)
```
