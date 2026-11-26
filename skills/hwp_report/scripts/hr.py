#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hwp_report 명령 모음 — macOS·Windows·Linux 공통 진입점.

  python3 hr.py <명령> [인자]          Windows: py -3 hr.py <명령> … (또는 python hr.py …)

  setup    [--figures] [--pip-args "..."]                           1회 설치: ~/.hwp_report/venv 에 파이썬 패키지
  doctor                                                           설치 상태 점검(버전·패키지·PDF 읽기·한컴·미리보기·글꼴)
  update   [--force] [--pip-args "..."]                             스킬을 최신으로(git pull 또는 zip 다시 받기 → 다시 설치)
  config   show | init --style S --form F | set style|form 값 | forms | add-form 양식.hwpx --name 이름
  style    내보고서1.hwpx 내보고서2.pdf ...                        내 문체 만들기용 원문·통계 뽑기
  analyze  양식.hwpx                                               양식 구조·제목 후보·표 보기
  build    spec.yaml [-o out.hwpx] [--form 양식] [--figs 폴더]     spec → hwpx (+구조 검사)
  check    report.hwpx [--spec spec.yaml] [--form 원본양식.hwpx]   게이트(구조 + 작성 규칙 + 잔여물)
  extract  수정본.hwpx -o spec.yaml [--spec 이전spec]              hwpx → spec
  diff     a.hwpx b.hwpx [--style]                                 문단 단위 비교(같으면 종료코드 0)
  learn    이전판.hwpx 수정본.hwpx [-o 수정포인트.md]              작성자가 고친 곳·유형·반복 치환 표
  dump     문서.hwpx -o 폴더 | --find 정규식 | --memos             모든 구역 문단·표 칸·모양 번호·메모 덤프
  render   report.hwpx [outdir]                                    헤드리스 쪽 PNG 미리보기 (node 18+ 필요)
  pdf      report.hwpx [옵션]                                      한컴 PDF — Windows: 한글 COM / macOS: 한컴오피스
  fill     report.pdf --hwpx report.hwpx                           쪽 아래 빈칸(mm)
  tail     report.pdf --hwpx report.hwpx [--skip-form 양식.hwpx]   꼬리 줄(마지막 줄 몇 글자) 찾기
  selftest [--pdf]                                                 예시로 빌드·게이트·왕복 검사 (--pdf: 한컴 PDF·꼬리 줄까지)

파이썬은 $HWP_REPORT_PY → ~/.hwp_report/venv → 지금 실행한 파이썬 순서로 고른다.
사용자 자료 위치는 $HWP_REPORT_HOME(기본 ~/.hwp_report)으로 바꿀 수 있다.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/Chihun-Lee/hwp-report-skills"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
HOME = Path(os.environ.get("HWP_REPORT_HOME") or (Path.home() / ".hwp_report")).expanduser()
NEED = "lxml, yaml, PIL, numpy"           # 없으면 setup 안내
BASE_PKGS = ["lxml", "pyyaml", "pillow", "numpy", "pymupdf"]
WIN_PKGS = ["pywin32"]

SCRIPTS = {
    "config": "config.py", "style": "style_samples.py", "analyze": "analyze_form.py",
    "build": "build_report.py", "check": "check_report.py", "extract": "extract_spec.py",
    "diff": "diff_hwpx.py", "learn": "learn_diff.py", "dump": "dump_hwpx.py",
    "tail": "tail_check.py", "fill": "page_fill.py", "render": "render.py",
}

for _s in (sys.stdout, sys.stderr):       # Windows 콘솔(cp949)에서 ✓·○ 같은 글자로 죽지 않게
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


def venv_python():
    return HOME / "venv" / ("Scripts/python.exe" if WIN else "bin/python")


def child_env():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("HWP_REPORT_HOME", str(HOME))
    return env


