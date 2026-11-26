# -*- coding: utf-8 -*-
"""꼬리 줄 점검 — 한컴 PDF에서 문단 마지막 줄에 몇 글자만 넘어간 곳(「…연동 / 함」)을 찾는다.

    python tail_check.py report.pdf --hwpx report.hwpx [--max 4] [--skip-form 양식.hwpx] [--min-len 15]

- 한컴은 한글을 **글자 단위로** 줄바꿈한다. 미리보기(rhwp)·LibreOffice의 줄바꿈은 다르므로 반드시 한컴 PDF로 본다.
- hwpx 본문 문단(글 15자 이상)을 PDF 줄과 맞춰, 몇 줄로 나뉘었는지와 마지막 줄 글자 수를 센다.
- `--skip-form`: 양식(또는 남이 쓴 원본)에 똑같이 있는 문단은 건너뛴다. 주관기관 통합 양식에 우리 파트만 넣었을 때
  주관기관 원본 양식을 주면 우리 문단만 검사한다.
- 쪽 번호(-12-, - 12 -)와 여러 쪽에 되풀이되는 머리말·꼬리말 줄은 본문 줄 사이에서 뺀다.
- 고치는 법: 같은 뜻으로 몇 글자 줄여 한 줄에 맞추거나, 이웃 문장과 합친다(writing_rules.md B12).
필요: poppler(pdftotext).
"""
import argparse
import collections
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwpx_text import body_texts  # noqa: E402


def norm(s):
    # 공백·가운뎃점·글머리 기호는 PDF에서 빠지거나 다른 글자로 나오므로 비교에서 뺀다
    return re.sub(r"[\s·ㆍ‧・∙❍○ｏ□■◦•●\-–—※]+", "", s)


def pdf_lines(pdf):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "b.html"
        subprocess.run(["pdftotext", "-bbox-layout", str(pdf), str(out)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = etree.parse(str(out), etree.HTMLParser(encoding="utf-8")).getroot()
    lines = []
    for pno, page in enumerate(root.iter("page"), 1):
        for ln in page.iter("line"):
            t = " ".join((w.text or "") for w in ln.iter("word"))
            if t.strip():
                lines.append((pno, float(ln.get("ymin")), t))
    return lines


def drop_margins(lines):
    npages = max((p for p, _, _ in lines), default=1)
    rep = collections.Counter(norm(t) for _, _, t in lines)
    out = []
    for p, y, t in lines:
        n = norm(t)
        if not n or re.fullmatch(r"-?\d{1,3}-?", n):
            continue
        if npages >= 5 and rep[n] >= max(3, npages * 0.3) and len(n) < 40:
            continue                      # 머리말·꼬리말
        out.append((p, y, n))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--hwpx", required=True)
    ap.add_argument("--max", type=int, default=4, help="이 글자 수 이하로 넘어간 마지막 줄을 꼬리 줄로 봄")
    ap.add_argument("--skip-form", help="이 hwpx에 똑같이 있는 문단은 검사하지 않음(양식·남의 원본)")
    ap.add_argument("--min-len", type=int, default=15)
    x = ap.parse_args()

    skip = {norm(t) for _, _, t in body_texts(x.skip_form)} if x.skip_form else set()
    paras = [(s, i, t) for s, i, t in body_texts(x.hwpx, x.min_len) if norm(t) not in skip]
    flat = drop_margins(pdf_lines(x.pdf))
    tails, lost, start = [], [], 0
    for s, i, t in paras:
        target = norm(t)
        if len(target) < 8:
            continue
        key = target[:14]
        found = None
        # 문서 순서대로 찾되, 못 찾으면 처음부터 다시 본다(그림 캡션·표 때문에 순서가 어긋날 수 있음)
        for rng in (range(start, len(flat)), range(0, start)):
            for k in rng:
                line = flat[k][2]
                if key not in line:
                    continue
                acc, n = line[line.find(key):], 1
                while len(acc) < len(target) and k + n < len(flat):
                    acc += flat[k + n][2]
                    n += 1
                if acc.startswith(target):
                    found = (k, n, acc)
                    break
            if found:
                break
        if not found:
            lost.append((s, i, t))
            continue
        k, n, acc = found
        start = k + n
        if n > 1:
            last = flat[k + n - 1][2]
            rest = len(target) - (len(acc) - len(last))
            if 0 < rest <= x.max:
                tails.append((flat[k][0], n, rest, s, i, t))
    for pno, n, rest, s, i, t in tails:
        print(f"꼬리 줄 | PDF {pno}쪽 | {n}줄, 마지막 줄 {rest}자 | 구역{s} 문단{i} | {t[:90]}")
    for s, i, t in lost[:30]:
        print(f"못 찾음 | 구역{s} 문단{i} | {t[:70]}")
    if len(lost) > 30:
        print(f"못 찾음 {len(lost) - 30}개 더 (표 안 글·특수 기호가 많은 문단일 수 있음)")
    print(f"\n검사 {len(paras)}문단 · 꼬리 줄 {len(tails)} · 못 찾음 {len(lost)}")
    sys.exit(1 if tails else 0)


if __name__ == "__main__":
    main()
