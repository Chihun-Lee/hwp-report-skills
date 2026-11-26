# -*- coding: utf-8 -*-
"""hwpx 패키지 읽기·쓰기와 문단·표 조작 도구 (남이 만든 양식에 우리 내용을 끼워 넣을 때).

주관기관이 보낸 통합 양식처럼 **이미 남의 글·표가 든 문서**에 우리 파트를 넣을 때 쓴다(references/consortium_merge.md).
빌드 엔진(build_report.py)은 양식을 처음부터 채우고, 이 도구는 남의 것을 그대로 두고 필요한 곳만 고친다.
- Package: zip 항목을 순서대로 읽고, 고친 XML만 다시 써서 저장한다(나머지 항목·그림은 바이트 그대로).
- 문단: 양식 안의 기존 문단을 복제해 그 문단·글자 모양을 그대로 쓰고 글만 바꾼다(clone_para).
- 표: 칸 글 교체(칸 안 메모·계산식 보존), 행 복제·삭제(세로 병합 보정 포함), 격자 검사.
- 머리: 아래첨자 같은 글자 모양 변형 추가, 그림 manifest 추가, id 충돌 확인.
사용 예는 references/consortium_merge.md의 「스크립트 뼈대」.
"""
import copy
import re
import zipfile
from collections import OrderedDict

from lxml import etree

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "opf": "http://www.idpf.org/2007/opf/",
}
HP = "{%s}" % NS["hp"]
HH = "{%s}" % NS["hh"]
HC = "{%s}" % NS["hc"]
OPF = "{%s}" % NS["opf"]
DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
PARSER = etree.XMLParser(huge_tree=True, remove_blank_text=False)
NOID = "2147483648"   # 한컴이 대부분의 문단에 쓰는 id


# ───────────────────────── 패키지 ─────────────────────────
class Package:
    def __init__(self, path):
        self.path = str(path)
        self.entries = OrderedDict()          # 이름 -> [ZipInfo, bytes]
        with zipfile.ZipFile(self.path) as z:
            for info in z.infolist():
                self.entries[info.filename] = [info, z.read(info.filename)]
        self.trees = {}

    def xml(self, name):
        if name not in self.trees:
            self.trees[name] = etree.fromstring(self.entries[name][1], PARSER)
        return self.trees[name]

    def has(self, name):
        return name in self.entries

    def add_file(self, name, data):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        self.entries[name] = [info, data]

    def save(self, out):
        for name, root in self.trees.items():
            self.entries[name][1] = DECL + etree.tostring(root, encoding="UTF-8")
        names = list(self.entries)
        assert names[0] == "mimetype", "mimetype이 첫 항목이 아님"
        with zipfile.ZipFile(str(out), "w") as z:
            for name in names:
                info, data = self.entries[name]
                zi = zipfile.ZipInfo(name, date_time=info.date_time)
                zi.compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
                zi.external_attr = info.external_attr
                z.writestr(zi, data)


# ───────────────────────── 글 ─────────────────────────
def _in_memo(t):
    return any(a.tag == HP + "fieldBegin" for a in t.iterancestors())


def ptext(p, include_tables=False):
    """문단 글. 메모 내용은 뺀다. include_tables=False면 문단 안 표·글상자 글도 뺀다."""
    out = []
    for t in p.iter(HP + "t"):
        if _in_memo(t):
            continue
        if not include_tables:
            skip = False
            for a in t.iterancestors():
                if a is p:
                    break
                if a.tag in (HP + "tbl", HP + "subList"):
                    skip = True
                    break
            if skip:
                continue
        out.append("".join(t.itertext()))
    return "".join(out)


def runs_of(p):
    """문단의 (글자모양, 글) 목록. 메모·표·그림은 뺀다. 같은 글자모양이 이어지면 합친다."""
    out = []
    for r in p.findall(HP + "run"):
        cp = r.get("charPrIDRef")
        for ch in r:
            if ch.tag == HP + "t":
                s = "".join(ch.itertext())
                if not s:
                    continue
                if out and out[-1][0] == cp:
                    out[-1] = (cp, out[-1][1] + s)
                else:
                    out.append((cp, s))
    return out


def memo_fields(p):
    """문단 안 메모 fieldBegin 요소 목록."""
    return [fb for fb in p.iter(HP + "fieldBegin") if fb.get("type") == "MEMO"]


