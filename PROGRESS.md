# 작업 진행 기록 (인수인계용)

> 다른 AI/세션이 이어받을 때 이 파일부터 읽으세요. 작업할 때마다 맨 아래 "작업 로그"에 추가합니다.
> 브랜치: `claude/beautiful-gates-6udr26` (여기에만 커밋/푸시)

## 1. 사용자 요구사항 (2026-11-05 세션)

1. 지금까지 한 작업(중간발표, 기존 코드)을 참고할 것.
2. **로봇 팔 2개(양팔)** 로 태스크를 성공시킬 것.
3. **기기 4종 모두 성공** (tv_remote, stb_remote(AAA), ac_remote, light_remote(AAA)).
4. 중간발표에서 말한 **얇은 공구(스패너/분해공구 같은 것)** 를 써서 건전지를 꺼낼 것.
5. 리모컨 구조를 **실제와 유사하게**: "스프링 쪽으로 밀기만 하면 저절로 튀어나오는" 구조(기존 fulcrum rib pop-up) 금지.
   → 스프링 쪽으로 밀고(+ 끝을 립 밖으로) **공구로 + 끝을 들어 올려야** 빠지는 구조.
6. **완벽하게 될 때까지 반복** (목표: 4기기 × 여러 seed 100%).
7. **보고서와 PPT는 아직 작성하지 말 것** (사용자가 결과 먼저 보고 수정 지시 예정).
8. 진행상황을 이 파일에 계속 기록할 것.

과제 PDF: `인공지능프로젝트 과제2.pdf` (SO101-Nexus/MuJoCo만 사용, seed 20개 이상 권장, 실패분석 필요).

## 2. 실행 환경 세팅 (클라우드 컨테이너 기준)

```bash
uv venv /home/user/venv --python 3.12
uv pip install --python /home/user/venv/bin/python mujoco==3.17.0 "numpy>=2.0" pillow trimesh manifold3d imageio imageio-ffmpeg so101-nexus==0.10.0
apt-get install -y libegl1 libosmesa6 libgles2      # 오프스크린 렌더링용 (EGL은 실패, OSMesa 사용)
cd code && MUJOCO_GL=osmesa /home/user/venv/bin/python run_episode.py --seeds 0 --device tv_remote
```
- 렌더링은 `MUJOCO_GL=osmesa` 필수. 시뮬레이션만이면 없어도 됨.
- 에피소드 1회 ≈ 실시간 대비 1.5배 (약 60~100 s sim, 40~70 s wall).

## 3. 현재 설계 (이번 세션에서 바꾼 것)

### 3.1 리모컨 배터리 칸 (`code/battery_sim/devices.py`)
- 기존 pop-up 리브(FULCRUM) **삭제**. 셀은 바닥에 평평하게 놓임 (AA/AAA 모두 pitch 16/17 mm → 셀 최저선 |y|=8~8.5 mm).
- `+` 끝: **고정 립** 4.5 mm (셀 크레스트와 0.5 mm 틈), 립은 |y|≥4.8 mm (`LIP_IN`) → 두 립 사이 틈 9.6 mm < AAA 직경 → 뒤집어도 셀이 못 빠짐.
- `-` 끝: 코일 스프링 플런저(400 N/m, 1.5 mm 예압, 스트로크 10 mm), **포켓 높이만큼 키 큰 접점판**, 마찰 0.12 (← retention에 필요. 0.03으로 하면 뒤집었을 때 빠짐 확인됨). 후드(hood)는 들어올리기를 막아서 제거.
- **pry notch**: `+` 끝 뒤 폭 ±9.5 mm, 길이 16 mm, 바닥 3 mm 낮음, recess가 셀 밑으로 16 mm(`PRY_EXT`). 넓은 notch + 좁은 립 = 실제 배터리 홀더형.
- 접촉: 경량 부품 `solref 0.005`(STIFF). 셀 마찰 0.25, 포켓 측벽(ledge) 0.2.
- 커버 래치: weld + **누르면서(≥1 N) 미는(≥1.5 N)** 조건 (`env.py`).
- 검증: `dev_tools/retention_test.py <dev>` → 4기기 모두 공구 없이 뒤집고 흔들어도 **retained**.

### 3.2 장면 (`code/battery_sim/scene.py`)
- 팔 R(원점, +x 향함) + **팔 L** (`l_`, `LEFT_BASE=(0.50,0,0)`, yaw π; so101.xml을 ElementTree로 복제).
- **pry tool** (`pry_tool`): **T자형 팁** — 아래 넓은 블레이드 16.8 mm(셀 두 개 + 끝면을 밀고, 발이 두 셀 밑으로), 위 좁은 목 8 mm(립 사이 통과), 두께 0.8 mm, 5 mm 갈고리 발(공구 프레임에서 10° 위로 꺾임), 손잡이 11×22×55 mm(고무, 비틀림마찰 0.02). 사이트 `pry_tip` = 블레이드 +x면/발 뿌리.
- **포크형 거치대** `TOOL_RACK=(0.32,-0.14), plate_z=0.046`, 슬롯 −x로 열림.

