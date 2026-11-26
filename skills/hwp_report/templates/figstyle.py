# -*- coding: utf-8 -*-
"""논문 figure 공통 스타일 (실데이터 그림 전용 — 생성 이미지·픽토그램 사용 안 함)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as _fm

_HAVE = {f.name for f in _fm.fontManager.ttflist}


def _pick(*names):
    return [n for n in names if n in _HAVE]


# 영문·숫자는 Arial, 한글은 이 컴퓨터에 있는 글꼴로 자동 대체
#   macOS: 나눔고딕 → 애플 SD 고딕 · Windows: 맑은 고딕 · Linux: Noto Sans CJK
LATIN = (_pick("Arial", "Liberation Sans", "Helvetica") or ["DejaVu Sans"])[:1]
KOREAN = _pick("Nanum Gothic", "NanumGothic", "Malgun Gothic", "Apple SD Gothic Neo", "AppleGothic",
               "Noto Sans CJK KR", "Noto Sans KR")[:1]
# 굵은 한글: 나눔고딕 ttc의 굵은체는 matplotlib이 못 읽으므로 굵은체 파일이 따로 있는 글꼴을 먼저 쓴다
KOREAN_BOLD = (_pick("KoPubDotum", "KoPubWorldDotum", "Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR") or KOREAN)[:1]
if not KOREAN:
    import sys
    print("⚠️ figstyle: 한글 글꼴 없음 — 나눔고딕 또는 맑은 고딕을 설치해야 한글이 네모로 안 나온다", file=sys.stderr)

MM = 1 / 25.4
FULL_W = 178 * MM          # 두 단 폭(보고서 본문 폭 170 mm에 거의 1:1로 들어감)
# 글자 기준: 본문 9 pt, 패널 제목 9.5~10 pt, 표 9 pt 이상, 최소 7.5 pt

C = dict(navy="#1F3A5F", blue="#3C7DB5", teal="#2BA59A", green="#5FA83A",
         orange="#E07B39", red="#C8423A", gray="#8A8F98", light="#D9DEE4")
SERIES = ["#3C7DB5", "#E07B39", "#5FA83A", "#8E5BB5", "#1F3A5F"]   # 계열 색 순서

plt.rcParams.update({
    "font.family": LATIN + KOREAN + ["DejaVu Sans"],   # 영문·숫자 Arial, 한글은 있는 글꼴로 자동 대체
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9.5,
    "axes.linewidth": 0.7,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "legend.fontsize": 8.5,
    "legend.frameon": False,
    "lines.linewidth": 1.0,
    "savefig.dpi": 400,
    "pdf.fonttype": 42,
    "axes.spines.top": True,
    "axes.spines.right": True,
})


def panel(ax, letter, x=-0.02, y=1.02):
    """Nature식 굵은 소문자 패널 라벨"""
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=12, fontweight="bold",
            va="bottom", ha="right")


def img_ax(ax, img, title=None, scalebar=None):
    """사진·현미경 이미지 패널: 축 숨김, 선택적 스케일바 (len_px, label)"""
    ax.imshow(img, cmap="gray" if img.ndim == 2 else None)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.4); s.set_color("#666")
    if title:
        ax.set_title(title, pad=2)
    if scalebar:
        L, lab = scalebar
        h, w = img.shape[:2]
        x0, y0 = w * 0.95 - L, h * 0.93
        import matplotlib.patheffects as pe
        st = [pe.withStroke(linewidth=1.6, foreground="black")]
        ax.plot([x0, x0 + L], [y0, y0], color="white", lw=2.2, solid_capstyle="butt", path_effects=st)
        ax.text(x0 + L / 2, y0 - h * 0.025, lab, color="white", ha="center", va="bottom", fontsize=8.5,
                fontweight="bold", path_effects=st)


def tern_xy(a, b, c):
    """3원 조성(합=1) → 정삼각형 좌표 (a: 오른쪽 아래, b: 위, c: 왼쪽 아래 기준)"""
    a, b, c = np.asarray(a, float), np.asarray(b, float), np.asarray(c, float)
    s = a + b + c
    a, b, c = a / s, b / s, c / s
    x = a + 0.5 * b
    y = np.sqrt(3) / 2 * b
    return x, y


def tern_frame(ax, labels, grid=True):
    """정삼각형 틀 + 10% 격자 + 꼭짓점 라벨 (labels=(right, top, left))"""
    tri = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3) / 2], [0, 0]])
    ax.plot(tri[:, 0], tri[:, 1], color="k", lw=0.6)
    if grid:
        for f in np.arange(0.2, 1.0, 0.2):
            for (p, q) in [((f, 0, 1 - f), (f, 1 - f, 0)), ((0, f, 1 - f), (1 - f, f, 0)),
                           ((1 - f, 0, f), (0, 1 - f, f))]:
                x, y = tern_xy([p[0], q[0]], [p[1], q[1]], [p[2], q[2]])
                ax.plot(x, y, color="#C9CED6", lw=0.35, zorder=0)
    r, t, l = labels
    ax.text(1.02, -0.03, r, ha="left", va="top", fontsize=9.5)
    ax.text(0.5, np.sqrt(3) / 2 + 0.03, t, ha="center", va="bottom", fontsize=9.5)
    ax.text(-0.02, -0.03, l, ha="right", va="top", fontsize=9.5)
    ax.set_xlim(-0.08, 1.08); ax.set_ylim(-0.08, 0.95)
    ax.set_aspect("equal"); ax.axis("off")


def save(fig, path):
    fig.savefig(path, dpi=400, bbox_inches="tight", pad_inches=0.015, facecolor="white")
    fig.savefig(str(path).rsplit(".", 1)[0] + ".pdf", bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)
    from PIL import Image                      # hwpx·pptx 삽입용 jpg (보고서 빌드는 jpg를 쓴다)
    Image.open(path).convert("RGB").save(str(path).rsplit(".", 1)[0] + ".jpg", quality=92)


# ── 그림 안 a·b·c 패널 글자 없음, 소제목은 볼드 ─────────────────
# 볼드 한글은 KOREAN_BOLD(KoPub돋움 → 맑은 고딕 → Noto 순, 위에서 고름)로 쓴다.
BOLD_KO = dict(family=LATIN + KOREAN_BOLD, weight="bold")
SPLIT_W = 140 * MM         # 본문 사이에 넣는 분할 그림 설계 폭(보고서에 1:1로 들어감, 본문 170 mm의 약 80 %)


def btitle(ax, text, size=9.5, loc="center", pad=3, **kw):
    """볼드 소제목 (패널 글자 대신)"""
    return ax.set_title(text, fontsize=size, loc=loc, pad=pad, fontdict=BOLD_KO, **kw)


def btext(ax_or_fig, x, y, text, size=9.5, **kw):
    """볼드 한글 텍스트 (fig.text 또는 ax.text)"""
    return ax_or_fig.text(x, y, text, fontsize=size, **BOLD_KO, **kw)