def strip_lineseg(el):
    n = 0
    for lsa in list(el.iter(HP + "linesegarray")):
        lsa.getparent().remove(lsa)
        n += 1
    return n


# ───────────────────────── 문단 만들기 ─────────────────────────
def clone_para(tpl, pp=None, runs=(), keep_id=False):
    """tpl 문단을 복제해 글만 바꾼다. runs: [(charPr, 글)]. 컨트롤·개체·줄배치 캐시는 지운다."""
    p = copy.deepcopy(tpl)
    for ch in list(p):
        p.remove(ch)
    if not keep_id:
        p.set("id", NOID)
    if pp is not None:
        p.set("paraPrIDRef", str(pp))
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    if not runs:
        r = etree.SubElement(p, HP + "run")
        r.set("charPrIDRef", str(tpl.find(HP + "run").get("charPrIDRef") if tpl.find(HP + "run") is not None else "0"))
        return p
    for cp, s in runs:
        r = etree.SubElement(p, HP + "run")
        r.set("charPrIDRef", str(cp))
        t = etree.SubElement(r, HP + "t")
        t.text = s
    return p


def obj_para(tpl, pp, cp, obj):
    """그림·표 하나를 담은 문단(글자처럼 취급). tpl은 네임스페이스 문맥용 기존 문단."""
    p = clone_para(tpl, pp=pp, runs=[(cp, "")])
    r = p.find(HP + "run")
    for ch in list(r):
        r.remove(ch)
    r.append(obj)
    etree.SubElement(r, HP + "t")
    return p


def attach_memo(p, fb):
    """문단 p의 글 전체에 메모 fieldBegin(fb, 이미 번호를 고친 것)을 단다."""
    runs = p.findall(HP + "run")
    first, last = runs[0], runs[-1]
    ctrl_b = etree.Element(HP + "ctrl")
    ctrl_b.append(fb)
    first.insert(0, ctrl_b)
    ctrl_e = etree.SubElement(last, HP + "ctrl")
    fe = etree.SubElement(ctrl_e, HP + "fieldEnd")
    fe.set("beginIDRef", fb.get("id"))
    fe.set("fieldid", fb.get("fieldid"))
    return p


# ───────────────────────── 표 ─────────────────────────
def tables(root):
    return list(root.iter(HP + "tbl"))


def cells(tbl):
    """표의 칸 목록: [(r, c, rs, cs, tc)] — 이 표의 직속 칸만(중첩 표 제외)."""
    out = []
    for tr in tbl.findall(HP + "tr"):
        for tc in tr.findall(HP + "tc"):
            a, s = tc.find(HP + "cellAddr"), tc.find(HP + "cellSpan")
            out.append((int(a.get("rowAddr")), int(a.get("colAddr")),
                        int(s.get("rowSpan")), int(s.get("colSpan")), tc))
    return out


def cell(tbl, r, c):
    for rr, cc, rs, cs, tc in cells(tbl):
        if rr == r and cc == c:
            return tc
    raise KeyError(f"칸 없음 r{r} c{c}")


def cell_text(tc):
    sub = tc.find(HP + "subList")
    return " / ".join(x for x in (ptext(p) for p in sub.findall(HP + "p")) if x.strip()) if sub is not None else ""


def _field_pairs(sub):
    """칸 안 필드(메모·계산식 등)의 (fieldBegin ctrl, fieldEnd ctrl) 쌍."""
    begins, ends = {}, {}
    for c in sub.iter(HP + "ctrl"):
        fb, fe = c.find(HP + "fieldBegin"), c.find(HP + "fieldEnd")
        if fb is not None and (fb.getparent() is c):
            begins[fb.get("id")] = c
        if fe is not None:
            ends[fe.get("beginIDRef")] = c
    return [(begins[k], ends.get(k)) for k in begins]


