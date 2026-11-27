# -*- coding: utf-8 -*-
"""수정 가능한 PPT 그림 예시(가상 자료) — hr.py figs examples/ppt_figs/ 로 만든다.

그림 1개 = 슬라이드 1장. 그래프는 네이티브 차트(PowerPoint에서 「데이터 편집」), 도식은 도형, 사진만 그림 개체다.
"""
from pathlib import Path

from figlib import C, Rect, text_width

ORDER = 10                                        # 보고서 등장 순서
PHOTO = Path(__file__).resolve().parent.parent / "figs" / "ex_chart.jpg"


def build(deck):
    # 1) 산점 + 기준선 — 예측 대 측정
    f = deck.figure("ex_ppt_parity", "예측 모델의 시편 경도 예측값과 측정값의 비교")
    meas = [312, 318, 325, 331, 336, 342, 347, 351, 356, 362]
    pred = [315, 316, 327, 329, 338, 340, 349, 350, 358, 360]
    f.scatter(40, 70, 400, 380, series=[
        dict(name="시편", pts=list(zip(meas, pred))),
        dict(name="y = x", pts=[(300, 300), (370, 370)], kind="line", color=C["INK"], dash=True),
    ], xaxis=dict(title="측정 경도 (HV)", min=300, max=370, major=20),
       yaxis=dict(title="예측 경도 (HV)", min=300, max=370, major=20),
       legend=(0.22, 0.04, 0.34, 0.16))                  # 범례는 그림 영역 안 왼쪽 위(차트 대비 비율)
    f.note(250, 330, 170, 30, "R² = 0.97")              # 핵심 수치는 빈 곳에 — 위치는 렌더를 보고 정한다

    # 2) 묶은 막대 — 조건별 두 지표
    f = deck.figure("ex_ppt_bars", "공정 조건별 상대 밀도와 인장 강도")
    f.bars(40, 70, 760, 360, ["조건 A", "조건 B", "조건 C", "조건 D"], series=[
        dict(name="상대 밀도 (%)", values=[99.1, 99.6, 98.4, 99.8]),
        dict(name="정규화 인장 강도 (%)", values=[96.0, 98.5, 91.2, 99.0]),
    ], yaxis=dict(min=80, max=100, major=5), fmt="0.0", legend="b")      # 막대 위 값과 겹치지 않게 범례는 아래

    # 3) 도식 + 사진 — 처리 흐름
    f = deck.figure("ex_ppt_flow", "시편 영상 자동 분석 흐름")
    f.flow(40, 70, 760, 90, [("촬영", "광학 현미경"), ("전처리", "잡음 제거"), ("분할", "기공 검출"), ("집계", "기공률 계산")])
    r = f.picture(PHOTO, 0, 0, fit=Rect(40, 185, 760, 250))   # 그림 전체 폭은 760~840 pt(글자가 보고서에서 10 pt 이상)
    name = "분석 결과 예시"
    f.tag(r.r - text_width(name, 16) - 16 * 1.1 - 8, r.y + 8, name)   # 사진 위 흰 이름표(빈 귀퉁이에)
