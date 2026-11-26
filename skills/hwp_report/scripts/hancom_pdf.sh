#!/bin/zsh
# macOS 한컴오피스 한글로 hwpx → PDF (쪽 나눔·꼬리 줄 최종 확인용).
#   zsh hancom_pdf.sh report.hwpx [최대 대기 초, 기본 $QA_WAIT 또는 900]   → report.pdf (같은 폴더)
#
# 안전 규칙 (2026-11 실제 사고에서 정함)
# - 원본을 직접 열지 않는다. 임시 폴더에 「HRQA_시각_이름.hwpx」 사본을 만들어 그 창만 열고 닫는다.
#   → 작성자가 같은 문서를 한컴에 열어 두고 고치는 중이어도 그 창은 건드리지 않는다. 한컴도 끄지 않는다.
# - 사용자가 키보드·마우스를 쓰는 중이면 포커스를 빌리지 않는다. 입력이 IDLE_NEED초 이상 멈췄을 때만 한컴을 앞으로 올리고,
#   키를 보내기 직전에 「맨 앞 앱이 한컴인가」, 「그 사이 입력이 없었나」를 다시 본다. 조건이 깨지면 키를 보내지 않고 물러난다.
#   (정해진 시각에 Return을 보내던 옛 방식은 사용자가 메신저에 입력 중일 때 키가 그쪽으로 갔다)
# - 화면이 꺼져 있거나(덮개 닫힘·디스플레이 잠자기) 잠겨 있으면 한컴 창이 0개로 잡혀 PDF를 못 뽑는다 → 바로 종료 코드 3.
#   외장 모니터에 덮개를 닫고 쓰는 경우가 있으므로 덮개가 아니라 「Display Asleep」과 화면 잠금을 본다.
# - 남아 있는 「PDF로 저장하기」 창은 Escape로 취소한다. 「자동 저장 파일 복구」 창이 뜨면 사용자 자동저장본일 수 있으니
#   스크립트는 건드리지 않고 실패로 끝낸다(사람이 「불러옴」으로 보존).
# - 한컴 PDF는 A4 쪽 안에 본문이 약 0.73~0.77배로 줄어 저장된다(쪽 나눔·줄바꿈은 실제와 같음). page_fill.py가 보정한다.
# - 120쪽이 넘는 문서는 PDF가 생기기까지 몇 분 걸린다. 파일 크기가 멈출 때까지 기다린다.
set -u
SRC="${1:A}"; LIMIT="${2:-${QA_WAIT:-900}}"
IDLE_NEED="${IDLE_NEED:-12}"
APP="Hancom Office HWP"
[ -f "$SRC" ] || { echo "파일 없음: $SRC" >&2; exit 2; }
OUT="${SRC%.*}.pdf"

# 0) 화면 켜짐·잠금 확인
if system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Display Asleep: Yes"; then
  echo "화면이 꺼져 있음(Display Asleep) — 한컴 창을 다룰 수 없어 PDF를 못 뽑음. 화면이 켜진 뒤 다시 실행" >&2; exit 3
fi
if ioreg -n Root -d1 2>/dev/null | grep -q '"CGSSessionScreenIsLocked"=Yes'; then
  echo "화면이 잠겨 있음 — 잠금이 풀린 뒤 다시 실행" >&2; exit 3
fi

