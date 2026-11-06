# 폐가전 리모컨 건전지 분리 — 양팔 SO-101 + 분해 공구 (인공지능프로젝트 과제 2)

2024315782 이호섭 · SO101-Nexus 0.10.0 (MuJoCo 3.17.0) · 정책: LLM(Claude Code)이 작성한 스킬 함수 + 상태 머신

실제 리모컨처럼 + 끝이 고정 립에, − 끝이 스프링에 물린 건전지를, 주 팔이 리모컨을 잡고 공구 팔이 얇은 분해 공구로 밀고 들어 올려 풀어낸 뒤,
수거함 위에서 뒤집어 떨어뜨리고 빈 본체를 소형 폐가전 상자에 넣는다. 리모컨 4종(TV, 셋톱박스 AAA, 에어컨, 조명 AAA).

## 제출물 구성 (과제2.pdf 5절)

| 경로 | 내용 |
|---|---|
| `presentation/` | 중간 발표 PPT(`2024315782_이호섭.pptx`, PDF), **최종 발표 PPT**(`2024315782_이호섭_최종발표.pptx`), 발표 스크립트(`final_script.md`, 노트에도 들어 있음), 시연 영상 스크립트(`demo_video_script.md`) |
| `code/` | 전체 소스, `README.md`(설치·실행), `requirements.txt`, 평가 결과(`renders/*.json`), LLM 프롬프트 기록(`PROMPTS_phase1.md`, `PROMPTS_phase2.md`) |
| `report.pdf` | 최종 리포트 (Task Definition / Environment Design / Policy / Evaluation / Failure Analysis / Discussion). **수정용 Word 파일: `report.docx`** — Word에서 고친 뒤 "다른 이름으로 저장 → PDF"로 `report.pdf`를 다시 만든다. (자동 생성: `python report/build_report.py` → `python3 report/build_docx.py`. 다시 생성하면 Word에서 고친 내용이 덮어써지므로 주의) |
| `demo.mp4` | 3분 이내 시연 영상 (직접 촬영: `presentation/demo_video_script.md`, `code/DEMO_GUIDE.md`) |

참고 자료(ZIP에 넣지 않아도 됨): `records/phase1_single_arm/`(중간 발표까지의 팔 1대 실험 기록·데이터·그림), `PROGRESS.md`(최종 단계 작업 로그), `REPORT_MATERIAL.md`(설계·실패 분석 정리).

## 빠른 실행

```bash
cd code
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
python run_episode.py --seeds 0 --device tv_remote          # 1회 실행 (자세한 로그)
python live_demo.py --device tv_remote --seed 5             # 대화형 뷰어 데모
```

자세한 내용은 `code/README.md`.

## 제출 전 확인 (과제2.pdf 7절)

| 항목 | 위치 |
|---|---|
| 태스크 시나리오(환경·과정·성공 판별) | `report.pdf` 1장, 최종 PPT 2–3번 |
| 직접 구성한 환경, 의도대로 렌더링 | `report.pdf` 2장, `code/renders/final/`, `code/render_rollout_stages.py` |
| 정책 선정과 이유 | `report.pdf` 3장 |
| 여러 seed 롤아웃 success rate | `report.pdf` 4장 (seed 0–39 × 4기기), `code/renders/*.json` |
| 실패 케이스 원인 분석 | `report.pdf` 5장 (Phase 1·2, 환경/정책 구분, 전후 비교) |
| 중간·최종 PPT, 코드, Report PDF, Demo Video | `presentation/`, `code/`, `report.pdf`, `demo.mp4`(직접 촬영) |
| README만 보고 실행 가능 | `code/README.md` |
| LLM 모델·프롬프트·생성 코드 | `code/PROMPTS_phase1.md`(모델명 포함), `code/PROMPTS_phase2.md`, `code/` |
| Secret 미포함 | API 키·토큰 없음 (코드는 로컬 시뮬레이션만 사용) |
| Demo 3분 이내, 환경·롤아웃·평가 설명 | `presentation/demo_video_script.md` |

ZIP 이름: `2024315782_이호섭_assignment2.zip` — `presentation/`, `code/`, `report.pdf`, `demo.mp4`를 최상위에 넣는다
(`code/dev_tools/_out/`, `code/.venv/`, `__pycache__`는 넣지 않아도 됨).
