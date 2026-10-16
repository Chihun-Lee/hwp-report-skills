# -*- coding: utf-8 -*-
"""채워진 보고서 hwpx(한컴에서 고친 사용자 수정본 포함) → spec(YAML) 역추출.

    python extract_spec.py 수정본.hwpx -o report.yaml [--figs-out figs/] [--match-figs 그림폴더 ...]
                           [--form 양식] [--spec 이전spec.yaml]

- 양식과 비교해 바뀐 표지·표 칸만 spec에 적는다. 양식에 없는 절은 건너뛴다.
- 본문은 개조식 마크업으로 되돌린다(빌드할 때 자동으로 생기는 빈 줄은 빼고, 사용자가 넣은 빈 줄은 남긴다).
- 그림은 BinData에서 꺼내고, --match-figs 폴더에 같은 파일(md5)이 있으면 그 파일 이름(ID)을 쓴다.
- 다른 양식에서 sections:/tables:를 썼다면 --spec으로 이전 spec을 주면 그 부분도 되돌린다.
왕복 검증: build_report.py로 다시 빌드한 뒤 diff_hwpx.py로 원본과 비교하면 차이가 0이어야 한다.
"""
import argparse
import io
import re
import sys
import zipfile
from pathlib import Path

import yaml
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_lib import MM, NS, HH, Form, cell_lines, md5, rows_of, row_height  # noqa: E402
from settings import resolve_form  # noqa: E402

text = Form.text


class Doc:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.root = etree.fromstring(self.z.read("Contents/section0.xml"))
        hdr = etree.fromstring(self.z.read("Contents/header.xml"))
        self.bold = {c.get("id") for c in hdr.iter("{%s}charPr" % HH) if c.find("hh:bold", NS) is not None}
        hpf = self.z.read("Contents/content.hpf").decode("utf-8")
        self.items = dict(re.findall(r'<opf:item id="([^"]+)" href="([^"]+)"', hpf))
        self.P = self.root.findall("hp:p", NS)
        self.T = [text(p).strip() for p in self.P]

    def find(self, rx, start=0, end=None):
        if not rx:
            return None
        end = len(self.P) if end is None else end
        for i in range(max(start, 0), end):
            if self.P[i].find(".//hp:tbl", NS) is None and re.search(rx, self.T[i]):
                return i
        return None

    def find_last(self, rx, start=0, end=None):
        if not rx:
            return None
        end = len(self.P) if end is None else end
        hits = [i for i in range(max(start, 0), end)
                if self.P[i].find(".//hp:tbl", NS) is None and re.search(rx, self.T[i])]
        return hits[-1] if hits else None

    def table_after(self, i, limit=6):
        for k in range(i + 1, min(i + 1 + limit, len(self.P))):
            t = self.P[k].find(".//hp:tbl", NS)
            if t is not None:
                return k, t
        return None, None

    def is_bold(self, p):
        r = p.find("hp:run", NS)
        return r is not None and r.get("charPrIDRef") in self.bold


def one(lines):
    return lines[0] if len(lines) == 1 else lines


def is_blank(p):
    return p.find(".//hp:pic", NS) is None and p.find(".//hp:tbl", NS) is None and not text(p).strip()


def _rh(tr):
    try:
        return row_height(tr)
    except ValueError:
        return 0


