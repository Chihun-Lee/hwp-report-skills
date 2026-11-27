# -*- coding: utf-8 -*-
"""보고서 그림용 PPT 도구 — 그림 1개 = 빈 슬라이드 1장, 전부 수정 가능한 형태.

작성자가 PowerPoint에서 그림을 직접 고쳐 보고서에 다시 붙일 수 있게 만든다.
  · 배경은 흰색. 그림 안에 소제목(판 이름표)과 표를 넣지 않는다. 설명은 보고서 본문과 캡션에 쓴다.
  · 그래프 = 네이티브 차트(데이터 편집 가능). 모든 그래프가 같은 글자 크기(CHART_PT)·표식 크기·선 굵기·색 순서를 쓴다.
    그림 영역은 얇은 검은 테두리, 눈금선 없음, 범례는 그림 영역 안(legend=(x, y, w, h)) 또는 아래.
  · 도식 = 도형(글은 도형 안, 화살표는 도형에 붙음), 사진·화면 캡처만 그림 개체. 사진 위 이름은 흰 이름표(tag).

좌표 단위는 pt. 슬라이드는 1058.25 × 595.25 pt.
그림은 (40, 60)부터 그린다. 위 60 pt는 그림 번호·캡션 머리글 자리다(보고서 그림에는 안 들어간다).
보고서에는 그림 폭 1 pt가 0.2095 mm로 들어가고 165 mm를 넘으면 165 mm로 줄어든다(폭 788 pt부터 줄어든다).
  → 폭 760 pt 그림의 18 pt 글자는 10.7 pt, 폭 840 pt 그림은 10.0 pt로 인쇄된다. 본문이 12 pt이므로 그림 글자는 18 pt 이상으로 쓴다.

글꼴: 기본 Malgun Gothic(맑은 고딕, Windows 기본). FigureDeck(font="Paperlogy") 또는 환경변수 HR_FIG_FONT로 바꾼다.
  text·box의 weight(regular·medium·semibold·bold)는 무게별 글꼴이 있으면 그 글꼴, 없으면 같은 글꼴 + 굵게로 그린다.

사용 예 (그림 모듈 figs/fig_결과.py — `hr.py figs figs/` 가 모아서 PPTX·PNG·JPG로 만든다)
    from figlib import C
    ORDER = 10                                   # 보고서 등장 순서
    def build(deck):
        f = deck.figure("porosity_parity", "자동 분석 기공률과 수작업 측정 기공률의 비교")
        f.scatter(40, 70, 372, 360, series=[dict(name="시편", pts=[(1.2, 1.0), (3.5, 3.9)])],
                  xaxis=dict(title="수작업 측정 기공률 (%)", min=0, max=6, major=2),
                  yaxis=dict(title="자동 분석 기공률 (%)", min=0, max=6, major=2))
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_MARK
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

SLIDE_W, SLIDE_H = 1058.25, 595.25
X0, Y0 = 40.0, 60.0                      # 그림 시작점(왼쪽 위)
MAX_W, MAX_H = SLIDE_W - 2 * X0, SLIDE_H - Y0 - 20.0

# 그래프 색은 PowerPoint(Office) 기본 순서: BLUE · ORANGE · GRAY · GOLD · LBLUE · GREEN. 강조·기준선은 INK·RED.
C = dict(BLUE="4472C4", ORANGE="ED7D31", GRAY="A5A5A5", GOLD="FFC000", LBLUE="5B9BD5", GREEN="70AD47",
         NAVY="264478", RED="C00000", PURPLE="7030A0", INK="222222", TEXT2="555555", AXIS="7F7F7F",
         LINE="8C8C8C", GRID="D9D9D9", WHITE="FFFFFF", STEP="DEEBF7")
SERIES = ["BLUE", "ORANGE", "GRAY", "GOLD", "LBLUE", "GREEN"]     # 계열 색 순서
CHART_PT = 18                            # 모든 그래프의 글자 크기(축·눈금·범례)
TEXT_PT = 18                             # 그림 안 한글 글자 크기
MARKER, LINE_W = 11, 2.0                 # 모든 그래프의 표식 크기·선 굵기
# 글꼴 무게 표식 — 실제 글꼴 이름은 set_font()가 정한다(_face)
F_REG, F_MED, F_SEMI, F_BOLD = "@regular", "@medium", "@semibold", "@bold"
F_CHART = "Arial"                        # 차트의 숫자·영문은 Arial, 한글은 본문 글꼴(아래 _chart_ea)
WEIGHTED = {                             # 무게별로 따로 설치되는 글꼴
    "paperlogy": {"@regular": "Paperlogy 4 Regular", "@medium": "Paperlogy 5 Medium",
                  "@semibold": "Paperlogy 6 SemiBold", "@bold": "Paperlogy 7 Bold"},
}
_FONT = {}


def set_font(name=None):
    """그림 글꼴을 정한다. name: 'Malgun Gothic'(기본)·'NanumGothic'·'Paperlogy' 등."""
    name = name or os.environ.get("HR_FIG_FONT") or "Malgun Gothic"
    w = WEIGHTED.get(name.lower())
    _FONT.clear()
    if w:
        _FONT.update({k: (v, False) for k, v in w.items()})
    else:
        _FONT.update({"@regular": (name, False), "@medium": (name, False), "@semibold": (name, True), "@bold": (name, True)})
    return name


def _face(name):
    """무게 표식 → (글꼴 이름, 굵게). 표식이 아니면 그 이름 그대로."""
    if not _FONT:
        set_font()
    return _FONT.get(name, (name, False))


set_font()


def E(v):
    return Emu(int(round(v * 12700)))


def rgb(h):
    return RGBColor.from_string(h)


def text_width(text, size):
    """글자 폭 어림(pt). 한글·전각 0.92, 영문 대문자 0.68, 소문자·숫자 0.56, 공백 0.28, 문장부호 0.34."""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if o >= 0x1100:
            w += 0.92
        elif ch == " ":
            w += 0.28
        elif ch.isupper():
            w += 0.68
        elif ch.isalnum():
            w += 0.56
        else:
            w += 0.34
    return w * size


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def r(self):
        return self.x + self.w

    @property
    def b(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


def _set_font(run, name, size, color, bold=False):
    name, heavy = _face(name)
    run.font.size = Pt(size)
    run.font.bold = bold or heavy
    run.font.name = name
    run.font.color.rgb = rgb(color)
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", name)


def _fill_text(tf, text, name, size, color, align="c", anchor="m", inset=(4, 2, 4, 2), wrap=True, line=1.0):
    """글상자·도형 안에 글을 넣는다. text의 \\n은 문단 나눔."""
    tf.word_wrap = wrap
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = (E(v) for v in inset)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    bp = tf._txBody.find(qn("a:bodyPr"))
    for tag in ("a:spAutoFit", "a:normAutofit", "a:noAutofit"):
        for el in bp.findall(qn(tag)):
            bp.remove(el)
    etree.SubElement(bp, qn("a:noAutofit"))
    for i, part in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        p.line_spacing = line
        r = p.add_run()
        r.text = part
        _set_font(r, name, size, color)


def _no_line(sh):
    sh.line.fill.background()


def _no_shadow(sh):
    """그림자 없음. 빈 effectLst만으로는 LibreOffice가 도형 스타일(effectRef idx=2)의 그림자를 그리므로 idx도 0으로."""
    sp = sh._element.find(qn("p:spPr"))
    if sp is not None and sp.find(qn("a:effectLst")) is None:
        etree.SubElement(sp, qn("a:effectLst"))
    st = sh._element.find(qn("p:style"))
    if st is not None and st.find(qn("a:effectRef")) is not None:
        st.find(qn("a:effectRef")).set("idx", "0")


def _chart_white(ch):
    """차트 바탕을 흰색으로 채우고 테두리를 없앤다(PowerPoint 기본 차트 모양). 그림 영역은 채움·테두리 없음."""
    cs = ch._chartSpace
    c_chart = cs.find(qn("c:chart"))
    for el in cs.findall(qn("c:spPr")):
        cs.remove(el)
    sp = etree.Element(qn("c:spPr"))
    etree.SubElement(etree.SubElement(sp, qn("a:solidFill")), qn("a:srgbClr")).set("val", C["WHITE"])
    etree.SubElement(etree.SubElement(sp, qn("a:ln")), qn("a:noFill"))
    c_chart.addnext(sp)
    rc = cs.find(qn("c:roundedCorners"))
    if rc is None:
        rc = etree.Element(qn("c:roundedCorners"))
        cs.insert(0, rc) if cs.find(qn("c:date1904")) is None else cs.find(qn("c:date1904")).addnext(rc)
    rc.set("val", "0")
    pa = c_chart.find(qn("c:plotArea"))
    for el in pa.findall(qn("c:spPr")):
        pa.remove(el)
    # 그림 영역을 얇은 선으로 둘러싼다(눈금선 없음) — 국책보고서 최종본 그래프 양식.
    psp = etree.SubElement(pa, qn("c:spPr"))
    etree.SubElement(psp, qn("a:noFill"))
    ln = etree.SubElement(psp, qn("a:ln"), w=str(int(Pt(1.0))))
    etree.SubElement(etree.SubElement(ln, qn("a:solidFill")), qn("a:srgbClr")).set("val", C["INK"])


def _chart_ea(ch):
    """차트 안 모든 글자의 한글 글꼴을 본문 글꼴로(Arial에는 한글이 없어 PowerPoint가 임의 글꼴로 바꾼다)."""
    for tag in ("a:defRPr", "a:rPr"):
        for rpr in ch._chartSpace.iter(qn(tag)):
            for t in ("a:latin", "a:ea", "a:cs"):
                el = rpr.find(qn(t))
                if t == "a:latin":
                    if el is None:
                        etree.SubElement(rpr, qn(t)).set("typeface", F_CHART)
                    continue
                if el is None:
                    el = etree.SubElement(rpr, qn(t))
                el.set("typeface", _face(F_REG)[0])


def _legend_inside(ch, box, hide=()):
    """범례를 그림 영역 안에 둔다. box = (x, y, w, h) 차트 크기 대비 비율. hide = 범례에서 뺄 계열 번호."""
    lg = ch._chartSpace.find(qn("c:chart")).find(qn("c:legend"))
    pos = lg.find(qn("c:legendPos"))
    for k in sorted(hide, reverse=True):
        le = etree.Element(qn("c:legendEntry"))
        etree.SubElement(le, qn("c:idx")).set("val", str(k))
        etree.SubElement(le, qn("c:delete")).set("val", "1")
        pos.addnext(le)
    for el in lg.findall(qn("c:layout")):
        lg.remove(el)
    lay = etree.Element(qn("c:layout"))
    ml = etree.SubElement(lay, qn("c:manualLayout"))
    etree.SubElement(ml, qn("c:xMode")).set("val", "edge")
    etree.SubElement(ml, qn("c:yMode")).set("val", "edge")
    for n, v in zip(("c:x", "c:y", "c:w", "c:h"), box):
        etree.SubElement(ml, qn(n)).set("val", f"{v:.4f}")
    last = lg.findall(qn("c:legendEntry"))
    (last[-1] if last else pos).addnext(lay)
    ov = lg.find(qn("c:overlay"))
    if ov is None:
        ov = etree.Element(qn("c:overlay"))
        lay.addnext(ov)
    ov.set("val", "1")


def positive_ax_ids(prs):
    """python-pptx 차트 템플릿의 음수 축 ID(스키마 위반)를 차트마다 작은 양수로 다시 매긴다."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    seen = set()
    for sl in prs.slides:
        for rel in sl.part.rels.values():
            if rel.reltype != RT.CHART or id(rel.target_part) in seen:
                continue
            seen.add(id(rel.target_part))
            els = list(rel.target_part._element.iter(qn("c:axId"), qn("c:crossAx")))
            new = {}
            for el in els:
                v = el.get("val")
                new.setdefault(v, str(100000001 + len(new)))
                el.set("val", new[v])