WORK="$(mktemp -d /private/tmp/hwp_report_qa.XXXXXX)"; BASE="HRQA_$(date +%H%M%S)_$(basename "$SRC")"; DOC="$WORK/$BASE"; PDF="${DOC%.*}.pdf"
cp "$SRC" "$DOC"
cleanup() {
  # 검수 사본 창만 닫고, 「저장할까요」가 뜨면 검수 사본일 때만 「저장 안 함」
  osascript -e 'tell application "System Events" to tell process "'"$APP"'"
    repeat with w in (every window whose name starts with "HRQA_")
      try
        perform action "AXPress" of (first button of w whose subrole is "AXCloseButton")
      end try
    end repeat
  end tell' >/dev/null 2>&1
  sleep 1
  osascript -e 'tell application "System Events" to tell process "'"$APP"'"
    repeat with w in (every window whose subrole is "AXDialog")
      try
        if (value of static text 2 of w) contains "HRQA_" then perform action "AXPress" of (button "저장 안 함" of w)
      end try
    end repeat
  end tell' >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

idle()  { ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {printf "%d\n", $NF/1000000000; exit}'; }
front() { osascript -e 'tell application "System Events" to get name of first process whose frontmost is true' 2>/dev/null; }
ask()   { osascript -e 'tell application "System Events" to tell process "'"$APP"'" to '"$1" 2>/dev/null; }
has_dialog()  { [ "$(ask 'exists window "PDF로 저장하기"')" = "true" ]; }
has_doc()     { [ "$(ask 'exists window "'"$BASE"'"')" = "true" ]; }
has_recover() { ask 'name of every window' | grep -q "복구"; }
T0=$(date +%s)
left() { echo $(( LIMIT - ($(date +%s) - T0) )); }
wait_idle() { while [ "$(idle)" -lt "$IDLE_NEED" ]; do [ "$(left)" -le 0 ] && return 1; sleep 2; done; return 0; }
safe_key() {   # $1 키 코드, $2 한컴을 앞으로 올린 시각
  local code="$1" since="$2" now=$(date +%s)
  [ "$(front)" = "$APP" ] || return 1
  [ "$(idle)" -ge $(( now - since )) ] || return 1
  osascript -e 'tell application "System Events" to key code '"$code" >/dev/null 2>&1
}
borrow()   { PREV="$(front)"; ask 'set frontmost to true' >/dev/null; sleep 0.8; BORROW_AT=$(date +%s); }
giveback() { [ -n "${PREV:-}" ] && [ "$PREV" != "$APP" ] && osascript -e 'tell application "System Events" to tell process "'"$PREV"'" to set frontmost to true' >/dev/null 2>&1; }

while [ "$(left)" -gt 0 ]; do
  if has_recover; then echo "「자동 저장 파일 복구」 창이 떠 있음 — 사람이 「불러옴」으로 처리한 뒤 다시 실행" >&2; exit 4; fi
  # 1) 남은 저장 창 취소
  if has_dialog; then
    wait_idle || break
    borrow; ask 'perform action "AXRaise" of window "PDF로 저장하기"' >/dev/null; sleep 0.4
    safe_key 53 "$BORROW_AT"; sleep 1; giveback
    has_dialog && { sleep 3; continue; }
  fi
  # 2) 검수 사본 열기(포커스를 가져오지 않는 -g)
  if ! has_doc; then
    open -g -a "$APP" "$DOC"
    for i in $(seq 1 30); do has_doc && break; sleep 1.5; done
    has_doc || { echo "문서 창이 열리지 않음 — 다시 시도" >&2; sleep 3; continue; }
    sleep 4
  fi
  # 3) 파일 → PDF로 저장하기 → Return (입력이 멈췄을 때만)
  wait_idle || break
  borrow
  ask 'perform action "AXRaise" of window "'"$BASE"'"' >/dev/null; sleep 0.4
  if [ "$(front)" != "$APP" ]; then giveback; sleep 3; continue; fi
  ask 'click menu item "PDF로 저장하기..." of menu of menu bar item "파일" of menu bar 1' >/dev/null
  for i in 1 2 3 4 5 6 7 8; do has_dialog && break; sleep 0.5; done
  if ! has_dialog; then giveback; sleep 3; continue; fi
  sleep 0.6
  if safe_key 36 "$BORROW_AT"; then
    for i in 1 2 3 4 5 6; do has_dialog || break; sleep 0.5; done
    has_dialog && { safe_key 36 "$BORROW_AT"; sleep 1.5; }      # 같은 이름이 있을 때 덮어쓰기 확인
  fi
  giveback
  for i in $(seq 1 240); do [ -f "$PDF" ] && break; sleep 1; done
  if [ -f "$PDF" ]; then
    last=-1; same=0
    while [ $same -lt 3 ]; do sz=$(stat -f %z "$PDF" 2>/dev/null || echo 0); if [ "$sz" = "$last" ] && [ "$sz" != "0" ]; then same=$((same+1)); else same=0; fi; last=$sz; sleep 2; done
    mv -f "$PDF" "$OUT"
    echo "pdf: $OUT"
    exit 0
  fi
  sleep 3
done
echo "PDF 저장 실패 — 사용자가 계속 입력 중이었거나 한컴 창을 찾지 못함(대기 ${LIMIT}초). 자리를 비웠을 때 다시 실행" >&2
exit 1
