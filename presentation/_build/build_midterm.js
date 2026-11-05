// Mid-term presentation (1 slide) for 인공지능프로젝트 과제 2 — e-waste battery removal.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const SKILL = process.env.PPTX_SKILL_DIR;
const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));

const IMG = path.join(__dirname, "..", "img");
const OUT = path.join(__dirname, "..", process.env.OUT_NAME || "midterm_presentation.pptx");
const SCRIPT = fs.readFileSync(path.join(__dirname, "..", "midterm_script_notes.txt"), "utf8");

// Industrial-safety palette: charcoal dominant, safety yellow accent, battery-bin red, steel blue.
const THEME = {
  name: "Ewaste Safety",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "1F2328", lt1: "FFFFFF", dk2: "4A5159", lt2: "F1F3F5",
    accent1: "F2B705", accent2: "C8102E", accent3: "2F6F95", accent4: "2E8B57",
    accent5: "8A939C", accent6: "E3E7EB", hlink: "2F6F95", folHlink: "4A5159",
  },
};

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "폐가전 건전지 자동 분리 — 중간 발표";
  pres.author = "이호섭";
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "SUMMARY",
    background: { color: "FFFFFF" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.45, y: 0.28, w: 12.4, h: 0.62,
        fontSize: 28, bold: true, color: C.text1, align: "left", valign: "middle", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "subtitle", type: "body", x: 0.45, y: 0.9, w: 12.4, h: 0.34,
        fontSize: 12, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
    ],
  });

  pres.addSection({ title: "중간 발표" });
  const s = pres.addSlide({ masterName: "SUMMARY", sectionTitle: "중간 발표" });
  s.addText("폐가전 건전지 자동 분리 — SO-101 단일 팔 해체 셀", { placeholder: "title" });
  s.addText("인공지능프로젝트 과제 2 · 중간 발표 · SO101-Nexus (MuJoCo 3.17) · 이호섭", { placeholder: "subtitle" });

  // ---- helpers -------------------------------------------------------------
  const header = (x, y, num, label, name) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: 0.36, h: 0.36, fill: { color: C.accent1 }, line: { type: "none" },
      objectName: `${name}-badge` });
    s.addText(String(num), { x, y, w: 0.36, h: 0.36, fontSize: 13, bold: true, color: C.text1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `${name}-num` });
    s.addText(label, { x: x + 0.46, y, w: 3.3, h: 0.36, fontSize: 16, bold: true, color: C.text1, valign: "middle",
      margin: 0, isTextBox: true, objectName: `${name}-label` });
  };
  const pill = (x, y, label, name) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 0.62, h: 0.3, rectRadius: 0.15, fill: { color: C.text1 },
      line: { type: "none" }, objectName: `${name}-pill` });
    s.addText(label, { x, y, w: 0.62, h: 0.3, fontSize: 11, bold: true, color: C.background1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `${name}-pilltext` });
  };

  // ---- column 1: target task ----------------------------------------------
  const ax = 0.45, aw = 3.95;
  header(ax, 1.45, 1, "Target Task", "task");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ax, y: 1.95, w: aw, h: 1.2, rectRadius: 0.08,
    fill: { color: C.text1 }, line: { type: "none" }, objectName: "problem-card" });
  s.addText([
    { text: "파쇄 전 위험 부품 분리, 아직 수작업", options: { fontSize: 15, bold: true, color: C.accent1, breakLine: true } },
    { text: "대표 사례로 교체형 원통형 셀(AA·AAA, 18650 리튬) 분리. 접착된 내장 배터리는 공구가 필요해 범위 밖 · 향후 과제",
      options: { fontSize: 12, color: C.background1 } },
  ], { x: ax + 0.18, y: 2.02, w: aw - 0.36, h: 1.06, valign: "middle", margin: 0, paraSpaceAfter: 4,
    isTextBox: true, objectName: "problem-text" });

  const rowX = ax + 0.78, rowW = aw - 0.78;
  pill(ax, 3.38, "환경", "env");
  s.addText("해체 작업대 지그 위 폐 리모컨(배터리면 ↑). 셀은 스프링 단자와 + 단자 걸림 턱에 고정되어 있음", {
    x: rowX, y: 3.33, w: rowW, h: 0.8, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true,
    objectName: "env-text" });
  pill(ax, 4.28, "과정", "proc");
  s.addText([
    { text: "① 펜스에 고정 후 커버 밀어 분리", options: { breakLine: true } },
    { text: "② 슬롯에 넣어 셀을 스프링 쪽으로 밀기", options: { breakLine: true } },
    { text: "③ 걸림이 풀리면 잡고 뒤집어 셀 투하", options: { breakLine: true } },
    { text: "④ 빈 본체는 크레이트로" },
  ], { x: rowX, y: 4.23, w: rowW, h: 1.3, fontSize: 12, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 3, isTextBox: true, objectName: "proc-text" });
  pill(ax, 5.68, "성공", "succ");
  s.addText([
    { text: "모든 셀 ∈ 수거함 · 본체 ∈ 크레이트", options: { breakLine: true } },
    { text: "크레이트에 셀 0개 · 최대 접촉력 ≤ 40 N", options: { breakLine: true } },
    { text: "4개 조건 모두 만족 시 성공 (자동 판정)", options: { color: C.text2, fontSize: 11 } },
  ], { x: rowX, y: 5.63, w: rowW, h: 1.05, fontSize: 12, bold: false, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 3, isTextBox: true, objectName: "succ-text" });

  // ---- column 2: simulation environment -----------------------------------
  const bx = 4.62, bw = 4.95;
  header(bx, 1.45, 2, "시뮬레이션 환경", "env2");
  s.addImage({ path: path.join(IMG, "env_overview.jpg"), x: bx, y: 1.95, w: bw, h: bw * 9 / 16,
    altText: "SO-101 arm on a steel ESD workbench with jig, red battery bin, blue crate and pegboard", objectName: "env-image" });
  s.addText("국내 소형 폐가전 해체 라인 재현 (에폭시 바닥 · ESD 매트 · 타공판 · 한글 표지 · 3D 스캔 공구). 리모컨: 걸쇠 커버 · 스프링 단자 · + 단자 걸림 턱 · 핑거 슬롯", {
    x: bx, y: 4.8, w: bw, h: 0.5, fontSize: 10.5, color: C.text2, valign: "top", margin: 0, isTextBox: true,
    objectName: "env-caption" });
  const tw = 1.17, gap = (bw - 4 * tw) / 3, ty = 5.36, th = tw * 0.75;
  const steps = [["latch1.jpg", "커버 분리"], ["latch2.jpg", "스프링 쪽 밀기"], ["latch3.jpg", "뒤집어 투하"], ["latch4.jpg", "본체 분류"]];
  steps.forEach(([f, cap], i) => {
    const x = bx + i * (tw + gap);
    s.addImage({ path: path.join(IMG, f), x, y: ty, w: tw, h: th, altText: `step ${i + 1}: ${cap}`, objectName: `step${i + 1}-img` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.05, y: ty + 0.05, w: 0.26, h: 0.26, fill: { color: C.accent1 },
      line: { type: "none" }, objectName: `step${i + 1}-badge` });
    s.addText(String(i + 1), { x: x + 0.05, y: ty + 0.05, w: 0.26, h: 0.26, fontSize: 10, bold: true, color: C.text1,
      align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `step${i + 1}-num` });
    s.addText(cap, { x, y: ty + th + 0.05, w: tw, h: 0.26, fontSize: 10.5, color: C.text1, align: "center",
      valign: "middle", margin: 0, isTextBox: true, objectName: `step${i + 1}-cap` });
  });
  s.addText("※ ①–④는 seed 0 실제 정책 롤아웃 장면 (걸림 턱 적용)", { x: bx, y: 6.62, w: bw, h: 0.26,
    fontSize: 10, italic: true, color: C.text2, margin: 0, isTextBox: true, objectName: "staged-note" });

  // ---- column 3: policy plan + status -------------------------------------
  const cx = 9.77, cw = 3.11;
  header(cx, 1.45, 3, "정책", "policy");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 1.95, w: cw, h: 2.05, rectRadius: 0.08,
    fill: { color: C.background2 }, line: { type: "none" }, objectName: "policy-card" });
  s.addText([
    { text: "LLM 생성 스킬 + 상태 머신", options: { fontSize: 14, bold: true, color: C.text1, breakLine: true } },
    { text: "Claude가 IK 기반 스킬 생성: 커버 밀기 · 스프링 밀어 걸림 해제 · 힘 제한 파지 · 뒤집기 · 투하", options: { bullet: { indent: 11 }, breakLine: true } },
    { text: "뒤집기 자세는 충돌·여유거리 검사로 탐색, 단계마다 확인 후 재시도", options: { bullet: { indent: 11 }, breakLine: true } },
    { text: "RL 대신: 접촉 단계가 뚜렷해 일주일 안 학습이 어렵고, 재현·실패 추적이 쉬움", options: { bullet: { indent: 11 } } },
  ], { x: cx + 0.15, y: 2.03, w: cw - 0.3, h: 1.9, fontSize: 11, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 4, isTextBox: true, objectName: "policy-text" });

  header(cx, 4.17, 4, "현재 상태", "status");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 4.65, w: cw, h: 1.08, rectRadius: 0.08,
    fill: { color: "E8F3EC" }, line: { type: "none" }, objectName: "done-card" });
  s.addText([
    { text: "구현됨", options: { fontSize: 12, bold: true, color: C.accent4, breakLine: true } },
    { text: "seed 0–9 성공률 100% (10/10), 최대 접촉력 ≤ 30 N", options: { bullet: { indent: 11 }, breakLine: true } },
    { text: "걸림 해제를 빼면 0/5 → 턱이 실제로 셀을 잡음", options: { bullet: { indent: 11 } } },
  ], { x: cx + 0.15, y: 4.7, w: cw - 0.3, h: 0.98, fontSize: 11, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 2, isTextBox: true, objectName: "done-text" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 5.85, w: cw, h: 1.03, rectRadius: 0.08,
    fill: { color: "FBE9EC" }, line: { type: "none" }, objectName: "todo-card" });
  s.addText([
    { text: "미해결", options: { fontSize: 12, bold: true, color: C.accent2, breakLine: true } },
    { text: "해제 없이도 한쪽 셀이 빠지는 비대칭", options: { bullet: { indent: 11 }, breakLine: true } },
    { text: "떨어진 커버가 펜스에 끼면 해제 재시도", options: { bullet: { indent: 11 }, breakLine: true } },
    { text: "20+ seed 평가 · 실패 분석", options: { bullet: { indent: 11 } } },
  ], { x: cx + 0.15, y: 5.9, w: cw - 0.3, h: 0.95, fontSize: 11, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 1, isTextBox: true, objectName: "todo-text" });

  // ---- bottom strip: device-type expansion in progress -------------------
  const sy = 6.95, sh = 0.45;
  s.addText([
    { text: "확장 진행 중 · 기기 4종", options: { fontSize: 11, bold: true, color: C.text1, breakLine: true } },
    { text: "TV 리모컨만 성공, 나머지 3종 디버깅 중", options: { fontSize: 10, color: C.text2 } },
  ], { x: 0.45, y: sy, w: 2.85, h: sh, valign: "middle", margin: 0, isTextBox: true, objectName: "devices-label" });
  s.addImage({ path: path.join(IMG, "devices_strip.jpg"), x: 3.35, y: sy, w: sh * 6.49, h: sh,
    altText: "Four waste remote types: TV (AA), set-top box (AAA), air-conditioner (AA, large), lighting (AAA)",
    objectName: "devices-strip" });
  s.addText("TV(AA) · 셋톱박스(AAA) · 에어컨(AA, 대형) · 조명(AAA) 리모컨 → 다음: 18650 리튬 셀 기기 (손전등·휴대용 선풍기)", {
    x: 3.35 + sh * 6.49 + 0.15, y: sy, w: 12.88 - (3.35 + sh * 6.49 + 0.15), h: sh, fontSize: 10.5, color: C.text1,
    valign: "middle", margin: 0, isTextBox: true, objectName: "devices-names" });

  s.addNotes(SCRIPT);

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
