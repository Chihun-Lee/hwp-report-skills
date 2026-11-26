# -*- coding: utf-8 -*-
"""내 문체 만들기 1단계 — 내가 쓴 보고서들에서 글을 뽑고 문체 통계를 낸다.

    python style_samples.py 내보고서1.hwpx 내보고서2.pdf ... [-o ~/.hwp_report/style_samples]

지원: .hwpx  .docx  .pdf(pdftotext 또는 PyMuPDF)  .txt  .md   (.hwp는 한글에서 hwpx로 저장해서 준다)
결과: <out>/<파일>.txt (뽑은 글) + <out>/stats.md (끝맺음·글머리·문장 길이·괄호·자주 쓰는 표현).
Claude는 stats.md와 원문을 읽고 references/style_guide.md 틀대로 ~/.hwp_report/style.md를 쓴다.
"""
import argparse
import collections
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def hwpx_lines(p):
    z = zipfile.ZipFile(p)
    out = []
    for n in sorted(x for x in z.namelist() if re.match(r"Contents/section\d+\.xml", x)):
        root = etree.fromstring(z.read(n))
        for para in root.iter("{%s}p" % HP):
            if para.find(".//{%s}tbl" % HP) is not None:
                continue
            t = "".join((x.text or "") + "".join(c.tail or "" for c in x) for x in para.iter("{%s}t" % HP))
            out.append(t)
    return out


def docx_lines(p):
    root = etree.fromstring(zipfile.ZipFile(p).read("word/document.xml"))
    return ["".join(t.text or "" for t in para.iter("{%s}t" % W)) for para in root.iter("{%s}p" % W)]


def pdf_lines(p):
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    try:
        import pymupdf as fitz  # PyMuPDF
    except ImportError:
        import fitz
    return [ln for pg in fitz.open(p) for ln in pg.get_text().splitlines()]


def read(p):
    s = p.suffix.lower()
    if s == ".hwpx":
        return hwpx_lines(p)
    if s == ".docx":
        return docx_lines(p)
    if s == ".pdf":
        return pdf_lines(p)
    if s in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="ignore").splitlines()
    if s == ".hwp":
        raise SystemExit(f"{p.name}: .hwp는 한글에서 「다른 이름으로 저장 → hwpx」 후 다시 주세요")
    raise SystemExit(f"{p.name}: 지원하지 않는 형식")


BULLETS = [("ｏ/ㅇ/o", r"^[ｏㅇo]\s"), ("-", r"^[-–]\s"), ("‧/·", r"^[‧·∙]\s"), ("□", r"^□"), ("■", r"^■"),
           ("○", r"^○"), ("①", r"^[①-⑳]"), ("1.", r"^\d+\.\s"), ("1)", r"^\d+\)"), ("가.", r"^[가-하]\.\s"), ("※", r"^※")]
ENDINGS = [("명사형(~구축·~확보 등 명사로 끝)", r"(구축|확보|개발|수립|도출|완료|설계|분석|평가|검토|진행|예정|추진|적용|활용|제시|확인|강화|정립|마련)$"),
           ("~함", r"함$"), ("~임", r"임$"), ("~됨", r"됨$"), ("~음", r"음$"), ("~다.", r"다\.$"), ("~다", r"다$"),
           ("~습니다", r"습니다\.?$"), ("마침표로 끝", r"\.$")]


def stats(lines):
    body = [ln.strip() for ln in lines if len(ln.strip()) >= 8]
    n = max(len(body), 1)
    out = [f"- 분석한 줄: {len(body)}"]
    lens = sorted(len(x) for x in body)
    out.append(f"- 줄 길이(글자): 중앙값 {lens[len(lens) // 2] if lens else 0}, 상위 10% {lens[int(len(lens) * .9)] if lens else 0}")
    out.append("- 글머리 기호: " + ", ".join(f"{k} {sum(1 for x in body if re.match(rx, x)) * 100 // n}%"
                                         for k, rx in BULLETS if any(re.match(rx, x) for x in body)))
    out.append("- 끝맺음: " + ", ".join(f"{k} {sum(1 for x in body if re.search(rx, x)) * 100 // n}%"
                                      for k, rx in ENDINGS))
    out.append(f"- 괄호가 있는 줄: {sum(1 for x in body if '(' in x) * 100 // n}%  · 화살표(→) 쓴 줄: {sum(1 for x in body if '→' in x) * 100 // n}%"
               f"  · 영문 기술어가 있는 줄: {sum(1 for x in body if re.search('[A-Za-z]{3,}', x)) * 100 // n}%")
    words = collections.Counter(w for x in body for w in re.findall(r"[가-힣]{2,}(?:하여|하고|으로|에서|및|를 통해|에 따른|기반)", x))
    out.append("- 자주 쓰는 연결 표현: " + ", ".join(f"{w}({c})" for w, c in words.most_common(15)))
    tails = collections.Counter(re.sub(r"^.*?([가-힣]+)$", r"\1", x)[-4:] for x in body if re.search(r"[가-힣]$", x))
    out.append("- 자주 쓰는 줄 끝 4글자: " + ", ".join(f"{w}({c})" for w, c in tails.most_common(15)))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from settings import HOME
    out = Path(a.out).expanduser() if a.out else HOME / "style_samples"
    out.mkdir(parents=True, exist_ok=True)
    every = []
    report = ["# 내 문체 통계 (style_samples.py)", ""]
    for f in a.files:
        p = Path(f).expanduser()
        lines = read(p)
        (out / f"{p.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
        every += lines
        report += [f"## {p.name}", stats(lines), ""]
    report += ["## 전체", stats(every)]
    (out / "stats.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"\n원문·통계: {out}")


if __name__ == "__main__":
    main()