class Extractor:
    def __init__(self, doc, form_path, prof, figs_out, match_dirs, cap_fmt=None, prev=None, dpi=400, box=(150, 105)):
        self.d = doc
        self.t = Form(form_path)
        self.prof = prof
        self.A = prof.get("anchors", {}) or {}
        self.samples = set(prof.get("samples") or [])
        self.figs_out = Path(figs_out)
        self.match = {}
        for d in match_dirs or []:
            for f in sorted(Path(d).glob("*")):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    self.match.setdefault(md5(f), f.stem)
        self.cap_fmt = cap_fmt
        self.prev = prev or {}
        self.dpi, self.box = dpi, box
        self.used_ids = {}

    # ── 캡션 형식 추정 ──
    def guess_caption(self):
        if self.cap_fmt:
            return self.cap_fmt
        if self.prev.get("caption_format"):
            return self.prev["caption_format"]
        for i, p in enumerate(self.d.P[:-1]):
            if p.find(".//hp:pic", NS) is not None:
                c = self.d.T[i + 1]
                if c.startswith("<") and c.endswith(">"):
                    return "<{}>"
                if c.startswith("그림. "):
                    return "그림. {}"
                return "{}"
        return "<{}>"

    def uncaption(self, c):
        pre, post = self.cap_fmt.split("{}")
        if c.startswith(pre) and c.endswith(post):
            return c[len(pre):len(c) - len(post) if post else None]
        return c

    # ── 그림 ──
    def fig_line(self, p, caption):
        pic = p.find(".//hp:pic", NS)
        iid = pic.find(".//{http://www.hancom.co.kr/hwpml/2011/core}img").get("binaryItemIDRef")
        href = self.d.items[iid]
        data = self.d.z.read(href)
        h = md5(data)
        if h in self.match:
            fid = self.match[h]
        else:
            fid = self.used_ids.get(h) or Path(href).stem
            self.figs_out.mkdir(parents=True, exist_ok=True)
            ext = Path(href).suffix.lower().replace(".jpeg", ".jpg")
            (self.figs_out / f"{fid}{ext}").write_bytes(data)
        self.used_ids[h] = fid
        w_doc = int(pic.find("hp:sz", NS).get("width"))
        from PIL import Image
        pw, ph = Image.open(io.BytesIO(data)).size
        f = 7200 / self.dpi
        w, hh = pw * f, ph * f
        k = min(1.0, self.box[0] * MM / w, self.box[1] * MM / hh)
        opt = "" if abs(w * k - w_doc) / MM < 0.3 else f" 폭={w_doc / MM:.1f}"
        return f"[그림 {fid}{opt}] {caption}"

    # ── 본문 → 개조식 마크업 ──
    def outline(self, idx, drop_tail=0):
        P = self.d.P
        idx = list(idx)
        for _ in range(drop_tail):
            if idx and is_blank(P[idx[-1]]):
                idx.pop()
        toks, k = [], 0
        while k < len(idx):
            p = P[idx[k]]
            if p.find(".//hp:pic", NS) is not None:
                cap = ""
                if k + 1 < len(idx) and not is_blank(P[idx[k + 1]]) and P[idx[k + 1]].find(".//hp:pic", NS) is None:
                    cap = self.uncaption(text(P[idx[k + 1]]).strip())
                    k += 1
                toks.append(("fig", self.fig_line(p, cap)))
            elif is_blank(p):
                toks.append(("blank", ""))
            else:
                t = text(p).strip()
                if re.match(r"^ｏ\s*", t):
                    body = re.sub(r"^ｏ\s*", "", t)
                    toks.append(("head", "## " + body) if self.d.is_bold(p) else ("o", "o " + body))
                elif t.startswith("- "):
                    toks.append(("-", t))
                elif re.match(r"^[‧·]\s", t):
                    toks.append(("dot", "· " + t[2:]))
                elif t.startswith("※"):
                    toks.append(("note", t))
                elif self.d.is_bold(p):
                    toks.append(("sub", "# " + t))
                else:
                    toks.append(("text", t))
            k += 1
        out = []
        for k, (kind, line) in enumerate(toks):
            if kind == "blank":
                prev = out[-1][0] if out else None
                nxt = toks[k + 1][0] if k + 1 < len(toks) else None
                if prev == "fig" and nxt not in (None, "blank", "o", "head"):
                    continue                     # 캡션 뒤 자동 빈 줄
                if nxt in ("o", "head") and prev not in (None, "blank"):
                    continue                     # 묶음 사이 자동 빈 줄
            out.append((kind, line))
        s = "\n".join(line for _, line in out)
        return s + "\n" if s else ""

    def tail_blanks(self, t_head_rx, t_end_rx):
        """양식에서 제목 뒤 빈 줄 수 — 빌드가 첫 빈 줄을 쓰므로 나머지는 양식 몫"""
        tt = [text(p).strip() for p in self.t.P]
        a = next((i for i, x in enumerate(tt) if t_head_rx and re.search(t_head_rx, x)), None)
        if a is None:
            return 0
        b = next((i for i in range(a + 1, len(tt)) if t_end_rx and re.search(t_end_rx, tt[i])), len(tt))
        has_samples = any(tt[i] in self.samples for i in range(a + 1, b))
        nb = sum(1 for i in range(a + 1, b) if is_blank(self.t.P[i]))
        return nb if has_samples else max(0, nb - 1)

    # ── 표 ──
    @staticmethod
    def body_rows(tbl, header_rows, prefix=""):
        rows = []
        for tr in rows_of(tbl)[header_rows:]:
            vals = []
            for tc in tr.findall("hp:tc", NS):
                ls = cell_lines(tc)
                if prefix:
                    ls = [x[len(prefix):] if x.startswith(prefix) else x for x in ls]
                vals.append(one(ls))
            rows.append(vals)
        return rows

    @staticmethod
    def groups(tbl, header_rows, label_col=0):
        out, cur = [], None
        for tr in rows_of(tbl)[header_rows:]:
            tcs = tr.findall("hp:tc", NS)
            lab = [tc for tc in tcs if int(tc.find("hp:cellAddr", NS).get("colAddr")) == label_col]
            if lab:
                cur = {"label": one(cell_lines(lab[0])), "rows": []}
                out.append(cur)
            cur["rows"].append([one(cell_lines(tc)) for tc in tcs
                                if int(tc.find("hp:cellAddr", NS).get("colAddr")) != label_col])
        return out

    @staticmethod
    def cell_map(tbl):
        m = {}
        for tc in tbl.iter("{%s}tc" % NS["hp"]):
            if tc.getparent().getparent() is not tbl:
                continue
            a = tc.find("hp:cellAddr", NS)
            m[(int(a.get("rowAddr")), int(a.get("colAddr")))] = (tc, cell_lines(tc))
        return m

    def diff_cells(self, t_tpl, t_doc, fix=lambda ls: ls):
        a, b = self.cell_map(t_tpl), self.cell_map(t_doc)
        out = {}
        for k, (_, lb) in b.items():
            la = fix(a[k][1]) if k in a else None
            if la != lb:
                out[f"{k[0]},{k[1]}"] = one(lb)
        return out

    # ── 전체 ──
    def run(self):
        d, A, s = self.d, self.A, {}
        self.cap_fmt = self.guess_caption()
        TP = self.t.P
        tt = [text(p).strip() for p in TP]
        tfind = lambda key, start=0: next((i for i in range(start, len(tt)) if A.get(key)  # noqa: E731
                                           and TP[i].find(".//hp:tbl", NS) is None and re.search(A[key], tt[i])), None)

        # 표지~목차: 양식과 문단 수가 같으므로 같은 번호로 맞춘다
        i_toc_t, i_toc = tfind("toc"), d.find(A.get("toc"))
        if i_toc_t is not None and i_toc != i_toc_t:
            raise SystemExit("표지~목차 문단 수가 양식과 다름 — 다른 양식으로 만든 문서인지 확인(--form)")
        cover = {}
        i_ko, i_en = tfind("title_ko"), tfind("title_en")
        if i_ko is not None:
            cover["title_ko"] = d.T[i_ko]
        if i_en is not None:
            cover["title_en"] = d.T[i_en]
            i_org = tfind("org", i_en)
            for i in range(i_en + 1, i_org if i_org is not None else min(len(tt), 30)):
                if A.get("cover_date") and re.match(A["cover_date"], tt[i]):
                    cover["date"] = text(d.P[i]) or " "
        i_sub = tfind("submit_sentence")
        i_sdate = tfind("date", i_sub or 0)
        if i_sdate is not None:
            cover["submit_date"] = text(d.P[i_sdate]).strip() or "년      월      일"
        if cover:
            s["cover"] = cover
        if i_sdate is not None:
            i_part, tp_tpl = self.t.table_after(i_sdate)
            _, tp_doc = d.table_after(i_sdate)
            s["participants"] = self.diff_cells(tp_tpl, tp_doc)
            _, ts_tpl = self.t.table_after(i_part)
            _, ts_doc = d.table_after(i_part)
            ph = self.prof.get("sign_placeholder") or "\0"
            sign = None
            for _, (_, ls) in self.cell_map(ts_doc).items():
                for x in ls:
                    m = re.match(r"^(연구책임자:\s+)(.+?)(\s+\(인\))$", x)
                    if m and ph not in x:
                        sign = m.group(2)
            sd = cover.get("submit_date", "")
            date_rx = re.compile(A["date"])

            def fix(ls):
                out = []
                for x in ls:
                    x = date_rx.sub(sd, x)
                    if sign:
                        x = x.replace(ph, sign)
                    out.append(x)
                return out
            s["summary"] = self.diff_cells(ts_tpl, ts_doc, fix)
            if sign:
                s["summary_sign"] = sign
            fr = [r for r, (ta, tb) in enumerate(zip(rows_of(ts_tpl), rows_of(ts_doc))) if _rh(tb) > _rh(ta)]
            if fr:
                s["summary_fit_rows"] = fr

        # 목차·본문 위치
        i_work = d.find(A.get("work"))
        start = (i_toc if i_toc is not None else -1) + 1
        i_ov = d.find_last(A.get("overview"), start, i_work) if i_work is not None else d.find(A.get("overview"), start)
        if i_toc is not None:
            rng = range(i_toc + 1, i_ov if i_ov is not None else i_toc + 20)
            s["toc"] = {"page_numbers": any(d.P[i].find(".//hp:tab", NS) is not None for i in rng),
                        "attachments": any(A.get("toc_attachments") and re.match(A["toc_attachments"], d.T[i])
                                           for i in rng)}
            if any(d.P[i].find(".//hp:tbl", NS) is not None for i in rng):
                s["guide_box"] = True
        s["caption_format"] = self.cap_fmt
        i_rev = d.find(A.get("review"), i_work or 0)
        i_res = d.find(A.get("results"), max(i_rev or 0, i_work or 0))
        pos = {"overview": i_ov, "work": i_work, "review": i_rev, "results": i_res}
        for k in ("progress", "targets", "outputs", "unplanned", "budget"):
            pos[k] = d.find(A.get(k), i_res or 0)
        pos["next_year"] = d.find(A.get("next_year"), max(pos["budget"] or 0, i_res or 0))
        pos["references"] = d.find(A.get("references"), pos["next_year"] or 0)
        # 다른 양식의 sections: 제목도 경계로 쓴다
        secs = {rx: d.find_last(rx) for rx in (self.prev.get("sections") or {})}
        found = sorted({v for v in list(pos.values()) + list(secs.values()) if v is not None})
        end_of = lambda i: next((j for j in found if j > i), len(d.P))  # noqa: E731

        if i_ov is not None:
            s["overview"] = self.outline(range(i_ov + 1, i_work if i_work is not None else end_of(i_ov)),
                                         drop_tail=self.tail_blanks(A.get("overview"), A.get("work")))
        if i_work is not None:
            stop = i_rev if i_rev is not None else end_of(i_work)
            s["work"] = self.outline(range(i_work + 1, stop),
                                     drop_tail=self.tail_blanks(A.get("work"), A.get("review") or A.get("results")))
        if i_rev is not None:
            _, t_rev = d.table_after(i_rev)
            if t_rev is not None:
                s["review"] = self.body_rows(t_rev, self.prof["header_rows"].get("review", 1), prefix="‧ ")
        if pos["progress"] is not None:
            _, t31 = d.table_after(pos["progress"])
            s["progress"] = self.groups(t31, self.prof["header_rows"].get("progress", 1))
        if pos["targets"] is not None:
            i_32t, t32 = d.table_after(pos["targets"])
            j32 = tfind("targets")
            _, t32_tpl = self.t.table_after(j32)
            hr = self.prof["header_rows"].get("targets", 2)
            hdr = {k: v for k, v in self.diff_cells(t32_tpl, t32).items() if int(k.split(",")[0]) < hr}
            s["targets"] = {"header": hdr, "groups": self.groups(t32, hr)}
            notes = range(i_32t + 1, end_of(pos["targets"]))
            if not any(d.T[i] in self.samples for i in notes):
                s["target_notes"] = self.outline(notes, drop_tail=1)

        if pos["outputs"] is not None:
            outs, i, stop = {}, pos["outputs"] + 1, end_of(pos["outputs"])
            if any(A.get("outputs_note") and re.match(A["outputs_note"], d.T[k]) for k in range(pos["outputs"], stop)):
                s["outputs_note"] = True
            while i < stop:
                x = d.T[i]
                if d.P[i].find(".//hp:tbl", NS) is None and x.startswith("□"):
                    _, tb = d.table_after(i, limit=4)
                    if tb is not None:
                        outs[x[1:].strip()] = self.body_rows(tb, 1)
                elif d.P[i].find(".//hp:tbl", NS) is None and x.startswith("[기타 성과"):
                    _, tb = d.table_after(i, limit=2)
                    if tb is not None:
                        outs["기타 성과"] = one(cell_lines(tb.find(".//hp:tc", NS)))
                i += 1
            s["outputs"] = outs
            s["reference_notes"] = any("<참고" in d.T[k] for k in range(pos["outputs"], stop))

        if pos["unplanned"] is not None:
            rng = list(range(pos["unplanned"] + 1, end_of(pos["unplanned"])))
            if not any(A.get("unplanned_note") and re.match(A["unplanned_note"], d.T[k]) for k in rng):
                s["unplanned"] = self.outline(rng, drop_tail=1)

        if pos["next_year"] is not None:
            ny = {}
            stop = pos["references"] if pos["references"] is not None else len(d.P)
            heads = [i for i in range(pos["next_year"] + 1, stop)
                     if re.match(r"^\d\)\s*", d.T[i]) and d.P[i].find(".//hp:tbl", NS) is None]
            t4 = tfind("next_year")
            t5 = tfind("references", t4 or 0) or len(tt)
            theads = [i for i in range(t4 + 1, t5) if re.match(r"^\d\)\s*", tt[i])] if t4 is not None else []
            tblank = {}
            for a, b in zip(theads, theads[1:] + [t5]):
                tblank[re.match(r"^(\d)\)", tt[a]).group(1)] = sum(1 for k in range(a + 1, b) if is_blank(TP[k]))
            for a, b in zip(heads, heads[1:] + [stop]):
                n = re.match(r"^(\d)\)", d.T[a]).group(1)
                body = self.outline(range(a + 1, b), drop_tail=max(0, tblank.get(n, 1) - 1))
                if body.strip():
                    ny[int(n)] = body
            s["next_year"] = ny

        # 다른 양식: sections / tables
        if secs:
            s["sections"] = {}
            want = {re.sub(r"\s+", "", t) for t in self.prof.get("suggested_sections") or []}
            sug_d = [i for i, t in enumerate(d.T) if d.P[i].find(".//hp:tbl", NS) is None and re.sub(r"\s+", "", t) in want]
            sug_t = [i for i, p in enumerate(TP) if p.find(".//hp:tbl", NS) is None
                     and re.sub(r"\s+", "", text(p)) in want]
            heads_d = sorted(set(found) | set(sug_d))

            def stop_of(P, i, heads):
                nxt = next((j for j in heads if j > i), len(P))
                return next((j for j in range(i + 1, nxt) if P[j].find(".//hp:tbl", NS) is not None), nxt)
            for rx, i in secs.items():
                v = self.prev["sections"][rx]
                if i is None or (isinstance(v, dict) and v.get("mode") == "insert"):
                    s["sections"][rx] = v          # insert 모드는 양식 글과 섞여 되돌릴 수 없어 이전 값을 둔다
                    continue
                # 양식에서 같은 제목 본문 끝의 빈 줄 수(빌드가 남겨 둔 몫)
                ti = next((j for j in reversed(range(len(TP))) if TP[j].find(".//hp:tbl", NS) is None
                           and re.search(rx, tt[j])), None)
                nb = 0
                if ti is not None:
                    th = sorted(set(sug_t) | {j for j in range(len(TP)) if any(
                        TP[j].find(".//hp:tbl", NS) is None and re.search(r2, tt[j]) for r2 in secs)})
                    k = stop_of(TP, ti, th)
                    while k - 1 > ti and is_blank(TP[k - 1]):
                        nb, k = nb + 1, k - 1
                s["sections"][rx] = self.outline(range(i + 1, stop_of(d.P, i, heads_d)), drop_tail=nb)
        if self.prev.get("tables"):
            s["tables"] = []
            for t in self.prev["tables"]:
                i = d.find_last(t["after"])
                _, tb = d.table_after(i, limit=t.get("within", 6)) if i is not None else (None, None)
                if tb is None:
                    continue
                e = {k: v for k, v in t.items() if k not in ("rows", "cells")}
                if "rows" in t:
                    e["rows"] = self.body_rows(tb, t.get("header_rows", 1), prefix=t.get("prefix", ""))
                if "cells" in t:
                    m = self.cell_map(tb)
                    e["cells"] = {k: one(m[tuple(map(int, k.split(",")))][1]) for k in t["cells"]
                                  if tuple(map(int, k.split(","))) in m}
                s["tables"].append(e)
        return s


