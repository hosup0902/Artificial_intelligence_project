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

- ✅ **eval7 (4기기 × seed 0-2): 10/12 성공** — TV 3/3, AC 3/3, STB 2/3, 조명 2/3. 실패 2건 모두 `pry_cells`(STB seed0, light seed1). 피크 접촉력 26~34 N (STB seed0 42.5 N).
- 이번에 해결한 것(뒤집기): ① roll 경로를 5° 단계로(10° 단계에서 관절 변화 >25°로 거부되던 문제), ② 운반 중 셀 쏟아짐 조건을 방향별로(`cells_safe`: 옆 30°, 뒤 30°, 앞 55°), ③ 셀은 회전 중 개구부 방향(−y)으로 약 0.35 m/s로 미끄러져 7 cm 앞에 떨어짐(측정) → 수거함을 그 방향으로 연장(11×17 cm, 중심 (0.12,0.30)), 플래너 조준점은 `FLIP_AIM=(0.12,0.33)` 유지, ④ 크레이트 투하: 크레이트 내부 격자 탐색으로 기기를 수평(긴 축 y)으로 놓을 수 있는 자세 선택, ⑤ L이 먼저 물러난 뒤 R 재파지(순차) → R 비행 ∥ L 공구 반납, ⑥ 손가락 고무패드(비틀림 마찰 0.02), ⑦ notch 길이 10 mm(셀이 홈에 빠지던 문제).
- [진행중] pry 간헐 실패 원인 분석.
- [미해결] return_tool(거치대 꽂기) 자주 실패(성공 판정 무관).
- [미착수] seed 다수(기기당 10+) 평가, ablation(공구 없음/들어올리기 없음), README·render 스크립트 갱신, 디버그 출력 정리.

## 5. 작업 로그

- 세션 시작: 저장소/중간발표 대본/과제 PDF 검토, venv+OSMesa 구성, 기존 단일팔 TV seed0 재현.
- devices/env/ik/scene 양팔·공구·실제형 칸으로 재작성. policy 제너레이터 양팔 재작성.
- 공구 파지 문제들 해결(높은 접근 불가 → 저고도 측면 접근, 포크형 거치대, 파지 기울기 최소화, 짧은 공구).
- pry 디버깅 이력(원인→해결): IK 불가(wrist_flex 95°) → 기울임 / 팁 오차 → 실측 피드백 / R 카메라 충돌 → 방향 반전 / 기울인 블레이드가 셀 윗모서리 밀어 걸림 → 밀 땐 수직 / 후드가 회전 막음 → 후드 제거+키 큰 접점판 / 발이 두 셀 사이 V홈을 쐐기처럼 밀어 14 N 측력 → 넓은 notch+T자 팁 / 넓은 notch에서 셀이 빠짐 → 좁은 립 / 발이 립 끝에 걸려 기기 들림 → 얇은 블레이드+더 밀기 / 커버가 손가락에 끼어 기기 위로 떨어짐 → drop_cover / 기기 앞쪽이 들림(− 끝 마찰) → R이 중앙을 잡음 / 양팔 손목 충돌 → L은 손잡이 폭 방향 파지, R은 20° 기울여 잡기 / 빠지면서 셀 침 → 옆으로 빠짐.
- **TV seed 0 전체 성공** (2026-11-05).
- 4기기 평가 시작. flip 플래너 개선(후보 확대, 착지점 조준, 낮은 높이 선호), 그립 조절(regulate_grip), 수거함 확대(15×15), L이 먼저 물러난 뒤 R 재파지(순차), 운반 중 셀 안전 조건, 손가락 패드.
- 뒤집기 문제 해결 → eval7 10/12 성공.
