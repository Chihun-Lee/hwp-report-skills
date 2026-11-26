#!/usr/bin/env bash
# hwp_report 명령 모음 — 어디서든:  bash <스킬>/scripts/hwp_report.sh <명령> [인자]
#   config   show | init --style S --form F | set style|form 값 | forms | add-form 양식.hwpx --name 이름
#   style    내보고서1.hwpx 내보고서2.pdf ...                         내 문체 만들기용 원문·통계 뽑기
#   analyze  양식.hwpx                                                양식 구조·제목 후보·표 보기
#   build    spec.yaml [-o out.hwpx] [--form 양식] [--figs 폴더]      spec → hwpx (+구조 검사)
#   check    report.hwpx [--spec spec.yaml]                           게이트(구조 + 작성 규칙)
#   extract  수정본.hwpx -o spec.yaml [--spec 이전spec] [--match-figs 폴더 ...]   hwpx → spec
#   diff     a.hwpx b.hwpx [--style]                                  문단 단위 비교(같으면 종료코드 0)
#   learn    이전판.hwpx 수정본.hwpx [-o 수정포인트.md]               작성자가 고친 곳·유형·반복 치환 표
#   dump     문서.hwpx -o 폴더 | --find 정규식                         모든 구역 문단·표 칸·모양 번호 덤프
#   render   report.hwpx [outdir]                                     헤드리스 쪽 PNG (node·rsvg-convert)
#   pdf      report.hwpx [대기초]                                     macOS 한컴 PDF(사본으로, 입력 중엔 기다림)
#   fill     report.pdf --hwpx report.hwpx                            쪽 아래 빈칸(mm)
#   tail     report.pdf --hwpx report.hwpx [--skip-form 양식.hwpx]    꼬리 줄(마지막 줄 몇 글자) 찾기
#   selftest                                                          예시로 빌드·게이트·왕복 검사
# 파이썬: $HWP_REPORT_PY → ~/.hwp_report/venv → python3 순서로 찾는다(setup.sh가 venv를 만든다).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
HRH="${HWP_REPORT_HOME:-$HOME/.hwp_report}"
PY="${HWP_REPORT_PY:-}"
[ -z "$PY" ] && [ -x "$HRH/venv/bin/python" ] && PY="$HRH/venv/bin/python"
[ -z "$PY" ] && PY="$(command -v python3)"
"$PY" -c "import lxml, yaml, PIL" 2>/dev/null || { echo "파이썬 패키지 없음 → bash $ROOT/scripts/setup.sh 를 먼저 실행 (현재: $PY)"; exit 2; }
cmd="$1"; shift || true
case "$cmd" in
  config)  exec "$PY" "$HERE/config.py" "$@" ;;
  style)   exec "$PY" "$HERE/style_samples.py" "$@" ;;
  analyze) exec "$PY" "$HERE/analyze_form.py" "$@" ;;
  build)   exec "$PY" "$HERE/build_report.py" "$@" ;;
  check)   exec "$PY" "$HERE/check_report.py" "$@" ;;
  extract) exec "$PY" "$HERE/extract_spec.py" "$@" ;;
  diff)    exec "$PY" "$HERE/diff_hwpx.py" "$@" ;;
  learn)   exec "$PY" "$HERE/learn_diff.py" "$@" ;;
  dump)    exec "$PY" "$HERE/dump_hwpx.py" "$@" ;;
  tail)    exec "$PY" "$HERE/tail_check.py" "$@" ;;
  render)  PYTHON="$PY" exec bash "$HERE/render.sh" "$@" ;;
  pdf)     exec zsh "$HERE/hancom_pdf.sh" "$@" ;;
  fill)    exec "$PY" "$HERE/page_fill.py" "$@" ;;
  selftest)
    T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
    export HWP_REPORT_HOME="$T/home"          # 내 설정과 무관하게 기본 양식·기본 문체로 검사
    cd "$ROOT/examples"
    "$PY" "$HERE/build_report.py" report.example.yaml -o "$T/ex.hwpx"
    "$PY" "$HERE/check_report.py" "$T/ex.hwpx" --spec report.example.yaml --quiet
    "$PY" "$HERE/extract_spec.py" "$T/ex.hwpx" -o "$T/rt.yaml" --spec report.example.yaml --figs-out "$T/figs" >/dev/null
    "$PY" "$HERE/build_report.py" "$T/rt.yaml" -o "$T/rt.hwpx" >/dev/null
    out="$("$PY" "$HERE/diff_hwpx.py" "$T/ex.hwpx" "$T/rt.hwpx")" || { echo "$out"; echo "selftest 실패: 왕복 차이"; exit 1; }
    echo "$out" | tail -1
    "$PY" "$HERE/learn_diff.py" "$T/ex.hwpx" "$T/rt.hwpx" -o "$T/learn.md" | tail -1
    "$PY" "$HERE/dump_hwpx.py" "$T/ex.hwpx" -o "$T/dump" | tail -1
    if command -v node >/dev/null; then node "$HERE/render.mjs" "$T/ex.hwpx" "$T/svg"; fi
    echo "selftest OK" ;;
  ""|-h|--help) sed -n '2,19p' "$0" ;;
  *) echo "모르는 명령: $cmd"; sed -n '2,19p' "$0"; exit 2 ;;
esac