def set_cell(tc, lines, cp_override=None):
    """칸 글을 lines(문자열 목록)로 바꾼다. 첫 문단의 문단 모양과 첫 글 조각의 글자 모양을 쓴다.
    cp_override를 주면 그 글자 모양으로 쓴다(예: 빨강 예시 행을 복제한 행을 검정 글자로).
    칸 안의 메모 필드는 새 글 첫 줄을 감싸도록 그대로 살리고, 계산식(FORMULA) 필드는 값이 있으면 살려
    LastResult·Command 캐시를 새 값으로 맞추고, 값을 비우면 계산식을 뺀다."""
    if isinstance(lines, str):
        lines = [lines]
    sub = tc.find(HP + "subList")
    ps = sub.findall(HP + "p")
    first = ps[0]
    run0 = first.find(HP + "run")
    cp = run0.get("charPrIDRef") if run0 is not None else "0"
    # 글이 있는 첫 run의 글자 모양을 우선
    for r in first.findall(HP + "run"):
        if r.find(HP + "t") is not None and "".join(r.find(HP + "t").itertext()).strip():
            cp = r.get("charPrIDRef")
            break
    pairs = []
    for b, e in _field_pairs(sub):
        fb = b.find(HP + "fieldBegin")
        typ = fb.get("type")
        if typ == "FORMULA":
            if not (lines and lines[0].strip()):
                continue          # 값을 비우면 계산식도 뺀다
            for prm in fb.iter(HP + "stringParam"):
                if prm.get("name") == "LastResult":
                    prm.text = lines[0]
                elif prm.get("name") == "Command" and prm.text and ";;" in prm.text:
                    prm.text = prm.text.rsplit(";;", 1)[0] + ";;" + lines[0]
        pairs.append((copy.deepcopy(b), copy.deepcopy(e) if e is not None else None))
    # colPr 등 필드가 아닌 첫 문단 컨트롤은 살린다
    ctrls = [copy.deepcopy(c) for r in first.findall(HP + "run") for c in r.findall(HP + "ctrl")
             if c.find(HP + "fieldBegin") is None and c.find(HP + "fieldEnd") is None]
    if cp_override is not None:
        cp = str(cp_override)
    for p in ps:
        sub.remove(p)
    for i, line in enumerate(lines):
        p = clone_para(first, runs=[(cp, line)], keep_id=True)
        r = p.find(HP + "run")
        if i == 0:
            for k, c in enumerate(ctrls):
                r.insert(k, c)
            t = r.find(HP + "t")
            for b, e in pairs:
                t.addprevious(b)
                if e is not None:
                    t.addnext(e)
        sub.append(p)
    strip_lineseg(tc)
    return tc


def add_cell_line(tc, line):
    """칸의 마지막 문단을 복제해 한 줄 덧붙인다(기존 글 유지)."""
    sub = tc.find(HP + "subList")
    last = sub.findall(HP + "p")[-1]
    cp = None
    for r in last.findall(HP + "run"):
        cp = r.get("charPrIDRef")
    p = clone_para(last, runs=[(cp, line)], keep_id=True)
    for c in list(p.iter(HP + "ctrl")):
        c.getparent().remove(c)
    sub.append(p)
    strip_lineseg(tc)
    return tc


def grid_check(tbl):
    """모든 격자 칸이 정확히 한 번 덮이는지 검사. 문제 목록을 돌려준다."""
    R, C = int(tbl.get("rowCnt")), int(tbl.get("colCnt"))
    cover = {}
    probs = []
    for r, c, rs, cs, tc in cells(tbl):
        for i in range(r, r + rs):
            for j in range(c, c + cs):
                if (i, j) in cover:
                    probs.append(f"겹침 ({i},{j})")
                cover[(i, j)] = 1
    for i in range(R):
        for j in range(C):
            if (i, j) not in cover:
                probs.append(f"빈 격자 ({i},{j})")
    trs = tbl.findall(HP + "tr")
    if len(trs) != R:
        probs.append(f"tr 수 {len(trs)} != rowCnt {R}")
    for k, tr in enumerate(trs):
        for tc in tr.findall(HP + "tc"):
            if int(tc.find(HP + "cellAddr").get("rowAddr")) != k:
                probs.append(f"tr{k}에 rowAddr {tc.find(HP + 'cellAddr').get('rowAddr')} 칸")
                break
    return probs


def _row_height(tr):
    hs = [int(tc.find(HP + "cellSz").get("height")) for tc in tr.findall(HP + "tc")
          if tc.find(HP + "cellSpan").get("rowSpan") == "1"]
    return max(hs) if hs else 0


