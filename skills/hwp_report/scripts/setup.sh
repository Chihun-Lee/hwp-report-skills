#!/usr/bin/env bash
# 1회 설치: ~/.hwp_report/venv 에 파이썬 패키지를 깐다(전역 환경·스킬 폴더는 건드리지 않음).
#   bash scripts/setup.sh            # 보고서 빌드·검사·역추출 (lxml, pyyaml, pillow, numpy)
#   bash scripts/setup.sh --figures  # + 그림 만들기용 matplotlib
# Anaconda 기본 채널은 쓰지 않는다(상용 라이선스). venv + PyPI만 쓴다.
set -e
HRH="${HWP_REPORT_HOME:-$HOME/.hwp_report}"
BASE="${PYTHON:-python3}"
"$BASE" -c "import sys; assert sys.version_info >= (3, 9)" || { echo "Python 3.9 이상 필요"; exit 2; }
mkdir -p "$HRH"
[ -x "$HRH/venv/bin/python" ] || "$BASE" -m venv "$HRH/venv"
"$HRH/venv/bin/python" -m pip install -q --upgrade pip
PKGS="lxml pyyaml pillow numpy"
[ "$1" = "--figures" ] && PKGS="$PKGS matplotlib"
"$HRH/venv/bin/python" -m pip install -q $PKGS
echo "✓ 파이썬 패키지: $PKGS → $HRH/venv"
command -v node >/dev/null && echo "✓ node $(node --version) — 헤드리스 렌더 가능" \
  || echo "· node 없음 — 렌더(render) 쓰려면 Node 18+ 설치 (brew install node)"
command -v rsvg-convert >/dev/null && echo "✓ rsvg-convert — PNG 변환 가능" \
  || echo "· rsvg-convert 없음 — PNG 미리보기 쓰려면 brew install librsvg"
command -v pdftoppm >/dev/null && echo "✓ pdftoppm — 쪽 빈칸 측정·PDF 글 뽑기 가능" \
  || echo "· pdftoppm 없음 — page_fill·PDF 문체 샘플 쓰려면 brew install poppler"
[ -d "/Applications/Hancom Office HWP.app" ] && echo "✓ 한컴오피스 — PDF 최종 확인 가능" \
  || echo "· 한컴오피스(macOS) 없음 — 최종 쪽 배치는 한글에서 직접 열어 확인"