### 3.3 환경 (`code/battery_sim/env.py`): `ArmIO`(R,L), `set_ctrl(q,grip,arm=)`, `q_of`, `grip_force(arm, body)`, 기기 최대 접촉력(양팔+공구) 모니터.

### 3.4 정책 (`code/battery_sim/policy.py`) — 제너레이터 기반 양팔 동시 실행
- `Arm` 클래스 프리미티브는 제너레이터(1 tick=20 ms 후 yield). `SkillPolicy.run_par(g1, g2)` 동시 실행.
- 흐름: [R: push_to_fence → slide_cover(커버가 손가락에 끼면 `drop_cover`로 펜스 너머에 버림) → reseat] ∥ [L: pick_tool] → L: tool_standby → **R: grasp_device(lift=False, lean=20°)** 로 기기를 잡아 고정 → L: **pry_cells**(최대 3회) → [R: release → 수직 재파지 → flip_over_bin → drop_in_crate] ∥ [L: return_tool → home].
- 공구 파지: 손잡이 22 mm 폭 방향으로 집음(TCP x = tool +y) → 팔 L의 고정조 윗부분/카메라가 팔 R 쪽으로 안 감. 저고도에서 −x쪽으로 접근해 집고, 4 mm 들어 −x로 빼냄.
- `pry_cells`: 10° 뒤로 기울여 notch 위 접근(wrist_flex 95° 한계 때문) → 실측 팁 피드백 보정(`correct`, 팔이 막히면 중단) → 내려간 뒤 **수직으로 세워** 0.5 mm씩 밀기(셀 ≥6.2 mm) → **1.5 mm 단계 들어올리기 + 기울기 0→10° 점진(지렛대)** + 횡방향 감쇠 보정 → −x로 이동해 셀을 립 위에 올림 → 내려서 발을 빼고 −x → **옆(−y)으로 빠짐**(들린 셀 끝을 치지 않게).
- 판정 `cells_free()`: 두 셀 + 끝 바닥이 `cov_z0 − 0.5 mm` 이상.
- 디버그 훅: `pol.on_phase = callback`.

### 3.5 개발 도구 (`code/dev_tools/`, 출력 `dev_tools/_out/`, 모두 `code/`에서 실행)
- `snap.py save <dev> <seed>`: pry 직전(R이 잡은 상태)까지 실행 후 저장. `dbg_pry.py <dev> <seed>`: 스냅샷에서 pry만 실행 + 단계별 로그/반투명 렌더(`_out/pry_*.png`, 로그는 리다이렉트).
- `dbg_slide.py`, `view_snap.py`, `retention_test.py`, `retention_trace.py`, `pry_ik.py`, `grasp_sweep.py`, `view.py`.

## 4. 현재 상태 / 남은 문제 (최신이 위)

- 평가 이력(4기기 × seed 0-19 = 80회): eval12 79/80 → eval13 79/80 → eval14 78/80 (AA 40/40, AAA 38/40). 매번 다른 AAA seed가 1~2개 실패.
  결과 파일(가장 최근 확정): `code/renders/eval_bimanual_<device>.json`은 eval10(seed 0-9, 40/40). eval11~15 로그는 `code/dev_tools/_out/evalN/`.
- eval15 결과: TV 20/20, AC 20/20, STB 19/20(11), light 14/20(0,7,10,13,16,17) → 원인 분석 후 수정(아래), **[진행중] eval16** (`code/dev_tools/_out/eval16/`).
- eval15 이후 수정(원인 → 해결):
  - R 팔 hold 파지에서 고정 조(fixed jaw)가 기기 옆이 아니라 **윗모서리에 올라앉음**(조 위치 여유 0 mm) → force limiter가 누르는 힘을 squeeze로 오인해 그리퍼를 다 열어버림 → 기기가 누르기만으로 고정되다가 공구 접촉에 회전(12°)·이탈. 해결: `env.jaw_force()`(움직이는 조 접촉력만)로 파지 실패 감지 → 열고 2.5 mm 바깥으로 재파지(최대 3회). (light 0/10, stb 11 해결)
  - 공구를 notch 안에서 기울임→수직으로 세우면 블레이드 옆 모서리가 notch 벽을 쓸어 기기를 밈 → **notch 위(T+3 mm)에서 먼저 수직으로 세우고** 보정 후 수직 하강.
  - 블레이드 yaw 피드백(손목 roll로 보정, `yaw_axes`) — 미는 동안/들어올리는 동안.
  - 들어올리다 블레이드가 립 밑에 걸려 기기를 들면(밀기 직후 기기 높이 대비 +0.8 mm 또는 기울기) → 내려서 더 밀고 다시 들기(snag guard, 최대 3회).
  - 밀기 조기 종료 조건: 늦은 셀도 `lip_len+1.2 mm`(블레이드 뒷면이 립 끝을 지남) 이상일 때만.
  - 들어올리기 측방 보정(lat) 적분 windup → 셀이 튀어나갈 때 공구가 3 mm 옆으로 튐(light 13) → 감쇠(0.9) + ±2 mm 제한.

