# -*- coding: utf-8 -*-
"""쪽마다 본문 아래에 남은 빈칸(mm)을 잰다 — 큰 그림이 다음 쪽으로 밀려 빈칸이 생긴 곳 찾기.

    python page_fill.py report.pdf --hwpx report.hwpx          # 한컴 PDF (권장, 쪽 나눔이 정확)
    python page_fill.py report_render/ --hwpx report.hwpx      # render.sh 결과 PNG 폴더

배율은 쪽 안 글자 폭(본문 폭이 가장 넓은 줄)으로 자동 보정한다(한컴 PDF는 약 0.77배로 축소 저장됨).
빈칸이 --min(기본 45 mm)보다 크면 표시한다. 장 끝·쪽 나눔 직전 쪽은 정상일 수 있으니 PNG를 직접 본다.
"""
import argparse
import glob
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
U = 283.465  # HWPUNIT/mm


def page_geom(hwpx):
    root = etree.fromstring(zipfile.ZipFile(hwpx).read("Contents/section0.xml"))
    pp = root.find(".//{%s}pagePr" % HP)
    mg = pp.find("{%s}margin" % HP)
    g = {k: int(mg.get(k)) / U for k in ("left", "right", "top", "bottom", "header", "footer")}
    g["w"], g["h"] = int(pp.get("width")) / U, int(pp.get("height")) / U
    return g


def load_pages(src, dpi):
    src = Path(src)
    if src.is_dir():
        return [np.asarray(Image.open(f).convert("L")) for f in sorted(glob.glob(str(src / "p*.png")))]
    tmp = Path(tempfile.mkdtemp())
    try:
        if shutil.which("pdftoppm"):
            subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", str(src), str(tmp / "p")], check=True)
            return [np.asarray(Image.open(f).convert("L")) for f in sorted(tmp.glob("p*.png"))]
        import fitz  # PyMuPDF
        doc = fitz.open(src)
        out = []
        for pg in doc:
            pix = pg.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
            out.append(np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="PDF 또는 render.sh PNG 폴더")
    ap.add_argument("--hwpx", required=True, help="쪽 여백을 읽을 hwpx")
    ap.add_argument("--min", type=float, default=45, help="표시할 빈칸 기준 mm")
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()
    g = page_geom(a.hwpx)
    pages = load_pages(a.src, a.dpi)
    if not pages:
        sys.exit("쪽 이미지가 없음")
    masks = [p < 200 for p in pages]
    H, W = pages[0].shape
    px_mm = W / g["w"]                                 # 쪽 이미지 px / 실제 쪽 mm
    cols = [np.where(m.any(axis=0))[0] for m in masks if m.any()]
    xmin = np.percentile([c[0] for c in cols], 10)
    xmax = np.percentile([c[-1] for c in cols], 90)
    body_w = g["w"] - g["left"] - g["right"]
    s = (xmax - xmin) / (body_w * px_mm)               # 본문 축소 배율(한컴 PDF ≈ 0.77, 렌더 ≈ 1)
    x0 = xmin - g["left"] * s * px_mm                  # 왼쪽 위 원점(축소 기준점)
    y0 = x0 * (H / W) * (g["w"] / g["h"]) if s < 0.98 else 0.0
    body_bot = y0 + (g["h"] - g["bottom"] - g["footer"]) * s * px_mm
    print(f"배율 {s:.3f} · 본문 아래 끝 {body_bot:.0f}px · 쪽 {len(pages)}")
    flagged = []
    for i, m in enumerate(masks, 1):
        rows = np.where(m[: int(body_bot) + 2].any(axis=1))[0]
        last = rows[-1] if len(rows) else 0
        blank = (body_bot - last) / (s * px_mm)
        mark = "  ◀ 빈칸 큼" if blank > a.min else ""
        if mark:
            flagged.append(i)
        print(f"  {i:2d}쪽  아래 빈칸 {max(0, blank):5.0f} mm{mark}")
    if flagged:
        print("확인할 쪽:", ", ".join(map(str, flagged)),
              "— 다음 쪽 첫머리가 큰 그림이면 그림 폭(폭=)·분할·문단 순서를 조정")


if __name__ == "__main__":
    main()
