#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hwp-report-skills 설치 — Windows·macOS·Linux 공통.

    python install.py                 # 스킬 두 개를 ~/.claude/skills/ 에 넣고, 파이썬 패키지 설치(그림용 matplotlib 포함), 자가검사
    python install.py --no-figures    # 그림(report-figure)용 matplotlib은 빼고 설치
    python install.py --link          # 복사 대신 연결(git pull 하면 바로 최신). Windows는 디렉터리 정션
    python install.py --copy          # 연결 대신 복사 (Windows 기본)
    python install.py --dest <폴더>   # 다른 스킬 폴더(예: 프로젝트의 .claude/skills)
    python install.py --pip-args "--trusted-host pypi.org --trusted-host files.pythonhosted.org"   # 회사망 SSL 오류
    python install.py --uninstall     # 스킬 두 개만 지움(설정 ~/.hwp_report 는 남김)

Windows에서는 install.cmd 를 더블클릭해도 된다. Claude Code에게 맡길 때의 절차는 INSTALL.md.
- 이 설치가 복사한 스킬 폴더에는 표식 파일(.hwp-report-skills.json)을 둔다. 다시 설치하면 표식이 있는 폴더는 그냥 바꾼다.
- 표식이 없는 같은 이름의 스킬(직접 만든 것 등)은 ~/.hwp_report/backup/ 으로 옮겨 둔다(스킬 폴더 안에 백업을 남기면 스킬이 두 번 잡힌다).
- 설치 기록은 ~/.hwp_report/install.json 에 남긴다(hr.py update 가 읽는다).
"""
import argparse
import datetime
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
REPO_URL = "https://github.com/Chihun-Lee/hwp-report-skills"
SKILLS = [d for d in sorted((REPO / "skills").iterdir()) if (d / "SKILL.md").exists()]
WIN = os.name == "nt"
HOME = Path(os.environ.get("HWP_REPORT_HOME") or (Path.home() / ".hwp_report")).expanduser()
MARK = ".hwp-report-skills.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


def version():
    try:
        return json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except Exception:  # noqa: BLE001
        return "?"


def git_url():
    if not (REPO / ".git").exists() or not shutil.which("git"):
        return REPO_URL
    r = subprocess.run(["git", "-C", str(REPO), "remote", "get-url", "origin"], capture_output=True)
    u = r.stdout.decode(errors="replace").strip()
    return u[:-4] if u.endswith(".git") else (u or REPO_URL)


def is_link(p):
    return p.is_symlink() or (WIN and hasattr(os.path, "isjunction") and os.path.isjunction(p)) or _junction(p)


def _junction(p):
    if not WIN or not p.exists():
        return False
    try:
        return bool(os.readlink(p))          # 3.8+: 정션도 읽힌다
    except (OSError, ValueError):
        return False


def target_of(p):
    try:
        return Path(os.readlink(p)).resolve()
    except OSError:
        return None


def link(src, t):
    if WIN:
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(t), str(src)], capture_output=True)
        if r.returncode:                       # cmd 출력은 cp949일 수 있어 바이트로 받아 풀어 쓴다
            raise OSError((r.stdout + r.stderr).decode("mbcs" if WIN else "utf-8", errors="replace"))
    else:
        os.symlink(src, t, target_is_directory=True)


def _force_writable(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)              # Windows 읽기 전용 파일(git 객체 등)도 지울 수 있게
    func(path)


def remove(t):
    if is_link(t):
        os.rmdir(t) if WIN else t.unlink()     # 정션·링크만 지운다(원본은 그대로)
    elif t.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(t, onexc=_force_writable)
        else:
            shutil.rmtree(t, onerror=_force_writable)
    elif t.exists():
        t.unlink()


def backup(t):
    stamp = f"{datetime.datetime.now():%Y%m%d%H%M%S}"
    bk = HOME / "backup" / f"{t.name}.{stamp}"
    bk.parent.mkdir(parents=True, exist_ok=True)
    if is_link(t):
        old = target_of(t)
        (bk.parent / f"{t.name}.{stamp}.link.txt").write_text(f"{t} → {old}\n", encoding="utf-8")
        remove(t)
        print(f"  기존 {t.name} 연결 해제 (원래 대상 {old} — 기록: {bk.parent / (t.name + '.' + stamp + '.link.txt')})")
    else:
        shutil.move(str(t), str(bk))
        print(f"  기존 {t.name} 백업 → {bk}")


def ours(t):
    """이 설치가 전에 복사한 폴더인가(표식 파일)."""
    return not is_link(t) and (t / MARK).is_file()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=str(Path.home() / ".claude" / "skills"))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--link", action="store_true")
    g.add_argument("--copy", action="store_true")
    f = ap.add_mutually_exclusive_group()
    f.add_argument("--figures", action="store_true", help="(기본값) 그림용 matplotlib도 설치")
    f.add_argument("--no-figures", action="store_true", help="matplotlib 빼고 설치")
    ap.add_argument("--pip-args", default=os.environ.get("HR_PIP_ARGS", ""))
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--no-setup", action="store_true", help="파이썬 패키지 설치·자가검사 건너뜀")
    a = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 이상이 필요하다 — https://www.python.org/downloads/")
    dest = Path(a.dest).expanduser().resolve()
    use_link = a.link or (not a.copy and not WIN)
    figures = not a.no_figures
    ver = version()

    if a.uninstall:
        for d in SKILLS:
            t = dest / d.name
            if t.exists() or is_link(t):
                remove(t)
                print(f"  - {t}")
        rec = HOME / "install.json"
        if rec.exists():
            rec.unlink()
        print(f"\n스킬을 지웠다. 설정·가상환경·받은 원본까지 지우려면 {HOME} 폴더를 지운다.")
        return

    dest.mkdir(parents=True, exist_ok=True)
    print(f"hwp-report-skills {ver} 설치 → {dest}  ({'연결' if use_link else '복사'})")
    for d in SKILLS:
        t = dest / d.name
        if use_link and is_link(t) and target_of(t) == d.resolve():
            print(f"  = {d.name} (이미 연결됨)")
            continue
        if ours(t):
            remove(t)                          # 전에 이 설치가 복사한 것 → 백업 없이 바꾼다
        elif t.exists() or is_link(t):
            backup(t)
        if use_link:
            link(d, t)
            print(f"  + {d.name} → {d}")
        else:
            shutil.copytree(d, t, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            (t / MARK).write_text(json.dumps({"version": ver, "source": str(REPO)}, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
            print(f"  + {d.name} (복사)")

    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "install.json").write_text(json.dumps({
        "version": ver, "source": str(REPO), "git": (REPO / ".git").exists(), "repo_url": git_url(),
        "dest": str(dest), "mode": "link" if use_link else "copy", "figures": figures,
        "skills": [d.name for d in SKILLS], "installed": f"{datetime.datetime.now():%Y-%m-%d %H:%M}",
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    hr = dest / "hwp_report" / "scripts" / "hr.py"
    if not a.no_setup:
        print()
        cmd = [sys.executable, "-X", "utf8", str(hr), "setup"]
        if figures:
            cmd.append("--figures")
        if a.pip_args:
            cmd += ["--pip-args", a.pip_args]
        if subprocess.call(cmd):
            sys.exit("\n설치가 끝나지 않았다 — 위 안내대로 다시 실행한다")
        print()
        if subprocess.call([sys.executable, "-X", "utf8", str(hr), "selftest"]):
            sys.exit("\n자가검사 실패 — 위 출력을 확인한다")
    me = "py -3" if WIN else "python3"
    print(f"\n✓ 설치 완료 (hwp-report-skills {ver})")
    print("  - Claude Code를 다시 시작하면(새 대화) /hwp_report 와 report-figure 스킬이 보인다.")
    print("  - 「연차보고서 만들어줘」라고 말하면 된다. 처음 쓸 때 문체(기본/내 문체)와 양식(기본/다른 양식)을 묻는다.")
    print(f"  - 설정·가상환경: {HOME}")
    print(f"  - 상태 점검: {me} \"{hr}\" doctor")
    print(f"  - 업데이트:  {me} \"{hr}\" update")


if __name__ == "__main__":
    main()
