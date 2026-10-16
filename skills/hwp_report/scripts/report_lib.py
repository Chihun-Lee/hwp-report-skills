# -*- coding: utf-8 -*-
"""hwp_report 공용 라이브러리 — 양식 hwpx의 문단·표·그림을 다룬다.

- 양식 스타일(charPr/paraPr)을 그대로 쓰고, 글머리 내어쓰기용 paraPr만 헤더 끝에 추가한다.
- 본문은 「개조식 마크업」(outline) 문자열로 받는다. 문법은 parse_outline() 참조.
- 그림은 400 dpi 설계 크기 1:1(픽셀 × 7200/dpi HWPUNIT)로 넣고 상한(기본 150 × 105 mm)에서 줄인다.
"""
import copy
import hashlib
import re
import zipfile
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
NS = {"hp": HP, "hh": HH, "hc": HC}
MM = 283.465                      # HWPUNIT / mm  (7200 / 25.4)


def q(tag):
    pre, name = tag.split(":")
    return "{%s}%s" % ({"hp": HP, "hh": HH, "hc": HC}[pre], name)


# ── 글머리 문단 모양 (KoPub바탕 12pt 실측: ｏ·‧ ≈ 1080, '-' ≈ 600 HWPUNIT) ─────────
#   left/intent는 hp:case 값, hp:default는 × 2 (한컴 저장 규약)
PARA_STYLES = {
    "L1": dict(left=600, intent=-1600, align="JUSTIFY"),                        # ｏ 항목
    "L2": dict(left=2200, intent=-1100, align="JUSTIFY"),                       # - 항목, ※ 메모
    "L3": dict(left=3300, intent=-1600, align="JUSTIFY"),                       # ‧ 항목
    "IMG": dict(left=0, intent=0, align="CENTER", keep_next=True, prev=400, line=100),  # 인라인 그림 줄
    "CAP": dict(left=0, intent=0, align="JUSTIFY", next_=500),                  # (예비) 왼쪽 캡션
    "L1K": dict(left=600, intent=-1600, align="JUSTIFY", keep_next=True),       # ｏ 굵은 소제목(다음 문단과 함께)
    "KEEP": dict(left=0, intent=0, align="JUSTIFY", keep_next=True),            # 양식 제목(다음 문단과 함께)
    "CAPC": dict(left=0, intent=0, align="CENTER", prev=400, next_=400),        # 그림 캡션(가운데)
}
BULLET = {"o": "ｏ ", "-": "- ", "dot": "‧ "}


