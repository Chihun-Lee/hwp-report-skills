# -*- coding: utf-8 -*-
"""사용자 설정·양식 프로필 찾기.

사용자 자료는 스킬 폴더가 아니라 ~/.hwp_report/ 에 둔다(레포를 업데이트해도 남도록).
    ~/.hwp_report/config.yaml          style: default | personal | skill:<스킬이름>,  form: default | <양식이름>
    ~/.hwp_report/style.md             내 문체 가이드(style: personal일 때)
    ~/.hwp_report/forms/<이름>/        등록한 양식: form.hwpx + profile.yaml
    ~/.hwp_report/venv/                파이썬 패키지(hr.py setup)
위치는 환경변수 HWP_REPORT_HOME으로 바꿀 수 있다.
"""
import os
import re
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("HWP_REPORT_HOME", Path.home() / ".hwp_report")).expanduser()
BUNDLED_FORMS = SKILL / "assets" / "forms"
DEFAULT_FORM = "annual_review_2026"
CONFIG = HOME / "config.yaml"


def load_config():
    if CONFIG.exists():
        return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    return {}


def save_config(cfg):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def form_dirs():
    """이름 → 양식 폴더 (사용자 등록 양식이 같은 이름의 기본 양식보다 우선)"""
    out = {}
    for root in (BUNDLED_FORMS, HOME / "forms"):
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if (d / "profile.yaml").exists():
                    out[d.name] = d
    return out


def load_profile(d):
    prof = yaml.safe_load((Path(d) / "profile.yaml").read_text(encoding="utf-8")) or {}
    prof.setdefault("anchors", {})
    prof.setdefault("samples", [])
    prof.setdefault("header_rows", {})
    return prof


def resolve_form(arg=None, base=None):
    """--form / spec form: / config form: 순서로 양식을 찾아 (form.hwpx 경로, 프로필, 양식 폴더)를 돌려준다.
    값은 양식 이름(기본·등록), 양식 폴더, 또는 .hwpx 경로(옆에 profile.yaml이 없으면 기본 프로필을 쓴다)."""
    if not arg or arg == "default":
        arg = load_config().get("form") or "default"
    if arg == "default":
        arg = DEFAULT_FORM
    forms = form_dirs()
    if arg in forms:
        d = forms[arg]
        prof = load_profile(d)
        return d / prof.get("form", "form.hwpx"), prof, d
    p = Path(arg).expanduser()
    if not p.is_absolute() and base is not None and (Path(base) / p).exists():
        p = Path(base) / p
    if p.is_dir() and (p / "profile.yaml").exists():
        prof = load_profile(p)
        return p / prof.get("form", "form.hwpx"), prof, p
    if p.suffix.lower() == ".hwpx" and p.exists():
        side = p.with_name("profile.yaml")
        prof = load_profile(p.parent) if side.exists() else load_profile(forms[DEFAULT_FORM])
        return p, prof, p.parent
    raise SystemExit(f"양식을 찾지 못함: {arg} — 등록된 양식: {', '.join(forms)} (hr.py config forms)")


def style_info(cfg=None):
    """적용할 문체: (종류, 가이드 파일 경로 또는 None)"""
    cfg = load_config() if cfg is None else cfg
    st = cfg.get("style") or "default"
    if st == "personal":
        return st, HOME / "style.md"
    if st.startswith("skill:"):
        name = st.split(":", 1)[1]
        for root in (Path.home() / ".claude" / "skills", SKILL.parent):
            if (root / name / "SKILL.md").exists():
                return st, root / name / "SKILL.md"
        return st, None
    return "default", SKILL / "references" / "writing_rules.md"


def style_lint():
    """내 문체(style.md) 맨 위 YAML의 lint: {forbid: [...], warn: [...]}"""
    st, path = style_info()
    if st != "personal" or not path or not path.exists():
        return {}
    m = re.match(r"^---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    return (yaml.safe_load(m.group(1)) or {}).get("lint", {}) or {}
