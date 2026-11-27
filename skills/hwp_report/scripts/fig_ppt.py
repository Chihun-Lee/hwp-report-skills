# -*- coding: utf-8 -*-
"""그림 모듈 → 수정 가능한 PPTX 1개 + 보고서에 넣을 그림 PNG·JPG.   (hr.py figs 가 부른다)

    hr.py figs <폴더|fig_*.py ...> [--out 폴더] [--pptx 파일] [--engine auto|powerpoint|libreoffice|none]
    hr.py figs --from 작성자가_고친.pptx --out 폴더        고친 PPTX를 다시 그림으로 뽑기

- 그림 모듈: `ORDER = 숫자`(보고서 등장 순서, 작을수록 앞)와 `def build(deck)`를 둔다. figlib.py 사용법은 그 파일 머리말.
  폴더를 주면 그 안의 fig_*.py를 모두 모은다.
- 결과(<out>, 기본 = 첫 모듈 폴더 옆 <폴더>_out)
    그림_편집용.pptx   그림 1개 = 슬라이드 1장. 작성자가 PowerPoint에서 고치는 원본
    <그림ID>.png·jpg   보고서에 넣을 그림(그림 범위만 잘라 냄). hwp_report spec의 figures 폴더로 쓴다
    figures.json       그림 번호·ID·캡션·범위·픽셀 크기
- 그림 이미지는 PPTX를 실제 프로그램으로 그려서 자른다.
    Windows: PowerPoint(창 없이 사본을 열고 닫음, 열려 있던 다른 프레젠테이션은 그대로) → 없으면 LibreOffice
    macOS·Linux: LibreOffice → 없으면 PowerPoint(macOS)
    둘 다 없으면 PPTX만 만든다(종료 코드 4) — PowerPoint에서 그림을 복사해 「그림으로 붙여넣기」 하면 된다.
- 작성자가 고친 PPTX는 덮어쓰지 않는다. 지난번에 만든 PPTX와 내용이 다르면 멈추고 --from 이나 새 --pptx 이름을 쓰라고 알린다.
종료 코드: 0 성공 · 2 인자·환경 오류 · 4 그릴 프로그램 없음(PPTX만 만듦) · 6 그리기 실패 · 7 시간 초과
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
EMU = 12700.0

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ── 그림 모듈 모으기 ──────────────────────────────────────────────────
def load_modules(inputs):
    files = []
    for x in inputs:
        p = Path(x).resolve()
        if p.is_dir():
            files += sorted(p.glob("fig_*.py"))
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"없음: {p}")
    if not files:
        sys.exit("그림 모듈(fig_*.py)이 없다")
    sys.path.insert(0, str(HERE))                       # from figlib import …
    mods = []
    for f in files:
        sys.path.insert(0, str(f.parent))               # 같은 폴더의 도우미 모듈
        spec = importlib.util.spec_from_file_location(f"hrfig_{f.stem}", f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        if not hasattr(m, "build"):
            sys.exit(f"{f.name}: def build(deck) 가 없다")
        mods.append(m)
    return sorted(mods, key=lambda m: getattr(m, "ORDER", 50)), files


# ── PPTX에서 그림 범위 읽기(작성자가 고친 판도 같은 방법) ─────────────
def meta_from_pptx(path):
    from pptx import Presentation
    prs = Presentation(str(path))
    size = (prs.slide_width / EMU, prs.slide_height / EMU)
    meta = []
    for i, sl in enumerate(prs.slides, 1):
        fid, cap, ext = None, "", None
        for sh in sl.shapes:
            nm = sh.name or ""
            if nm.endswith(":header"):                  # 그림 번호·캡션 머리글 — 그림 범위에서 뺀다
                fid = nm[: -len(":header")]
                cap = sh.text_frame.text if sh.has_text_frame else ""
                continue
            if sh.width is None or sh.left is None:
                continue
            x, y, w, h = sh.left / EMU, sh.top / EMU, sh.width / EMU, sh.height / EMU
            ext = [x, y, x + w, y + h] if ext is None else \
                [min(ext[0], x), min(ext[1], y), max(ext[2], x + w), max(ext[3], y + h)]
        if ext is None:
            ext = [0, 0, size[0], size[1]]
        meta.append(dict(no=i, id=fid or f"slide{i:02d}", caption=cap,
                         bbox=[round(ext[0], 2), round(ext[1], 2), round(ext[2] - ext[0], 2), round(ext[3] - ext[1], 2)]))
    return meta, size


# ── 그리기(PPTX → PDF) ───────────────────────────────────────────────
def find_soffice():
    for c in ("soffice", "libreoffice"):
        p = shutil.which(c)
        if p:
            return p
    cands = [r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
             "/Applications/LibreOffice.app/Contents/MacOS/soffice", "/opt/homebrew/bin/soffice", "/usr/bin/soffice"]
    return next((c for c in cands if Path(c).exists()), None)


def has_powerpoint():
    if WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\CLSID"):
                return True
        except OSError:
            return False
    if MAC:
        return Path("/Applications/Microsoft PowerPoint.app").exists()
    return False


def engines(choice):
    if choice == "none":
        return []
    if choice != "auto":
        return [choice]
    pp, lo = has_powerpoint(), bool(find_soffice())
    order = ["powerpoint", "libreoffice"] if WIN else ["libreoffice", "powerpoint"]
    return [e for e in order if (pp if e == "powerpoint" else lo)]


def pdf_libreoffice(pptx, pdf, timeout):
    so = find_soffice()
    if not so:
        raise RuntimeError("LibreOffice 없음")
    tmp = Path(tempfile.mkdtemp(prefix="hr_lo_"))
    try:
        src = tmp / "figs.pptx"
        shutil.copy2(pptx, src)
        subprocess.run([so, "--headless", "--norestore", f"-env:UserInstallation={(tmp / 'profile').as_uri()}",
                        "--convert-to", "pdf", "--outdir", str(tmp), str(src)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        out = tmp / "figs.pdf"
        if not out.exists():
            raise RuntimeError("LibreOffice PDF 변환 실패")
        shutil.move(str(out), str(pdf))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_powerpoint_win(pptx, pdf, timeout):
    import pythoncom
    import win32com.client
    import win32com.client.dynamic
    tmp = Path(tempfile.mkdtemp(prefix="hr_pp_"))
    copy = tmp / f"HRFIG_{datetime.now():%H%M%S}.pptx"
    shutil.copy2(pptx, copy)
    out = tmp / (copy.stem + ".pdf")

    def on_timeout():
        print(f"⏱ PowerPoint가 {timeout:.0f}초 안에 끝나지 않음 — 확인 창이 떠 있을 수 있다. 작업 표시줄의 PowerPoint를 확인한다")
        os._exit(7)

    timer = threading.Timer(timeout, on_timeout)
    timer.daemon = True
    timer.start()
    pythoncom.CoInitialize()
    try:
        try:
            win32com.client.GetActiveObject("PowerPoint.Application")
            running = True
        except Exception:  # noqa: BLE001
            running = False
        app = win32com.client.dynamic.Dispatch("PowerPoint.Application")
        pres = app.Presentations.Open(str(copy), -1, 0, 0)        # 읽기 전용 · 제목 있음 · 창 없음
        try:
            try:
                pres.SaveAs(str(out), 32)                         # ppSaveAsPDF
            except Exception:  # noqa: BLE001
                pres.ExportAsFixedFormat(str(out), 2)             # ppFixedFormatTypePDF
        finally:
            pres.Close()
        if not running:
            try:
                if int(app.Presentations.Count) == 0:
                    app.Quit()
            except Exception:  # noqa: BLE001
                pass
        if not out.exists():
            raise RuntimeError("PowerPoint PDF 저장 실패")
        shutil.move(str(out), str(pdf))
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
        timer.cancel()
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_powerpoint_mac(pptx, pdf, timeout):
    g = Path.home() / "Library" / "Group Containers" / "UBF8T346G9.Office"   # Office 샌드박스 권한 창을 피하는 위치
    base = g if g.is_dir() else Path(tempfile.mkdtemp(prefix="hr_pp_"))
    name = f"_hr_fig_{os.getpid()}.pptx"
    src, out = base / name, base / (name[:-5] + ".pdf")
    shutil.copy2(pptx, src)
    script = f'''with timeout of {int(timeout)} seconds
tell application "Microsoft PowerPoint"
  open POSIX file "{src}"
  set p to presentation "{name}"
  save p in POSIX file "{out}" as save as PDF
  close p saving no
end tell
end timeout'''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=timeout + 30)
        if r.returncode or not out.exists():
            raise RuntimeError("PowerPoint PDF 저장 실패: " + r.stderr.decode(errors="replace")[-300:])
        shutil.move(str(out), str(pdf))
    finally:
        src.unlink(missing_ok=True)


def to_pdf(engine, pptx, pdf, timeout):
    if engine == "libreoffice":
        return pdf_libreoffice(pptx, pdf, timeout)
    if WIN:
        return pdf_powerpoint_win(pptx, pdf, timeout)
    if MAC:
        return pdf_powerpoint_mac(pptx, pdf, timeout)
    raise RuntimeError("이 운영체제에는 PowerPoint가 없다")


# ── 자르기 ───────────────────────────────────────────────────────────
def crop(pdf, meta, size, out, dpi, margin=3.0):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    from PIL import Image
    doc = pymupdf.open(str(pdf))
    if doc.page_count != len(meta):
        raise RuntimeError(f"쪽 수 {doc.page_count} ≠ 그림 수 {len(meta)}")
    k = dpi / 72.0
    for page, m in zip(doc, meta):
        sx, sy = page.rect.width / size[0], page.rect.height / size[1]
        x, y, w, h = m["bbox"]
        clip = pymupdf.Rect((x - margin) * sx, (y - margin) * sy, (x + w + margin) * sx, (y + h + margin) * sy) & page.rect
        pix = page.get_pixmap(matrix=pymupdf.Matrix(k / sx, k / sy), clip=clip, alpha=False)
        png = out / f"{m['id']}.png"
        pix.save(str(png))
        with Image.open(png) as im:
            im.convert("RGB").save(out / f"{m['id']}.jpg", quality=92, dpi=(dpi, dpi))
            m["px"] = list(im.size)
    doc.close()


def main():
    ap = argparse.ArgumentParser(prog="hr.py figs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="그림 모듈 폴더 또는 fig_*.py")
    ap.add_argument("--from", dest="src", help="이미 있는 PPTX(작성자가 고친 판)를 그림으로 뽑는다")
    ap.add_argument("--out", help="그림 PNG·JPG 폴더")
    ap.add_argument("--pptx", help="저장할 PPTX (기본 <out>/그림_편집용.pptx)")
    ap.add_argument("--engine", default="auto", choices=["auto", "powerpoint", "libreoffice", "none"])
    ap.add_argument("--font", help="그림 글꼴 (기본 Malgun Gothic, 예: NanumGothic, Paperlogy)")
    ap.add_argument("--dpi", type=int, default=400)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--force", action="store_true", help="고친 흔적이 있는 PPTX도 덮어쓴다")
    a = ap.parse_args()
    if importlib.util.find_spec("pptx") is None:
        print("python-pptx 없음 → hr.py setup --figures")
        sys.exit(2)
    if not a.inputs and not a.src:
        ap.error("그림 모듈 폴더(또는 fig_*.py)나 --from PPTX가 필요하다")

    if a.src:
        pptx_path = Path(a.src).resolve()
        if not pptx_path.is_file():
            sys.exit(f"없음: {pptx_path}")
        out = Path(a.out).resolve() if a.out else pptx_path.with_name(pptx_path.stem + "_그림")
        out.mkdir(parents=True, exist_ok=True)
    else:
        from figlib import FigureDeck  # noqa: E402  (load_modules가 경로를 넣은 뒤)
        mods, files = load_modules(a.inputs)
        first = files[0].parent
        out = Path(a.out).resolve() if a.out else first.with_name(first.name + "_out")
        out.mkdir(parents=True, exist_ok=True)
        pptx_path = Path(a.pptx).resolve() if a.pptx else out / "그림_편집용.pptx"
        rec = out / "figures.json"
        if pptx_path.exists() and not a.force:
            old = json.loads(rec.read_text(encoding="utf-8")).get("pptx_sha256") if rec.exists() else None
            if old != sha(pptx_path):
                print(f"⚠️ {pptx_path.name}은 지난번에 만든 판과 다르다(작성자가 고친 것일 수 있다) — 덮어쓰지 않는다.\n"
                      f"  · 고친 판을 그림으로 뽑기: hr.py figs --from \"{pptx_path}\" --out <폴더>\n"
                      "  · 새 판은 다른 이름으로: --pptx <새 이름.pptx>   · 그래도 덮어쓰기: --force")
                sys.exit(2)
        deck = FigureDeck(font=a.font)
        for m in mods:
            m.build(deck)
        deck.save(pptx_path)
        pptx_path.with_suffix(".figures.json").unlink(missing_ok=True)      # figlib가 남기는 사본은 figures.json 하나로
    meta, size = meta_from_pptx(pptx_path)
    print(f"PPTX {pptx_path} — 그림 {len(meta)}개")

    code = 0
    order = engines(a.engine)
    if not order:
        if a.engine == "auto":
            print("· PowerPoint·LibreOffice가 없어 그림 이미지는 만들지 않음 — PPTX만 만들었다.\n"
                  "  PowerPoint에서 그림을 골라 복사 → 한글에서 「그림으로 붙여넣기」, 또는 LibreOffice 설치 후 다시 실행")
            code = 4
    else:
        tmp = Path(tempfile.mkdtemp(prefix="hr_figs_"))
        pdf = tmp / "render.pdf"
        done = None
        for eng in order:
            t0 = time.time()
            try:
                to_pdf(eng, pptx_path, pdf, a.timeout)
                crop(pdf, meta, size, out, a.dpi)
                done = eng
                print(f"그리기: {'PowerPoint' if eng == 'powerpoint' else 'LibreOffice'} ({time.time() - t0:.0f}초)")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  ({eng} 실패: {e})")
        shutil.rmtree(tmp, ignore_errors=True)
        if not done:
            print("그림 이미지를 만들지 못함 — PPTX는 만들어졌다")
            code = 6
        else:
            for m in meta:
                w = m["bbox"][2]
                print(f"  {m['no']:2d} {m['id']:<24} {m['px'][0]}×{m['px'][1]} px · 폭 {w:.0f} pt "
                      f"(보고서 165 mm에서 18 pt 글자 → {18 * min(1.0, 787.6 / w) * 0.594:.1f} pt)")
            if done == "libreoffice":
                print("  · LibreOffice 그림은 글꼴·간격이 PowerPoint와 조금 다를 수 있다(최종 확인은 PowerPoint)")
    info = dict(pptx=str(pptx_path), pptx_sha256=sha(pptx_path), figures=meta)
    if not a.src:
        (out / "figures.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        (out / "figures.json").write_text(json.dumps(dict(info, source="--from"), ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(f"→ {out}")
    sys.exit(code)


if __name__ == "__main__":
    main()
