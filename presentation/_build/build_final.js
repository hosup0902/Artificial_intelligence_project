// Final presentation (12 slides, 10 min) for 인공지능프로젝트 과제 2 — bimanual e-waste battery removal.
//   PPTX_SKILL_DIR=<pptx skill dir> node presentation/_build/build_final.js
// Speaker notes are read from presentation/final_script.md ("## 슬라이드 N" sections).
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const SKILL = process.env.PPTX_SKILL_DIR;
const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
const ROOT = path.join(__dirname, "..", "..");
const A = (f) => path.join(ROOT, "report", "assets", f);
const OUT = path.join(ROOT, "presentation", "2024315782_이호섭_최종발표.pptx");
const VIDEO = path.join(ROOT, "code", "videos", "seed005_tv_remote_success.mp4");
const R = JSON.parse(fs.readFileSync(path.join(__dirname, "results.json"), "utf8"));   // written by make_results.py

// same palette as the mid-term deck: charcoal dominant, safety yellow accent, battery-bin red, steel blue
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
const HEX = THEME.colors;

function notes() {
  const md = fs.readFileSync(path.join(ROOT, "presentation", "final_script.md"), "utf8");
  const out = {};
  const parts = md.split(/^## 슬라이드 (\d+)[^\n]*\n/m);
  for (let i = 1; i < parts.length; i += 2) out[+parts[i]] = parts[i + 1].split(/\n---\n/)[0].trim();
  return out;
}

async function main() {
  const NOTES = notes();
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "폐가전 전처리: 양팔 SO-101과 분해 공구로 리모컨 건전지 분리 — 최종 발표";
  pres.author = "이호섭";
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: "FFFFFF" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.55, y: 0.32, w: 11.2, h: 0.7,
        fontSize: 30, bold: true, color: C.text1, align: "left", valign: "middle", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "kicker", type: "body", x: 0.55, y: 1.0, w: 12.2, h: 0.38,
        fontSize: 14, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "2024315782 이호섭 · 과제 2 최종 발표", options: { x: 0.55, y: 7.08, w: 6, h: 0.28, fontSize: 10,
        color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 12.3, y: 7.08, w: 0.5, h: 0.28, fontSize: 10, color: C.accent5, align: "right" },
  });
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: HEX.dk1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.7, w: 7.4, h: 1.9,
        fontSize: 34, bold: true, color: C.background1, align: "left", valign: "top", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "kicker", type: "body", x: 0.6, y: 2.7, w: 7.2, h: 0.9,
        fontSize: 15, color: C.accent6, align: "left", valign: "top", margin: 0 }, text: "" } },
    ],
  });

  // ---------------------------------------------------------------- helpers
  let S = null;
  let n = 0;
  const add = (master, title, kicker, section) => {
    n += 1;
    S = pres.addSlide({ masterName: master, sectionTitle: section });
    S.addText(title, { placeholder: "title" });
    if (kicker) S.addText(kicker, { placeholder: "kicker" });
    if (NOTES[n]) S.addNotes(NOTES[n]);
    return S;
  };
  const badge = (x, y, num, label, name, w = 4.5, dark = false) => {
    S.addShape(pres.shapes.OVAL, { x, y, w: 0.4, h: 0.4, fill: { color: C.accent1 }, line: { type: "none" }, objectName: `${name}-badge` });
    S.addText(String(num), { x, y, w: 0.4, h: 0.4, fontSize: 14, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `${name}-num` });
    S.addText(label, { x: x + 0.52, y: y - 0.02, w, h: 0.44, fontSize: 18, bold: true, color: dark ? C.background1 : C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: `${name}-label` });
  };
  const card = (x, y, w, h, fill, name) => S.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { type: "none" }, objectName: name });
  const text = (t, o, name) => S.addText(t, Object.assign({ isTextBox: true, margin: 0, valign: "top", fontSize: 14, color: C.text1, objectName: name }, o));
  const bullets = (items, o, name) => S.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    Object.assign({ isTextBox: true, margin: 0, valign: "top", fontSize: 14, color: C.text1, paraSpaceAfter: 6, objectName: name }, o));
  const img = (f, x, y, w, h, name) => S.addImage({ path: A(f), x, y, w, h, objectName: name, sizing: { type: "cover", w, h } });
  const pill = (x, y, label, name, fill = C.text1, color = C.background1, w = 0.8) => {
    S.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.34, rectRadius: 0.17, fill: { color: fill }, line: { type: "none" }, objectName: `${name}-pill` });
    S.addText(label, { x, y, w, h: 0.34, fontSize: 12, bold: true, color, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `${name}-pilltext` });
  };
  const stat = (x, y, w, big, small, name, onDark = false, color = null) => {
    text(big, { x, y, w, h: 0.75, fontSize: 36, bold: true, color: color || (onDark ? C.accent1 : C.text1) }, `${name}-big`);
    text(small, { x, y: y + 0.78, w, h: 0.6, fontSize: 12, color: onDark ? C.accent6 : C.text2 }, `${name}-small`);
  };

  // ================================================================ 1. title
  pres.addSection({ title: "도입" });
  add("DARK", "폐가전 전처리: 양팔 SO-101과\n얇은 분해 공구로 리모컨 건전지 분리",
      "실제와 같은 고정 구조(+ 단자 립, − 단자 스프링)에서 공구로 밀고 들어 올려 빼는 바이매뉴얼 조작\n인공지능프로젝트 과제 2 · 최종 발표 · 2024315782 이호섭", "도입");
  img("start_hero.jpg", 8.25, 0.7, 4.5, 3.9, "title-image", true);
  stat(0.6, 4.75, 2.9, R.main, "주 평가 성공\n4기기 × seed 0–19", "s1", true);
  stat(3.6, 4.75, 2.9, R.held, "추가 검증 성공\n개발에 안 쓴 seed 20–39", "s2", true);
  stat(6.6, 4.75, 2.9, "0 / 40", "대조실험: 뒤집기만·밀기만\n수거함에 들어간 셀", "s3", true);
  stat(9.6, 4.75, 3.1, `${R.peak} N`, "기기에 걸린 최대 접촉력\n(판정 기준 40 N)", "s4", true);
  text("SO101-Nexus 0.10.0 (MuJoCo 3.17) · 정책: LLM(Claude Code)이 작성한 스킬 함수 + 상태 머신", { x: 0.6, y: 6.75, w: 12, h: 0.35, fontSize: 11, color: C.accent5 }, "s1-foot");

  // ================================================================ 2. task
  pres.addSection({ title: "태스크와 환경" });
  add("CONTENT", "Target Task — 파쇄 전 건전지 분리", "교체형 원통형 셀(AA·AAA)이 든 폐 리모컨 4종 · 접착된 내장 배터리는 범위 밖(향후 과제)", "태스크와 환경");
  const rowsT = [
    ["환경", "해체 작업대 지그 위에 폐 리모컨(배터리 면 ↑, 위치·각도 seed마다 무작위). 빨간 폐건전지 수거함, 파란 소형 폐가전 상자, 공구 거치대, SO-101 두 대"],
    ["과정", "① 펜스에 붙이기 ∥ 공구 집기  ② 커버 누르며 밀어 열기  ③ 주 팔이 잡아 고정  ④ 공구로 밀고 들어 셀 풀기  ⑤ 다시 잡아 수거함 위에서 뒤집기 ∥ 공구 반납  ⑥ 빈 본체를 상자로"],
    ["성공", "모든 셀 ∈ 수거함 · 본체 ∈ 상자 · 상자에 셀 0개 · 로봇→기기 접촉력 ≤ 40 N (네 조건 모두, 자동 판정)"],
  ];
  rowsT.forEach(([k, v], i) => {
    pill(0.55, 1.75 + i * 1.45, k, `t${i}`);
    text(v, { x: 1.55, y: 1.68 + i * 1.45, w: 5.6, h: 1.3, fontSize: 15 }, `t${i}-text`);
  });
  img("start_overview.jpg", 7.45, 1.6, 5.35, 3.6, "task-image", true);
  card(7.45, 5.4, 5.35, 1.45, HEX.lt2, "task-why");
  text([{ text: "왜 이 태스크인가  ", options: { bold: true } },
        { text: "실제 공정의 수작업 · mm 단위 접촉(틈 0.5 mm, 립 4.5 mm) · 공구 사용 · 양팔 협조 · 5자유도 팔의 자세 제약 · 기기 4종 일반화" }],
       { x: 7.65, y: 5.52, w: 4.95, h: 1.25, fontSize: 13 }, "task-why-text");

  // ================================================================ 3. mechanism
  add("CONTENT", "핵심: 실제와 같은 고정 구조", "커버를 열고 뒤집어도, 스프링 쪽으로 밀기만 해도 셀은 빠지지 않는다", "태스크와 환경");
  img("fig_pry_mechanism.png", 0.55, 1.55, 12.25, 3.43, "mech-figure");
  const mech = [
    ["립 틈 9.6 mm", "가장 가는 AAA(10.5 mm)보다 좁음 → 뒤집어도 립에 걸림"],
    ["스프링 0.6 N 예압", "밀기만 하면 셀을 다시 립 밑으로 밀어 넣음"],
    ["pry notch + 홈", "얇은 공구 발이 + 끝 밑까지 들어감 (실제 홀더의 손톱 홈)"],
  ];
  mech.forEach(([k, v], i) => {
    card(0.55 + i * 3.15, 5.25, 2.95, 1.6, HEX.lt2, `mech-card${i}`);
    text(k, { x: 0.75 + i * 3.15, y: 5.4, w: 2.6, h: 0.4, fontSize: 16, bold: true }, `mech-k${i}`);
    text(v, { x: 0.75 + i * 3.15, y: 5.85, w: 2.6, h: 0.9, fontSize: 13, color: C.text2 }, `mech-v${i}`);
  });
  card(10.0, 5.25, 2.8, 1.6, HEX.dk1, "mech-abl");
  text("대조실험", { x: 10.2, y: 5.38, w: 2.4, h: 0.35, fontSize: 13, bold: true, color: C.accent1 }, "mech-abl-k");
  text("뒤집기만 0/20\n밀기만 0/20\n셀 0/40 · 0/40", { x: 10.2, y: 5.75, w: 2.4, h: 1.0, fontSize: 15, bold: true, color: C.background1 }, "mech-abl-v");

  // ================================================================ 4. environment
  add("CONTENT", "시뮬레이션 환경", "SO101-Nexus(MuJoCo) 위에 국내 소형 폐가전 해체 작업장 구성 · 모든 작업 대상은 SO-101 도달 거리 0.36 m 안", "태스크와 환경");
  img("start_wide.jpg", 0.55, 1.6, 4.1, 2.6, "env-wide", true);
  img("pick_tool.jpg", 4.8, 1.6, 4.1, 2.6, "env-hero", true);
  img("devices.jpg", 9.05, 1.6, 3.75, 2.6, "env-devices", true);
  text("공장: 에폭시 바닥·패널 벽·한글 안전 표지", { x: 0.55, y: 4.25, w: 4.1, h: 0.3, fontSize: 11, color: C.text2 }, "env-c1");
  text("양팔 + 포크형 공구 거치대 + 분해 공구", { x: 4.8, y: 4.25, w: 4.1, h: 0.3, fontSize: 11, color: C.text2 }, "env-c2");
  text("리모컨 4종 (TV·셋톱박스 AAA·에어컨·조명 AAA)", { x: 9.05, y: 4.25, w: 3.75, h: 0.3, fontSize: 11, color: C.text2 }, "env-c3");
  const env = [
    ["배치", "지그(펜스 2면) · 수거함(뒤집기 도달 분석으로 위치 결정) · 상자 · 거치대 · 장식 3D 스캔 공구(YCB·GSO, 팔이 닿지 않는 곳)"],
    ["로봇·카메라", "SO-101 ×2 마주 봄(공구 팔 x = 0.50 m, yaw 180°) · 초기 자세 HOME · 카메라 9개(overview, hero, closeup, slotcam, bincam …)"],
    ["무작위화", "seed마다 x −20~0 mm, y −12~+22 mm, yaw ±14.3° · 0.5 s 안정화 후 시작 · timestep 2 ms, 제어 50 Hz"],
  ];
  env.forEach(([k, v], i) => {
    pill(0.55, 4.8 + i * 0.72, k, `env${i}`, C.text1, C.background1, 1.4);
    text(v, { x: 2.15, y: 4.78 + i * 0.72, w: 10.6, h: 0.62, fontSize: 13.5 }, `env${i}-text`);
  });

  // ================================================================ 5. policy
  pres.addSection({ title: "정책" });
  add("CONTENT", "정책: LLM이 작성한 스킬 + 상태 머신", "Claude Code가 코드를 작성·실행·수정 · 평가 중 LLM 호출 없음(결정적, 재현 가능) · 프롬프트 원문 제출", "정책");
  card(0.55, 1.6, 4.2, 5.25, HEX.lt2, "pol-why");
  text("왜 스크립트인가", { x: 0.8, y: 1.78, w: 3.8, h: 0.4, fontSize: 17, bold: true }, "pol-why-t");
  bullets(["강화학습: 에피소드 70 s(제어 3,500 step), 보상이 끝에만, 누르며 밀기·밀고 들기 같은 좁은 조건을 탐색으로 찾기 어려움, GPU 없음",
           "단계가 뚜렷해 스킬로 나누기 쉽고 mm 단위 접촉을 기하로 직접 다룸",
           "단계별 판정 로그로 실패 지점 추적·재현이 쉬움"], { x: 0.8, y: 2.3, w: 3.75, h: 3.0, fontSize: 13.5 }, "pol-why-b");
  text("인지 = 시뮬레이터 상태값(한계) · IK = 감쇠 최소제곱", { x: 0.8, y: 5.95, w: 3.8, h: 0.7, fontSize: 12, color: C.text2 }, "pol-why-foot");
  // two-lane flow
  const lane = (y, label, color, steps, name) => {
    pill(5.05, y + 0.18, label, `${name}-lab`, color, color === C.accent1 ? C.text1 : C.background1, 1.0);
    steps.forEach(([x, w, t, hl], i) => {
      S.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.7, rectRadius: 0.06, fill: { color: hl ? (color === C.accent1 ? HEX.accent1 : HEX.dk1) : HEX.lt2 },
        line: { color: HEX.accent6, width: 0.75 }, objectName: `${name}-s${i}` });
      text(t, { x: x + 0.05, y: y + 0.05, w: w - 0.1, h: 0.6, fontSize: 11.5, bold: !!hl, align: "center", valign: "middle",
        color: hl && color !== C.accent1 ? C.background1 : C.text1 }, `${name}-t${i}`);
    });
  };
  text("두 팔이 tick(20 ms)마다 번갈아 진행 → 실제 병렬 작업", { x: 5.05, y: 1.62, w: 7.7, h: 0.35, fontSize: 13, color: C.text2 }, "pol-flow-k");
  lane(2.15, "주 팔 R", C.text1, [[6.2, 1.2, "펜스에\n붙이기"], [7.45, 1.2, "커버\n누르며 밀기"], [8.7, 1.2, "잡아서\n고정", 1], [11.2, 1.55, "다시 잡아 뒤집기\n→ 상자 투입", 1]], "laneR");
  lane(3.15, "공구 팔 L", C.accent1, [[6.2, 2.45, "거치대에서 공구 집기 · 대기"], [9.95, 1.2, "밀고 들어\n셀 풀기", 1], [11.2, 1.55, "공구 반납"]], "laneL");
  const skills = [
    ["측정 → 판정 → 재시도", "모든 단계가 측정값(위치·높이·접촉력·조 각도)으로 성공을 확인하고, 실패하면 정해진 복구를 함"],
    ["힘 제한 파지", "서보 토크를 제한해 기기 파지력 18–30 N 유지(최대 토크면 42.6 N)"],
    ["뒤집기 계획", "관절 자세 12만 개 샘플링 → 5° roll 경로·운반 중 셀 쏟아짐·충돌 검사 → 수거함 조준점에 가장 가까운 경로"],
  ];
  skills.forEach(([k, v], i) => {
    text([{ text: k + "  ", options: { bold: true } }, { text: v, options: { color: C.text2 } }],
      { x: 5.05, y: 4.25 + i * 0.86, w: 7.75, h: 0.78, fontSize: 13.5 }, `pol-sk${i}`);
  });

  // ================================================================ 6. pry skill
  add("CONTENT", "공구 스킬: 밀고, 들고, 립 위에 얹기", "가장 어려운 단계 — 실측 피드백으로 mm 오차를 잡는다 (TV seed 5 실제 장면)", "정책");
  const pry = [["pry_in.jpg", "① 블레이드를 notch에 수직으로"], ["pry_push.jpg", "② 두 셀을 스프링 쪽으로 밀기"], ["pry_lift.jpg", "③ 지렛대로 + 끝 들기"], ["pry_done.jpg", "④ 셀이 립 위에 → 공구 빠짐"]];
  pry.forEach(([f, c], i) => {
    img(f, 0.55 + i * 3.1, 1.6, 2.95, 2.0, `pry-img${i}`, true);
    text(c, { x: 0.55 + i * 3.1, y: 3.66, w: 2.95, h: 0.35, fontSize: 12.5, bold: true }, `pry-cap${i}`);
  });
  const fb = [
    ["공구 자세 보정", "손 안의 공구 자세 측정 → 공구 팁 기준 IK, 실측 팁으로 0.3 mm 이내까지 재조준"],
    ["밀기", "0.5 mm씩 밀며 두 셀 위치 측정 · 블레이드 비틀림을 손목 roll로 보정 · 늦은 셀도 립 끝 통과 확인"],
    ["들기", "1.5 mm씩 올리며 0°→10° 기울임(지렛대) · 높이 차 2 mm ↑면 발을 늦은 셀 쪽으로 · 리모컨이 들리면 내려서 더 밀기"],
    ["얹기·판정", "+ 끝 바닥 > 립 윗면 + 1.5 mm → 뒤로 빼면 스프링이 립 위에 얹음 · 실패 시 최대 3회 재시도"],
  ];
  fb.forEach(([k, v], i) => {
    const x = 0.55 + (i % 2) * 6.2, y = 4.2 + Math.floor(i / 2) * 1.32;
    card(x, y, 6.0, 1.2, HEX.lt2, `fb-card${i}`);
    text(k, { x: x + 0.2, y: y + 0.12, w: 1.5, h: 0.95, fontSize: 15, bold: true, valign: "middle" }, `fb-k${i}`);
    text(v, { x: x + 1.75, y: y + 0.12, w: 4.1, h: 0.95, fontSize: 12.5, color: C.text2, valign: "middle" }, `fb-v${i}`);
  });

  // ================================================================ 7. phase 1 -> 2
  add("CONTENT", "중간 발표 이후: 단순화를 없애다", "중간 발표 = 팔 1대 · 최종 = 팔 2대 + 공구 · 시행착오는 보고서 5장에 모두 기록", "정책");
  card(0.55, 1.6, 5.9, 5.25, HEX.lt2, "p1-card");
  text("Phase 1 · 중간 발표 (팔 1대)", { x: 0.8, y: 1.75, w: 5.4, h: 0.4, fontSize: 18, bold: true }, "p1-t");
  img("p1_latch.jpg", 0.8, 2.25, 5.4, 1.17, "p1-img");
  bullets(["그리퍼 끝 모양 때문에 + 끝을 들 수 없음 → 밀면 바닥 지지대로 + 끝이 \"저절로\" 들리게 함 = 환경이 로봇 대신 일한 단순화",
           "중간 발표 TV 10/10은 이후 코드로 재현 안 됨 → 재측정 7/10, 잡는 위치 1 mm 변화에 0/10까지 (민감)",
           "셋톱박스·에어컨·조명 0/6 (AAA 끝면이 작아 밀지 못함, 얇은 본체 미끄러짐, 뒤집기 자세 없음)"],
          { x: 0.8, y: 3.6, w: 5.45, h: 3.1, fontSize: 13 }, "p1-b");
  S.addShape(pres.shapes.RIGHT_ARROW, { x: 6.55, y: 3.8, w: 0.45, h: 0.55, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "p12-arrow" });
  card(7.1, 1.6, 5.7, 5.25, HEX.dk1, "p2-card");
  text("Phase 2 · 최종 (팔 2대 + 공구)", { x: 7.35, y: 1.75, w: 5.2, h: 0.4, fontSize: 18, bold: true, color: C.accent1 }, "p2-t");
  img("hold.jpg", 7.35, 2.25, 5.2, 1.65, "p2-img", true);
  bullets(["저절로 들리는 지지대 삭제 → 립 + 스프링 + notch (실제 구조)",
           "공구 팔이 얇은 공구로 밀고 직접 들어 올림, 주 팔은 잡아 고정",
           "모든 동작에 측정값 피드백·재시도 → 상수 민감도 제거",
           `결과: 4기기 ${R.main} + 추가 검증 ${R.held}`],
          { x: 7.35, y: 4.1, w: 5.25, h: 2.6, fontSize: 13.5, color: C.background1 }, "p2-b");

  // ================================================================ 8. results
  pres.addSection({ title: "평가와 실패 분석" });
  add("CONTENT", "평가 결과", "최종 코드 고정 · 같은 seed · 같은 성공 기준 · 기기별 seed 20개 이상", "평가와 실패 분석");
  S.addChart(pres.charts.BAR, [
      { name: "주 평가 seed 0–19", labels: R.devices, values: R.mainPer },
      { name: "추가 검증 seed 20–39", labels: R.devices, values: R.heldPer }],
    { x: 0.55, y: 1.55, w: 7.3, h: 4.0, barDir: "col", barGrouping: "clustered", chartColors: [HEX.dk1, HEX.accent1],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt", dataLabelColor: HEX.dk1,
      valAxisMinVal: 0, valAxisMaxVal: 20, valAxisMajorUnit: 5, valAxisLabelFontSize: 11, catAxisLabelFontSize: 12,
      valAxisLabelFontFace: "+mn-lt", catAxisLabelFontFace: "+mn-lt", valAxisLabelColor: HEX.dk2, catAxisLabelColor: HEX.dk1,
      valGridLine: { color: "E3E7EB", size: 0.75 }, catGridLine: { style: "none" }, showLegend: true, legendPos: "b",
      legendFontSize: 12, legendFontFace: "+mn-lt", showTitle: true, title: "기기별 성공 에피소드 (각 20회 중)", titleFontSize: 14, titleFontFace: "+mn-lt",
      titleColor: HEX.dk1, objectName: "res-chart" });
  stat(8.2, 1.6, 2.2, R.main, "주 평가\nseed 0–19", "r1");
  stat(10.5, 1.6, 2.3, R.held, "추가 검증\n개발에 안 쓴 seed", "r2");
  const aux = [[`${R.peak} N`, "최대 접촉력 (기준 40 N)"], [`${R.time} s`, "평균 시뮬레이션 시간"], [R.steps, "평균 물리 step (2 ms)"], [R.tool, "공구 반납 (참고 지표)"]];
  aux.forEach(([v, k], i) => {
    const x = 8.2 + (i % 2) * 2.3, y = 3.2 + Math.floor(i / 2) * 1.15;
    text(v, { x, y, w: 2.2, h: 0.5, fontSize: 22, bold: true }, `aux-v${i}`);
    text(k, { x, y: y + 0.5, w: 2.2, h: 0.4, fontSize: 11.5, color: C.text2 }, `aux-k${i}`);
  });
  card(0.55, 5.8, 12.25, 1.05, HEX.lt2, "abl-card");
  text([{ text: "대조실험 (seed 0–4 × 4기기)  ", options: { bold: true } },
        { text: "공구 없이 뒤집기만 0/20 (셀 0/40) · 공구로 밀기만 0/20 (셀 0/40) · 전체 정책 " + R.main + " — 밀고 + 들어야만 빠진다" }],
       { x: 0.8, y: 5.95, w: 11.8, h: 0.8, fontSize: 14, valign: "middle" }, "abl-text");

  // ================================================================ 9. history
  add("CONTENT", "실패 분석 ① 개선 이력", "평가 → 실패 원인 측정 → 수정 → 80회 전체 재평가를 20번 넘게 반복 (회귀도 바로 발견)", "평가와 실패 분석");
  const H = R.history;
  S.addChart(pres.charts.BAR, [
      { name: "Phase 1 (팔 1대)", labels: H.labels, values: H.p1 },
      { name: "Phase 2 (팔 2대 + 공구)", labels: H.labels, values: H.p2 }],
    { x: 0.55, y: 1.5, w: 12.25, h: 4.0, barDir: "col", barGrouping: "stacked", chartColors: [HEX.accent3, HEX.accent2],
      showValue: true, dataLabelPosition: "inEnd", dataLabelFormatCode: '0;;;', dataLabelFontSize: 10, dataLabelColor: "FFFFFF", dataLabelFontFace: "+mn-lt",
      valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25, valAxisLabelFormatCode: '0"%"', valAxisLabelFontSize: 10, catAxisLabelFontSize: 9.5,
      valAxisLabelFontFace: "+mn-lt", catAxisLabelFontFace: "+mn-lt", valAxisLabelColor: HEX.dk2, catAxisLabelColor: HEX.dk1,
      valGridLine: { color: "E3E7EB", size: 0.75 }, catGridLine: { style: "none" }, showLegend: true, legendPos: "t", legendFontSize: 11, legendFontFace: "+mn-lt",
      showTitle: false, objectName: "hist-chart" });
  const notesH = [
    ["중간 발표 10/10 → 재측정 7/10", "상수 1 mm에 민감, 다른 기기 0/6"],
    ["40/40 (10 seed) → 20 seed에서 AAA 실패", "AAA 셀을 들 때 불균형·튕김"],
    ["73/80 회귀 → 원인 측정으로 해결", "한 치수 수정이 다른 실패를 만듦"],
    [`최종 ${R.main} · 추가 ${R.held}`, "고정 코드, 개발에 안 쓴 seed 포함"],
  ];
  notesH.forEach(([k, v], i) => {
    card(0.55 + i * 3.1, 5.7, 2.95, 1.15, i === 3 ? HEX.dk1 : HEX.lt2, `hn-card${i}`);
    text(k, { x: 0.7 + i * 3.1, y: 5.8, w: 2.7, h: 0.5, fontSize: 13, bold: true, color: i === 3 ? C.accent1 : C.text1 }, `hn-k${i}`);
    text(v, { x: 0.7 + i * 3.1, y: 6.3, w: 2.7, h: 0.45, fontSize: 11.5, color: i === 3 ? C.accent6 : C.text2 }, `hn-v${i}`);
  });

  // ================================================================ 10. cases
  add("CONTENT", "실패 분석 ② 대표 원인과 개선", "환경 = 시뮬레이션 모델·기구 설계 문제 · 정책 = 스킬·계획·제어 문제", "평가와 실패 분석");
  const cases = [
    ["정책", C.accent2, "손가락이 옆면이 아닌 윗모서리에", "관절 5개라 '20° 기울기 + 조 방향'을 정확히 못 맞춤 → IK 오차 4–9 mm가 위치로", "IK 목표 사전 보정(오차를 방향으로) · 0° 기울기는 두 팔 충돌이라 기각", "hold.jpg"],
    ["환경", C.accent3, "AAA 셀이 기울고 튕겨 나감", "간격 19 mm: 공구 발이 셀 옆 곡면을 쐐기처럼 밀어 15 N 옆힘 · 16 mm: 셀 중심이 블레이드 끝과 겹쳐 모서리를 돌아 탈출", "AAA 간격 14 mm (중심이 블레이드 안쪽 1 mm) · 보유력 시험 재확인", "pry_lift_aaa.jpg"],
    ["정책", C.accent2, "공구 발이 립 위에 내려앉음", "두꺼운 기기(TV·에어컨)에서는 notch 위 수직 자세가 손목 한계로 도달 불가 (IK 6–16 mm)", "도달 가능할 때만 위에서 세우고, 아니면 기울여 하강 후 바닥에서 세움", "pry_in.jpg"],
    ["환경", C.accent3, "에어컨 seed 20: 셀이 뒤집힘", "− 끝이 같이 들려 스프링 접점판 위 모서리 → 압축력 짝힘이 − 끝을 돌려 접점판을 넘김", "에어컨 스프링 400 → 300 N/m (TV와 같음) → 160/160", "jump_b.jpg"],
  ];
  cases.forEach(([tag, col, title, cause, fix, im], i) => {
    const x = 0.55 + (i % 2) * 6.2, y = 1.55 + Math.floor(i / 2) * 2.7;
    card(x, y, 6.0, 2.55, HEX.lt2, `case${i}`);
    img(im, x + 0.15, y + 0.15, 1.9, 2.25, `case${i}-img`, true);
    pill(x + 2.25, y + 0.15, tag, `case${i}-tag`, col, C.background1, 0.8);
    text(title, { x: x + 3.15, y: y + 0.13, w: 2.75, h: 0.4, fontSize: 13.5, bold: true, valign: "middle" }, `case${i}-t`);
    text([{ text: "원인 ", options: { bold: true, color: C.text1 } }, { text: cause }], { x: x + 2.25, y: y + 0.62, w: 3.6, h: 1.0, fontSize: 11.5, color: C.text2 }, `case${i}-c`);
    text([{ text: "개선 ", options: { bold: true, color: C.text1 } }, { text: fix }], { x: x + 2.25, y: y + 1.65, w: 3.6, h: 0.8, fontSize: 11.5, color: C.text2 }, `case${i}-f`);
  });

  // ================================================================ 11. demo
  pres.addSection({ title: "데모와 결론" });
  add("CONTENT", "데모: TV 리모컨 seed 5", "펜스 ∥ 공구 집기 → 커버 → 고정 → 밀고·들기 → 뒤집기 ∥ 공구 반납 → 상자 (실제 롤아웃, 약 70 s)", "데모와 결론");
  if (fs.existsSync(VIDEO)) {
    S.addMedia({ type: "video", path: VIDEO, x: 0.55, y: 1.55, w: 8.55, h: 4.81, cover: A("start_hero.jpg"), objectName: "demo-video" });
  } else {
    img("start_hero.jpg", 0.55, 1.55, 8.55, 4.81, "demo-video-placeholder", true);
  }
  const steps = ["펜스에 붙이기 ∥ 공구 집기", "커버 누르며 밀어 열기", "주 팔이 잡아 고정", "공구로 밀고 들기 → 립 위", "다시 잡아 수거함 위 뒤집기", "빈 본체를 상자로 ∥ 공구 반납"];
  steps.forEach((t, i) => {
    S.addShape(pres.shapes.OVAL, { x: 9.4, y: 1.6 + i * 0.8, w: 0.42, h: 0.42, fill: { color: C.accent1 }, line: { type: "none" }, objectName: `demo-n${i}` });
    text(String(i + 1), { x: 9.4, y: 1.6 + i * 0.8, w: 0.42, h: 0.42, fontSize: 13, bold: true, align: "center", valign: "middle" }, `demo-nt${i}`);
    text(t, { x: 9.95, y: 1.6 + i * 0.8, w: 2.85, h: 0.45, fontSize: 13, valign: "middle" }, `demo-t${i}`);
  });
  text("시연 영상(demo.mp4)과 같은 롤아웃 · 재생: python code/live_demo.py --device tv_remote --seed 5", { x: 0.55, y: 6.5, w: 12.25, h: 0.35, fontSize: 11, color: C.text2 }, "demo-foot");

  // ================================================================ 12. conclusion
  add("DARK", "결론", null, "데모와 결론");
  const conc = [
    ["잘 된 점", ["실제와 같은 고정 구조에서 공구를 쓰는 양팔 조작", `4종 리모컨 ${R.main} + 개발에 안 쓴 seed ${R.held}`, "측정값 피드백·재시도로 mm 오차·5자유도 제약 극복"]],
    ["한계", ["물체 자세를 시뮬레이터 상태값으로 앎(비전 없음)", "정책이 기기 치수를 알고 있음", "셀 간격·스프링 일부를 실패 분석으로 조정"]],
    ["다음 단계", ["손목 카메라 기반 자세 추정 · 전류 기반 힘 추정", "셀을 하나씩 드는 pry · − 끝 감시", "18650 셀 기기, 나사 고정 커버로 확장"]],
  ];
  conc.forEach(([k, items], i) => {
    const x = 0.6 + i * 4.15;
    badge(x, 2.45, i + 1, k, `conc${i}`, 3.2, true);
    bullets(items, { x, y: 3.1, w: 3.85, h: 2.9, fontSize: 15, color: C.background1, paraSpaceAfter: 10 }, `conc${i}-b`);
  });
  text("감사합니다", { x: 0.6, y: 6.3, w: 6, h: 0.6, fontSize: 22, bold: true, color: C.accent1 }, "thanks");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