class Form:
    """양식 hwpx 한 개를 열어 section0을 고치고 다시 저장한다."""

    def __init__(self, path, base_parapr="0"):
        self.path = Path(path)
        with zipfile.ZipFile(self.path) as z:
            self.files = {n: z.read(n) for n in z.namelist()}
            self.infos = {i.filename: i for i in z.infolist()}
        self.root = etree.fromstring(self.files["Contents/section0.xml"])
        self.header = etree.fromstring(self.files["Contents/header.xml"])
        self.P = self.root.findall("hp:p", NS)          # 양식 원본 문단 목록(인덱스 고정)
        self._id = 1900000000
        self.figs = []                                   # [(item_id, Path)]
        props = self.header.find(".//hh:paraProperties", NS)
        ids = [int(p.get("id")) for p in props.findall("hh:paraPr", NS)]
        nxt = max(ids) + 1
        self.pp = {}
        for k in PARA_STYLES:
            self.pp[k] = str(nxt)
            nxt += 1
        self.base_parapr = base_parapr
        self._keep_cache = {}
        self.cp_body = "31"
        self.cp_bold = "29"

    # ── 찾기 ──
    @staticmethod
    def text(p):
        out = []
        for t in p.iter(q("hp:t")):
            out.append(t.text or "")
            for ch in t:
                out.append(ch.tail or "")
        return "".join(out)

    def find(self, pattern, start=0, end=None, top_only=True, flags=0):
        """정규식이 처음 맞는 양식 문단 인덱스 (표 안 문단은 건너뜀)"""
        rx = re.compile(pattern, flags)
        end = len(self.P) if end is None else end
        for i in range(start, end):
            p = self.P[i]
            if top_only and p.find(".//hp:tbl", NS) is not None:
                continue
            if rx.search(self.text(p).strip()):
                return i
        raise KeyError(f"양식에서 문단을 찾지 못함: {pattern}")

    def find_last(self, pattern, start, end):
        rx = re.compile(pattern)
        hit = None
        for i in range(start, end):
            p = self.P[i]
            if p.find(".//hp:tbl", NS) is None and rx.search(self.text(p).strip()):
                hit = i
        if hit is None:
            raise KeyError(pattern)
        return hit

    def table_after(self, i, limit=6):
        for k in range(i + 1, min(i + 1 + limit, len(self.P))):
            t = self.P[k].find(".//hp:tbl", NS)
            if t is not None:
                return k, t
        raise KeyError(f"{i}번 문단 뒤에 표가 없음")

    def remove(self, *idx):
        for i in idx:
            p = self.P[i]
            if p.getparent() is not None:
                p.getparent().remove(p)

    def detect_charpr_auto(self):
        """예시 문단이 없는 양식: 본문에서 가장 많이 쓴 글자 모양 = 본문, 같은 크기의 굵은 모양 = 굵게"""
        import collections
        cps = {c.get("id"): c for c in self.header.iter(q("hh:charPr"))}
        cnt = collections.Counter()
        for p in self.P:
            if p.find(".//hp:tbl", NS) is not None or not self.text(p).strip():
                continue
            for r in p.findall("hp:run", NS):
                cnt[r.get("charPrIDRef")] += len("".join(t.text or "" for t in r.findall("hp:t", NS)))
        bold = lambda i: cps[i].find("hh:bold", NS) is not None  # noqa: E731
        body = next((i for i, _ in cnt.most_common() if i in cps and not bold(i)), None)
        if body is None:
            return
        self.cp_body = body
        h = cps[body].get("height")
        same = [i for i, c in cps.items() if bold(i) and c.get("height") == h]
        used = [i for i, _ in cnt.most_common() if i in same]
        self.cp_bold = (used or same or [body])[0]

    def detect_charpr(self, body_idx, bold_idx):
        """본문 charPr = 양식 예시 「ｏ 세부설명」, 굵게 = 「1) 당해연도…」 제목"""
        r = self.P[body_idx].find("hp:run", NS)
        if r is not None:
            self.cp_body = r.get("charPrIDRef")
        r = self.P[bold_idx].find("hp:run", NS)
        if r is not None:
            self.cp_bold = r.get("charPrIDRef")

    # ── 문단 만들기 ──
    def nid(self):
        self._id += 1
        return str(self._id)

    def make_p(self, runs, ppr=None, page_break=False):
        p = etree.Element(q("hp:p"), nsmap={"hp": HP})
        p.set("id", self.nid())
        p.set("paraPrIDRef", ppr if ppr is not None else self.pp["L1"])
        p.set("styleIDRef", "0")
        p.set("pageBreak", "1" if page_break else "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
        for text, cpr in runs:
            r = etree.SubElement(p, q("hp:run"))
            r.set("charPrIDRef", cpr)
            etree.SubElement(r, q("hp:t")).text = text
        return p

    def keep_with_next(self, p):
        """문단 자신의 paraPr을 복제해 keepWithNext만 켠다(제목이 쪽 끝에 홀로 남지 않게)"""
        src = p.get("paraPrIDRef")
        if src not in self._keep_cache:
            props = self.header.find(".//hh:paraProperties", NS)
            base = props.find(f"hh:paraPr[@id='{src}']", NS)
            pp = copy.deepcopy(base)
            new_id = str(max(int(v) for v in self.pp.values()) + 1 + len(self._keep_cache))
            pp.set("id", new_id)
            pp.find("hh:breakSetting", NS).set("keepWithNext", "1")
            self._keep_cache[src] = (new_id, pp)
        p.set("paraPrIDRef", self._keep_cache[src][0])

    # ── 개조식 마크업 → 문단 ──
    def render(self, items, figs_dir, caption_fmt="<{}>", fig_box=(150, 105), dpi=400):
        out = []
        n = len(items)
        for k, it in enumerate(items):
            kind = it[0]
            if kind in ("o", "head") and out and not _is_blank(out[-1]):
                out.append(self.make_p([(" ", self.cp_body)], ppr=self.base_parapr))   # 묶음 사이 빈 줄
            if kind == "blank":
                prev = out[-1].get("paraPrIDRef") if out else self.base_parapr
                out.append(self.make_p([("", self.cp_body)], ppr=prev))
            elif kind == "sub":
                out.append(self.make_p([(it[1], self.cp_bold)], ppr=self.base_parapr))
            elif kind == "head":
                out.append(self.make_p([(BULLET["o"] + it[1], self.cp_bold)], ppr=self.pp["L1K"]))
            elif kind == "o":
                out.append(self.make_p([(BULLET["o"] + it[1], self.cp_body)], ppr=self.pp["L1"]))
            elif kind == "-":
                out.append(self.make_p([(BULLET["-"] + it[1], self.cp_body)], ppr=self.pp["L2"]))
            elif kind == "dot":
                out.append(self.make_p([(BULLET["dot"] + it[1], self.cp_body)], ppr=self.pp["L3"]))
            elif kind == "note":
                out.append(self.make_p([(it[1], self.cp_body)], ppr=self.pp["L2"]))
            elif kind == "text":
                out.append(self.make_p([(it[1], self.cp_body)], ppr=self.base_parapr))
            elif kind == "fig":
                _, fid, opts, cap = it
                out.extend(self.figure(fid, cap, figs_dir, caption_fmt, fig_box, dpi, opts))
                nxt = items[k + 1][0] if k + 1 < n else None
                if nxt not in (None, "blank", "o", "head"):
                    out.append(self.make_p([("", self.cp_body)], ppr=self.pp["CAPC"]))   # 캡션 뒤 빈 줄
        return out

    # ── 그림 ──
    def figure(self, fid, caption, figs_dir, caption_fmt, fig_box, dpi, opts):
        src = find_image(figs_dir, fid)
        from PIL import Image
        with Image.open(src) as im:
            pw, ph = im.size
        # 한컴 규약대로 image1, image2 … (rhwp 등 뷰어가 이름의 번호로 BinData를 찾는다)
        item_id = next((i for i, s in self.figs if s == src), None)
        if item_id is None:
            item_id = f"image{len(self.figs) + 1}"
            self.figs.append((item_id, src))
        f = 7200 / dpi                                    # 400 dpi → 18 HWPUNIT/px
        w, h = round(pw * f), round(ph * f)
        if opts.get("폭") or opts.get("w"):
            ww = float(opts.get("폭") or opts.get("w")) * MM
            w, h = round(ww), round(h * ww / w)
        else:
            k = min(1.0, fig_box[0] * MM / w, fig_box[1] * MM / h)
            w, h = round(w * k), round(h * k)
        return [self.image_p(item_id, pw, ph, w, h),
                self.make_p([(caption_fmt.format(caption), self.cp_body)], ppr=self.pp["CAPC"])]

    def image_p(self, item_id, pw, ph, width, height):
        dw, dh = pw * 75, ph * 75          # 한컴 규약: imgDim·imgClip = 원본 픽셀 × 75
        p = self.make_p([], ppr=self.pp["IMG"])
        r = etree.SubElement(p, q("hp:run"))
        r.set("charPrIDRef", self.cp_body)
        cx, cy = width // 2, height // 2
        pic = etree.fromstring(
            f'<hp:pic xmlns:hp="{HP}" xmlns:hc="{HC}" id="{self.nid()}" zOrder="0" numberingType="PICTURE" '
            f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" '
            f'groupLevel="0" instid="{self.nid()}" reverse="0"><hp:offset x="0" y="0"/>'
            f'<hp:orgSz width="{width}" height="{height}"/><hp:curSz width="{width}" height="{height}"/>'
            f'<hp:flip horizontal="0" vertical="0"/>'
            f'<hp:rotationInfo angle="0" centerX="{cx}" centerY="{cy}" rotateimage="0"/>'
            f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
            f'<hc:img binaryItemIDRef="{item_id}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
            f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{width}" y="0"/>'
            f'<hc:pt2 x="{width}" y="{height}"/><hc:pt3 x="0" y="{height}"/></hp:imgRect>'
            f'<hp:imgClip left="0" right="{dw}" top="0" bottom="{dh}"/>'
            f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:imgDim dimwidth="{dw}" dimheight="{dh}"/><hp:effects/>'
            f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" height="{height}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
            f'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/></hp:pic>')
        r.append(pic)
        etree.SubElement(r, q("hp:t"))
        return p

    # ── 저장 ──
    def _header_xml(self):
        props = self.header.find(".//hh:paraProperties", NS)
        base = props.find(f"hh:paraPr[@id='{self.base_parapr}']", NS)
        for key, o in PARA_STYLES.items():
            pp = copy.deepcopy(base)
            pp.set("id", self.pp[key])
            pp.find("hh:align", NS).set("horizontal", o["align"])
            if o.get("keep_next"):
                pp.find("hh:breakSetting", NS).set("keepWithNext", "1")
            for path, mul in ((".//hp:case", 1), (".//hp:default", 2)):
                mg = pp.find(path + "/hh:margin", NS)
                if mg is None:
                    continue
                mg.find("hc:intent", NS).set("value", str(o["intent"] * mul))
                mg.find("hc:left", NS).set("value", str(o["left"] * mul))
                mg.find("hc:prev", NS).set("value", str(o.get("prev", 0) * mul))
                mg.find("hc:next", NS).set("value", str(o.get("next_", 0) * mul))
            if o.get("line"):   # 인라인 그림 줄은 % 줄간격이 그림 높이에 곱해지므로 100%
                for ls in pp.iter(q("hh:lineSpacing")):
                    ls.set("value", str(o["line"]))
            props.append(pp)
        for _, (_, pp) in sorted(self._keep_cache.items(), key=lambda kv: int(kv[1][0])):
            props.append(pp)
        props.set("itemCnt", str(len(props.findall("hh:paraPr", NS))))
        return etree.tostring(self.header, encoding="utf-8", xml_declaration=True, standalone=True)

    def save(self, out):
        for ls in self.root.findall(".//hp:linesegarray", NS):   # 한컴이 다시 계산하게 줄배치 캐시 제거
            ls.getparent().remove(ls)
        sec = etree.tostring(self.root, encoding="utf-8", xml_declaration=True, standalone=True)
        header = self._header_xml()
        hpf = self.files["Contents/content.hpf"].decode("utf-8")
        items = "".join(
            f'<opf:item id="{iid}" href="BinData/{iid}{src.suffix.lower()}" '
            f'media-type="{_mime(src)}" isEmbeded="1"/>' for iid, src in self.figs)
        hpf = hpf.replace("</opf:manifest>", items + "</opf:manifest>")
        out = Path(out)
        tmp = out.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            order = ["mimetype"] + [n for n in self.files if n != "mimetype"]
            for name in order:
                if name not in self.files:
                    continue
                data = self.files[name]
                if name == "Contents/section0.xml":
                    data = sec
                elif name == "Contents/header.xml":
                    data = header
                elif name == "Contents/content.hpf":
                    data = hpf.encode("utf-8")
                info = self.infos[name]
                if name == "mimetype":
                    z.writestr(info, data, compress_type=zipfile.ZIP_STORED)
                else:
                    z.writestr(info, data)
            for iid, src in self.figs:
                z.write(src, f"BinData/{iid}{src.suffix.lower()}")
        tmp.replace(out)
        return out


def _is_blank(p):
    return p.find(".//hp:pic", NS) is None and p.find(".//hp:tbl", NS) is None and not Form.text(p).strip()


def _mime(src):
    return {".png": "image/png", ".bmp": "image/bmp", ".gif": "image/gif"}.get(src.suffix.lower(), "image/jpeg")


def find_image(figs_dir, fid):
    for d in (figs_dir if isinstance(figs_dir, (list, tuple)) else [figs_dir]):
        d = Path(d)
        for ext in (".jpg", ".jpeg", ".png", ".JPG", ".PNG"):
            if (d / f"{fid}{ext}").exists():
                return d / f"{fid}{ext}"
    raise FileNotFoundError(f"그림 파일 없음: {fid}(.jpg/.png) in {figs_dir}")


def md5(path_or_bytes):
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    return hashlib.md5(data).hexdigest()


# ── 개조식 마크업 ─────────────────────────────────────────────
#   ## 굵은 소항목   → ｏ 굵게 (다음 문단과 함께, 앞에 빈 줄 자동)
#   #  굵은 제목     → 굵게, 들여쓰기 없음
#   o  항목          → ｏ 항목 (앞에 빈 줄 자동, 첫 항목 제외)
#   -  항목          → - 항목
#   ·  항목          → ‧ 항목  (· ‧ * . 모두 허용)
#   ※ 메모           → ※ 메모 (- 항목 들여쓰기)
#   [그림 파일ID] 캡션        → 그림 + 캡션(<캡션>), 캡션 뒤 빈 줄 자동
#   [그림 파일ID 폭=110] 캡션 → 폭 110 mm 고정
#   (빈 줄)          → 빈 문단(바로 앞 문단 모양 그대로 — 한컴에서 Enter 친 것과 같음)
#   그 밖의 줄       → 들여쓰기 없는 본문
FIG_RX = re.compile(r"^\[그림\s+([^\]\s]+)((?:\s+[^\]\s=]+=[^\]\s]+)*)\s*\]\s*(.*)$")


def parse_outline(text):
    items = []
    if not text:
        return items
    if isinstance(text, list):
        text = "\n".join(text)
    lines = text.split("\n")
    while lines and not lines[-1].strip():      # 끝 빈 줄은 무시(YAML 블록 끝)
        lines.pop()
    for raw in lines:
        s = raw.strip()
        if not s:
            items.append(("blank",))
            continue
        m = FIG_RX.match(s)
        if m:
            opts = dict(kv.split("=", 1) for kv in m.group(2).split())
            items.append(("fig", m.group(1), opts, m.group(3).strip()))
        elif s.startswith("## "):
            items.append(("head", s[3:].strip()))
        elif s.startswith("# "):
            items.append(("sub", s[2:].strip()))
        elif re.match(r"^[oｏ]\s", s):
            items.append(("o", s[2:].strip()))
        elif s.startswith("- "):
            items.append(("-", s[2:].strip()))
        elif re.match(r"^[·‧*.]\s", s):
            items.append(("dot", s[2:].strip()))
        elif s.startswith("※"):
            items.append(("note", s))
        else:
            items.append(("text", s))
    return items


# ── 표 ───────────────────────────────────────────────────────
def set_p_text(p, text):
    ts = p.findall(".//hp:t", NS)
    for t in ts:   # hp:t 안의 줄바꿈·탭 요소와 그 뒤 글자(tail)까지 비운다
        for ch in list(t):
            t.remove(ch)
    if ts:
        ts[0].text = text
        for t in ts[1:]:
            t.text = ""
    else:
        run = p.find("hp:run", NS)
        if run is None:
            run = etree.SubElement(p, q("hp:run"))
            run.set("charPrIDRef", "0")
        etree.SubElement(run, q("hp:t")).text = text
    for ls in p.findall(".//hp:linesegarray", NS):
        ls.getparent().remove(ls)


def cell(tbl, r, c):
    for tc in tbl.iter(q("hp:tc")):
        a = tc.find("hp:cellAddr", NS)
        if a is not None and int(a.get("rowAddr")) == r and int(a.get("colAddr")) == c:
            if tc.getparent().getparent() is tbl:
                return tc
    raise KeyError((r, c))


def as_lines(v):
    if v is None:
        return [""]
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return str(v).split("\n")


def set_cell(tbl, r, c, value):
    """셀을 lines로 채운다. 줄 수가 기존 문단 수와 같으면 문단별 서식을 그대로 두고 글자만 바꾼다."""
    lines = as_lines(value)
    tc = cell(tbl, r, c)
    sub = tc.find("hp:subList", NS)
    ps = sub.findall("hp:p", NS)
    if len(ps) == len(lines) and len(ps) > 1:
        for p, line in zip(ps, lines):
            set_p_text(p, line)
        return
    proto = copy.deepcopy(ps[0])
    for p in ps:
        sub.remove(p)
    for line in lines:
        p = copy.deepcopy(proto)
        set_p_text(p, line)
        sub.append(p)


def cell_lines(tc):
    return [Form.text(p) for p in tc.find("hp:subList", NS).findall("hp:p", NS)]


def rows_of(tbl):
    return tbl.findall("hp:tr", NS)


def row_height(tr):
    return max(int(tc.find("hp:cellSz", NS).get("height")) for tc in tr.findall("hp:tc", NS)
               if tc.find("hp:cellSpan", NS).get("rowSpan") == "1")


def renumber_rows(tbl):
    rows = rows_of(tbl)
    for i, tr in enumerate(rows):
        for tc in tr.findall("hp:tc", NS):
            tc.find("hp:cellAddr", NS).set("rowAddr", str(i))
    tbl.set("rowCnt", str(len(rows)))


def fill_rows(tbl, rows, header_rows=1, prefix=""):
    """머리행 아래 본문 행을 첫 본문 행 복제로 len(rows)개 만들고 채운다"""
    trs = rows_of(tbl)
    proto = trs[header_rows]
    for tr in trs[header_rows:]:
        tbl.remove(tr)
    anchor = trs[header_rows - 1]
    for vals in rows:
        new = copy.deepcopy(proto)
        anchor.addnext(new)
        anchor = new
    renumber_rows(tbl)
    for i, vals in enumerate(rows, header_rows):
        for c, v in enumerate(vals):
            lines = as_lines(v)
            if prefix:
                lines = [prefix + x if x and not x.startswith(prefix) else x for x in lines]
            set_cell(tbl, i, c, lines)
    fit_rows(tbl, only=set(range(header_rows, header_rows + len(rows))))


def rebuild_groups(tbl, header_rows, groups, label_col=0):
    """세부기술처럼 첫 열이 병합된 표를 groups=[{label, rows}]로 다시 짠다.
    첫 본문 행(라벨 셀 포함)과 이어지는 행(라벨 셀 없음)을 원형으로 복제한다."""
    trs = rows_of(tbl)
    body = trs[header_rows:]
    first = body[0]
    cont = None
    for tr in body[1:]:
        cols = [int(tc.find("hp:cellAddr", NS).get("colAddr")) for tc in tr.findall("hp:tc", NS)]
        if label_col not in cols:
            cont = tr
            break
    if cont is None:   # 이어지는 행 원형이 없으면 첫 행에서 라벨 셀을 뺀다
        cont = copy.deepcopy(first)
        for tc in cont.findall("hp:tc", NS):
            if int(tc.find("hp:cellAddr", NS).get("colAddr")) == label_col:
                cont.remove(tc)
    first, cont = copy.deepcopy(first), copy.deepcopy(cont)
    h1 = row_height(cont) if cont.findall("hp:tc", NS) else 1000
    for tr in body:
        tbl.remove(tr)
    anchor = trs[header_rows - 1]
    plan = []
    for g in groups:
        for k, _ in enumerate(g["rows"]):
            new = copy.deepcopy(first if k == 0 else cont)
            if k == 0:
                for tc in new.findall("hp:tc", NS):
                    if int(tc.find("hp:cellAddr", NS).get("colAddr")) == label_col:
                        tc.find("hp:cellSpan", NS).set("rowSpan", str(len(g["rows"])))
                        tc.find("hp:cellSz", NS).set("height", str(h1 * len(g["rows"])))
            anchor.addnext(new)
            anchor = new
            plan.append((g, k))
    renumber_rows(tbl)
    r = header_rows
    for g in groups:
        set_cell(tbl, r, label_col, g.get("label", ""))
        for k, vals in enumerate(g["rows"]):
            cols = [int(tc.find("hp:cellAddr", NS).get("colAddr"))
                    for tc in rows_of(tbl)[r + k].findall("hp:tc", NS)]
            cols = [c for c in cols if c != label_col]
            for c, v in zip(cols, vals):
                set_cell(tbl, r + k, c, v)
        r += len(g["rows"])
    fit_rows(tbl, only=set(range(header_rows, r)))


def text_w(text, fs):
    w = 0
    for ch in text:
        k = ord(ch)
        w += fs * (1.0 if k >= 0x1100 else (0.3 if ch == " " else 0.55))
    return w


def fit_rows(tbl, only=None, fs=1000, pitch=1.6, pad=300):
    """셀 글자량으로 행 높이를 추정해 cellSz·표 높이를 맞춘다 (한컴은 최소높이로 취급, rhwp는 그대로 그림)"""
    rows = rows_of(tbl)
    need = {}
    for tr in rows:
        for tc in tr.findall("hp:tc", NS):
            a, sp = tc.find("hp:cellAddr", NS), tc.find("hp:cellSpan", NS)
            r, span = int(a.get("rowAddr")), int(sp.get("rowSpan"))
            mg = tc.find("hp:cellMargin", NS)
            avail = int(tc.find("hp:cellSz", NS).get("width")) - int(mg.get("left")) - int(mg.get("right"))
            lines = 0
            for p in tc.find("hp:subList", NS).findall("hp:p", NS):
                t = "".join(x.text or "" for x in p.iter(q("hp:t")))
                lines += max(1, -(-int(text_w(t, fs) * 1.08) // max(avail, 1)))
            h = int(lines * fs * pitch) + int(mg.get("top")) + int(mg.get("bottom")) + pad
            need.setdefault(r, []).append((span, h))
    heights = []
    for tr in rows:
        try:
            heights.append(row_height(tr))
        except ValueError:     # 모든 셀이 병합 셀이면 0에서 시작
            heights.append(0)
    for r in range(len(rows)):
        if only is not None and r not in only:
            continue
        for span, h in need.get(r, []):
            if span == 1:
                heights[r] = max(heights[r], h)
    for r in range(len(rows)):     # 병합셀: 부족분을 마지막 행에 더함
        if only is not None and r not in only:
            continue
        for span, h in need.get(r, []):
            if span > 1 and sum(heights[r:r + span]) < h:
                heights[r + span - 1] += h - sum(heights[r:r + span])
    for tr in rows:
        for tc in tr.findall("hp:tc", NS):
            r = int(tc.find("hp:cellAddr", NS).get("rowAddr"))
            span = int(tc.find("hp:cellSpan", NS).get("rowSpan"))
            tc.find("hp:cellSz", NS).set("height", str(sum(heights[r:r + span])))
    tbl.find("hp:sz", NS).set("height", str(sum(heights)))