- 최근 수정(이유):
  - TV seed 0: 기울어진 셀이 블레이드(+ 끝 아래)와 스프링판(− 끝 위) 사이에서 대각선 압축되어 튀어오름 → TV 스프링 300 N/m(기기별 `RemoteSpec.spring_k`).
  - AAA: 가벼운 셀이 스프링 에너지로 튕겨 나감 → AAA 스프링 150 N/m(예압 0.6 N 유지: `springref = -0.6/k`), AAA는 립 끝+1.1 mm만 밀기.
  - AAA 셀 + 끝이 셀 밑 홈에 빠짐 → AAA 간격 19 mm(최저선 9.5 mm), notch/recess 폭 ±9.0, 공구 팁 ±8.0 mm, 넓은 블레이드 높이 9.5 mm.
  - slide back 때 발이 립 끝에 걸림 → 되돌리기 전 발을 립 윗면 +1 mm 위로.
  - 운반 중 느슨한 셀이 앞(스프링 쪽)으로 미끄러져 재고정 → `cells_safe` 앞쪽 기울기 ≤20°.
  - 밀기 중 한 셀만 과도하게 밀림 → 한쪽 > 목표+1.5 mm이면 정지, 들어올리는 중 과밀림이면 공구 후퇴(두 셀 모두 충분할 때만).
  - 한 셀만 빠진 뒤 재시도 → 삽입 위치를 notch 뒤쪽(cx0-9 mm)으로.
- 남은 알려진 문제: AAA 들어올리기에서 두 셀 높이 불균형(공구 발이 옆으로 밀림) → 높은 셀이 립 위 3 mm 넘으면 내려놓기로 전환하는데, 이때 낮은 셀이 립 끝에 걸려 공구가 손 안에서 돌아가는 경우(light seed 16).
- ✅ ablation: no_tool 0/12, push_only 0/12 (eval10 설정 기준). 최신 설정에서 AC/TV no_tool 0/8 셀 재확인.
- `dev_tools/retention_test.py`(±3 g 흔들기)는 설계 점검용으로 과혹함. AC가 이 시험에서 간헐적으로 실패하지만 실제 로봇 뒤집기(ablation)에서는 셀이 빠지지 않음.

## 5. 작업 로그