def pick_python():
    if os.environ.get("HWP_REPORT_PY"):
        return os.environ["HWP_REPORT_PY"]
    v = venv_python()
    return str(v) if v.exists() else sys.executable


def has(py, mods):
    r = subprocess.run([py, "-c", f"import {mods}"], capture_output=True, env=child_env())
    return r.returncode == 0


def run_script(py, name, args, **kw):
    return subprocess.call([py, "-X", "utf8", str(HERE / name), *args], env=child_env(), **kw)


def need_python():
    py = pick_python()
    if not has(py, NEED):
        me = "py -3" if WIN else "python3"
        print(f"파이썬 패키지 없음 → 먼저 설치:  {me} \"{HERE / 'hr.py'}\" setup\n  (지금 파이썬: {py})")
        sys.exit(2)
    return py


# ── setup ────────────────────────────────────────────────────────────
def setup(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="hr.py setup")
    ap.add_argument("--figures", action="store_true", help="그림(report-figure)용 matplotlib도 설치")
    ap.add_argument("--pip-args", default=os.environ.get("HR_PIP_ARGS", ""),
                    help='pip에 넘길 인자. 회사망 SSL 오류면 "--trusted-host pypi.org --trusted-host files.pythonhosted.org"')
    a = ap.parse_args(argv)
    if sys.version_info < (3, 9):
        sys.exit(f"Python 3.9 이상 필요 (지금 {platform.python_version()})")
    HOME.mkdir(parents=True, exist_ok=True)
    vpy = venv_python()
    if not vpy.exists():
        print(f"가상환경 만드는 중 → {HOME / 'venv'}")
        r = subprocess.run([sys.executable, "-m", "venv", str(HOME / "venv")])
        if r.returncode or not vpy.exists():
            sys.exit("venv를 만들지 못함 — Linux면 python3-venv 패키지를 설치한다")
    extra = a.pip_args.split()
    pip = [str(vpy), "-m", "pip", "install", "-q", "--disable-pip-version-check", *extra]
    pkgs = BASE_PKGS + (WIN_PKGS if WIN else []) + (["matplotlib"] if a.figures else [])
    print("파이썬 패키지 설치:", " ".join(pkgs))
    subprocess.run(pip + ["--upgrade", "pip"], capture_output=True)      # 실패해도 계속(오래된 pip로도 대개 된다)
    if subprocess.run(pip + pkgs).returncode:
        print("\n⚠️ pip 설치 실패. 회사망이면 프록시·SSL 검사 때문일 수 있다. 다시 시도:\n"
              '  hr.py setup --pip-args "--trusted-host pypi.org --trusted-host files.pythonhosted.org"'
              + (" --figures" if a.figures else ""))
        sys.exit(1)
    if WIN:
        # 한글 COM의 「파일 접근 허용」 창을 없애는 보안 모듈 DLL만 받는다(pyhwpx, MIT — 의존 패키지는 받지 않음)
        r = subprocess.run(pip + ["--no-deps", "pyhwpx"], capture_output=True)
        if r.returncode:
            print("· 보안 모듈(pyhwpx) 받기 실패 — 한컴 PDF 때 「모두 허용」을 한 번 눌러야 한다")
        else:
            subprocess.call([str(vpy), "-X", "utf8", str(HERE / "hancom_pdf_win.py"), "--register-only"],
                            env=child_env())
    print(f"✓ 설치 완료 → {HOME / 'venv'}\n")
    doctor()


# ── doctor ───────────────────────────────────────────────────────────
def hancom_status():
    if MAC:
        apps = [p for p in ("/Applications/Hancom Office HWP.app", "/Applications/Hancom Office HWP 2024.app")
                if Path(p).exists()] or list(Path("/Applications").glob("Hancom Office HWP*.app"))
        return (True, f"한컴오피스(macOS) {apps[0]}") if apps else (False, "한컴오피스(macOS) 없음")
    if WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"HWPFrame.HwpObject\CLSID"):
                pass
            return True, "한컴오피스 한글 COM(HWPFrame.HwpObject) 등록됨"
        except OSError:
            return False, "한글 COM(HWPFrame.HwpObject)을 찾지 못함 — 한컴오피스 한글 설치 필요"
    return False, "Linux — 한컴 PDF 자동화 없음(한글에서 직접 PDF로 저장)"


