#!/bin/zsh
# macOS 한컴오피스 한글로 hwpx → PDF (쪽 나눔 최종 확인용). 사용: zsh hancom_pdf.sh report.hwpx
# - 한컴을 종료하지 않는다(다른 문서·자동 복구본 보호). 대상 문서 창만 닫았다 다시 열어 「PDF로 저장하기」.
# - 화면 잠금 상태, 「한컴 자동 업데이트」 창, 「자동 저장 파일 복구」 창이 떠 있으면 실패한다
#   → 업데이트 창은 「취소」, 복구 창은 「불러옴」(사용자 자동저장본 보존) 후 다시 실행.
# - 한컴 PDF는 A4 쪽 안에 본문이 약 0.77배로 축소되어 저장된다(쪽 나눔은 실제와 같음). page_fill.py가 보정한다.
DOC="${1:A}"; BASE="$(basename "$DOC")"; PDF="${DOC%.*}.pdf"
[ -f "$DOC" ] || { echo "파일 없음: $DOC"; exit 2; }
APP="Hancom Office HWP"
rm -f "$PDF"
osascript <<OSA 2>/dev/null
tell application "System Events" to tell process "$APP"
  if exists window "$BASE" then
    click (first button of window "$BASE" whose subrole is "AXCloseButton")
  end if
end tell
OSA
sleep 3
open -g -a "$APP" "$DOC"
for i in {1..20}; do
  sleep 2
  osascript -e "tell application \"System Events\" to tell process \"$APP\" to exists window \"$BASE\"" 2>/dev/null | grep -q true && break
done
sleep 4
osascript <<OSA
tell application "System Events"
  set prevApp to name of first application process whose frontmost is true
  tell process "$APP"
    set frontmost to true
    perform action "AXRaise" of window "$BASE"
    delay 1
    click menu item "PDF로 저장하기..." of menu of menu bar item "파일" of menu bar 1
    delay 3
    perform action "AXRaise" of window "PDF로 저장하기"
    delay 1
  end tell
  key code 36
  delay 3
  tell process "$APP"
    if exists window "PDF로 저장하기" then
      key code 36
      delay 2
    end if
  end tell
  tell process prevApp to set frontmost to true
end tell
OSA
for i in {1..15}; do sleep 2; [ -f "$PDF" ] && break; done
[ -f "$PDF" ] && echo "pdf: $PDF" || { echo "PDF 저장 실패 — 한컴 창 상태 확인(위 주석)"; exit 1; }
