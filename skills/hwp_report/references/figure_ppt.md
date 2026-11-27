# 수정 가능한 PPT 그림 — `HR figs`

작성자가 「그림을 수정 가능한 PPT로」, 「PowerPoint에서 고칠 수 있게」라고 하면 이 방법으로 만든다. 작성자가 그림을 직접 고쳐 보고서에 다시 붙이는 경우다. 그 밖에는 matplotlib 그림(`report-figure` 스킬)도 된다.

## 결과

| 파일 | 내용 |
|---|---|
| `그림_편집용.pptx` | 그림 1개 = 빈 슬라이드 1장. 그래프는 네이티브 차트(PowerPoint 「데이터 편집」으로 값 수정), 도식은 도형(화살표가 도형에 붙어 있음), 사진·화면만 그림 개체. 슬라이드 위쪽에 「그림 N. 캡션 (ID)」 머리글이 있다(이미지에는 안 들어감) |
| `<그림ID>.png`·`.jpg` | 보고서에 넣을 그림. 그림 범위만 잘라 400 dpi로 저장한다. 이 폴더를 spec의 `figures`로 쓴다(파일 이름 = 그림 ID) |
| `figures.json` | 그림 번호·ID·캡션·범위(pt)·픽셀 크기, PPTX 지문 |

## 절차

1. 그림 폴더(예: `그림/figs/`)에 주제마다 `fig_<주제>.py`를 만든다.
   - 모듈에는 `ORDER = 숫자`(보고서 등장 순서)와 `def build(deck)`를 둔다.
   - 예시는 `examples/ppt_figs/fig_example.py`에 있다. 산점+기준선, 묶은 막대, 흐름도+사진 예시다.
2. `HR figs 그림/figs --out 그림/out`을 실행한다. PPTX와 그림 이미지가 함께 나온다.
   - 그리는 프로그램은 OS마다 다르다.
     - Windows: PowerPoint(창 없이 사본을 열고 닫음) → 없으면 LibreOffice
     - macOS·Linux: LibreOffice → 없으면 PowerPoint
   - 둘 다 없으면 PPTX만 만들고 종료 코드 4로 끝난다. 이때는 PowerPoint에서 그림을 복사해 한글에 「그림으로 붙여넣기」 하라고 알린다.
3. **이미지를 직접 열어 본다.** 범례·수치 글상자·이름표가 점·막대·선과 겹치면 좌표를 고쳐 다시 돌린다.
4. **작성자가 PPTX를 고쳐 오면** `HR figs --from 고친.pptx --out 그림/out_v2`를 실행한다. 고친 판 그대로 이미지를 뽑는다.
   - 고친 PPTX를 모듈로 다시 만들어 덮어쓰지 않는다.
   - `HR figs`도 지난번에 만든 판과 다른 PPTX는 덮어쓰지 않고 멈춘다.

## figlib 사용법

좌표 단위는 pt다. 그림은 (40, 60)부터 그린다. 슬라이드 크기는 1058 × 595 pt다.

| 메서드 | 쓰임 |
|---|---|
| `f = deck.figure("id", "캡션")` | 그림 1개 시작. id는 영문 소문자·숫자·밑줄 |
| `f.scatter(x, y, w, h, series=[dict(name, pts=[(x, y), …], kind="point"/"line", color, marker, dash, labels={i: "글"})], xaxis, yaxis, legend)` | XY 산점·선. **점 계열을 선 계열보다 앞에** 둔다 |
| `f.lines(...)` | 꺾은선(scatter와 같은 인자, 기본 선) |
| `f.bars(x, y, w, h, ["범주", …], series=[dict(name, values=[…])], yaxis, horizontal, stacked, labels=True, fmt="0.0", legend)` | 막대 |
| `f.box(x, y, w, h, "글", fill, line, weight, shape="round"/"rect"/"diamond"/"chevron"/"ellipse")` | 글이 든 도형 |
| `f.arrow(a, b)` | 도형 a → b 화살표(도형에 붙음) |
| `f.flow(x, y, w, h, ["단계", …] 또는 [("제목", "설명"), …], orient="h"/"v", numbered)` | 단계 상자 + 화살표 |
| `f.picture(path, x, y, w=…)` 또는 `fit=Rect(x, y, w, h)` | 사진·화면 캡처(비율 유지) |
| `f.tag(x, y, "이름")` | 사진 위 흰 이름표(장비 이름 등) |
| `f.text(...)`, `f.note(x, y, w, h, "R² = 0.97")` | 글상자, 그래프 안 핵심 수치 |
| `f.placeholder(x, y, w, h)` | 아직 못 받은 사진 자리(점선) |

- 축 `xaxis`·`yaxis`: `dict(title="한글 축 제목 (단위)", min, max, major, fmt="0.0", grid=False)`
- 범례 `legend`
  - `None`: 범례 없음
  - `"b"`·`"r"`·`"t"`: 아래·오른쪽·위
  - `(x, y, w, h)`: 그림 영역 안. 차트 크기 대비 비율로 준다. 범례에서 뺄 계열 번호를 다섯째 값으로 줄 수 있다
- 색은 `C["BLUE"]`·`C["ORANGE"]`·`C["GRAY"]`·`C["GOLD"]`·`C["INK"]`·`C["RED"]`. Office 기본 색 순서다.

## 크기·양식

- **그림 폭 760~840 pt.** 그러면 보고서(165 mm)에서 18 pt 글자가 10 pt 이상으로 찍힌다. 폭이 788 pt를 넘으면 165 mm로 줄어든다. `HR figs`가 그림마다 찍히는 글자 크기를 알려 준다.
- 글자: 그래프·그림 모두 18 pt(`CHART_PT`·`TEXT_PT`).
- 글꼴: 기본은 맑은 고딕(Malgun Gothic)이다. `--font NanumGothic` 또는 환경변수 `HR_FIG_FONT`로 바꾼다. 무게별 글꼴(`Paperlogy`)도 된다.
- 양식은 `figure_rules.md`를 따른다.
  - 흰 배경
  - 그림 안 소제목·표·날짜 없음
  - 그림 영역 테두리, 눈금선 없음, 범례는 그림 영역 안 빈 곳
  - 핵심 수치는 그래프 안에 적는다
  - 축·범례는 한글
  - 모든 그래프의 양식을 통일한다
- 그림이 슬라이드 밖으로 나가면 저장할 때 멈춘다. 오류 메시지에 그림 ID와 범위가 나온다.
- LibreOffice로 그린 이미지는 글꼴·간격이 PowerPoint와 조금 다를 수 있다. 최종 확인은 PowerPoint로 한다.
