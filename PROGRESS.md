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
- 기존 pop-up 리브(FULCRUM) **삭제**. 셀은 바닥에 평평하게 놓임.
- `+` 끝: 위에 **고정 립(lip)** 4.5 mm, 셀 크레스트와 0.5 mm 틈. `-` 끝: 코일 스프링 플런저(400 N/m, 1.5 mm 예압, 스트로크 8.5 mm) + **후드(hood)** (셀 위 1.3 mm, 1.5 mm 덮음) → 뒤집어도 `-` 끝이 스프링판에서 벗어나 빠지지 않음.
- **pry notch(공구 홈)**: `+` 끝 뒤 폭 ±7 mm, 길이 16 mm, 바닥 3 mm 낮음, 그 recess가 셀 `+` 끝 아래로 14 mm 연장(`PRY_EXT`) → 공구 발(foot)이 셀 밑으로 들어감.
- 셀 간격: AA pitch 16 mm(1.5 mm rib), AAA pitch 13.5 mm. 경량 부품 접촉 강성 `solref 0.005` (기본값이면 23 g 셀에 공구가 수 mm 파고듦).
- 커버 래치: weld + **누르면서(≥1 N) 미는(≥1.5 N)** 조건에서만 해제 (`env.py`).
- 검증됨(운동학 공구 테스트 `dev_tools/mech_test.py`): 공구 없이/밀기만 하고 뒤집어 흔들면 **셀 유지(retained)**.

### 3.2 장면 (`code/battery_sim/scene.py`)
- 팔 R(기존, 원점, +x 향함) + **팔 L** (`l_` 접두사, `LEFT_BASE=(0.50,0,0)`, yaw π, so101.xml을 ElementTree로 복제해 이름 접두사 부여, 메시/재질/클래스 공유).
- **pry tool** (`pry_tool` free body): 강철 블레이드 12.6×1.2 mm, 길이 24.5 mm, 끝에 5 mm 갈고리 발(foot, 공구 프레임에서 10° 위로 꺾임), shank, 손잡이 11×18×55 mm. 사이트 `pry_tip` = 블레이드 +x면/발 뿌리.
- **포크형 공구 거치대** `TOOL_RACK=(0.32,-0.14), plate_z=0.046`: 슬롯이 −x쪽으로 열림 → 4 mm 들고 옆(−x)으로 빼냄 (SO-101은 TCP 높이 ~0.07 m 이상에서 수직 접근 불가하기 때문).

### 3.3 환경 (`code/battery_sim/env.py`)
- `ArmIO`(R, L), `set_ctrl(q, grip, arm=)`, `q_of(arm)`, `grip_force(arm, body)`, `arm_bodies`, `robot_bodies`(양팔+공구) → 기기 최대 접촉력 모니터(≤40 N).

### 3.4 정책 (`code/battery_sim/policy.py`) — 제너레이터 기반 양팔 동시 실행
- `Arm` 클래스: `move/goto/goto_q/wait/grip/compliant_close/home` 모두 제너레이터(1 tick = 20 ms 후 yield). `SkillPolicy.run_par(g1, g2)`가 동시 실행.
- 흐름: [R: push_to_fence → slide_cover → reseat] ∥ [L: pick_tool] → L: tool_standby → R: hold_device(뒤쪽 눌러 고정, 카메라 마운트가 L 반대쪽 향하도록 `0: -y`) → L: **pry_cells**(최대 3회) → R: release → [R: grasp → flip_over_bin → drop_in_crate] ∥ [L: return_tool → home].
- `pry_cells`: 기울인 공구(10° lean, wrist_flex 한계 때문)로 notch 위 접근 → 실제 팁 위치 피드백 보정(`correct`) → 내려가서 **수직으로 세움**(기울인 채 밀면 셀 윗모서리를 밀어 + 끝이 들려 립에 걸림) → 0.5 mm씩 밀기(셀 이동 ≥5.2 mm까지) → 들어올리기(현재 디버깅 중) → −x로 이동해 셀을 립 위에 내려놓기 → 빼기.
- 판정 `cells_free()`: 두 셀의 + 끝 바닥이 `cov_z0 − 0.5 mm` 이상(립 위에 올라앉음).
- 디버그 훅: `pol.on_phase = callback` (pry 내부 단계 이름으로 호출).

### 3.5 개발 도구 (`code/dev_tools/`, 출력은 `dev_tools/_out/`)
- `snap.py save <dev> <seed>`: pry 직전까지 실행 후 상태 저장(pickle). `load()`로 복원.
- `dbg_pry.py <dev> <seed>`: 스냅샷에서 pry만 실행, 단계별 셀 상태 출력 + 반투명 하우징 렌더.
- `pry_ik.py <dev> <lean_deg>`: pry 웨이포인트 IK 가능성 오프라인 확인.
- `grasp_sweep.py`: 공구 파지 높이/여유 스윕. `mech_test.py`: 운동학 공구로 칸 구조 검증. `view.py`: 렌더 헬퍼.

## 4. 현재 상태 / 남은 문제 (최신이 위)

- [진행중] **pry 들어올리기 단계 불안정**. 단순 1회 리프트에선 두 셀 모두 들렸으나(한 셀은 립 위, 한 셀은 립 바깥 모서리에 걸림) 좌우 불균형. 스텝형 리프트+횡보정으로 바꿨더니 bias 누적 보정이 발산(팁이 ±10 mm 흔들림, 셀 하나 튕겨나감) → **보정 루프 재설계 필요** (bias 누적 대신 제한된 보정/측정 기반 절대 목표).
- [미해결] slide_cover 1차 시도가 35 mm에서 멈춤(2차에서 성공). 원인 미조사.
- [미해결] R grasp 후 `no reachable flip pose` (팔 L/공구가 충돌검사에 포함되며 생긴 문제 가능, 또는 upright_min). 미조사.
- [미해결] return_tool 미검증.
- [미착수] 나머지 3개 기기, 다수 seed 평가, ablation(공구 없음/밀기만) 재실행, README/run 스크립트 갱신(render_*.py 등은 구 API 사용 중일 수 있음).

## 5. 작업 로그

- 2026-11-05 세션 시작: 저장소/중간발표 대본/과제 PDF 검토. venv+OSMesa 구성. 기존 단일팔 TV seed0 성공 재현.
- devices.py 재작성(실제형 배터리 칸, pop-up 제거, notch/recess, 후드, 강한 접촉), env.py 양팔화, ik.py 접두사 지원, scene.py에 팔 L·공구·거치대 추가.
- 운동학 공구 테스트로 retention 확인(공구 없음/밀기만 → 셀 유지). 후드 없을 땐 뒤집으면 빠졌음 → 후드 추가로 해결.
- policy.py 전면 재작성(제너레이터 양팔). 공구 파지 문제 해결 과정: 높은 접근 불가 → 측면 저고도 접근; 공구 쓰러짐 → 포크형 거치대; 파지 기울기 → 손가락끝 판 위 13 mm, 고정조 2 mm 여유(기울기 ~2°); 공구 짧게(팁-손잡이 33 mm).
- pry: IK 불가(wrist_flex 95° 한계) → 10° lean; 팁 오차 3.5 mm로 notch 테두리에 걸림 → 실측 팁 피드백 보정; 팔 R 카메라 마운트가 팔 L과 충돌 → R hold 방향 반전; 기울인 블레이드가 셀 윗모서리를 밀어 걸림 → 밀 때는 수직; 발 5 mm, recess 14 mm.
- 현재: 들어올리기 보정 루프 재설계 중.
