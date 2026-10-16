# -*- coding: utf-8 -*-
"""두 hwpx의 본문을 문단 단위로 비교한다 (사용자 수정본 ↔ 빌드본).

    python diff_hwpx.py 빌드본.hwpx 사용자수정본.hwpx [--style]

- 빈 문단은 공백 차이를 무시하고 「(빈 줄)」로 맞춘다. 그림은 이미지 md5와 표시 크기(mm)로 비교한다.
- 표는 셀 글자를 (행,열) 순서로 비교한다. --style은 문단 정렬·여백·글자 크기·굵기까지 비교한다.
차이가 없으면 종료 코드 0, 있으면 1.
"""
import argparse
import difflib
import hashlib
import re
import sys
import zipfile

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
NS = {"hp": HP, "hh": HH, "hc": HC}


def ptext(p):
    out = []
    for t in p.iter("{%s}t" % HP):
        out.append(t.text or "")
        for ch in t:
            out.append({"tab": "\\t", "lineBreak": "\\n"}.get(etree.QName(ch).localname, "") + (ch.tail or ""))
    return "".join(out)


def styles(z):
    hdr = etree.fromstring(z.read("Contents/header.xml"))
    cps, pps = {}, {}
    for c in hdr.iter("{%s}charPr" % HH):
        cps[c.get("id")] = f'{int(c.get("height")) / 100:g}pt{"B" if c.find("hh:bold", NS) is not None else ""}'
    for p in hdr.iter("{%s}paraPr" % HH):
        al = p.find("hh:align", NS)
        mg = p.find(".//hp:case/hh:margin", NS)
        if mg is None:
            mg = p.find(".//hh:margin", NS)
        g = (lambda k: mg.find("hc:" + k, NS).get("value")) if mg is not None else (lambda k: "0")
        pps[p.get("id")] = f'{(al.get("horizontal") if al is not None else "")[:1]} L{g("left")} I{g("intent")}'
    return cps, pps


def lines(path, with_style=False):
    z = zipfile.ZipFile(path)
    root = etree.fromstring(z.read("Contents/section0.xml"))
    hpf = z.read("Contents/content.hpf").decode("utf-8")
    items = dict(re.findall(r'<opf:item id="([^"]+)" href="([^"]+)"', hpf))
    cps, pps = styles(z) if with_style else ({}, {})
    out = []
    for p in root.findall("hp:p", NS):
        st = ""
        if with_style:
            r = p.find("hp:run", NS)
            st = f'{{{pps.get(p.get("paraPrIDRef"), "?")} {cps.get(r.get("charPrIDRef"), "?") if r is not None else ""}}} '
        pb = "⏎" if p.get("pageBreak") == "1" else ""
        pics = p.findall(".//hp:pic", NS)
        tbls = p.findall(".//hp:tbl", NS)
        if pics:
            for pic in pics:
                iid = pic.find(".//hc:img", NS).get("binaryItemIDRef")
                h = hashlib.md5(z.read(items[iid])).hexdigest()[:10] if iid in items else "없음"
                sz = pic.find("hp:sz", NS)
                out.append(f'{pb}{st}[그림 md5:{h} {int(sz.get("width")) / 283.465:.0f}×{int(sz.get("height")) / 283.465:.0f} mm]')
        elif tbls:
            for tbl in tbls:
                out.append(f'{pb}[표 {tbl.get("rowCnt")}×{tbl.get("colCnt")}]')
                for tc in tbl.iter("{%s}tc" % HP):
                    a = tc.find("hp:cellAddr", NS)
                    tx = " / ".join(ptext(x).strip() for x in tc.find("hp:subList", NS).findall("hp:p", NS))
                    out.append(f'   ({a.get("rowAddr")},{a.get("colAddr")}) {tx}')
        else:
            t = ptext(p)
            out.append(f"{pb}{st}" + (t.strip() if t.strip() else "(빈 줄)"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--style", action="store_true")
    ap.add_argument("-n", type=int, default=1, help="문맥 줄 수")
    x = ap.parse_args()
    la, lb = lines(x.a, x.style), lines(x.b, x.style)
    d = list(difflib.unified_diff(la, lb, x.a, x.b, n=x.n, lineterm=""))
    for line in d:
        print(line)
    n_del = sum(1 for line in d if line.startswith("-") and not line.startswith("---"))
    n_add = sum(1 for line in d if line.startswith("+") and not line.startswith("+++"))
    print(f"\n문단 {len(la)} ↔ {len(lb)} · 삭제 {n_del} · 추가 {n_add}" + (" · 동일" if not d else ""))
    sys.exit(1 if d else 0)


if __name__ == "__main__":
    main()
