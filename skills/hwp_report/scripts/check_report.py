# -*- coding: utf-8 -*-
"""보고서 hwpx 게이트: 구조 검사 + 본문 작성 규칙 검사(lint).

    python check_report.py report.hwpx [--spec report.yaml]

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
STYLE_LINT = [  # (등급, 정규식, 설명)
    ("ERROR", r"\((그림|Fig\.?|표)\s*\d", "본문에서 그림·표를 괄호로 언급하지 않음"),
    ("ERROR", r"협력팀", "「협력팀」 표기 금지"),
    ("WARN", r"무인", "「무인」 대신 「자동화」"),
    ("WARN", r"(?<![\d.])\d{1,2}/\d{1,2}(?![\d/])", "꼭 필요한 수치가 아니면 날짜를 쓰지 않음"),
    ("WARN", r"\d{4}\.\s?\d{1,2}\.\s?\d{1,2}\.?", "날짜 생략 권장"),
    ("WARN", r"\d{1,2}월\s?\d{1,2}일", "날짜 생략 권장(「연내」 등으로)"),
    ("WARN", r"\([^()]*[·,][^()]*[·,][^()]*\)", "괄호 안 나열 금지 — 괄호는 최소한"),
    ("WARN", r"(했다|하였다|합니다|됩니다|입니다|이다)\.?$", "개조식 명사형 종결(~함·~임·~구축)"),
    ("WARN", r"[가-힣]\.$", "개조식은 마침표 없음"),
]
# 문체와 관계없이 항상
FORM_LINT = [
    ("WARN", r"세부설명|ㅇ  ㅇ  ㅇ|\(과제명\)|※\s*해당하는 경우|작성분으로 수합", "양식 예시·자리표시가 남음"),
]


def active_lint():
    from settings import style_info, style_lint
    st, _ = style_info()
    rules = list(FORM_LINT)
    if st == "personal":
        sl = style_lint()
        rules += [("ERROR", rx, "내 문체: 금지") for rx in sl.get("forbid", []) or []]
        rules += [("WARN", rx, "내 문체: 피함") for rx in sl.get("warn", []) or []]
    else:
        rules += STYLE_LINT
    return rules


def form_texts(form):
    """양식에 원래 있던 글자(각주·참고표·주의문 등)는 검사하지 않는다"""
    if not form or not Path(form).exists():
        return set()
    root = etree.fromstring(zipfile.ZipFile(form).read("Contents/section0.xml"))
    return {ptext(p).strip() for p in root.iter("{%s}p" % HP)}


def lint(path, spec=None, form=None, anchors=None):
    skip = form_texts(form)
    A = anchors or {}
    rules = active_lint()
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
    cap_rx = re.compile("^" + re.escape(cap_fmt).replace(r"\{\}", ".+") + "$")
    for i, p in enumerate(P):
        if i < i_body:
            continue
        has_tbl = p.find(".//hp:tbl", NS) is not None
        lines = [] if has_tbl else [texts[i]]
        for tc in p.iter("{%s}tc" % HP):
            lines += [ptext(x).strip() for x in tc.find("hp:subList", NS).findall("hp:p", NS)]
        for t in lines:
            if not t or t in skip:
                continue
            for lvl, rx, msg in rules:
                if re.search(rx, t):
                    out.append((lvl, i, msg, t))
            for w in forbid:
                if w and w in t:
                    out.append(("ERROR", i, f"금지어 「{w}」(업체명 등)", t))
            if year and i_h2 is not None and i_h3 is not None and i_h2 < i < i_h3:
                for m in re.finditer(r"(\d)차년도", t):
                    if int(m.group(1)) > int(year):
                        out.append(("WARN", i, "당해 성과 절에 다음 연차 내용", t))
        if p.find(".//hp:pic", NS) is not None and i + 1 < len(P):
            cap = texts[i + 1]
            if not cap_rx.match(cap) and cap not in skip:
                out.append(("ERROR", i + 1, f"그림 캡션 형식이 {cap_fmt} 아님", cap))
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
        print(f"{lvl} [{i:03d}] {msg}\n      {t[:110]}")
    print(f"\n구조 {'OK' if not errs else 'FAIL'} · ERROR {n_err} · WARN {n_warn}")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
