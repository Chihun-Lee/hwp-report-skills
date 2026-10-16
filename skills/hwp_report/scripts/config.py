# -*- coding: utf-8 -*-
"""hwp_report 사용자 설정 (~/.hwp_report/config.yaml).

    python config.py show                          현재 설정 (없으면 「첫 사용 설정 필요」)
    python config.py init --style default --form default
    python config.py set style personal            문체: default | personal | skill:<문체 스킬 이름>
    python config.py set form <양식 이름>           양식: default | 등록한 양식 이름
    python config.py forms                         쓸 수 있는 양식 목록
    python config.py add-form 새양식.hwpx --name 단계보고서   양식 등록(분석 + 프로필 초안) 후 기본 양식으로
    python config.py style-path                    지금 적용할 문체 가이드 파일 경로
"""
import argparse
import datetime
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from settings import CONFIG, HOME, form_dirs, load_config, load_profile, save_config, style_info  # noqa: E402

STYLE_HELP = "default(기본 보고서 문체) | personal(내 문체 — ~/.hwp_report/style.md) | skill:<이름>(설치된 문체 스킬)"


def check_style(v):
    if v in ("default", "personal") or v.startswith("skill:"):
        return v
    raise SystemExit(f"문체 값 오류: {v} — {STYLE_HELP}")


def check_form(v):
    if v == "default" or v in form_dirs():
        return v
    raise SystemExit(f"양식 없음: {v} — 등록된 양식: {', '.join(form_dirs())} (add-form으로 등록)")


def show():
    cfg = load_config()
    if not cfg:
        print(f"설정 없음 — 첫 사용 설정 필요 ({CONFIG})")
        print("  문체:", STYLE_HELP)
        print("  양식: default(2026 전략연구사업 연차점검 양식1) | 다른 양식 hwpx 등록(add-form)")
        sys.exit(3)
    st, guide = style_info(cfg)
    form = cfg.get("form", "default")
    d = form_dirs().get("annual_review_2026" if form == "default" else form)
    print(f"설정: {CONFIG}")
    print(f"  문체: {cfg.get('style', 'default')} → 가이드 {guide if guide else '(없음 — 만들거나 다시 고르기)'}"
          + ("" if not guide or Path(guide).exists() else "  ⚠️ 파일 없음"))
    print(f"  양식: {form} → {d / 'profile.yaml' if d else '⚠️ 없음'}" + (f"  ({load_profile(d).get('name')})" if d else ""))
    if cfg.get("author"):
        print(f"  작성자: {cfg['author']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    p = sub.add_parser("init")
    p.add_argument("--style", default="default")
    p.add_argument("--form", default="default")
    p.add_argument("--author", default=None)
    p = sub.add_parser("set")
    p.add_argument("key", choices=["style", "form", "author"])
    p.add_argument("value")
    sub.add_parser("forms")
    p = sub.add_parser("add-form")
    p.add_argument("hwpx")
    p.add_argument("--name", required=True)
    p.add_argument("--no-default", action="store_true", help="등록만 하고 기본 양식은 바꾸지 않음")
    sub.add_parser("style-path")
    a = ap.parse_args()

    if a.cmd == "show":
        show()
    elif a.cmd == "init":
        cfg = {"style": check_style(a.style), "form": check_form(a.form),
               "created": datetime.date.today().isoformat()}
        if a.author:
            cfg["author"] = a.author
        save_config(cfg)
        show()
    elif a.cmd == "set":
        cfg = load_config()
        cfg[a.key] = check_style(a.value) if a.key == "style" else check_form(a.value) if a.key == "form" else a.value
        save_config(cfg)
        show()
    elif a.cmd == "forms":
        cur = load_config().get("form", "default")
        for name, d in form_dirs().items():
            mark = "*" if name == cur or (cur == "default" and name == "annual_review_2026") else " "
            print(f" {mark} {name:24s} {load_profile(d).get('name', '')}  ({d})")
    elif a.cmd == "add-form":
        src = Path(a.hwpx).expanduser()
        if src.suffix.lower() != ".hwpx":
            raise SystemExit("hwpx만 등록할 수 있다 — .hwp는 한글에서 「다른 이름으로 저장 → hwpx」")
        d = HOME / "forms" / a.name
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, d / "form.hwpx")
        subprocess.run([sys.executable, str(Path(__file__).with_name("analyze_form.py")), str(d / "form.hwpx"),
                        "--profile-out", str(d / "profile.yaml"), "--name", a.name], check=True)
        if not a.no_default:
            cfg = load_config()
            cfg["form"] = a.name
            save_config(cfg)
        print(f"\n등록: {d}  — profile.yaml을 확인·수정한 뒤 spec을 쓴다(references/forms.md)")
    elif a.cmd == "style-path":
        st, guide = style_info()
        print(guide or "")


if __name__ == "__main__":
    main()
