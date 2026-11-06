"""Build report.docx (editable Word version of the report) from report/report.html.

  python report/build_report.py      # fills the result tables -> report/report.html (+ report.pdf)
  python3 report/build_docx.py       # -> report.docx  (needs python-docx, beautifulsoup4)

Headings use Word's built-in Heading 1-3 styles (navigation pane / TOC work), tables are real Word tables,
figures are inline pictures with captions. Fonts: 맑은 고딕 (Malgun Gothic) for Korean and Latin text.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT = "Malgun Gothic"
MONO = "Consolas"
INK = RGBColor(0x1B, 0x1F, 0x24)
MUTED = RGBColor(0x5B, 0x64, 0x70)
TAG_COLORS = {"E": "2F6FA5", "P": "B4321F", "EP": "6B4FA0"}
TEXT_W = Cm(17.0)          # A4 21 cm - 2 x 2 cm margins


# ------------------------------------------------------------------ low-level helpers
def set_font(run, name=FONT, size=None, bold=None, color=None, italic=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), name if name != MONO or a != "w:eastAsia" else FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color if isinstance(color, RGBColor) else RGBColor.from_string(color)


def shade(cell_or_par, hex_fill):
    el = cell_or_par._tc if hasattr(cell_or_par, "_tc") else cell_or_par._p
    pr = el.get_or_add_tcPr() if hasattr(cell_or_par, "_tc") else el.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    pr.append(shd)


def cell_margins(table, top=50, bottom=50, left=80, right=80):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)


def no_borders(table):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for k in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:val"), "nil")
        b.append(e)
    tblPr.append(b)


def light_borders(table, color="D9DDE3"):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for k in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trPr.append(e)


def cant_split(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def set_col_widths(table, widths):
    table.autofit = False
    grid = table._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w.twips if hasattr(w, "twips") else w)))
    for row in table.rows:
        for c, w in zip(row.cells, widths):
            c.width = w


def page_field(par):
    run = par.add_run()
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), kind)
            run._r.append(f)
        else:
            t = OxmlElement("w:instrText")
            t.set(qn("xml:space"), "preserve")
            t.text = txt
            run._r.append(t)
    set_font(run, size=8, color=MUTED)


# ------------------------------------------------------------------ inline content
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def add_inline(par, node, size=None, bold=False, color=None, italic=False):
    """Append the inline content of an HTML node to a python-docx paragraph."""
    for ch in node.children:
        if isinstance(ch, NavigableString):
            t = norm(str(ch))
            if t:
                r = par.add_run(t)
                set_font(r, size=size, bold=bold or None, color=color, italic=italic or None)
            continue
        if not isinstance(ch, Tag):
            continue
        name = ch.name
        cls = ch.get("class") or []
        if name == "br":
            par.add_run().add_break()
        elif name in ("b", "strong"):
            add_inline(par, ch, size, True, color, italic)
        elif name in ("i", "em"):
            add_inline(par, ch, size, bold, color, True)
        elif name == "code":
            r = par.add_run(norm(ch.get_text()))
            set_font(r, name=MONO, size=(size or 10) - 0.5, bold=bold or None, color=RGBColor(0x2B, 0x33, 0x3B))
        elif name == "span" and "tag" in cls:
            key = next((k for k in ("EP", "E", "P") if k in cls), "P")
            r = par.add_run(f"[{norm(ch.get_text())}]")
            set_font(r, size=(size or 10) - 1, bold=True, color=TAG_COLORS[key])
        else:
            add_inline(par, ch, size, bold, color, italic)


def strip_edges(par):
    if par.runs:
        par.runs[0].text = par.runs[0].text.lstrip()
        par.runs[-1].text = par.runs[-1].text.rstrip()


# ------------------------------------------------------------------ block content
class Builder:
    def __init__(self):
        self.doc = Document()
        self._styles()
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.orientation = WD_ORIENT.PORTRAIT
        sec.left_margin = sec.right_margin = Cm(2.0)
        sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.8)
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run("2024315782 이호섭 · 과제 2 최종 리포트 · ")
        set_font(r, size=8, color=MUTED)
        page_field(fp)

    def _styles(self):
        st = self.doc.styles
        normal = st["Normal"]
        normal.font.name, normal.font.size = FONT, Pt(10)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        normal.paragraph_format.space_after = Pt(4)
        normal.paragraph_format.line_spacing = 1.25
        for name, size, before, after in (("Title", 22, 0, 6), ("Heading 1", 15, 16, 6), ("Heading 2", 12, 12, 4), ("Heading 3", 10.5, 8, 3)):
            s = st[name]
            s.font.name, s.font.size, s.font.bold = FONT, Pt(size), True
            s.font.color.rgb = INK
            rpr = s.element.get_or_add_rPr()
            rf = rpr.find(qn("w:rFonts"))
            if rf is None:
                rf = OxmlElement("w:rFonts")
                rpr.insert(0, rf)
            for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                rf.set(qn(a), FONT)
            for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                if rf.get(qn(a)) is not None:
                    del rf.attrib[qn(a)]
            pf = s.paragraph_format
            pf.space_before, pf.space_after, pf.keep_with_next = Pt(before), Pt(after), True
        cap = st["Caption"]
        cap.font.name, cap.font.size, cap.font.italic, cap.font.bold = FONT, Pt(8.5), False, False
        cap.font.color.rgb = MUTED
        for n in ("List Bullet", "List Number"):
            st[n].font.name, st[n].font.size = FONT, Pt(10)
            st[n].paragraph_format.space_after = Pt(2)

    # ---- elements
    def heading(self, tag, level):
        p = self.doc.add_heading(level=level)
        add_inline(p, tag)
        strip_edges(p)
        for r in p.runs:
            set_font(r, size=None, color=INK)

    def paragraph(self, tag, style=None, size=None, color=None, align=None):
        p = self.doc.add_paragraph(style=style)
        add_inline(p, tag, size=size, color=color)
        strip_edges(p)
        if align == "justify":
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        return p

    def caption(self, tag):
        p = self.doc.add_paragraph(style="Caption")
        add_inline(p, tag, size=8.5, color=MUTED)
        strip_edges(p)
        return p

    def lst(self, tag):
        style = "List Number" if tag.name == "ol" else "List Bullet"
        for li in tag.find_all("li", recursive=False):
            p = self.doc.add_paragraph(style=style)
            add_inline(p, li)
            strip_edges(p)

    def picture(self, src, width, container=None):
        path = (HERE / src).resolve()
        if container is None:
            self.doc.add_picture(str(path), width=width)
            self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self.doc.paragraphs[-1].paragraph_format.keep_with_next = True
        else:
            container.add_run().add_picture(str(path), width=width)

    def figure(self, fig, width=TEXT_W):
        img = fig.find("img")
        if img:
            self.picture(img["src"], width)
        cap = fig.find("figcaption")
        if cap:
            self.caption(cap)

    def row(self, div):
        figs = div.find_all("figure", recursive=False)
        n = len(figs)
        t = self.doc.add_table(rows=2, cols=n)
        no_borders(t)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        w = Cm(17.0 / n - 0.25)
        for i, fig in enumerate(figs):
            c0 = t.rows[0].cells[i].paragraphs[0]
            c0.alignment = WD_ALIGN_PARAGRAPH.CENTER
            img = fig.find("img")
            if img:
                self.picture(img["src"], w, container=c0)
            cap = fig.find("figcaption")
            if cap:
                cp = t.rows[1].cells[i].paragraphs[0]
                cp.style = self.doc.styles["Caption"]
                add_inline(cp, cap, size=8.5, color=MUTED)
                strip_edges(cp)
        set_col_widths(t, [Cm(17.0 / n)] * n)

    def table(self, tbl, font=8.5):
        rows = tbl.find_all("tr")
        ncol = max(sum(int(c.get("colspan", 1)) for c in r.find_all(["td", "th"])) for r in rows)
        t = self.doc.add_table(rows=0, cols=ncol)
        light_borders(t)
        cell_margins(t)
        # column widths: explicit % on the header cells, else proportional to content length
        first = rows[0].find_all(["td", "th"])
        lens = [0] * ncol
        for r in rows:
            for j, c in enumerate(r.find_all(["td", "th"])[:ncol]):
                lens[j] = max(lens[j], min(len(norm(c.get_text())), 90))
        pct = []
        for j in range(ncol):
            m = re.search(r"width:\s*([\d.]+)%", first[j].get("style", "")) if j < len(first) else None
            pct.append(float(m.group(1)) if m else None)
        rest = 100 - sum(p for p in pct if p)
        free = [j for j in range(ncol) if pct[j] is None]
        tot = sum(max(lens[j], 6) ** 0.8 for j in free) or 1
        for j in free:
            pct[j] = rest * max(lens[j], 6) ** 0.8 / tot
        # columns that hold only an E/P tag need room for "[환경+정책]"
        for j in range(ncol):
            col = [r.find_all(["td", "th"])[j] for r in rows if len(r.find_all(["td", "th"])) > j]
            if col and all((c.name == "th" and not norm(c.get_text())) or (c.find("span", class_="tag") and len(norm(c.get_text())) <= 6) for c in col):
                pct[j] = max(pct[j], 9.5 if any("+" in c.get_text() for c in col) else 7.5)
        scale = 100 / sum(pct)
        pct = [x * scale for x in pct]
        widths = [Cm(17.0 * p / 100) for p in pct]
        for i, r in enumerate(rows):
            cells = r.find_all(["td", "th"])
            row = t.add_row()
            cant_split(row)
            is_head = all(c.name == "th" for c in cells)
            if i == 0 and is_head:
                repeat_header(row)
            for j, c in enumerate(cells[:ncol]):
                cell = row.cells[j]
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.1
                if "n" in (c.get("class") or []):
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                add_inline(p, c, size=font, bold=(c.name == "th"))
                strip_edges(p)
                if c.name == "th":
                    shade(cell, "F4F6F8")
        set_col_widths(t, widths)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def note(self, div):
        t = self.doc.add_table(rows=1, cols=1)
        cell_margins(t, 90, 90, 140, 140)
        light_borders(t, "F0D49C")
        c = t.rows[0].cells[0]
        shade(c, "FFF6E8")
        p = c.paragraphs[0]
        add_inline(p, div, size=9)
        strip_edges(p)
        set_col_widths(t, [TEXT_W])
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def pre(self, tag):
        t = self.doc.add_table(rows=1, cols=1)
        cell_margins(t, 80, 80, 120, 120)
        c = t.rows[0].cells[0]
        shade(c, "F4F6F8")
        lines = tag.get_text().strip("\n").split("\n")
        p = c.paragraphs[0]
        for k, line in enumerate(lines):
            r = p.add_run(line)
            set_font(r, name=MONO, size=8)
            if k < len(lines) - 1:
                r.add_break()
        set_col_widths(t, [TEXT_W])
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def bars(self, div):
        bars = div.find_all("div", class_="bar")
        t = self.doc.add_table(rows=1, cols=4)
        light_borders(t)
        cell_margins(t)
        for j, h in enumerate(("평가", "단계", "결과", "성공률")):
            p = t.rows[0].cells[j].paragraphs[0]
            r = p.add_run(h)
            set_font(r, size=8.5, bold=True)
            shade(t.rows[0].cells[j], "F4F6F8")
        repeat_header(t.rows[0])
        for b in bars:
            lab = norm(b.find("div", class_="lab").get_text())
            val = norm(b.find("div", class_="val").get_text())
            ok, n = (int(x) for x in val.split("/"))
            phase = "Phase 1 (팔 1대)" if lab.startswith("P1") else "Phase 2 (양팔 + 공구)"
            row = t.add_row()
            cant_split(row)
            for j, txt in enumerate((re.sub(r"^P[12] ", "", lab), phase, val, f"{100 * ok / n:.0f} %")):
                p = row.cells[j].paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                if j >= 2:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                r = p.add_run(txt)
                set_font(r, size=8.5, bold=(j == 3 and ok == n), color=("B4321F" if j == 3 and ok == n else None))
        set_col_widths(t, [Cm(7.5), Cm(4.5), Cm(2.5), Cm(2.5)])
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def cover(self, sec):
        kicker = sec.find("div", class_="kicker")
        p = self.doc.add_paragraph()
        r = p.add_run(norm(kicker.get_text()))
        set_font(r, size=10, color=MUTED)
        h1 = sec.find("h1")
        p = self.doc.add_paragraph(style="Title")
        for k, part in enumerate(h1.decode_contents().split("<br/>")):
            if k:
                p.add_run().add_break()
            r = p.add_run(norm(BeautifulSoup(part, "html.parser").get_text()))
            set_font(r, size=22, bold=True, color=INK)
        sub = sec.find("div", class_="sub")
        p = self.doc.add_paragraph()
        r = p.add_run(norm(sub.get_text()))
        set_font(r, size=12, color=MUTED)
        img = sec.find("img")
        self.picture(img["src"], TEXT_W)
        stats = sec.find_all("div", class_="stat")
        t = self.doc.add_table(rows=1, cols=len(stats))
        no_borders(t)
        cell_margins(t, 100, 100, 120, 120)
        for j, s in enumerate(stats):
            c = t.rows[0].cells[j]
            shade(c, "F4F6F8")
            p = c.paragraphs[0]
            r = p.add_run(norm(s.find("b").get_text()))
            set_font(r, size=16, bold=True, color=INK)
            p2 = c.add_paragraph()
            add_inline(p2, s.find("span"), size=8, color=MUTED)
            strip_edges(p2)
        set_col_widths(t, [Cm(17.0 / len(stats))] * len(stats))
        meta = sec.find("div", class_="meta")
        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        add_inline(p, meta, size=10)
        strip_edges(p)
        p.add_run().add_break(WD_BREAK.PAGE)

    def walk(self, container):
        for el in container.children:
            if not isinstance(el, Tag):
                continue
            cls = el.get("class") or []
            if el.name == "section" and "cover" in cls:
                self.cover(el)
            elif el.name == "h2":
                self.heading(el, 1)
            elif el.name == "h3":
                self.heading(el, 2)
            elif el.name == "h4":
                self.heading(el, 3)
            elif el.name == "p":
                small = "small" in cls
                self.paragraph(el, size=8.8 if small else None, color=MUTED if small else None, align=None if small else "justify")
            elif el.name in ("ul", "ol"):
                self.lst(el)
            elif el.name == "table":
                self.table(el)
            elif el.name == "figure":
                self.figure(el)
            elif el.name == "figcaption":
                self.caption(el)
            elif el.name == "pre":
                self.pre(el)
            elif el.name == "div" and "row" in cls:
                self.row(el)
            elif el.name == "div" and "note" in cls:
                self.note(el)
            elif el.name == "div" and "toc" in cls:
                for d in el.find_all("div", recursive=False):
                    p = self.doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(1)
                    r = p.add_run(norm(d.get_text()))
                    set_font(r, size=9.5)
            elif el.name == "div" and el.find("div", class_="bar"):
                self.bars(el)
            elif el.name == "div":
                self.walk(el)


def main():
    html = (HERE / "report.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    b = Builder()
    b.walk(soup.body)
    b.doc.core_properties.title = norm(soup.title.get_text())
    b.doc.core_properties.author = "이호섭"
    out = ROOT / "report.docx"
    b.doc.save(str(out))
    print("wrote", out)


if __name__ == "__main__":
    main()
