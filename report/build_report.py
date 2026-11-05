"""Build report.pdf (repo root) from report_template.html + the evaluation JSON files.

  python report/build_report.py            (needs node + playwright; fonts: Noto Sans CJK KR)
"""
import json, statistics as st, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REN = ROOT / "code" / "renders"
DEVS = [("tv_remote", "TV 리모컨 (AA)"), ("stb_remote", "셋톱박스 리모컨 (AAA)"), ("ac_remote", "에어컨 리모컨 (AA)"), ("light_remote", "조명 리모컨 (AAA)")]


def load(kind):
    out = {}
    for d, _ in DEVS:
        p = REN / ("eval_bimanual_%s.json" % d if kind == "main" else "heldout/eval_heldout_%s.json" % d)
        out[d] = json.loads(p.read_text(encoding="utf-8"))
    return out


def table(res, seeds):
    rows = []
    allr = []
    for d, lab in DEVS:
        rs = res[d]; allr += rs
        pf = [r["peak_force"] for r in rs]; t = [r["sim_time"] for r in rs]
        pry = [r.get("pry_attempts") for r in rs if r.get("pry_attempts") is not None]
        retry = sum(1 for a in pry if a > 1) if pry else None
        rows.append(f"<tr><td>{lab}</td><td class='n'><b>{sum(r['success'] for r in rs)}/{len(rs)}</b></td>"
                    f"<td class='n'>{sum(sum(r['cells_in_bin']) for r in rs)}/{2*len(rs)}</td>"
                    f"<td class='n'>{st.mean(pf):.1f} / {max(pf):.1f}</td><td class='n'>{st.mean(t):.1f} ({min(t):.1f}–{max(t):.1f})</td>"
                    f"<td class='n'>{st.mean(r['steps'] for r in rs):,.0f}</td>"
                    f"<td class='n'>{'—' if retry is None else retry}</td>"
                    f"<td class='n'>{sum(r['tool_returned'] for r in rs)}/{len(rs)}</td></tr>")
    pf = [r["peak_force"] for r in allr]; t = [r["sim_time"] for r in allr]
    pry = [r.get("pry_attempts") for r in allr if r.get("pry_attempts") is not None]
    rows.append(f"<tr><td><b>합계</b></td><td class='n'><b>{sum(r['success'] for r in allr)}/{len(allr)} "
                f"({100*sum(r['success'] for r in allr)/len(allr):.1f} %)</b></td>"
                f"<td class='n'>{sum(sum(r['cells_in_bin']) for r in allr)}/{2*len(allr)}</td>"
                f"<td class='n'>{st.mean(pf):.1f} / {max(pf):.1f}</td><td class='n'>{st.mean(t):.1f}</td>"
                f"<td class='n'>{st.mean(r['steps'] for r in allr):,.0f}</td>"
                f"<td class='n'>{'—' if not pry else sum(1 for a in pry if a > 1)}</td>"
                f"<td class='n'>{sum(r['tool_returned'] for r in allr)}/{len(allr)}</td></tr>")
    head = ("<table><tr><th>기기</th><th class='n'>성공</th><th class='n'>수거함 셀</th><th class='n'>최대 접촉력 평균 / 최대 (N)</th>"
            "<th class='n'>시뮬레이션 시간 평균 (최소–최대, s)</th><th class='n'>물리 step 평균</th><th class='n'>pry 재시도 에피소드</th>"
            "<th class='n'>공구 반납</th></tr>")
    return head + "".join(rows) + "</table>", allr


def bars():
    H = [("P1 v1 (턱 없음, TV)", 5, 10, 1), ("P1 v2 (턱 3 mm)", 9, 10, 1), ("P1 v3 (스프링 1000)", 0, 10, 1), ("P1 v4 (턱 4.5 mm) = 중간 발표", 10, 10, 1),
         ("P1 재측정 (TV)", 7, 10, 1), ("P1 다른 기기 3종", 0, 6, 1),
         ("P2 eval7 (4기기 × 3)", 10, 12, 2), ("P2 eval10 (4기기 × 10)", 40, 40, 2), ("P2 eval11", 39, 40, 2), ("P2 eval12 (4기기 × 20)", 79, 80, 2),
         ("P2 eval13", 79, 80, 2), ("P2 eval14", 78, 80, 2), ("P2 eval15 (AAA 치수 변경)", 73, 80, 2), ("P2 eval18 (중단)", 25, 32, 2),
         ("P2 eval19 (중단)", 68, 74, 2), ("P2 eval20", 80, 80, 2), ("P2 eval20 코드, seed 20–39", 79, 80, 2)]
    out = []
    for lab, ok, n, ph in H:
        out.append(f"<div class='bar'><div class='lab'>{lab}</div><div class='trk'><div class='fil{' p2' if ph == 2 else ''}' style='width:{100*ok/n:.1f}%'></div></div>"
                   f"<div class='val'>{ok}/{n}</div></div>")
    return "\n".join(out)


def main():
    main_r, held_r = load("main"), load("held")
    mt, ma = table(main_r, "0-19")
    ht, ha = table(held_r, "20-39")
    ok_m, ok_h = sum(r["success"] for r in ma), sum(r["success"] for r in ha)
    peak = max(r["peak_force"] for r in ma + ha)
    fails = [r for r in ma + ha if not r["success"]]
    notes = ("두 평가 모두 모든 에피소드가 성공했다." if not fails else
             "실패: " + ", ".join(f"{r['device']} seed {r['seed']} ({r['failed_stage']})" for r in fails) + ".")
    notes += (" 기기에 걸린 최대 접촉력의 최댓값은 %.1f N(기준 40 N)이다. 시뮬레이션 시간은 에피소드당 약 70 s이며 실제 실행 시간은 "
              "클라우드 컨테이너에서 평균 약 %.0f s(4개 평가 동시 실행)였다. 공구 반납 실패는 성공 기준 밖의 참고 지표로, 공구가 포크 거치대에 끝까지 "
              "들어가지 않은 경우다." % (peak, st.mean(r["wall"] for r in ma + ha)))
    s = (HERE / "report_template.html").read_text(encoding="utf-8")
    rep = {"{{MAIN_RATE}}": f"{ok_m}/{len(ma)}", "{{HELD_RATE}}": f"{ok_h}/{len(ha)}", "{{PEAK_MAX}}": f"{peak:.1f}",
           "{{MAIN_N}}": f"{ok_m}/{len(ma)}({100*ok_m/len(ma):.0f} %)", "{{HELD_N}}": f"{ok_h}/{len(ha)}({100*ok_h/len(ha):.1f} %)",
           "{{MAIN_N_SHORT}}": f"{ok_m}/{len(ma)}", "{{MAIN_CELLS}}": f"{sum(sum(r['cells_in_bin']) for r in ma)}/{2*len(ma)}",
           "{{MAIN_TABLE}}": mt, "{{HELD_TABLE}}": ht, "{{RESULT_NOTES}}": notes, "{{HISTORY_BARS}}": bars()}
    for k, v in rep.items():
        s = s.replace(k, v)
    assert "{{" not in s, s[s.index("{{"):s.index("{{") + 40]
    (HERE / "report.html").write_text(s, encoding="utf-8")
    subprocess.run(["node", str(HERE / "html2pdf.js"), str(HERE / "report.html"), str(ROOT / "report.pdf")], check=True)
    print("wrote", ROOT / "report.pdf")


if __name__ == "__main__":
    main()
