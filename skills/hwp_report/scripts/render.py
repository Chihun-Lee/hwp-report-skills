# -*- coding: utf-8 -*-
"""hwpx → 쪽 PNG(+ 두 쪽 묶음) 헤드리스 미리보기.  사용: python render.py report.hwpx [outdir]

- node(18+)로 rhwp(WASM)를 돌려 쪽마다 SVG를 만들고, PNG로 바꾼다(rsvg-convert가 있으면 그것, 없으면 PyMuPDF).
- 결과: <outdir>/p01.png … + pair_01.png(두 쪽 묶음). outdir 기본값은 <보고서>_render/
- 한계: 글자 폭이 근사라 줄바꿈·쪽 나눔은 한컴과 다를 수 있다. 쪽·꼬리 줄 판단은 한컴 PDF(hr.py pdf)로 한다.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def svg_to_png(svg, png, width=794):
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        r = subprocess.run([rsvg, "-w", str(width), "-b", "white", str(svg), "-o", str(png)], capture_output=True)
        if r.returncode == 0:
            return
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    with pymupdf.open(str(svg)) as doc:
        page = doc[0]
        z = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        pix.save(str(png))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    if not src.is_file():
        sys.exit(f"파일 없음: {src}")
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.with_name(src.stem + "_render")
    node = shutil.which("node")
    if not node:
        sys.exit("node 없음 → 미리보기를 건너뛴다(선택 기능). 쪽 확인은 한컴 PDF(hr.py pdf)로 한다.\n"
                 "  설치: https://nodejs.org (LTS)  ·  macOS: brew install node  ·  Windows: winget install OpenJS.NodeJS.LTS")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    subprocess.run([node, str(HERE / "render.mjs"), str(src), str(out)], check=True)
    svgs = sorted(out.glob("p*.svg"))
    for f in svgs:
        svg_to_png(f, f.with_suffix(".png"))
    pngs = sorted(out.glob("p*.png"))
    for k in range(0, len(pngs), 2):
        ims = [Image.open(f) for f in pngs[k:k + 2]]
        w = sum(i.size[0] for i in ims) + 10 * (len(ims) - 1)
        h = max(i.size[1] for i in ims)
        g = Image.new("RGB", (w, h), "gray")
        x = 0
        for im in ims:
            g.paste(im, (x, 0))
            x += im.size[0] + 10
        g.save(out / f"pair_{k + 1:02d}.png")
    print("png", len(pngs), "→", out)


if __name__ == "__main__":
    main()
