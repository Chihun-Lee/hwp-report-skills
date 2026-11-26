# -*- coding: utf-8 -*-
"""작성자 수정 포인트 표 — 빌드본(이전 판)과 작성자가 고친 판을 비교해 「무엇을 어떻게 고쳤는지」를 md로 뽑는다.

    python learn_diff.py 이전판.hwpx 수정본.hwpx [-o 수정포인트.md] [--json 수정포인트.json] [--max 400]

- 모든 구역(section0, 1, …)의 문단과 표 칸을 비교한다. 비슷한 문단끼리 짝지어 「변경」으로, 짝이 없으면 「삭제」·「추가」로 적는다.
- 변경 문단은 낱말 단위로 ~~지운 말~~ **넣은 말** 표시를 하고, 유형을 자동으로 붙인다
  (날짜 삭제 · 괄호 줄임 · 문장 줄임 · 숫자 변경 · 종결 변경 · 낱말 치환 · 글머리 변경 · 표 칸 …).
- 맨 위 요약에 유형별 횟수와 **두 번 이상 반복된 낱말 치환**(규칙 후보)을 적는다.
  반복 치환은 writing_rules.md(기본 문체)나 ~/.hwp_report/style.md(내 문체)의 규칙·lint 후보다.
diff_hwpx.py는 「같은가」를 보는 왕복 검사용이고, 이 도구는 「사람이 무엇을 고쳤나」를 읽는 용도다.
"""
import argparse
import collections
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hwpx_text import iter_paras  # noqa: E402

DATE = re.compile(r"\d{4}[.\-/년]\s?\d{1,2}|\d{1,2}월\s?\d{1,2}일|(?<![\d.])\d{1,2}/\d{1,2}(?![\d/])|\d{1,2}:\d{2}")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
BULLET = re.compile(r"^\s*([□■○❍ｏo◦•●\-‧·∙※▶▷*]|\d+\)|\(\d+\)|[①-⑳])\s*")
TOK = re.compile(r"\s+|[^\s]+")


def seq(path):
    out = []
    for s, i, kind, t, _ in iter_paras(path):
        if kind == "empty":
            continue
        if kind == "cell":
            if not t["text"]:
                continue
            out.append({"loc": f"구역{s} 표{t['t']} ({t['r']},{t['c']})", "kind": "cell", "text": t["text"]})
        elif kind == "pic":
            out.append({"loc": f"구역{s} 문단{i}", "kind": "pic", "text": "[그림] " + t})
        elif kind == "tbl":
            continue
        else:
            out.append({"loc": f"구역{s} 문단{i}", "kind": "text", "text": t})
    return out


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


def word_diff(a, b):
    ta, tb = TOK.findall(a), TOK.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    out, swaps = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        A, B = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if op == "equal":
            out.append(A)
        elif op == "delete":
            out.append(f"~~{A.strip()}~~ " if A.strip() else A)
        elif op == "insert":
            out.append(f"**{B.strip()}** " if B.strip() else B)
        else:
            out.append(f"~~{A.strip()}~~ **{B.strip()}** ")
            if A.strip() and B.strip() and len(A.split()) <= 3 and len(B.split()) <= 3:
                swaps.append((A.strip(), B.strip()))
    return "".join(out).replace("|", "\\|"), swaps


def tags(a, b, kind, swaps):
    t = []
    if kind == "cell":
        t.append("표 칸")
    if DATE.search(a) and not DATE.search(b):
        t.append("날짜 삭제")
    pa, pb = a.count("(") + a.count("（"), b.count("(") + b.count("（")
    if pa > pb:
        t.append("괄호 줄임")
    elif pb > pa:
        t.append("괄호 추가")
    if len(b) < len(a) * 0.85:
        t.append("문장 줄임")
    elif len(b) > len(a) * 1.15:
        t.append("문장 늘림")
    if sorted(NUM.findall(a)) != sorted(NUM.findall(b)):
        t.append("숫자 변경")
    ma, mb = BULLET.match(a), BULLET.match(b)
    if (ma.group(1) if ma else "") != (mb.group(1) if mb else ""):
        t.append("글머리 변경")
    ea, eb = re.sub(r"[\s.]+$", "", a)[-2:], re.sub(r"[\s.]+$", "", b)[-2:]
    if kind != "cell" and ea != eb and not (len(b) < len(a) * 0.5):
        t.append(f"종결 {ea}→{eb}")
    if swaps:
        t.append("낱말 치환")
    return t or ["표현 다듬기"]


