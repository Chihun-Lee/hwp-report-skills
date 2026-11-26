#!/usr/bin/env bash
# 예전 진입점(macOS·Linux·Windows Git Bash). 명령은 모두 hr.py가 처리한다 — 목록: bash hwp_report.sh --help
HERE="$(cd "$(dirname "$0")" && pwd)"
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; assert sys.version_info >= (3, 9)" >/dev/null 2>&1; then
    exec "$c" "$HERE/hr.py" "$@"
  fi
done
if command -v py >/dev/null 2>&1; then exec py -3 "$HERE/hr.py" "$@"; fi
echo "Python 3.9 이상이 필요하다 (https://www.python.org/downloads/)"; exit 2