class Fig:
    """보고서 그림 1개(슬라이드 1장)."""

    def __init__(self, deck, slide, fig_id, caption):
        self.deck, self.s, self.id, self.caption = deck, slide, fig_id, caption
        self._ext = None                         # 그림 범위(pt): [x0, y0, x1, y1]
        self._n = 0

    # ── 내부 ──────────────────────────────────────────────
    def _grow(self, x, y, w, h):
        e = self._ext
        self._ext = [x, y, x + w, y + h] if e is None else [min(e[0], x), min(e[1], y), max(e[2], x + w), max(e[3], y + h)]

    def _name(self, sh, kind):
        self._n += 1
        sh.name = f"{self.id}:{kind}{self._n}"
        return sh

    @property
    def bbox(self):
        return Rect(self._ext[0], self._ext[1], self._ext[2] - self._ext[0], self._ext[3] - self._ext[1])

    # ── 이름표·글 ──────────────────────────────────────────
    def tag(self, x, y, text, size=16, w=None, h=None):
        """사진 위에 놓는 흰 이름표(장비 이름 등). 그림의 소제목으로 쓰지 않는다. 폭은 글자 수로 정한다."""
        h = h or size * 1.6
        w = w or text_width(text, size) + size * 1.1
        sh = self._name(self.s.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(x), E(y), E(w), E(h)), "tag")
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(C["WHITE"])
        sh.line.fill.solid()
        sh.line.fill.fore_color.rgb = rgb(C["INK"])
        sh.line.width = Pt(0.75)
        _no_shadow(sh)
        _fill_text(sh.text_frame, text, F_MED, size, C["INK"], "c", "m", (2, 0, 2, 0), wrap=False)
        self._grow(x, y, w, h)
        return Rect(x, y, w, h)

    def note(self, x, y, w, h, text, align="r"):
        """그래프 안에 핵심 수치를 적는 글상자(차트 글자 크기, 테두리·채움 없음). 위치는 렌더를 보고 정한다."""
        return self.text(x, y, w, h, text, size=CHART_PT, align=align)

    def text(self, x, y, w, h, text, size=TEXT_PT, color=None, weight="regular", align="l", anchor="m", line=1.0):
        """글상자. weight: regular · medium · semibold · bold"""
        name = {"regular": F_REG, "medium": F_MED, "semibold": F_SEMI, "bold": F_BOLD}[weight]
        tb = self._name(self.s.shapes.add_textbox(E(x), E(y), E(w), E(h)), "text")
        _fill_text(tb.text_frame, text, name, size, color or C["INK"], align, anchor, (0, 0, 0, 0), line=line)
        self._grow(x, y, w, h)
        return Rect(x, y, w, h)

    def box(self, x, y, w, h, text, fill=None, line=None, size=TEXT_PT, color=None, weight="regular", shape="round", align="c"):
        """글이 안에 든 도형(옮기면 글이 따라온다). shape: round · rect · diamond · chevron · ellipse"""
        kind = {"round": MSO_SHAPE.ROUNDED_RECTANGLE, "rect": MSO_SHAPE.RECTANGLE, "diamond": MSO_SHAPE.DIAMOND,
                "chevron": MSO_SHAPE.CHEVRON, "ellipse": MSO_SHAPE.OVAL}[shape]
        sh = self._name(self.s.shapes.add_shape(kind, E(x), E(y), E(w), E(h)), "box")
        if shape == "round":
            sh.adjustments[0] = min(0.5, 8.0 / min(w, h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill or C["STEP"])
        if line:
            sh.line.fill.solid()
            sh.line.fill.fore_color.rgb = rgb(line)
            sh.line.width = Pt(1.0)
        else:
            _no_line(sh)
        _no_shadow(sh)
        name = {"regular": F_REG, "medium": F_MED, "semibold": F_SEMI, "bold": F_BOLD}[weight]
        _fill_text(sh.text_frame, text, name, size, color or C["INK"], align, "m", (6, 3, 6, 3))
        self._grow(x, y, w, h)
        return sh

    def arrow(self, a, b, color=None, width=1.5, sides=None):
        """도형 a → b 연결선(상자에 붙어 있어 상자를 옮기면 따라온다). sides=(a쪽, b쪽): t·l·b·r. 생략하면 위치로 정한다."""
        idx = {"t": 0, "l": 1, "b": 2, "r": 3}
        if sides is None:
            ax, ay = a.left + a.width / 2, a.top + a.height / 2
            bx, by = b.left + b.width / 2, b.top + b.height / 2
            sides = ("r", "l") if abs(bx - ax) >= abs(by - ay) and bx >= ax else \
                    ("l", "r") if abs(bx - ax) >= abs(by - ay) else ("b", "t") if by >= ay else ("t", "b")
        cn = self._name(self.s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, 0, 0), "arrow")
        cn.begin_connect(a, idx[sides[0]])
        cn.end_connect(b, idx[sides[1]])
        cn.line.fill.solid()
        cn.line.fill.fore_color.rgb = rgb(color or C["LINE"])
        cn.line.width = Pt(width)
        ln = cn.line._get_or_add_ln()
        etree.SubElement(ln, qn("a:tailEnd")).set("type", "triangle")
        return cn

    def flow(self, x, y, w, h, steps, orient="h", gap=22, size=TEXT_PT, numbered=False):
        """단계 상자 + 붙은 화살표. steps = ["글", ...] 또는 [("제목", "설명"), ...]. 상자 목록을 돌려준다."""
        n = len(steps)
        boxes = []
        if orient == "h":
            bw = (w - gap * (n - 1)) / n
            rects = [(x + i * (bw + gap), y, bw, h) for i in range(n)]
        else:
            bh = (h - gap * (n - 1)) / n
            rects = [(x, y + i * (bh + gap), w, bh) for i in range(n)]
        for i, (st, (bx, by, bw_, bh_)) in enumerate(zip(steps, rects)):
            title, desc = (st, None) if isinstance(st, str) else st
            if numbered:
                title = f"{i + 1}. {title}"
            sh = self.box(bx, by, bw_, bh_, title, size=size, weight="semibold" if desc else "regular",
                          line=C["LINE"])
            if desc:
                p = sh.text_frame.add_paragraph()
                p.alignment = PP_ALIGN.CENTER
                r = p.add_run()
                r.text = desc
                _set_font(r, F_REG, size - 2, C["TEXT2"])
            boxes.append(sh)
        for a, b in zip(boxes, boxes[1:]):
            self.arrow(a, b)
        return boxes

    # ── 그림 개체 ─────────────────────────────────────────
    def picture(self, path, x, y, w=None, h=None, border=True, fit=None):
        """사진·화면 캡처. w나 h 하나만 주면 비율 유지. fit=Rect를 주면 그 안에 가장 크게 넣고 가운데 맞춘다."""
        iw, ih = Image.open(path).size
        if fit is not None:
            k = min(fit.w / iw, fit.h / ih)
            w, h = iw * k, ih * k
            x, y = fit.x + (fit.w - w) / 2, fit.y + (fit.h - h) / 2
        elif w is None:
            w = h * iw / ih
        elif h is None:
            h = w * ih / iw
        pic = self._name(self.s.shapes.add_picture(str(path), E(x), E(y), E(w), E(h)), "pic")
        if border:
            pic.line.fill.solid()
            pic.line.fill.fore_color.rgb = rgb("BFBFBF")
            pic.line.width = Pt(0.75)
        self._grow(x, y, w, h)
        return Rect(x, y, w, h)

    def placeholder(self, x, y, w, h, text="사진 추가 예정"):
        """나중에 받을 사진·화면 자리(점선 빈칸)."""
        sh = self._name(self.s.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(x), E(y), E(w), E(h)), "blank")
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(C["WHITE"])
        sh.line.fill.solid()
        sh.line.fill.fore_color.rgb = rgb(C["LINE"])
        sh.line.width = Pt(1.25)
        sh.line.dash_style = MSO_LINE.DASH
        _no_shadow(sh)
        _fill_text(sh.text_frame, text, F_REG, TEXT_PT, C["LINE"], "c", "m")
        self._grow(x, y, w, h)
        return Rect(x, y, w, h)

    # ── 네이티브 차트 ─────────────────────────────────────
    def _axis(self, ax, spec, size):
        spec = spec or {}
        if "min" in spec:
            ax.minimum_scale = spec["min"]
        if "max" in spec:
            ax.maximum_scale = spec["max"]
        if "major" in spec:
            ax.major_unit = spec["major"]
        ax.has_major_gridlines = spec.get("grid", False)       # 기본 눈금선 없음(최종본 양식). grid=True로 켠다
        if ax.has_major_gridlines:
            ax.major_gridlines.format.line.fill.solid()
            ax.major_gridlines.format.line.fill.fore_color.rgb = rgb(C["GRID"])
            ax.major_gridlines.format.line.width = Pt(0.75)
        ax.format.line.fill.solid()
        ax.format.line.fill.fore_color.rgb = rgb(C["AXIS"])
        ax.format.line.width = Pt(1.0)
        ax.major_tick_mark = XL_TICK_MARK.OUTSIDE
        ax.minor_tick_mark = XL_TICK_MARK.NONE
        ax.tick_labels.font.size = Pt(size)
        ax.tick_labels.font.name = F_CHART
        ax.tick_labels.font.color.rgb = rgb(C["INK"])
        if spec.get("fmt"):
            ax.tick_labels.number_format = spec["fmt"]
            ax.tick_labels.number_format_is_linked = False
        if spec.get("title"):
            ax.has_title = True
            ax.axis_title.text_frame.text = spec["title"]
            for r in ax.axis_title.text_frame.paragraphs[0].runs:
                _set_font(r, F_CHART, size, C["INK"])

    def _chart_common(self, gf, size, legend):
        """legend: None · "b"/"r"/"t" · (x, y, w, h[, 숨길 계열 번호 튜플]) = 그림 영역 안 위치(차트 대비 비율)."""
        ch = gf.chart
        box = None
        if isinstance(legend, tuple):
            box, legend = legend, "r"
        ch.font.size = Pt(size)
        ch.font.name = F_CHART
        ch.font.color.rgb = rgb(C["INK"])
        ch.has_title = False
        _chart_white(ch)
        ch.has_legend = bool(legend)
        if legend:
            ch.legend.position = {"b": XL_LEGEND_POSITION.BOTTOM, "r": XL_LEGEND_POSITION.RIGHT,
                                  "t": XL_LEGEND_POSITION.TOP}[legend]
            ch.legend.include_in_layout = False
            ch.legend.font.size = Pt(size)
            ch.legend.font.name = F_CHART
        if box:
            _legend_inside(ch, box[:4], box[4] if len(box) > 4 else ())
        return ch

    def scatter(self, x, y, w, h, series, xaxis=None, yaxis=None, size=CHART_PT, legend=None):
        """네이티브 XY 산점. series = [dict(name, pts=[(x, y), ...], color, kind="point"|"line", ms=MARKER, lw=LINE_W,
        dash=False, marker="circle"|"triangle"|"square"|"diamond", labels={점 번호: "글"})].
        점 계열을 선 계열보다 먼저 둔다(LibreOffice는 첫 계열이 선이면 뒤 선을 그리지 않는다)."""
        cd = XyChartData()
        for sp in series:
            ser = cd.add_series(sp["name"])
            for px, py in sp["pts"]:
                ser.add_data_point(px, py)
        gf = self._name(self.s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, E(x), E(y), E(w), E(h), cd), "chart")
        ch = self._chart_common(gf, size, legend)
        mk = {"circle": XL_MARKER_STYLE.CIRCLE, "triangle": XL_MARKER_STYLE.TRIANGLE,
              "square": XL_MARKER_STYLE.SQUARE, "diamond": XL_MARKER_STYLE.DIAMOND}
        for k, (ser, sp) in enumerate(zip(ch.plots[0].series, series)):
            ser.smooth = False
            col = sp.get("color", C[SERIES[k % len(SERIES)]])
            if sp.get("kind", "point") == "line":
                ser.marker.style = XL_MARKER_STYLE.NONE
                ser.format.line.fill.solid()
                ser.format.line.fill.fore_color.rgb = rgb(col)
                ser.format.line.width = Pt(sp.get("lw", LINE_W))
                if sp.get("dash"):
                    ser.format.line.dash_style = MSO_LINE.DASH
            else:
                ser.format.line.fill.background()
                ser.marker.style = mk[sp.get("marker", "circle")]
                ser.marker.size = sp.get("ms", MARKER)
                ser.marker.format.fill.solid()
                ser.marker.format.fill.fore_color.rgb = rgb(col)
                ser.marker.format.line.fill.solid()
                ser.marker.format.line.fill.fore_color.rgb = rgb(sp.get("edge", C["WHITE"]))
                ser.marker.format.line.width = Pt(0.75)
            for i, lab in (sp.get("labels") or {}).items():
                dl = ser.points[i].data_label
                dl.has_text_frame = True
                dl.text_frame.text = lab
                dl.position = XL_LABEL_POSITION.ABOVE
                for r in dl.text_frame.paragraphs[0].runs:
                    _set_font(r, F_CHART, size, C["INK"])
        self._axis(ch.category_axis, xaxis, size)
        self._axis(ch.value_axis, yaxis, size)
        _chart_ea(ch)
        self._grow(x, y, w, h)
        return gf

    def bars(self, x, y, w, h, categories, series, yaxis=None, xaxis=None, size=CHART_PT, legend="b", horizontal=False,
             stacked=False, labels=True, fmt=None, gap=60):
        """네이티브 막대. series = [dict(name, values=[...], color)]. labels=True면 값 표시."""
        cd = CategoryChartData()
        cd.categories = categories
        for sp in series:
            cd.add_series(sp["name"], sp["values"])
        kind = {(False, False): XL_CHART_TYPE.COLUMN_CLUSTERED, (False, True): XL_CHART_TYPE.COLUMN_STACKED,
                (True, False): XL_CHART_TYPE.BAR_CLUSTERED, (True, True): XL_CHART_TYPE.BAR_STACKED}[(horizontal, stacked)]
        gf = self._name(self.s.shapes.add_chart(kind, E(x), E(y), E(w), E(h), cd), "chart")
        ch = self._chart_common(gf, size, legend if len(series) > 1 or isinstance(legend, tuple) else None)
        plot = ch.plots[0]
        plot.gap_width = gap
        if stacked:
            plot.overlap = 100
        for k, (ser, sp) in enumerate(zip(plot.series, series)):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = rgb(sp.get("color", C[SERIES[k % len(SERIES)]]))
            ser.invert_if_negative = False
        if labels:
            plot.has_data_labels = True
            dl = plot.data_labels
            dl.font.size = Pt(size)
            dl.font.name = F_CHART
            dl.font.color.rgb = rgb(C["INK"])
            if fmt:
                dl.number_format = fmt
                dl.number_format_is_linked = False
            if not stacked:
                dl.position = XL_LABEL_POSITION.OUTSIDE_END
        self._axis(ch.category_axis, dict(grid=False, **(xaxis or {})), size)
        self._axis(ch.value_axis, yaxis, size)
        _chart_ea(ch)
        self._grow(x, y, w, h)
        return gf

    def lines(self, x, y, w, h, series, xaxis=None, yaxis=None, size=CHART_PT, legend=None):
        """네이티브 XY 꺾은선(점을 잇는 선). series = scatter와 같되 kind 기본값이 line."""
        return self.scatter(x, y, w, h, [dict(kind="line", **{k: v for k, v in s.items() if k != "kind"}) for s in series],
                            xaxis, yaxis, size, legend)


