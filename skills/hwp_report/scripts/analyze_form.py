# -*- coding: utf-8 -*-
"""새 양식 hwpx를 살펴보고 프로필(profile.yaml) 초안을 만든다.

    python analyze_form.py 새양식.hwpx [--profile-out profile.yaml]

출력: ① 기본 프로필의 제목이 이 양식에 있는지(찾음/없음) ② 제목처럼 보이는 문단 목록(sections: 후보)
      ③ 표 목록(크기·바로 앞 제목) ④ 예시·자리표시 문단.
--profile-out을 주면 기본 프로필을 복사해 못 찾은 제목은 null로 바꾸고, 제목 후보를 suggested_sections로 적는다.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_lib import NS, Form, rows_of  # noqa: E402
from settings import BUNDLED_FORMS, DEFAULT_FORM, load_profile  # noqa: E402

HEAD_RX = re.compile(r"^(\d+\.\s|\d+\)\s?|[①-⑳]|□|■|◆|▶|\[[^\]]+\]|<[^>]+>|제\s*\d+\s*[장절])")
PLACEHOLDER_RX = re.compile(r"세부설명|ㅇ\s*ㅇ\s*ㅇ|○\s*○\s*○|\(과제명|작성해 주세요|기재합니다|기재하시오|예시\)|YYYY")


def analyze(path):
    f = Form(path)
    P = f.P
    base = load_profile(BUNDLED_FORMS / DEFAULT_FORM)
    texts = [f.text(p).strip() for p in P]
    is_tbl = [p.find(".//hp:tbl", NS) is not None for p in P]
    anchors = {}
    for k, rx in base["anchors"].items():
        hit = [i for i, t in enumerate(texts) if rx and not is_tbl[i] and re.search(rx, t)]
        anchors[k] = hit
    heads, tables, holders = [], [], []
    last_head = None
    for i, (p, t) in enumerate(zip(P, texts)):
        if is_tbl[i]:
            tb = p.find(".//hp:tbl", NS)
            tables.append((i, f"{tb.get('rowCnt')}×{tb.get('colCnt')}", last_head))
            continue
        if not t:
            continue
        r = p.find("hp:run", NS)
        bold = False
        if r is not None:
            cp = f.header.find(f".//hh:charPr[@id='{r.get('charPrIDRef')}']", NS)
            bold = cp is not None and cp.find("hh:bold", NS) is not None
        if (HEAD_RX.match(t) or bold) and len(t) <= 60:
            heads.append((i, t, bold))
            last_head = t
        if PLACEHOLDER_RX.search(t):
            holders.append((i, t))
    return base, anchors, heads, tables, holders, texts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hwpx")
    ap.add_argument("--profile-out")
    ap.add_argument("--name")
    a = ap.parse_args()
    base, anchors, heads, tables, holders, texts = analyze(a.hwpx)
    n_found = sum(1 for v in anchors.values() if v)
    print(f"# 양식 분석: {Path(a.hwpx).name} — 문단 {len(texts)}개, 표 {len(tables)}개")
    print(f"\n## ① 기본 양식(2026 연차점검) 제목 {n_found}/{len(anchors)}개 찾음")
    for k, v in anchors.items():
        print(f"  {'✓' if v else '·'} {k:16s} {('[%03d] ' % v[0]) + texts[v[0]][:40] if v else '없음'}")
    print("\n## ② 제목 후보 (spec의 sections: 키로 쓸 수 있음)")
    for i, t, b in heads:
        print(f"  [{i:03d}]{' B' if b else '  '} {t}")
    print("\n## ③ 표")
    for i, dim, h in tables:
        print(f"  [{i:03d}] {dim:7s} 앞 제목: {h or '-'}")
    print("\n## ④ 예시·자리표시 문단 (채울 자리)")
    for i, t in holders[:40]:
        print(f"  [{i:03d}] {t[:70]}")
    if a.profile_out:
        prof = dict(base)
        prof["name"] = a.name or Path(a.hwpx).stem
        prof["form"] = "form.hwpx"
        prof["anchors"] = {k: (base["anchors"][k] if v else None) for k, v in anchors.items()}
        covered = {v[0] for v in anchors.values() if v}
        prof["suggested_sections"] = [t for i, t, _ in heads if i not in covered]
        out = Path(a.profile_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        hdr = ("# 자동 생성 프로필 — 기본 양식 제목 중 이 양식에 없는 것은 null.\n"
               "# suggested_sections: 이 양식의 제목 후보. spec의 sections: {'^제목 정규식': 개조식}으로 채운다.\n")
        out.write_text(hdr + yaml.safe_dump(prof, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
        print(f"\nprofile: {out}")


if __name__ == "__main__":
    main()