def pair_block(A, B):
    """바뀐 덩어리 안에서 비슷한 문단끼리 짝짓기(순서 유지, 탐욕)"""
    pairs, used, j0 = [], set(), 0
    for a in A:
        best, bj = 0.0, None
        for j in range(j0, len(B)):
            if j in used:
                continue
            r = difflib.SequenceMatcher(None, a["text"], B[j]["text"], autojunk=False).ratio()
            if r > best:
                best, bj = r, j
        if bj is not None and best >= 0.45:
            pairs.append((a, B[bj]))
            used.add(bj)
            j0 = bj + 1
        else:
            pairs.append((a, None))
    # 짝 없는 추가 문단은 원래 순서대로 끼워 넣는다
    for j, b in enumerate(B):
        if j not in used:
            pairs.append((None, b))
    return pairs


def compare(pa, pb):
    A, B = seq(pa), seq(pb)
    sm = difflib.SequenceMatcher(None, [norm(x["text"]) for x in A], [norm(x["text"]) for x in B], autojunk=False)
    rows = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        for a, b in pair_block(A[i1:i2], B[j1:j2]):
            if a and b:
                md, swaps = word_diff(a["text"], b["text"])
                rows.append({"type": "변경", "loc": b["loc"], "before": a["text"], "after": b["text"], "md": md,
                             "tags": tags(a["text"], b["text"], b["kind"], swaps), "swaps": swaps})
            elif a:
                rows.append({"type": "삭제", "loc": a["loc"], "before": a["text"], "after": "", "md": f"~~{a['text']}~~",
                             "tags": ["그림 삭제" if a["kind"] == "pic" else ("표 칸 비움" if a["kind"] == "cell" else "문단 삭제")],
                             "swaps": []})
            else:
                rows.append({"type": "추가", "loc": b["loc"], "before": "", "after": b["text"], "md": f"**{b['text']}**",
                             "tags": ["그림 추가" if b["kind"] == "pic" else ("표 칸 채움" if b["kind"] == "cell" else "문단 추가")],
                             "swaps": []})
    return A, B, rows


def report(pa, pb, A, B, rows, limit):
    cnt = collections.Counter(t.split(" ")[0] if t.startswith("종결") else t for r in rows for t in r["tags"])
    sw = collections.Counter(s for r in rows for s in r["swaps"])
    rep = [(k, v) for k, v in sw.most_common() if v >= 2]
    L = [f"# 작성자 수정 포인트 — {Path(pb).name}", "",
         f"- 이전 판: `{pa}`", f"- 수정본: `{pb}`",
         f"- 문단·표 칸 {len(A)} → {len(B)} · 변경 {sum(r['type'] == '변경' for r in rows)} · "
         f"삭제 {sum(r['type'] == '삭제' for r in rows)} · 추가 {sum(r['type'] == '추가' for r in rows)}", "",
         "## 유형별 횟수", "", "| 유형 | 횟수 |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in cnt.most_common()]
    L += ["", "## 반복된 낱말 치환 (규칙 후보)", ""]
    L += ([f"- 「{a}」 → 「{b}」 × {v}" for (a, b), v in rep] or ["- 없음"])
    L += ["", "## 수정 목록", "", "| 위치 | 구분 | 유형 | 내용 (~~지움~~ **넣음**) |", "|---|---|---|---|"]
    for r in rows[:limit]:
        L.append(f"| {r['loc']} | {r['type']} | {' · '.join(r['tags'])} | {r['md'][:400]} |")
    if len(rows) > limit:
        L.append(f"\n… {len(rows) - limit}건 더 있음 (--max로 늘림)")
    L += ["", "## 다음에 할 일", "",
          "- 같은 유형이 여러 번 나오면 규칙으로 남긴다: 기본 문체면 `references/writing_rules.md`, 내 문체면 `~/.hwp_report/style.md`.",
          "- 실제 문장이 든 이 표는 개인 노트(`~/.hwp_report/notes/`)에 둔다. 공개 문서에는 익명화한 예시만 옮긴다."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("-o", "--out", help="md 출력(없으면 화면)")
    ap.add_argument("--json", help="json 출력")
    ap.add_argument("--max", type=int, default=400, help="md에 적을 최대 행 수")
    x = ap.parse_args()
    A, B, rows = compare(x.before, x.after)
    md = report(x.before, x.after, A, B, rows, x.max)
    if x.out:
        Path(x.out).write_text(md, encoding="utf-8")
        print(f"수정 포인트 {len(rows)}건 → {x.out}")
    else:
        print(md)
    if x.json:
        Path(x.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