def _repr_str(dumper, data):
    if "\n" in data:
        data = "\n".join(x.rstrip() for x in data.split("\n"))
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def dump(spec, path, header=""):
    yaml.add_representer(str, _repr_str, Dumper=yaml.SafeDumper)
    body = yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=10000, default_flow_style=None)
    Path(path).write_text(header + body, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hwpx")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--form", help="양식 이름·폴더·hwpx (기본: 이전 spec의 form → 설정 → 2026 연차점검 양식)")
    ap.add_argument("--spec", help="이전 spec(sections:/tables:·form·그림 폴더를 이어받음)")
    ap.add_argument("--figs-out", default=None, help="그림을 꺼낼 폴더 (기본: spec 옆 figs/)")
    ap.add_argument("--match-figs", nargs="*", default=[], help="같은 그림이 있으면 그 이름을 쓸 폴더")
    ap.add_argument("--caption-format")
    a = ap.parse_args()
    out = Path(a.out)
    prev = yaml.safe_load(Path(a.spec).read_text(encoding="utf-8")) if a.spec else {}
    prev_base = Path(a.spec).resolve().parent if a.spec else None
    form_arg = a.form or prev.get("form")
    form_path, prof, _ = resolve_form(form_arg, prev_base)
    match = list(a.match_figs)
    if not match and prev.get("figures"):
        fl = prev["figures"] if isinstance(prev["figures"], list) else [prev["figures"]]
        match = [str((prev_base / x) if not Path(x).is_absolute() else x) for x in fl]
    figs_out = Path(a.figs_out) if a.figs_out else out.parent / "figs"
    ex = Extractor(Doc(a.hwpx), form_path, prof, figs_out, match, a.caption_format, prev)
    spec = ex.run()
    rel = []
    for f in [str(Path(p).resolve()) for p in match] + [str(figs_out.resolve())]:
        try:
            r = str(Path(f).relative_to(out.parent.resolve()))
        except ValueError:
            r = f
        if r not in rel:
            rel.append(r)
    head = {"figures": rel}
    if form_arg and form_arg != "default":
        head = {"form": form_arg, **head}
    spec = {**head, **spec}
    for k in ("year", "lint", "figure_box_mm", "figure_dpi"):
        if k in prev:
            spec[k] = prev[k]
    dump(spec, out, f"# hwp_report spec — {Path(a.hwpx).name}에서 역추출\n")
    print("spec:", out)


if __name__ == "__main__":
    main()
