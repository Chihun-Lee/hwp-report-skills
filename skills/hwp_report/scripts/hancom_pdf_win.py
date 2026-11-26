# -*- coding: utf-8 -*-
"""Windows 한컴오피스 한글로 hwpx → PDF (쪽 나눔·줄바꿈 최종 확인용).

    python hancom_pdf_win.py report.hwpx [-o report.pdf] [--timeout 300] [--show]
    python hancom_pdf_win.py --status          보안 모듈 등록 상태만 보기
    python hancom_pdf_win.py --register-only   보안 모듈만 등록(setup이 부른다)

- 원본이 아니라 임시 폴더의 사본 HRQA_<시각>_<이름>.hwpx 를 연다. 원본과 작성자가 열어 둔 한글 창은 건드리지 않는다.
- 한글을 새로 띄워(창 숨김) COM(HWPFrame.HwpObject)으로 열고 PDF로 저장한 뒤 그 문서만 버리고 닫는다.
  그 한글에 다른 문서가 없을 때만 한글을 끝낸다.
- 「한글을 이용하여 파일에 접근하려는 시도」 보안 창: 보안 모듈(FilePathCheckerModule.dll)이 등록돼 있으면 뜨지 않는다.
  setup이 pyhwpx(MIT) 패키지의 DLL을 ~/.hwp_report/ 에 복사하고 HKCU\\Software\\HNC\\HwpAutomation\\Modules 에 등록한다.
  등록이 안 돼 있으면 한글 창을 보이게 띄우므로, 보안 창이 뜨면 「모두 허용」을 누른다.
- 필요: 한컴오피스 한글(2018 이후), pywin32(setup이 설치).
종료 코드: 0 성공 · 2 인자·환경 오류 · 5 한글 COM을 띄우지 못함 · 6 열기·PDF 저장 실패 · 7 시간 초과
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("HWP_REPORT_HOME") or (Path.home() / ".hwp_report")).expanduser()
REG_KEYS = (r"Software\HNC\HwpAutomation\Modules", r"Software\Hnc\HwpUserAction\Modules")
VALUE = "FilePathCheckerModule"
DLL_NAMES = ("FilePathCheckerModule.dll", "FilePathCheckerModuleExample.dll")
MSGBOX_OK = 0x1 | 0x10          # 「확인」만 있는 창 → 확인, 「확인/취소」 창 → 확인 (예/아니오 창은 그대로 둔다)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


# ── 보안 모듈 ─────────────────────────────────────────────────────────
def registered_dll():
    import winreg
    for sub in REG_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
                v, _ = winreg.QueryValueEx(k, VALUE)
                if v and Path(v).is_file():
                    return Path(v)
        except OSError:
            pass
    return None


def find_dll():
    cands = []
    if os.environ.get("HWP_SECURITY_DLL"):
        cands.append(Path(os.environ["HWP_SECURITY_DLL"]))
    cands += [HOME / n for n in DLL_NAMES]
    spec = importlib.util.find_spec("pyhwpx")        # 패키지를 import하지 않고 위치만 찾는다
    for loc in (spec.submodule_search_locations or []) if spec else []:
        cands += [Path(loc) / n for n in DLL_NAMES]
    return next((c for c in cands if c.is_file()), None)


def ensure_security_module(quiet=False):
    """등록된 DLL 경로를 돌려준다. 없으면 찾아서 ~/.hwp_report/ 로 복사해 HKCU에 등록한다."""
    cur = registered_dll()
    if cur:
        return cur
    dll = find_dll()
    if not dll:
        if not quiet:
            print("· 한글 보안 모듈 없음 — 파일 접근 확인 창이 뜨면 「모두 허용」을 누른다 (hr.py setup 으로 설치 가능)")
        return None
    HOME.mkdir(parents=True, exist_ok=True)
    stable = HOME / "FilePathCheckerModule.dll"
    if dll.resolve() != stable.resolve():
        shutil.copy2(dll, stable)
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEYS[0], 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, str(stable))
    if not quiet:
        print(f"✓ 한글 보안 모듈 등록: HKCU\\{REG_KEYS[0]}\\{VALUE} = {stable}")
    return stable


# ── 한글 COM ─────────────────────────────────────────────────────────
def save_pdf(hwp, path):
    """pyhwpx와 같은 순서: FileSaveAs_S(PDF) → FileSaveAsPdf → SaveAs"""
    for action, attr in (("FileSaveAs_S", 0), ("FileSaveAsPdf", 16384)):
        try:
            pset = hwp.HParameterSet.HFileOpenSave
            hwp.HAction.GetDefault(action, pset.HSet)
            pset.filename = str(path)
            pset.Format = "PDF"
            pset.Attributes = attr
            if hwp.HAction.Execute(action, pset.HSet) and wait_file(path, 60):
                return True
        except Exception as e:  # noqa: BLE001
            print(f"  ({action} 실패: {e})")
    try:
        return bool(hwp.SaveAs(str(path), "PDF", "")) and wait_file(path, 60)
    except Exception as e:  # noqa: BLE001
        print(f"  (SaveAs 실패: {e})")
        return False


def wait_file(path, limit):
    """파일이 생기고 크기가 멈출 때까지 기다린다(큰 문서는 저장이 늦게 끝난다)."""
    t0, last = time.time(), -1
    while time.time() - t0 < limit:
        if path.exists():
            sz = path.stat().st_size
            if sz > 0 and sz == last:
                return True
            last = sz
        time.sleep(0.7)
    return path.exists() and path.stat().st_size > 0


def close_doc(hwp):
    for f in (lambda: hwp.XHwpDocuments.Active_XHwpDocument.Clear(1),   # 1 = 저장하지 않고 버림
              lambda: hwp.Clear(1)):
        try:
            f()
            return
        except Exception:  # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hwpx", nargs="?")
    ap.add_argument("-o", "--output", help="PDF 경로 (기본: hwpx 옆 같은 이름 .pdf)")
    ap.add_argument("--timeout", type=float, default=300, help="전체 제한 시간(초)")
    ap.add_argument("--show", action="store_true", help="한글 창을 보이게 띄움")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--register-only", action="store_true")
    a, _unknown = ap.parse_known_args()      # macOS용 인자(대기초 등)가 와도 무시

    if os.name != "nt":
        sys.exit("Windows 전용 — macOS는 hancom_pdf.sh")
    if a.status:
        d = registered_dll()
        print(("✓ 한글 보안 모듈 등록됨: " + str(d)) if d else "· 한글 보안 모듈 미등록 — PDF 때 「모두 허용」 창이 뜰 수 있음")
        return
    if a.register_only:
        ensure_security_module()
        return
    if not a.hwpx:
        ap.error("hwpx 경로가 필요하다")
    src = Path(a.hwpx).resolve()
    if not src.is_file():
        print(f"파일 없음: {src}")
        sys.exit(2)
    out = Path(a.output).resolve() if a.output else src.with_suffix(".pdf")
    try:
        import pythoncom
        import win32com.client
        import win32com.client.dynamic
    except ImportError:
        print("pywin32 없음 → hr.py setup")
        sys.exit(2)

    tmp = Path(tempfile.mkdtemp(prefix="hwp_report_qa_"))
    copy = tmp / f"HRQA_{datetime.now():%H%M%S}_{src.name}"
    shutil.copy2(src, copy)
    tmp_pdf = tmp / (copy.stem + ".pdf")
    sec = ensure_security_module()
    show = a.show or sec is None              # 보안 창을 눌러야 하면 창을 보이게

    def on_timeout():
        print(f"\n⏱ {a.timeout:.0f}초 안에 끝나지 않음 — 한글에 확인 창이 떠 있을 수 있다.\n"
              "  작업 표시줄의 한글 창에서 확인 창을 닫거나, 작업 관리자에서 HRQA 문서를 연 Hwp.exe를 끝낸다.\n"
              f"  임시 폴더: {tmp}")
        os._exit(7)

    timer = threading.Timer(a.timeout, on_timeout)
    timer.daemon = True
    timer.start()
    t0 = time.time()
    pythoncom.CoInitialize()
    hwp, code = None, 0
    try:
        try:
            hwp = win32com.client.dynamic.Dispatch("HWPFrame.HwpObject")   # 새 한글 인스턴스(기존 창과 별개)
        except Exception as e:  # noqa: BLE001
            print(f"한글 COM을 띄우지 못함: {e}\n  한컴오피스 한글이 설치돼 있는지, 한 번 직접 실행해 초기 설정을 마쳤는지 확인")
            code = 5
            return
        if sec is not None:
            try:
                if not hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"):
                    print("· 보안 모듈을 쓰지 못함 — 확인 창이 뜨면 「모두 허용」")
                    show = True
            except Exception:  # noqa: BLE001
                show = True
        try:
            hwp.XHwpWindows.Item(0).Visible = bool(show)
        except Exception:  # noqa: BLE001
            pass
        try:
            hwp.SetMessageBoxMode(MSGBOX_OK)
        except Exception:  # noqa: BLE001
            pass
        opened = False
        for fmt, arg in (("", "forceopen:true"), ("HWPX", "forceopen:true"), ("", "")):
            try:
                if hwp.Open(str(copy), fmt, arg):
                    opened = True
                    break
            except Exception as e:  # noqa: BLE001
                print(f"  (열기 실패 {fmt or '자동'}: {e})")
        if not opened:
            print(f"한글에서 열지 못함: {src.name}")
            code = 6
            return
        try:
            pages = hwp.PageCount
        except Exception:  # noqa: BLE001
            pages = "?"
        if not save_pdf(hwp, tmp_pdf):
            print("PDF 저장 실패")
            code = 6
            return
        try:
            if out.exists():
                out.unlink()
            shutil.move(str(tmp_pdf), str(out))
        except PermissionError:
            alt = out.with_name(f"{out.stem}_{datetime.now():%H%M%S}.pdf")
            shutil.move(str(tmp_pdf), str(alt))
            print(f"· {out.name}이 다른 프로그램에 열려 있어 다른 이름으로 저장")
            out = alt
        print(f"✓ PDF {out}  ({pages}쪽, {time.time() - t0:.0f}초)")
    finally:
        if hwp is not None:
            close_doc(hwp)
            try:
                n = int(hwp.XHwpDocuments.Count)
            except Exception:  # noqa: BLE001
                n = 1
            if n <= 1:
                try:
                    hwp.Quit()
                except Exception:  # noqa: BLE001
                    pass
            else:
                print(f"· 이 한글에 다른 문서 {n - 1}개가 있어 한글은 끄지 않음")
            hwp = None
        try:
            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
        timer.cancel()
        shutil.rmtree(tmp, ignore_errors=True)
        if code:
            sys.exit(code)


if __name__ == "__main__":
    main()