class FigureDeck:
    def __init__(self, font=None):
        self.font = set_font(font)
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = E(SLIDE_W), E(SLIDE_H)
        self.figs: list[Fig] = []

    def figure(self, fig_id, caption):
        """그림 1개를 새 빈 슬라이드에 시작한다. fig_id = 영문 소문자·숫자·밑줄(파일 이름이 된다), caption = 보고서 캡션(괄호 없이)."""
        assert fig_id not in [f.id for f in self.figs], f"그림 ID 중복: {fig_id}"
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        f = Fig(self, slide, fig_id, caption)
        self.figs.append(f)
        return f

    def save(self, path):
        path = Path(path)
        meta = []
        for i, f in enumerate(self.figs, 1):
            assert f._ext is not None, f"{f.id}: 내용이 없음"
            b = f.bbox
            assert b.x >= 0 and b.y >= Y0 - 8 and b.r <= SLIDE_W and b.b <= SLIDE_H, \
                f"{f.id}: 그림이 슬라이드 밖으로 나감 {b}"
            tb = f.s.shapes.add_textbox(E(X0), E(14), E(SLIDE_W - 2 * X0), E(28))
            tb.name = f"{f.id}:header"
            _fill_text(tb.text_frame, f"그림 {i}. {f.caption}   ({f.id})", F_MED, 14, "595959", "l", "m", (0, 0, 0, 0))
            meta.append(dict(no=i, id=f.id, caption=f.caption, bbox=[round(v, 2) for v in (b.x, b.y, b.w, b.h)]))
        positive_ax_ids(self.prs)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(path)
        path.with_suffix(".figures.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return meta
