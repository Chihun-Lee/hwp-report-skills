#!/usr/bin/env bash
# hwp-report-skills 설치(macOS·Linux) — install.py 와 같다. 옵션: python3 install.py --help
cd "$(dirname "$0")" || exit 2
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; assert sys.version_info >= (3, 9)" >/dev/null 2>&1; then
    exec "$c" install.py "$@"
  fi
done
echo "Python 3.9 이상이 필요하다 (macOS: brew install python · https://www.python.org/downloads/)"; exit 2
