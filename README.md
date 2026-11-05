# 폐가전 리모컨 건전지 분리 — 양팔 SO-101 + 분해 공구 (인공지능프로젝트 과제 2)

2024315782 이호섭 · SO101-Nexus 0.10.0 (MuJoCo 3.17.0) · 정책: LLM(Claude Code)이 작성한 스킬 함수 + 상태 머신

실제 리모컨처럼 + 끝이 고정 립에, − 끝이 스프링에 물린 건전지를, 주 팔이 리모컨을 잡고 공구 팔이 얇은 분해 공구로 밀고 들어 올려 풀어낸 뒤,
수거함 위에서 뒤집어 떨어뜨리고 빈 본체를 소형 폐가전 상자에 넣는다. 리모컨 4종(TV, 셋톱박스 AAA, 에어컨, 조명 AAA).

## 제출물 구성 (과제2.pdf 5절)

| 경로 | 내용 |
|---|---|
| `presentation/` | 중간 발표 PPT(`2024315782_이호섭.pptx`, PDF), **최종 발표 PPT**(`2024315782_이호섭_최종발표.pptx`), 발표 스크립트(`final_script.md`, 노트에도 들어 있음), 시연 영상 스크립트(`demo_video_script.md`) |
| `code/` | 전체 소스, `README.md`(설치·실행), `requirements.txt`, 평가 결과(`renders/*.json`), LLM 프롬프트 기록(`PROMPTS_phase1.md`, `PROMPTS_phase2.md`) |
| `report.pdf` | 최종 리포트 (Task Definition / Environment Design / Policy / Evaluation / Failure Analysis / Discussion). 원본: `report/report_template.html`, 빌드: `python report/build_report.py` |
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