def clone_row(tbl, src_row, after_row, count=1):
    trs = tbl.findall(HP + "tr")
    src = trs[src_row]
    for tc in src.findall(HP + "tc"):
        if tc.find(HP + "cellSpan").get("rowSpan") != "1":
            raise ValueError(f"src_row {src_row}에 세로 병합 칸이 있어 복제 불가")
    # 세로 병합 보정: 경계(after_row | after_row+1)를 가로지르는 칸, 또는 src_row를 덮고 after_row에서 끝나는 칸
    for r, c, rs, cs, tc in cells(tbl):
        end = r + rs - 1
        if rs > 1 and r <= after_row and (end >= after_row + 1 or (r <= src_row <= end and end == after_row and r < src_row)):
            tc.find(HP + "cellSpan").set("rowSpan", str(rs + count))
    h = _row_height(src)
    anchor = trs[after_row]
    news = []
    for k in range(count):
        nt = copy.deepcopy(src)
        for p in nt.iter(HP + "p"):
            p.set("id", NOID) if p.get("id") not in (None, "0") else None
        # 복제한 행에 메모 필드가 따라오면 id가 겹친다 → 메모 필드는 뺀다
        for c in list(nt.iter(HP + "ctrl")):
            if c.find(HP + "fieldBegin") is not None or c.find(HP + "fieldEnd") is not None:
                c.getparent().remove(c)
        news.append(nt)
    for nt in reversed(news):
        anchor.addnext(nt)
    # 행 주소 다시 매기기
    for k, tr in enumerate(tbl.findall(HP + "tr")):
        for tc in tr.findall(HP + "tc"):
            tc.find(HP + "cellAddr").set("rowAddr", str(k))
    tbl.set("rowCnt", str(int(tbl.get("rowCnt")) + count))
    sz = tbl.find(HP + "sz")
    sz.set("height", str(int(sz.get("height")) + h * count))
    strip_lineseg(tbl)
    return tbl


def delete_row(tbl, row):
    trs = tbl.findall(HP + "tr")
    tr = trs[row]
    for tc in tr.findall(HP + "tc"):
        if tc.find(HP + "cellSpan").get("rowSpan") != "1":
            raise ValueError(f"row {row}에 세로 병합 시작 칸이 있어 삭제 불가")
    for r, c, rs, cs, tc in cells(tbl):
        if r < row <= r + rs - 1:
            tc.find(HP + "cellSpan").set("rowSpan", str(rs - 1))
    h = _row_height(tr)
    tbl.remove(tr)
    for k, t in enumerate(tbl.findall(HP + "tr")):
        for tc in t.findall(HP + "tc"):
            tc.find(HP + "cellAddr").set("rowAddr", str(k))
    tbl.set("rowCnt", str(int(tbl.get("rowCnt")) - 1))
    sz = tbl.find(HP + "sz")
    sz.set("height", str(max(0, int(sz.get("height")) - h)))
    strip_lineseg(tbl)
    return tbl


# ───────────────────────── 머리(header.xml) ─────────────────────────
def add_charpr_variant(header_root, base_id, kind="subscript"):
    """base charPr을 복제해 아래첨자(또는 위첨자) 글자 모양을 추가하고 새 id를 돌려준다."""
    cps = header_root.find(".//" + HH + "charProperties")
    base = None
    for cp in cps.findall(HH + "charPr"):
        if cp.get("id") == str(base_id):
            base = cp
    if base is None:
        raise KeyError(base_id)
    new = copy.deepcopy(base)
    nid = max(int(cp.get("id")) for cp in cps.findall(HH + "charPr")) + 1
    new.set("id", str(nid))
    for t in ("subscript", "superscript"):
        for e in new.findall(HH + t):
            new.remove(e)
    etree.SubElement(new, HH + kind)
    cps.append(new)
    cps.set("itemCnt", str(len(cps.findall(HH + "charPr"))))
    return nid


def add_manifest_image(hpf_root, item_id, href, media_type):
    man = hpf_root.find(".//" + OPF + "manifest")
    last_img = None
    for it in man.findall(OPF + "item"):
        if (it.get("href") or "").startswith("BinData/"):
            last_img = it
    new = etree.Element(OPF + "item")
    new.set("id", item_id)
    new.set("href", href)
    new.set("media-type", media_type)
    new.set("isEmbeded", "1")
    if last_img is not None:
        last_img.addnext(new)
    else:
        man.append(new)
    return new


def all_numeric_ids(roots):
    """문서 안 개체·필드 id로 쓰인 정수 집합(새 id 충돌 방지)."""
    ids = set()
    for root in roots:
        for el in root.iter():
            for a in ("id", "instid", "fieldid"):
                v = el.get(a)
                if v and v.isdigit():
                    ids.add(int(v))
    return ids