- 세션 시작: 저장소/중간발표 대본/과제 PDF 검토, venv+OSMesa 구성, 기존 단일팔 TV seed0 재현.
- devices/env/ik/scene 양팔·공구·실제형 칸으로 재작성. policy 제너레이터 양팔 재작성.
- 공구 파지 문제들 해결(높은 접근 불가 → 저고도 측면 접근, 포크형 거치대, 파지 기울기 최소화, 짧은 공구).
- pry 디버깅 이력(원인→해결): IK 불가(wrist_flex 95°) → 기울임 / 팁 오차 → 실측 피드백 / R 카메라 충돌 → 방향 반전 / 기울인 블레이드가 셀 윗모서리 밀어 걸림 → 밀 땐 수직 / 후드가 회전 막음 → 후드 제거+키 큰 접점판 / 발이 두 셀 사이 V홈을 쐐기처럼 밀어 14 N 측력 → 넓은 notch+T자 팁 / 넓은 notch에서 셀이 빠짐 → 좁은 립 / 발이 립 끝에 걸려 기기 들림 → 얇은 블레이드+더 밀기 / 커버가 손가락에 끼어 기기 위로 떨어짐 → drop_cover / 기기 앞쪽이 들림(− 끝 마찰) → R이 중앙을 잡음 / 양팔 손목 충돌 → L은 손잡이 폭 방향 파지, R은 20° 기울여 잡기 / 빠지면서 셀 침 → 옆으로 빠짐.
- **TV seed 0 전체 성공** (2026-11-05).
- 4기기 평가 시작. flip 플래너 개선(후보 확대, 착지점 조준, 낮은 높이 선호), 그립 조절(regulate_grip), 수거함 확대(15×15), L이 먼저 물러난 뒤 R 재파지(순차), 운반 중 셀 안전 조건, 손가락 패드.
- 뒤집기 문제 해결 → eval7 10/12 성공.
- **eval10 40/40 성공** (기기당 10 seed).
- ablation 0/12 ×2, README/legacy 정리, eval11 39/40 → pry 들어올리기 균형 로직 수정 후 80회 재검증 중.
- AA 안정(40/40), AAA 미세 실패 반복 추적 중 (eval12~15).
- eval15 분석 → hold 파지 실패 감지/재파지, 수직 진입, yaw 피드백, snag guard, lat 제한 추가 → eval16 진행.
- eval16(재파지 버그로 TV/STB hold 실패)·eval17(0° 기울기 → 두 팔 충돌) 중단. eval18(hold 원복 + pry 변경만): AA 양호, AAA 불안정.
- **AAA 근본 원인**: 셀 간격 19 mm면 셀 최저선(9.5 mm)이 공구 발(±8 mm) 밖 → 발이 셀 안쪽 곡면을 쐐기처럼 밀어 불균형. → **AAA pitch 16 mm**(AA와 같은 기하). retention 통과, light 1/3/7/13/16 1회 성공.
- hold 파지: `_hold_descend` = IK 목표 사전 보정(FK가 원하는 고정 조 위치가 될 때까지 목표 이동) + 관절공간 이동, 20° 유지, 움직이는 조 힘 <1.5 N이면 2 mm 바깥 재시도(AC 제외).
- 데모: `code/live_demo.py`(대화형 뷰어, Space 일시정지, 배속, 단계 표시, --mode no_tool/push_only), `code/DEMO_GUIDE.md`. 사용자가 직접 촬영 예정(영상 생성 불필요).
- 보고서 자료: 저장소 루트 `REPORT_MATERIAL.md` (최종 결과 11장은 평가 후 기입).
- eval19: STB 20/20, light 18/20, TV 19/20, AC 11/14(중단). 원인: AAA 셀이 블레이드 모서리를 돌아 탈출(→ pitch 14), 두꺼운 기기에서 notch 위 수직 자세 도달 불가(→ 조건부).
- ✅ **eval20: 80/80** (4기기 × seed 0-19, 모두 pry 1회 성공, 최대 접촉력 ≤ 32.6 N). 결과 `code/renders/eval_bimanual_<dev>.json`.
- ✅ held-out seed 20-39: 79/80 (AC seed 20 실패: 들어올리는 동안 셀 − 끝도 같이 들려 스프링 접점판을 넘어감. 미수정, 개선안은 REPORT_MATERIAL 11.2). 결과 `code/renders/heldout/`.
- ✅ 대조실험(최종 설계, seed 0-4 × 4기기): no_tool 0/20, push_only 0/20 (셀 0/40씩).
- README·DEMO_GUIDE(추천 seed: TV 5, STB 9, AC 5, light 15)·REPORT_MATERIAL 11장 갱신. 생성 파일(battery_scene.xml, remote_shell_*.obj)은 git 추적 해제.
- 남은 선택 작업: AC seed 20 대책(− 끝 높이 감시), 공구 반납 개선, render_scene.py로 최종 그림 재생성(현재 renders/의 일부 그림은 중간발표용).
- 사용자 요청(최종): AC seed 20 수정 + 160회 전부 성공, 보고서(report.pdf)·최종 PPT·발표 스크립트·데모 영상 가이드/스크립트 작성(ZIP 제외).
  - AC seed 20 원인: 들어올리는 중 셀 − 끝이 같이 들려 스프링 접점판 윗모서리를 넘음(블레이드–접점판 압축력 짝힘). → AC 스프링 400→300 N/m(TV와 동일). 보유력 시험 4기기 통과(최대 6.1 mm).
  - [진행중] eval21 = 최종 코드로 4기기 × seed 0-39 (`code/dev_tools/_out/eval21/`), AC 대조실험 재측정.
  - main 브랜치의 Phase 1(팔 1대) 기록 병합 → `records/phase1_single_arm/`(HANDOFF.md, data/, images/), 프롬프트 `code/PROMPTS_phase1.md`, `code/PROMPTS_phase2.md`.
  - 보고서: `report/report_template.html` + `report/build_report.py`(결과 JSON에서 표 생성) → `report.pdf`. 그림 `report/assets/`.
  - 최종 PPT: `presentation/_build/build_final.js`(+ `make_results.py`) → `presentation/2024315782_이호섭_최종발표.pptx`, 노트 = `presentation/final_script.md`.
  - 데모: `presentation/demo_video_script.md`(3분 컷 구성·내레이션), `code/DEMO_GUIDE.md`.
