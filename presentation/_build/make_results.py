"""Collect the numbers the final deck shows (from code/renders/*.json) into presentation/_build/results.json."""
import json, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
REN = ROOT / "code" / "renders"
DEVS = [("tv_remote", "TV"), ("stb_remote", "셋톱박스 (AAA)"), ("ac_remote", "에어컨"), ("light_remote", "조명 (AAA)")]
main = {d: json.loads((REN / f"eval_bimanual_{d}.json").read_text()) for d, _ in DEVS}
held = {d: json.loads((REN / "heldout" / f"eval_heldout_{d}.json").read_text()) for d, _ in DEVS}
allm = sum(main.values(), []); allh = sum(held.values(), [])
hist = [("P1 v1", 50, 1), ("P1 v2", 90, 1), ("P1 v3\n0 %", 0, 1), ("P1 v4\n중간발표", 100, 1), ("P1\n재측정", 70, 1), ("P1 다른\n기기 0 %", 0, 1),
        ("eval7", 83, 2), ("eval10", 100, 2), ("eval11", 97.5, 2), ("eval12", 98.8, 2), ("eval13", 98.8, 2), ("eval14", 97.5, 2),
        ("eval15", 91.3, 2), ("eval19\n(중단)", 91.9, 2), ("eval20", 100, 2),
        ("최종", 100 * sum(r["success"] for r in allm) / len(allm), 2), ("최종\n추가 seed", 100 * sum(r["success"] for r in allh) / len(allh), 2)]
out = dict(
    main=f"{sum(r['success'] for r in allm)}/{len(allm)}", held=f"{sum(r['success'] for r in allh)}/{len(allh)}",
    peak=f"{max(r['peak_force'] for r in allm + allh):.1f}", time=f"{st.mean(r['sim_time'] for r in allm + allh):.0f}",
    steps=f"{st.mean(r['steps'] for r in allm + allh):,.0f}",
    tool=f"{sum(r['tool_returned'] for r in allm + allh)}/{len(allm + allh)}",
    devices=[lab for _, lab in DEVS],
    mainPer=[sum(r["success"] for r in main[d]) for d, _ in DEVS], heldPer=[sum(r["success"] for r in held[d]) for d, _ in DEVS],
    history=dict(labels=[h[0] for h in hist], p1=[round(h[1], 1) if h[2] == 1 else 0 for h in hist], p2=[round(h[1], 1) if h[2] == 2 else 0 for h in hist]))
(Path(__file__).parent / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(out["main"], out["held"], out["peak"], out["time"], out["steps"], out["tool"])
