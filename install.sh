#!/usr/bin/env bash
# hwp-report-skills 설치 — 이 레포의 스킬을 Claude Code 스킬 폴더에 연결하고 의존성 설치·자가검사까지.
#   bash install.sh                 # ~/.claude/skills/ 에 심링크 (git pull 하면 바로 최신)
#   bash install.sh --copy          # 심링크 대신 복사
#   bash install.sh --dest <폴더>   # 다른 스킬 폴더(프로젝트 .claude/skills 등)
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills"; COPY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --copy) COPY=1; shift ;;
    *) echo "모르는 옵션: $1"; exit 2 ;;
  esac
done
mkdir -p "$DEST"
for d in "$REPO"/skills/*/; do
  name="$(basename "$d")"; src="${d%/}"; t="$DEST/$name"
  if [ -L "$t" ] && [ "$(readlink "$t")" = "$src" ]; then echo "  = $name (이미 연결됨)"; continue; fi
  if [ -e "$t" ] || [ -L "$t" ]; then bk="$t.bak.$(date +%Y%m%d%H%M%S)"; mv "$t" "$bk"; echo "  기존 $name 백업 → $bk"; fi
  if [ $COPY = 1 ]; then cp -R "$src" "$t"; echo "  + $name (복사)"; else ln -s "$src" "$t"; echo "  + $name → $src"; fi
done
bash "$REPO/skills/hwp_report/scripts/setup.sh"
bash "$REPO/skills/hwp_report/scripts/hwp_report.sh" selftest
echo
echo "✓ 설치 완료. Claude Code를 새로 열고 「연차보고서 만들어줘」 또는 /hwp_report"
echo "  처음 쓸 때 Claude가 문체(기본/내 문체)와 양식(기본/다른 양식)을 물어본다. 설정: ~/.hwp_report/"
echo "  업데이트: cd $REPO && git pull"
