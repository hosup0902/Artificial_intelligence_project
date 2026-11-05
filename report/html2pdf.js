// node html2pdf.js in.html out.pdf  — A4 PDF with page numbers (Chromium via playwright)
const { chromium } = require('playwright');
(async () => {
  const [src, out] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + src, { waitUntil: 'networkidle' });
  await p.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="font-size:8px;color:#888;width:100%;text-align:center;font-family:Noto Sans CJK KR">2024315782 이호섭 · 과제 2 최종 리포트 · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: { top: '16mm', bottom: '17mm', left: '15mm', right: '15mm' } });
  await b.close();
})();