def doctor(argv=()):
    py = pick_python()
    ok = lambda b: "✓" if b else "·"     # noqa: E731
    info = install_info()
    if info:
        how = "연결" if info.get("mode") == "link" else "복사"
        print(f"스킬:     hwp-report-skills {info.get('version', '?')} — {how} 설치 {info.get('installed', '')}, 원본 {info.get('source', '?')}")
    else:
        print(f"스킬:     {ROOT}" + ("  (플러그인)" if "plugins" in ROOT.parts else ""))
    print(f"운영체제: {platform.system()} {platform.release()}  ·  사용자 자료: {HOME}")
    print(f"파이썬:   {py}")
    base = has(py, NEED)
    print(f"  {ok(base)} 기본 패키지(lxml·pyyaml·pillow·numpy)" + ("" if base else "  ← hr.py setup 필요"))
    mu = has(py, "pymupdf") or has(py, "fitz")
    pdft = bool(shutil.which("pdftotext"))
    print(f"  {ok(mu or pdft)} PDF 읽기(꼬리 줄·쪽 빈칸): " + ("PyMuPDF" if mu else "pdftotext" if pdft else "없음 ← hr.py setup"))
    hc, msg = hancom_status()
    print(f"  {ok(hc)} {msg}")
    if WIN and hc:
        pw = has(py, "win32com.client")
        print(f"  {ok(pw)} pywin32" + ("" if pw else " 없음 ← hr.py setup"))
        r = subprocess.run([py, "-X", "utf8", str(HERE / "hancom_pdf_win.py"), "--status"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=child_env())
        if r.stdout.strip():
            print("  " + r.stdout.strip().replace("\n", "\n  "))
    node = shutil.which("node")
    nv = subprocess.run([node, "--version"], capture_output=True).stdout.decode(errors="replace").strip() if node else ""
    print(f"  {ok(node)} 미리보기(render): " + (f"node {nv}" if node else "node 없음 — 선택 사항(https://nodejs.org)"))
    if has(py, "matplotlib"):
        r = subprocess.run([py, "-c", "from matplotlib import font_manager as f; n={x.name for x in f.fontManager.ttflist};"
                            "print(','.join(k for k in ('Nanum Gothic','NanumGothic','Malgun Gothic','Apple SD Gothic Neo',"
                            "'AppleGothic','Noto Sans CJK KR','Noto Sans KR') if k in n))"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ko = r.stdout.strip()
        print(f"  {ok(ko)} 그림 한글 글꼴: " + (ko or "없음 — 나눔고딕 또는 맑은 고딕 설치"))
    else:
        print("  · 그림(matplotlib): 없음 — 보고서 그림을 만들려면 hr.py setup --figures")


# ── selftest ─────────────────────────────────────────────────────────
def selftest(argv=()):
    want_pdf = "--pdf" in argv
    py = need_python()
    ex = ROOT / "examples"
    with tempfile.TemporaryDirectory() as td:
        T = Path(td)
        env = child_env()
        env["HWP_REPORT_HOME"] = str(T / "home")      # 내 설정과 무관하게 기본 양식·기본 문체로 검사

        def step(*args, quiet=False, label=""):
            r = subprocess.run([py, "-X", "utf8", *map(str, args)], cwd=ex, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
                sys.exit(f"selftest 실패: {label or args[0]}")
            if not quiet and r.stdout.strip():
                print(r.stdout.strip().splitlines()[-1])
            return r

        S = lambda n: HERE / n               # noqa: E731
        step(S("build_report.py"), "report.example.yaml", "-o", T / "ex.hwpx", label="build")
        step(S("check_report.py"), T / "ex.hwpx", "--spec", "report.example.yaml", "--quiet", label="check")
        step(S("extract_spec.py"), T / "ex.hwpx", "-o", T / "rt.yaml", "--spec", "report.example.yaml",
             "--figs-out", T / "figs", quiet=True, label="extract")
        step(S("build_report.py"), T / "rt.yaml", "-o", T / "rt.hwpx", quiet=True, label="rebuild")
        step(S("diff_hwpx.py"), T / "ex.hwpx", T / "rt.hwpx", label="왕복 차이")
        step(S("learn_diff.py"), T / "ex.hwpx", T / "rt.hwpx", "-o", T / "learn.md", label="learn")
        step(S("dump_hwpx.py"), T / "ex.hwpx", "-o", T / "dump", label="dump")
        if shutil.which("node"):
            r = subprocess.run([shutil.which("node"), str(HERE / "render.mjs"), str(T / "ex.hwpx"), str(T / "svg")],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(("미리보기 " + r.stdout.strip()) if r.returncode == 0 else f"⚠️ 미리보기 실패(선택 기능): {r.stderr[-300:]}")
        if want_pdf:
            hx, pdf_out = T / "ex.hwpx", T / "ex.pdf"
            print("한컴 PDF 시험 — 한글을 띄워 예시 보고서를 PDF로 저장한다(1~3분)")
            if WIN:
                rc = subprocess.call([pick_python(), "-X", "utf8", str(HERE / "hancom_pdf_win.py"), str(hx),
                                      "-o", str(pdf_out), "--timeout", "240"], env=child_env())
            elif MAC:
                rc = subprocess.call([shutil.which("zsh") or "/bin/zsh", str(HERE / "hancom_pdf.sh"), str(hx), "300"])
            else:
                rc = None
                print("· Linux — 한컴 PDF 자동화 없음, 건너뜀")
            if rc:
                sys.exit(f"selftest 실패: 한컴 PDF (종료 코드 {rc}) — 위 출력 확인. 한글 없이도 hwpx 작성·게이트는 된다")
            if rc == 0:
                step(S("tail_check.py"), pdf_out, "--hwpx", hx, label="꼬리 줄(PDF 읽기)")
                print("한컴 PDF OK")
    print("selftest OK")


# ── update ───────────────────────────────────────────────────────────
def install_info():
    import json
    try:
        return json.loads((HOME / "install.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _git(src, *args):
    r = subprocess.run(["git", "-C", str(src), *args], capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace").strip()


def _rmtree(p):
    import stat

    def onerr(func, path, _e):
        try:
            os.chmod(path, stat.S_IWRITE)       # Windows 읽기 전용(git 객체 등)
            func(path)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=onerr)
    else:
        shutil.rmtree(p, onerror=onerr)


def _download(url, out):
    curl = shutil.which("curl")                 # Windows 10+ 기본 curl.exe — 회사 인증서(Windows 저장소)를 따른다
    if curl and subprocess.run([curl, "-fsSL", "--retry", "2", "-o", str(out), url]).returncode == 0:
        return True
    try:
        import urllib.request
        urllib.request.urlretrieve(url, str(out))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"내려받기 실패: {e}")
        return False


def update(argv):
    import argparse
    import zipfile
    ap = argparse.ArgumentParser(prog="hr.py update")
    ap.add_argument("--force", action="store_true", help="바뀐 것이 없어도 다시 설치")
    ap.add_argument("--pip-args", default=os.environ.get("HR_PIP_ARGS", ""))
    a = ap.parse_args(argv)
    info = install_info()
    if not info:
        if "plugins" in ROOT.parts:
            sys.exit("플러그인으로 설치됨 → claude plugin update hwp-report@hwp-report-skills (또는 /plugin 에서 업데이트)")
        sys.exit(f"설치 기록({HOME / 'install.json'})이 없다 → {REPO_URL} 의 INSTALL.md 절차로 다시 설치한다")
    src = Path(info.get("source", ""))
    old = info.get("version", "?")
    if (src / ".git").exists() and shutil.which("git"):
        _, before = _git(src, "rev-parse", "HEAD")
        rc, out = _git(src, "pull", "--ff-only")
        print(out)
        if rc:
            sys.exit(f"git pull 실패 — {src} 에서 직접 고친 파일이 있으면 정리하고 다시 실행한다")
        _, after = _git(src, "rev-parse", "HEAD")
        if before == after and not a.force:
            print(f"✓ 이미 최신 ({old}, {after[:7]})")
            return
        old = f"{old} ({before[:7]})"
    else:                                       # zip으로 받은 설치 → 최신 zip을 ~/.hwp_report/src 로 다시 받는다
        url = (info.get("repo_url") or REPO_URL).rstrip("/") + "/archive/refs/heads/main.zip"
        HOME.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=HOME) as td:
            z = Path(td) / "main.zip"
            print(f"내려받기: {url}")
            if not _download(url, z):
                sys.exit("최신본을 받지 못함 — 인터넷·회사망 차단을 확인한다")
            with zipfile.ZipFile(z) as zf:
                zf.extractall(td)
            top = next((d for d in Path(td).iterdir() if (d / "install.py").exists()), None)
            if not top:
                sys.exit("받은 zip에 install.py 가 없다")
            src = HOME / "src"
            if src.exists():
                _rmtree(src)
            if src.exists():                    # 못 지운 파일이 있으면 옆으로 비켜 둔다
                src.rename(src.with_name(f"src.old{os.getpid()}"))
            shutil.move(str(top), str(src))
    cmd = [sys.executable, "-X", "utf8", str(src / "install.py"), "--dest", info.get("dest", ""),
           "--link" if info.get("mode") == "link" else "--copy"]
    if not info.get("figures", True):
        cmd.append("--no-figures")
    if a.pip_args:
        cmd += ["--pip-args", a.pip_args]
    rc = subprocess.call(cmd)
    if rc == 0:
        new = install_info().get("version", "?")
        if (src / ".git").exists() and shutil.which("git"):
            new += f" ({_git(src, 'rev-parse', '--short', 'HEAD')[1]})"
        print(f"✓ 업데이트 {old} → {new}. Claude Code를 다시 시작하면 새 판이 쓰인다.")
    sys.exit(rc)


# ── pdf ──────────────────────────────────────────────────────────────
def pdf(argv):
    if WIN:
        py = pick_python()
        if not has(py, "win32com.client"):
            sys.exit("pywin32 없음 → hr.py setup 을 먼저 실행")
        sys.exit(run_script(py, "hancom_pdf_win.py", argv))
    if MAC:
        sh = shutil.which("zsh") or "/bin/zsh"
        sys.exit(subprocess.call([sh, str(HERE / "hancom_pdf.sh"), *argv]))
    sys.exit("이 운영체제에서는 한컴 PDF 자동화가 없다 — 한글에서 「PDF로 저장」한 파일로 tail·fill을 돌린다")


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else ""
    rest = argv[1:]
    if cmd in ("", "-h", "--help", "help"):
        print(__doc__)
        return
    if cmd == "setup":
        return setup(rest)
    if cmd == "doctor":
        return doctor(rest)
    if cmd == "selftest":
        return selftest(rest)
    if cmd == "update":
        return update(rest)
    if cmd == "pdf":
        return pdf(rest)
    if cmd in SCRIPTS:
        sys.exit(run_script(need_python(), SCRIPTS[cmd], rest))
    print(f"모르는 명령: {cmd}\n{__doc__}")
    sys.exit(2)


if __name__ == "__main__":
    main()
