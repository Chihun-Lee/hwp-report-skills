#!/usr/bin/env bash
# hwpx → 쪽 PNG(+ 두 쪽 묶음) 헤드리스 렌더.  사용: bash render.sh report.hwpx [outdir]
# 필요: node(18+), rsvg-convert(brew install librsvg). PNG 묶음은 Python(Pillow).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$1"; OUT="${2:-${SRC%.*}_render}"
PY="${PYTHON:-python3}"
[ -f "$SRC" ] || { echo "파일 없음: $SRC"; exit 2; }
rm -rf "$OUT" && mkdir -p "$OUT"
node "$HERE/render.mjs" "$SRC" "$OUT"
command -v rsvg-convert >/dev/null || { echo "rsvg-convert 없음 → SVG만 생성 ($OUT)"; exit 0; }
for f in "$OUT"/p*.svg; do rsvg-convert -w 794 -b white "$f" -o "${f%.svg}.png" 2>/dev/null; done
"$PY" - "$OUT" <<'PY'
import glob, sys
from PIL import Image
d = sys.argv[1]
fs = sorted(glob.glob(f"{d}/p*.png"))
for k in range(0, len(fs), 2):
    ims = [Image.open(f) for f in fs[k:k + 2]]
    w = sum(i.size[0] for i in ims) + 10 * (len(ims) - 1); h = max(i.size[1] for i in ims)
    g = Image.new("RGB", (w, h), "gray"); x = 0
    for im in ims:
        g.paste(im, (x, 0)); x += im.size[0] + 10
    g.save(f"{d}/pair_{k + 1:02d}.png")
print("png", len(fs), "→", d)
PY
