# -*- coding: utf-8 -*-
"""spec(YAML) → 보고서 hwpx.

    python build_report.py report.yaml                # → report.hwpx (spec 옆)
    python build_report.py report.yaml -o out.hwpx --form <양식 이름|폴더|hwpx> --figs ./figs

- 양식의 문단·표 서식을 그대로 쓰고, 위치는 양식 프로필(profile.yaml)의 제목 정규식으로 찾는다.
- 양식에 없는 절은 건너뛰고 경고한다. 다른 양식의 임의 제목은 spec의 sections:/tables:로 채운다.
spec 문법은 references/spec.md, 예시는 examples/report.example.yaml.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_lib import (NS, Form, fill_rows, fit_rows, parse_outline, rebuild_groups,  # noqa: E402
                        set_cell, set_p_text, q)
from settings import resolve_form  # noqa: E402

MAIN = ["overview", "work", "review", "results", "progress", "targets", "outputs",
        "unplanned", "budget", "next_year", "references"]


def rc(key):
    r, c = str(key).split(",")
    return int(r), int(c)


def norm(s):
    return re.sub(r"\s+", "", s or "")


class Builder:
    def __init__(self, spec, base, form=None, figs=None):
        self.s = spec
        self.base = base
        fpath, self.prof, self.form_dir = resolve_form(form or spec.get("form"), base)
        self.A = self.prof.get("anchors", {}) or {}
        self.f = Form(fpath)
        figs = figs or spec.get("figures") or "figs"
        figs = figs if isinstance(figs, list) else [figs]
        self.figs = [Path(d) if Path(d).is_absolute() else base / d for d in figs]
        self.cap = spec.get("caption_format", "<{}>")
        self.box = tuple(spec.get("figure_box_mm", (150, 105)))
        self.dpi = spec.get("figure_dpi", 400)
        self.samples = set(self.prof.get("samples") or [])
        self.warn = []

    # ── 찾기 ──
    def idx(self, key, start=0, end=None, last=False):
        rx = self.A.get(key)
        if not rx:
            return None
        try:
            if last:
                return self.f.find_last(rx, start, end if end is not None else len(self.f.P))
            return self.f.find(rx, start, end)
        except KeyError:
            return None

    def blank(self, i):
        p = self.f.P[i]
        return p.find(".//hp:tbl", NS) is None and p.find(".//hp:pic", NS) is None and not self.f.text(p).strip()

    def need(self, key, what):
        """spec에 내용이 있는데 양식에 자리가 없으면 경고"""
        if self.s.get(key) not in (None, "", [], {}):
            self.warn.append(f"양식에 「{what}」 자리가 없어 spec의 {key}: 를 넣지 못함")

    # ── 공통 ──
    def items(self, text):
        return self.f.render(parse_outline(text), self.figs, self.cap, self.box, self.dpi)

    def insert_before(self, anchor_p, text):
        for p in self.items(text):
            anchor_p.addprevious(p)

    def fill_region(self, head, end, text):
        """제목 head 뒤 ~ end 앞: 예시 문단이 있으면 그 자리에, 없으면 제목 바로 뒤 첫 빈 줄 자리에 넣는다"""
        if text is None:
            return
        P, f = self.f.P, self.f
        idx = [i for i in range(head + 1, end) if P[i].find(".//hp:tbl", NS) is None
               and f.text(P[i]).strip() in self.samples]
        if idx:
            self.insert_before(P[idx[-1] + 1], text)
            f.remove(*idx)
        elif head + 1 < len(P) and self.blank(head + 1):
            self.insert_before(P[head + 1], text)
            f.remove(head + 1)
        elif head + 1 < len(P):
            self.insert_before(P[head + 1], text)
        else:
            for p in self.items(text):
                P[head].getparent().append(p)

    # ── 단계 ──
    def run(self):
        f, P, s = self.f, self.f.P, self.s
        N = len(P)
        pos = {"toc": self.idx("toc"), "work": self.idx("work")}
        toc_after = (pos["toc"] if pos["toc"] is not None else -1) + 1
        pos["overview"] = (self.idx("overview", toc_after, pos["work"], last=True)
                           if pos["work"] is not None else self.idx("overview", toc_after))
        after = lambda k: (pos.get(k) or 0)  # noqa: E731
        pos["review"] = self.idx("review", after("work"))
        pos["results"] = self.idx("results", max(after("review"), after("work")))
        for k in ("progress", "targets", "outputs", "unplanned", "budget"):
            pos[k] = self.idx(k, after("results"))
        pos["next_year"] = self.idx("next_year", max(after("budget"), after("results")))
        pos["references"] = self.idx("references", after("next_year"))
        found = sorted(v for k, v in pos.items() if v is not None and k in MAIN)

        def end_of(i):
            return next((j for j in found if j > i), N)

        sample_body = next((i for i in range(N) if f.text(P[i]).strip() in self.samples
                            and f.text(P[i]).strip().startswith("ｏ")), None)
        if sample_body is not None and pos["progress"] is not None:
            f.detect_charpr(sample_body, pos["progress"])
        else:
            f.detect_charpr_auto()

        self.cover()
        self.toc(pos)

        # 1. 개요 · 2. 수행 내용
        for key, what in (("overview", "1. 연구개발과제의 개요"), ("work", "2. 수행과정 및 수행 내용")):
            if pos[key] is None:
                self.need(key, what)
            else:
                end = pos["review"] if key == "work" and pos["review"] is not None else end_of(pos[key])
                self.fill_region(pos[key], end, s.get(key))

        # 진도점검 지적사항 표
        if pos["review"] is not None:
            i_rev = pos["review"]
            P[i_rev].set("paraPrIDRef", f.pp["L1K"])
            if self.prof.get("review_title"):
                set_p_text(P[i_rev], self.prof["review_title"])
            try:
                i_revt, t_rev = f.table_after(i_rev)
                if s.get("review"):
                    fill_rows(t_rev, s["review"], header_rows=self.prof["header_rows"].get("review", 1), prefix="‧ ")
                if pos["results"] is not None:
                    f.remove(*[i for i in range(i_revt + 1, pos["results"]) if self.blank(i)])
            except KeyError:
                self.need("review", "진도점검 지적사항 표")
        else:
            self.need("review", "진도점검 지적사항")
        if pos["results"] is not None:
            P[pos["results"]].set("pageBreak", "1")
            stop = pos["references"] if pos["references"] is not None else N
            for i in range(pos["results"] + 1, stop):     # 3·4장 제목은 다음 문단과 함께
                t = f.text(P[i]).strip()
                if P[i].find(".//hp:tbl", NS) is None and P[i].get("pageBreak") != "1" \
                        and re.match(r"^(\d\)|\[[^\]]+\]|□)", t):
                    f.keep_with_next(P[i])

        # 3-1) 진척도 · 3-2) 성과목표 달성도
        if s.get("progress"):
            if pos["progress"] is None:
                self.need("progress", "1) 당해연도 사업추진 진척도")
            else:
                _, t = f.table_after(pos["progress"])
                rebuild_groups(t, self.prof["header_rows"].get("progress", 1), s["progress"])
        tg = s.get("targets") or {}
        if pos["targets"] is None:
            self.need("targets", "2) 기술적 성과목표 달성도")
            self.need("target_notes", "성과목표 달성도 설명")
        else:
            i_t, t = f.table_after(pos["targets"])
            for k, v in (tg.get("header") or {}).items():
                set_cell(t, *rc(k), v)
            if tg.get("groups"):
                rebuild_groups(t, self.prof["header_rows"].get("targets", 2), tg["groups"])
            if s.get("target_notes") is not None:
                self.fill_region(i_t, end_of(pos["targets"]), s["target_notes"])

        # 3-3) 세부 정량성과
        if s.get("outputs") is not None:
            if pos["outputs"] is None:
                self.need("outputs", "3) 세부 정량적 연구개발성과")
            else:
                self.outputs(pos["outputs"], end_of(pos["outputs"]), s["outputs"])

        # 3-4) 계획하지 않은 성과
        if s.get("unplanned") is not None:
            if pos["unplanned"] is None:
                self.need("unplanned", "4) 계획하지 않은 성과")
            else:
                text = s["unplanned"] if str(s["unplanned"]).strip() else "o 해당없음"
                i_note = self.idx("unplanned_note", pos["unplanned"], end_of(pos["unplanned"]))
                if i_note is not None:
                    self.insert_before(P[i_note + 1], text)
                    f.remove(i_note)
                else:
                    self.fill_region(pos["unplanned"], end_of(pos["unplanned"]), text)

        # 4. 다음 연도 계획
        ny = {str(k): v for k, v in (s.get("next_year") or {}).items()}
        if ny and pos["next_year"] is None:
            self.need("next_year", "4. 다음 연도 연구개발계획")
        elif ny:
            stop = pos["references"] if pos["references"] is not None else N
            heads = [i for i in range(pos["next_year"] + 1, stop)
                     if re.match(r"^(\d)\)\s*(.+)", f.text(P[i]).strip()) and P[i].find(".//hp:tbl", NS) is None]
            for i, j in zip(heads, heads[1:] + [stop]):
                m = re.match(r"^(\d)\)\s*(.+)", f.text(P[i]).strip())
                key = m.group(1) if m.group(1) in ny else next(
                    (k for k in ny if norm(k) and norm(m.group(2)).startswith(norm(k))), None)
                if key is not None and ny[key] is not None:
                    self.fill_region(i, j, ny[key])

        self.generic(found)
        return f

    def cover(self):
        f, P, s = self.f, self.f.P, self.s
        cv = s.get("cover", {}) or {}
        i_ko, i_en = self.idx("title_ko"), self.idx("title_en")
        if cv.get("title_ko") and i_ko is not None:
            set_p_text(P[i_ko], cv["title_ko"])
        if cv.get("title_en") and i_en is not None:
            set_p_text(P[i_en], cv["title_en"])
        if self.A.get("cover_date"):
            i_org = self.idx("org", i_en or 0)
            for i in range((i_en or 0) + 1, i_org if i_org is not None else min(len(P), 30)):
                if re.match(self.A["cover_date"], f.text(P[i]).strip()):
                    set_p_text(P[i], cv.get("date", " ") or " ")
        i_sub = self.idx("submit_sentence")
        if cv.get("title_ko") and i_sub is not None:
            p = P[i_sub]
            runs = p.findall("hp:run", NS)
            cp = runs[0].get("charPrIDRef")
            # 양식 문장 안에 누름틀 안내문(「과제명을 작성해 주세요」)이 섞여 있어 따옴표 안을 통째로 바꾼다
            text = re.sub(r"“.*?”", f"“{cv['title_ko']}에 관한 연구”", f.text(p), count=1)
            for r in runs:
                p.remove(r)
            for ls in p.findall(".//hp:linesegarray", NS):
                p.remove(ls)
            r = p.makeelement(q("hp:run"), {"charPrIDRef": cp})
            p.append(r)
            r.append(r.makeelement(q("hp:t"), {}))
            r[0].text = text
        sd = cv.get("submit_date", "년      월      일")
        i_sdate = self.idx("date", i_sub or 0)
        if i_sdate is None:
            if s.get("participants") or s.get("summary"):
                self.warn.append("제출문 날짜를 못 찾아 participants·summary 표를 채우지 못함")
            return
        set_p_text(P[i_sdate], sd)
        try:
            i_part, t_part = f.table_after(i_sdate)
            _, t_sum = f.table_after(i_part)
        except KeyError:
            self.warn.append("제출문 뒤 참여연구원·요약표를 찾지 못함")
            return
        date_rx = re.compile(self.A["date"])
        ph = self.prof.get("sign_placeholder")
        for t in t_sum.iter(q("hp:t")):
            if t.text and date_rx.search(t.text):
                t.text = date_rx.sub(sd, t.text)
            if t.text and ph and ph in t.text and s.get("summary_sign"):
                t.text = t.text.replace(ph, s["summary_sign"])
        for k, v in (s.get("participants") or {}).items():
            set_cell(t_part, *rc(k), v)
        for k, v in (s.get("summary") or {}).items():
            set_cell(t_sum, *rc(k), v)
        for ls in t_sum.findall(".//hp:linesegarray", NS):
            ls.getparent().remove(ls)
        if s.get("summary_fit_rows"):
            fit_rows(t_sum, only=set(s["summary_fit_rows"]))

    def toc(self, pos):
        f, P, s = self.f, self.f.P, self.s
        i_toc = pos["toc"]
        if i_toc is None:
            return
        toc = s.get("toc", {}) or {}
        stop = pos["overview"] if pos["overview"] is not None else min(len(P), i_toc + 20)
        i_box = next((i for i in range(i_toc + 1, stop) if P[i].find(".//hp:tbl", NS) is not None), None)
        toc_end = i_box if i_box is not None else stop
        if not toc.get("attachments", False):
            i_att = self.idx("toc_attachments", i_toc, toc_end)
            if i_att is not None:
                f.remove(*range(i_att, toc_end))
        if not toc.get("page_numbers", False):
            for i in range(i_toc + 1, toc_end):
                for tab in P[i].findall(".//hp:tab", NS):
                    tab.getparent().remove(tab)          # 탭 뒤 쪽번호(tail)도 함께 지워진다
        if i_box is not None and not s.get("guide_box", False) and pos["overview"] is not None:
            f.remove(i_box)
            P[pos["overview"]].set("pageBreak", "1")

    def outputs(self, i_33, i_34, spec_out):
        f, P = self.f, self.f.P
        keep = {norm(k): v for k, v in spec_out.items()}
        units, cur, tail = [], None, []
        i_note = None
        note_rx = self.A.get("outputs_note")
        i = i_33 + 1
        while i < i_34:
            t = f.text(P[i]).strip()
            tbl = P[i].find(".//hp:tbl", NS) is not None
            if not tbl and note_rx and re.match(note_rx, t):
                i_note = i
            elif not tbl and t.startswith("[기타 성과"):
                cur = {"kind": "etc", "title": "기타성과", "idx": [i, i + 1]}
                units.append(cur)
                tail = list(range(i + 2, i_34))
                break
            elif not tbl and re.match(r"^\[.+\]$", t):
                cur = {"kind": "cat", "title": t, "idx": [i], "kids": []}
                units.append(cur)
            elif not tbl and t.startswith("□"):
                cur = {"kind": "blk", "title": norm(t[1:]), "idx": [i]}
                cat = next((u for u in reversed(units) if u["kind"] == "cat"), None)
                if cat:
                    cat["kids"].append(cur)
                units.append(cur)
            elif cur is not None:
                cur["idx"].append(i)
            i += 1
        if i_note is not None and not self.s.get("outputs_note", False):
            f.remove(*([i_note] + ([i_note + 1] if self.blank(i_note + 1) else [])))

        def match(title):
            return next((k for k in keep if k and (title.startswith(k) or k.startswith(title))), None)

        for k in keep:
            if not any(u["kind"] in ("blk", "etc") and match(u["title"]) == k for u in units):
                self.warn.append(f"정량성과 항목 「{k}」을 양식에서 찾지 못함")
        for u in units:
            if u["kind"] == "blk":
                k = match(u["title"])
                if k is None:
                    f.remove(*u["idx"])
                    continue
                tbl = next((P[j].find(".//hp:tbl", NS) for j in u["idx"]
                            if P[j].find(".//hp:tbl", NS) is not None), None)
                if tbl is not None and keep[k]:
                    fill_rows(tbl, keep[k], header_rows=1)
            elif u["kind"] == "etc":
                k = match("기타성과")
                if k is None:
                    f.remove(*u["idx"])
                else:
                    set_cell(P[u["idx"][1]].find(".//hp:tbl", NS), 0, 0, keep[k])
        for u in units:
            if u["kind"] == "cat" and not any(match(k["title"]) for k in u["kids"]):
                f.remove(*u["idx"])
        if tail and not self.s.get("reference_notes", True):
            f.remove(*tail[:-1])

    def generic(self, found):
        """다른 양식용: sections: {제목 정규식: 개조식 | {mode: insert, text: 개조식}},
        tables: [{after: 제목 정규식, rows|cells}]
        기본(replace)은 제목 아래 ~ 다음 제목·표 앞까지의 글을 spec 내용으로 바꾼다(끝 빈 줄은 남김)."""
        f, P, s = self.f, self.f.P, self.s
        secs = s.get("sections") or {}
        hits = {}
        for rx in secs:
            try:
                hits[rx] = f.find_last(rx, 0, len(P))
            except KeyError:
                self.warn.append(f"sections: 제목 「{rx}」을 양식에서 찾지 못함")
        heads = sorted(set(found) | set(hits.values()) | set(section_heads(f, self.prof)))
        for rx, i in hits.items():
            v = secs[rx]
            mode, text = (v.get("mode", "replace"), v.get("text")) if isinstance(v, dict) else ("replace", v)
            stop = region_stop(f, i, heads)
            if mode == "insert":
                self.fill_region(i, stop, text)
                continue
            k = stop
            while k - 1 > i and self.blank(k - 1):
                k -= 1
            anchor = P[k] if k < len(P) else None
            if anchor is None:
                for p in self.items(text):
                    P[i].getparent().append(p)
            else:
                self.insert_before(anchor, text)
            f.remove(*range(i + 1, k))
        for t in s.get("tables") or []:
            try:
                i = f.find_last(t["after"], 0, len(P))
                _, tbl = f.table_after(i, limit=t.get("within", 6))
            except KeyError:
                self.warn.append(f"tables: 「{t.get('after')}」 뒤 표를 찾지 못함")
                continue
            if t.get("rows"):
                fill_rows(tbl, t["rows"], header_rows=t.get("header_rows", 1), prefix=t.get("prefix", ""))
            for k, v in (t.get("cells") or {}).items():
                set_cell(tbl, *rc(k), v)


def section_heads(f, prof):
    """프로필의 suggested_sections(양식 분석 때 찾은 제목들) 위치 — 다른 양식에서 절 경계로 쓴다"""
    want = {re.sub(r"\s+", "", t) for t in prof.get("suggested_sections") or []}
    return [i for i, p in enumerate(f.P) if p.find(".//hp:tbl", NS) is None
            and re.sub(r"\s+", "", f.text(p)) in want]


def region_stop(f, i, heads):
    """제목 i의 본문 끝: 다음 제목이나 표 중 먼저 오는 곳"""
    nxt = next((j for j in heads if j > i), len(f.P))
    tbl = next((j for j in range(i + 1, nxt) if f.P[j].find(".//hp:tbl", NS) is not None), nxt)
    return min(nxt, tbl)


def build(spec_path, out=None, form=None, figs=None):
    spec_path = Path(spec_path).resolve()
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    b = Builder(spec, spec_path.parent, form, figs)
    f = b.run()
    out = Path(out) if out else spec_path.with_suffix(".hwpx")
    f.save(out)
    return out, b.warn


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--form", help="양식 이름·폴더·hwpx (기본: spec의 form → 설정의 form → 2026 연차점검 양식)")
    ap.add_argument("--figs", help="그림 폴더 (기본: spec의 figures)")
    a = ap.parse_args()
    out, warn = build(a.spec, a.out, a.form, a.figs)
    from check_report import structure_errors
    errs = structure_errors(out)
    print("built:", out)
    for w in warn:
        print("WARN", w)
    if errs:
        print("구조 오류:", *errs, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
