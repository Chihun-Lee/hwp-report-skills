# -*- coding: utf-8 -*-
"""hwpx 구조 덤프 — 모든 구역의 문단(문단·글자 모양 번호와 뜻)과 표 칸을 글로 풀어 본다.

    python dump_hwpx.py 문서.hwpx -o 덤프폴더            # sec{N}_문단.txt · sec{N}_표칸.txt · 모양.txt
    python dump_hwpx.py 문서.hwpx --find '공동연구개발기관|재료'   # 맞는 문단만 화면에(구역·번호·모양)
    python dump_hwpx.py 문서.hwpx --memos                        # 메모(작성자·붙은 글·내용) — 주관기관 메모는 작업 지시다

남이 만든 양식(주관기관 통합 양식 등)에서 ① 우리 기관 칸이 어디인지, ② 그 자리의 이웃 문단이 어떤 문단·글자 모양을
쓰는지(복제할 본보기), ③ 작년 내용이 남은 칸이 있는지를 찾을 때 쓴다(references/consortium_merge.md).
문단 줄 형식:  P0123 pp=135 cp=[82] pb=0 | 글   (pp·cp 뜻은 모양.txt)
표 칸 형식:    T005 r02 c01 (1x2) np=1 | 글   (행 2, 열 1, 병합 1행×2열, 칸 안 문단 1개)
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwpx_text import HP, section_names, style_maps  # noqa: E402

P = "{%s}" % HP
SHAPES = {"rect", "line", "ellipse", "polygon", "curve", "connectLine", "arc"}


def own_text(p):
    out = []
    for run in p.findall(P + "run"):
        for ch in run:
            name = etree.QName(ch).localname
            if name == "t":
                out.append("".join(ch.itertext()))
            elif name == "tbl":
                out.append(f"[표 T{ch.get('_n')} {ch.get('rowCnt')}x{ch.get('colCnt')}]")
            elif name == "pic":
                out.append("[그림]")
            elif name == "container":
                out.append("[묶음 개체]")
            elif name in SHAPES:
                out.append("[도형]")
            elif name == "ctrl":
                for c in ch:
                    k = etree.QName(c).localname
                    if k == "fieldBegin" and c.get("type") == "MEMO":
                        out.append("[메모]")
                    elif k not in ("fieldEnd",):
                        out.append(f"[{k}]")
            elif name == "equation":
                out.append("[수식]")
            elif name == "ole":
                out.append("[OLE]")
    return "".join(out)


def memos(path):
    """[(구역, 문단번호, 작성자, 붙은 글, 메모 내용)] — 한컴 메모는 fieldBegin type=MEMO, 작성자는 Command의 6번째 칸"""
    z = zipfile.ZipFile(path)
    out = []
    for name in section_names(z):
        n = re.findall(r"\d+", name)[0]
        root = etree.fromstring(z.read(name), etree.XMLParser(huge_tree=True))
        top = root.findall(P + "p")
        for fb in root.iter(P + "fieldBegin"):
            if fb.get("type") != "MEMO":
                continue
            sub = fb.find(".//" + P + "subList")
            body = " / ".join("".join(t.text or "" for t in q.iter(P + "t")) for q in sub.iter(P + "p")) if sub is not None else ""
            cmd = next((e.text or "" for e in fb.iter() if e.get("name") == "Command"), "")
            parts = cmd.split("/")
            author = parts[5] if len(parts) > 5 else "?"
            anc = fb
            while anc.getparent() is not None and anc.getparent() is not root:
                anc = anc.getparent()
            idx = top.index(anc) if anc in top else -1
            at = "".join(t.text or "" for t in anc.iter(P + "t")
                         if not any(a.tag == P + "fieldBegin" for a in t.iterancestors()))
            out.append((n, idx, author, at.strip(), body.strip()))
    return out


def dump(path, outdir=None, find=None):
    z = zipfile.ZipFile(path)
    cps, pps = style_maps(path)
    rx = re.compile(find) if find else None
    if outdir:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "모양.txt").write_text(
            "## 문단 모양(pp)\n" + "\n".join(f"pp={k} {v}" for k, v in pps.items())
            + "\n\n## 글자 모양(cp)\n" + "\n".join(f"cp={k} {v}" for k, v in cps.items()), encoding="utf-8")
    for name in section_names(z):
        n = re.findall(r"\d+", name)[0]
        root = etree.fromstring(z.read(name), etree.XMLParser(huge_tree=True))
        tbls = list(root.iter(P + "tbl"))
        for i, t in enumerate(tbls):
            t.set("_n", f"{i:03d}")
        top = root.findall(P + "p")
        lines = []
        for i, p in enumerate(top):
            cp = ",".join(r.get("charPrIDRef") or "" for r in p.findall(P + "run"))
            txt = own_text(p)
            line = f"P{i:04d} pp={p.get('paraPrIDRef')} cp=[{cp}] pb={p.get('pageBreak')} | {txt}"
            if rx and rx.search(txt):
                first = (p.findall(P + "run") or [None])[0]
                print(f"구역{n} {line}\n        문단 모양: {pps.get(p.get('paraPrIDRef'), '?')} · "
                      f"글자 모양: {cps.get(first.get('charPrIDRef'), '?') if first is not None else '-'}")
            lines.append(line)
        tlines = []
        for t in tbls:
            anc = t
            while anc.getparent() is not None and anc.getparent() is not root:
                anc = anc.getparent()
            pidx = next((i for i, p in enumerate(top) if p is anc), -1)
            tlines.append(f"\n=== T{t.get('_n')}  {t.get('rowCnt')}행×{t.get('colCnt')}열  (문단 P{pidx:04d} 안)")
            for tr in t.findall(P + "tr"):
                for tc in tr.findall(P + "tc"):
                    ad, sp = tc.find(P + "cellAddr"), tc.find(P + "cellSpan")
                    sub = tc.find(P + "subList")
                    ps = sub.findall(P + "p") if sub is not None else []
                    txt = " / ".join(x for x in (own_text(q) for q in ps) if x.strip())
                    tl = (f"T{t.get('_n')} r{int(ad.get('rowAddr')):02d} c{int(ad.get('colAddr')):02d} "
                          f"({sp.get('rowSpan')}x{sp.get('colSpan')}) np={len(ps)} | {txt[:500]}")
                    if rx and rx.search(txt):
                        print(f"구역{n} {tl}")
                    tlines.append(tl)
        if outdir:
            (outdir / f"sec{n}_문단.txt").write_text("\n".join(lines), encoding="utf-8")
            (outdir / f"sec{n}_표칸.txt").write_text("\n".join(tlines), encoding="utf-8")
        if not rx:
            print(f"구역{n}: 문단 {len(top)} · 표 {len(tbls)} · 그림 {len(list(root.iter(P + 'pic')))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hwpx")
    ap.add_argument("-o", "--out", help="덤프 폴더")
    ap.add_argument("--find", help="이 정규식에 맞는 문단·표 칸만 화면에")
    ap.add_argument("--memos", action="store_true", help="메모 목록만 화면에")
    a = ap.parse_args()
    if a.memos:
        for n, i, au, at, body in memos(a.hwpx):
            print(f"구역{n} P{i:04d} [{au}] {body[:300]}\n    ← 붙은 글: {at[:120]}")
        return
    if not a.out and not a.find:
        ap.error("-o 덤프폴더, --find 정규식, --memos 중 하나는 줘야 함")
    dump(a.hwpx, a.out, a.find)
    if a.out:
        m = memos(a.hwpx)
        Path(a.out, "메모.txt").write_text("\n".join(f"구역{n} P{i:04d} [{au}] {body}\n    ← 붙은 글: {at}"
                                                    for n, i, au, at, body in m), encoding="utf-8")
        print(f"메모 {len(m)}개 → 메모.txt")


if __name__ == "__main__":
    main()
