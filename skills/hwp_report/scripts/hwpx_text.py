# -*- coding: utf-8 -*-
"""hwpx 본문 글 읽기 공용 도구 — 모든 구역(section0, 1, …)의 문단을 순서대로 꺼낸다.

learn_diff.py(수정 포인트 표), tail_check.py(꼬리 줄), dump_hwpx.py(구조 덤프)가 같이 쓴다.
빌드 엔진(report_lib.py)은 기존대로 section0만 다룬다.
"""
import re
import zipfile

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
NS = {"hp": HP, "hh": HH, "hc": HC}


def ptext(p, keep_breaks=False):
    """문단 하나의 글자. 표·글상자 안 글은 넣지 않는다(그건 cells()로 따로)."""
    out = []
    for run in p.findall("hp:run", NS):
        for t in run.findall("hp:t", NS):
            out.append(t.text or "")
            for ch in t:
                name = etree.QName(ch).localname
                if keep_breaks:
                    out.append({"tab": "\t", "lineBreak": "\n"}.get(name, ""))
                elif name == "tab":
                    out.append(" ")
                out.append(ch.tail or "")
    return "".join(out)


def section_names(z):
    names = [n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    return sorted(names, key=lambda n: int(re.findall(r"\d+", n)[0]))


def iter_paras(path, with_cells=True):
    """(구역, 문단번호, 종류, 글자, 문단요소) — 종류: text / empty / pic / tbl / cell
    cell은 표 칸 안 문단이며 글자 앞에 「T표번호 r행 c열」 주소를 붙인 dict를 함께 준다."""
    z = zipfile.ZipFile(path)
    for s, name in enumerate(section_names(z)):
        root = etree.fromstring(z.read(name))
        tno = 0
        for i, p in enumerate(root.findall("hp:p", NS)):
            pics = p.findall(".//hp:pic", NS)
            tbls = p.findall(".//hp:tbl", NS)
            t = ptext(p).strip()
            if tbls:
                for tbl in tbls:
                    yield s, i, "tbl", f'[표 {tbl.get("rowCnt")}×{tbl.get("colCnt")}] {t}'.strip(), p
                    if with_cells:
                        for tc in tbl.iter("{%s}tc" % HP):
                            a = tc.find("hp:cellAddr", NS)
                            sub = tc.find("hp:subList", NS)
                            txt = " / ".join(ptext(x).strip() for x in sub.findall("hp:p", NS)) if sub is not None else ""
                            yield s, i, "cell", {"t": tno, "r": int(a.get("rowAddr")), "c": int(a.get("colAddr")),
                                                 "text": txt.strip()}, tc
                    tno += 1
            elif pics:
                yield s, i, "pic", t, p
            elif t:
                yield s, i, "text", t, p
            else:
                yield s, i, "empty", "", p


def body_texts(path, min_len=1):
    """글이 있는 일반 문단만 [(구역, 문단번호, 글자)]"""
    return [(s, i, t) for s, i, k, t, _ in iter_paras(path, with_cells=False) if k == "text" and len(t) >= min_len]


def style_maps(path):
    """header.xml의 글자 모양(charPr)·문단 모양(paraPr)을 짧은 설명으로"""
    z = zipfile.ZipFile(path)
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    fonts = {}
    for ff in hdr.iter("{%s}fontface" % HH):
        if ff.get("lang") == "HANGUL":
            for f in ff.findall("hh:font", NS):
                fonts[f.get("id")] = f.get("face")
    cps, pps = {}, {}
    for c in hdr.iter("{%s}charPr" % HH):
        fr = c.find("hh:fontRef", NS)
        face = fonts.get(fr.get("hangul"), "?") if fr is not None else "?"
        cps[c.get("id")] = f'{face} {int(c.get("height")) / 100:g}pt{" 굵게" if c.find("hh:bold", NS) is not None else ""}'
    for p in hdr.iter("{%s}paraPr" % HH):
        al = p.find("hh:align", NS)
        mg = p.find(".//hp:case/hh:margin", NS)
        if mg is None:
            mg = p.find(".//hh:margin", NS)

        def g(k):
            if mg is None or mg.find("hc:" + k, NS) is None:
                return "0"
            return mg.find("hc:" + k, NS).get("value")
        ls = p.find(".//hh:lineSpacing", NS)
        hd = p.find("hh:heading", NS)
        pps[p.get("id")] = (f'{(al.get("horizontal") if al is not None else "")[:1]} 왼{g("left")} 들{g("intent")} '
                            f'위{g("prev")} 아래{g("next")} 줄{ls.get("value") if ls is not None else "?"}'
                            + (f' 글머리{hd.get("type")}' if hd is not None and hd.get("type") not in (None, "NONE") else ""))
    return cps, pps
