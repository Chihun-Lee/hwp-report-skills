# -*- coding: utf-8 -*-
"""보고서 hwpx 게이트: 구조 검사 + 본문 작성 규칙 검사(lint).

    python check_report.py report.hwpx [--spec report.yaml]
    python check_report.py 통합본.hwpx --form 주관기관양식.hwpx     # 구역 전부, 주관기관 원문은 빼고 우리 글만

오류(ERROR)가 하나라도 있으면 종료 코드 1. 규칙 근거는 references/writing_rules.md.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS = {"hp": HP, "hh": HH, "opf": "http://www.idpf.org/2007/opf/"}
REQUIRED = ["mimetype", "Contents/content.hpf", "Contents/header.xml", "Contents/section0.xml"]


def structure_errors(path):
    errs = []
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return ["ZIP이 아님"]
    names = z.namelist()
    for r in REQUIRED:
        if r not in names:
            errs.append(f"필수 파일 없음: {r}")
    if errs:
        return errs
    first = z.infolist()[0]
    if first.filename != "mimetype" or first.compress_type != zipfile.ZIP_STORED:
        errs.append("mimetype이 첫 항목·무압축이 아님")
    if z.read("mimetype").decode().strip() != "application/hwp+zip":
        errs.append("mimetype 내용 오류")
    xml = {}
    for n in names:
        if n.endswith((".xml", ".hpf")):
            try:
                xml[n] = etree.fromstring(z.read(n))
            except etree.XMLSyntaxError as e:
                errs.append(f"XML 오류 {n}: {e}")
    if errs:
        return errs
    hdr = xml["Contents/header.xml"]
    for cont, child in (("paraProperties", "paraPr"), ("charProperties", "charPr"), ("borderFills", "borderFill")):
        c = hdr.find(f".//hh:{cont}", NS)
        if c is not None and int(c.get("itemCnt", -1)) != len(c.findall(f"hh:{child}", NS)):
            errs.append(f"header {cont} itemCnt 불일치")
    pp = {p.get("id") for p in hdr.iter("{%s}paraPr" % HH)}
    cp = {p.get("id") for p in hdr.iter("{%s}charPr" % HH)}
    hpf = z.read("Contents/content.hpf").decode("utf-8")
    items = dict(re.findall(r'<opf:item id="([^"]+)" href="([^"]+)"', hpf))
    for n, root in xml.items():
        if not re.match(r"Contents/section\d+\.xml", n):
            continue
        bad_p = {p.get("paraPrIDRef") for p in root.iter("{%s}p" % HP)} - pp
        bad_c = {r.get("charPrIDRef") for r in root.iter("{%s}run" % HP)} - cp
        if bad_p:
            errs.append(f"{n}: 없는 paraPr 참조 {sorted(bad_p)[:5]}")
        if bad_c:
            errs.append(f"{n}: 없는 charPr 참조 {sorted(bad_c)[:5]}")
        for img in root.iter("{http://www.hancom.co.kr/hwpml/2011/core}img"):
            iid = img.get("binaryItemIDRef")
            if iid not in items:
                errs.append(f"그림 {iid}: content.hpf에 없음")
            elif items[iid] not in names:
                errs.append(f"그림 {iid}: {items[iid]} 파일 없음")
    return errs


def ptext(p):
    out = []
    for t in p.iter("{%s}t" % HP):
        out.append(t.text or "")
        for ch in t:
            out.append(ch.tail or "")
    return "".join(out)


# 기본 문체 규칙 — config style: default 일 때만 (내 문체면 style.md 맨 위 lint:를 쓴다)
# (등급, 정규식, 설명[, 범위])  범위 "body" = 본문 문단만(표 칸·주석 제외). 근거는 references/writing_rules.md
STYLE_LINT = [
    ("ERROR", r"\((그림|Fig\.?|표)\s*\d", "본문에서 그림·표를 괄호로 언급하지 않음 (A7)"),
    ("ERROR", r"협력팀", "「협력팀」 표기 금지 (A4)"),
    # 월/일: 분수(1/20 수준)·달성 비율(83/80)과 헷갈리지 않게, 요일·물결·「까지/부터」가 붙거나 연도가 앞설 때만
    ("WARN", r"(\d{4}[./]\s?)(1[0-2]|0?[1-9])/(3[01]|[12]\d|0?[1-9])(?![\d/])|(?<![\d./])(1[0-2]|0?[1-9])/(3[01]|[12]\d|0?[1-9])(?=\s*(\([월화수목금토일]\)|~|까지|부터))",
     "날짜를 쓰지 않음 — 교육 실적·행정 이정표·양식 칸만 예외 (A6)"),
    ("WARN", r"\d{4}\.\s?\d{1,2}\.\s?\d{1,2}\.?", "날짜 생략 권장 (A6)"),
    ("WARN", r"\d{1,2}월\s?\d{1,2}일", "날짜 생략 권장 — 교육 개최 실적이면 그대로 (A6)"),
    ("WARN", r"\([^()]*[·,][^()]*[·,][^()]*\)", "괄호 안 나열 금지 — 괄호는 최소한 (A5)"),
    ("WARN", r"^[-‧·❍ｏo□]?\s*\((?!세부기술|\d)[^()]{1,10}\)\s", "줄 머리 「(라벨)」 — 이웃 항목이 모두 쓰는 양식 관례가 아니면 뺌 (A5)", "body"),
    ("WARN", r"(했다|하였다|합니다|됩니다|입니다|이다)\.?$", "개조식 종결(~함·~임·명사형) (A2)"),
    ("WARN", r"[가-힣]\.$", "개조식은 문단 끝 마침표 없음 (A2)"),
    ("WARN", r"^(?![ｏo❍○□])[-‧·]?\s*[^:：\d*※]{2,25}[:：]\s", "「라벨: 내용」 대신 한 문장으로 (A8, ｏ·□ 제목 단계 제외)", "body"),
    ("WARN", r"→|⇒", "화살표 대신 문장으로 (A8)", "body"),
    ("WARN", r"위험이 없|제한\s?없이|완벽(하|히)|전혀 없", "서술 강도를 근거 수준으로 — 「~을 줄일 수 있음」 (A9)", "body"),
    ("WARN", r"하는 단계임$|단계에 있음$", "「~하는 단계임」 대신 완료형 「~함」 (A9)", "body"),
    ("WARN", r"」에\s*(기술|서술|정리|기재)(함|하였음|됨|하였다)", "다른 절로 미루는 상호참조 — 내용을 이 절에 씀 (national_report_guide 2절)", "body"),
    ("WARN", r"결정계수\s*(는|가)?\s*0\.[0-4]|오분류|외삽|신뢰할 수 없|한계 및 향후", "약한 지표·한계는 성과 절에서 뺌 (B5)", "body"),
    ("WARN", r"\d[\d,.]*\s*~\s*\d[\d,.]*\s*(초|분|시간)", "시간 범위는 상한·비율로 — 「10분 이내」, 「1/20 수준」 (B4)", "body"),
]
# 문체와 관계없이 항상 (양식 잔여물·제출 전 잔여물, writing_rules G)
FORM_LINT = [
    ("WARN", r"세부설명|ㅇ  ㅇ  ㅇ|\(과제명\)|※\s*해당하는 경우|작성분으로 수합", "양식 예시·자리표시가 남음"),
    ("ERROR", r"(?i)(?<![a-z])tbd(?![a-z])", "tbd 자리표시가 남음 (G)"),
    ("WARN", r"반영 예정|취합 후 반영|확정 자료를 반영", "자리 문장이 남음 — 제출 전 채움 (G)"),
    ("WARN", r"○○", "자리표시 ○○ — 칸 단위로 채우고, 남기면 넘길 때 알림 (F4)"),
    ("WARN", r"[ㄱ-ㅎㅏ-ㅣ]", "낱자모(오타) (G)"),
    ("WARN", r"\S[ \t]+,", "쉼표 앞 공백 (G)"),
    ("WARN", r"\d[ \t]+%", "숫자와 %는 붙여 씀 (C4)"),
]
ABBREV_GLOSS = r"\b[A-Z][A-Za-z0-9.\-]{1,10}\s?\((?=[^()]*[a-z가-힣])[^()]{3,50}\)"


def active_lint(spec=None):
    from settings import style_info, style_lint
    st, _ = style_info()
    rules = list(FORM_LINT)
    if st == "personal":
        sl = style_lint()
        rules += [("ERROR", rx, "내 문체: 금지") for rx in sl.get("forbid", []) or []]
        rules += [("WARN", rx, "내 문체: 피함") for rx in sl.get("warn", []) or []]
    else:
        rules += STYLE_LINT
        lo = (spec or {}).get("lint", {}) or {}
        if (lo.get("abbrev_gloss") or "never") == "never":
            rules.append(("WARN", ABBREV_GLOSS, "약어 풀이 괄호 — 이 문서는 풀이 없이 (C3, spec lint.abbrev_gloss)", "body"))
    for a, b in ((spec or {}).get("lint", {}) or {}).get("replace", {}).items():
        rules.append(("WARN", re.escape(a), f"과제 용어: 「{a}」 대신 「{b}」 (spec lint.replace)"))
    return rules


def form_texts(form):
    """양식에 원래 있던 글자(각주·참고표·주의문 등)는 검사하지 않는다"""
    if not form or not Path(form).exists():
        return set()
    z = zipfile.ZipFile(form)
    out = set()
    for n in z.namelist():
        if re.fullmatch(r"Contents/section\d+\.xml", n):
            root = etree.fromstring(z.read(n), etree.XMLParser(huge_tree=True))
            out |= {ptext(p).strip() for p in root.iter("{%s}p" % HP)}
    return out


def lint(path, spec=None, form=None, anchors=None):
    skip = form_texts(form)
    A = anchors or {}
    rules = active_lint(spec)
    z = zipfile.ZipFile(path)
    root = etree.fromstring(z.read("Contents/section0.xml"))
    P = root.findall("hp:p", NS)
    texts = [ptext(p).strip() for p in P]
    hit = lambda key: [i for i, t in enumerate(texts) if A.get(key) and re.search(A[key], t)]  # noqa: E731
    i_toc = (hit("toc") or [None])[0]
    i_h2 = (hit("work") or [None])[0]
    i_h3 = (hit("results") or [None])[0]
    ov = [i for i in hit("overview") if i_h2 is None or i < i_h2]
    i_body = ov[-1] if ov else ((i_toc + 1) if i_toc is not None else 0)
    out = []
    forbid = (spec or {}).get("lint", {}).get("forbid", [])
    year = (spec or {}).get("year")
    cap_fmt = (spec or {}).get("caption_format", "<{}>")
    cap_mode = (spec or {}).get("caption_mode", "below")      # below | above | none (writing_rules C1)
    cap_rx = re.compile("^" + re.escape(cap_fmt).replace(r"\{\}", ".+") + "$")

    def para_lines(p, t):
        """(글, 본문 여부) — 표가 든 문단은 칸 글만(본문 아님)"""
        ls = [] if p.find(".//hp:tbl", NS) is not None else [(t, True)]
        for tc in p.iter("{%s}tc" % HP):
            sub = tc.find("hp:subList", NS)
            ls += [(ptext(x).strip(), False) for x in sub.findall("hp:p", NS)] if sub is not None else []
        return ls

    def check(t, is_body, loc):
        for r in rules:
            lvl, rx, msg = r[:3]
            if len(r) > 3 and r[3] == "body" and not is_body:
                continue
            if re.search(rx, t):
                out.append((lvl, loc, msg, t))
        for w in forbid:
            if w and w in t:
                out.append(("ERROR", loc, f"금지어 「{w}」(업체명 등)", t))

    for i, p in enumerate(P):
        if i < i_body:
            continue
        for t, is_body in para_lines(p, texts[i]):
            if not t or t in skip:
                continue
            check(t, is_body and not t.startswith(("*", "※")), i)
            if year and i_h2 is not None and i_h3 is not None and i_h2 < i < i_h3:
                for m in re.finditer(r"(\d)차년도", t):
                    if int(m.group(1)) > int(year):
                        out.append(("WARN", i, "당해 성과 절에 다음 연차 내용", t))
        if cap_mode == "below" and p.find(".//hp:pic", NS) is not None and i + 1 < len(P):
            cap = texts[i + 1]
            if not cap_rx.match(cap) and cap not in skip:
                out.append(("ERROR", i + 1, f"그림 캡션 형식이 {cap_fmt} 아님", cap))
    # 구역이 여러 개인 문서(통합 양식 등): 구역1부터는 처음부터 끝까지 본다. 양식 원문(남의 글)은 skip으로 빠진다
    secs = sorted((n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n) and n != "Contents/section0.xml"),
                  key=lambda n: int(re.findall(r"\d+", n)[0]))
    for name in secs:
        k = re.findall(r"\d+", name)[0]
        Q = etree.fromstring(z.read(name), etree.XMLParser(huge_tree=True)).findall("hp:p", NS)
        qt = [ptext(q).strip() for q in Q]
        for i, q in enumerate(Q):
            for t, is_body in para_lines(q, qt[i]):
                if not t or t in skip:
                    continue
                check(t, is_body and not t.startswith(("*", "※")), f"{k}:{i:04d}")
            if cap_mode == "below" and q.find(".//hp:pic", NS) is not None and i + 1 < len(Q):
                cap = qt[i + 1]
                if cap and not cap_rx.match(cap) and cap not in skip and (spec or {}).get("caption_format"):
                    out.append(("WARN", f"{k}:{i + 1:04d}", f"그림 캡션 형식이 {cap_fmt} 아님", cap))
    if i_toc is not None:
        for i in range(i_toc + 1, min(i_toc + 20, len(P))):
            if P[i].find(".//hp:tab", NS) is not None and not (spec or {}).get("toc", {}).get("page_numbers"):
                out.append(("WARN", i, "목차에 쪽번호(탭)가 남음 — 수합 후 바뀌므로 비움", texts[i]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hwpx")
    ap.add_argument("--spec")
    ap.add_argument("--form", help="양식 이름·폴더·hwpx (기본: spec의 form → 설정) — 양식 원문은 검사 제외")
    ap.add_argument("--quiet", action="store_true", help="WARN은 개수만")
    a = ap.parse_args()
    spec = None
    if a.spec:
        import yaml
        spec = yaml.safe_load(Path(a.spec).read_text(encoding="utf-8"))
    errs = structure_errors(a.hwpx)
    for e in errs:
        print("ERROR 구조:", e)
    from settings import resolve_form
    form, prof, _ = resolve_form(a.form or (spec or {}).get("form"), Path(a.spec).resolve().parent if a.spec else None)
    res = lint(a.hwpx, spec, form, prof.get("anchors")) if not errs else []
    n_err = len(errs) + sum(1 for r in res if r[0] == "ERROR")
    n_warn = sum(1 for r in res if r[0] == "WARN")
    for lvl, i, msg, t in res:
        if lvl == "WARN" and a.quiet:
            continue
        print(f"{lvl} [{i:03d}] {msg}\n      {t[:110]}" if isinstance(i, int) else f"{lvl} [구역{i}] {msg}\n      {t[:110]}")
    print(f"\n구조 {'OK' if not errs else 'FAIL'} · ERROR {n_err} · WARN {n_warn}")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
