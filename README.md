# hwp-report-skills

연구보고서 한글(hwpx) 양식을 Claude Code로 채우는 스킬 묶음이다.

| 스킬 | 하는 일 |
|---|---|
| `hwp_report` | 국책 R&D 연구보고서(연차·연차점검·단계·최종)를 한글(hwpx)로 쓴다. 실제 보고서 두 건에서 작성자가 판마다 고친 곳과 최종 제출본을 대조해 뽑은 **작성 규칙·장별 작성법**을 따른다. 단독 양식은 YAML(spec) 한 장으로 hwpx를 만들고, 주관기관이 보낸 통합 양식에는 남의 글·표·메모를 그대로 둔 채 우리 칸만 채운다. 한컴 PDF로 꼬리 줄·쪽 빈칸을 확인하고, 작성자 수정본은 덮어쓰지 않고 거둬들여 수정 포인트를 규칙으로 쌓는다 |
| `report-figure` | 보고서용 그림을 실데이터 논문식으로 만든다(matplotlib, 한글 라벨, 400 dpi) |

## 설치 (한 번)

```bash
git clone https://github.com/Chihun-Lee/hwp-report-skills.git ~/hwp-report-skills
bash ~/hwp-report-skills/install.sh
```

- `~/.claude/skills/`에 두 스킬이 연결되고, 파이썬 패키지가 `~/.hwp_report/venv`에 설치된다. 끝에 자가검사(`selftest OK`)가 돈다.
- **필요**: macOS 또는 Linux, Python 3.9+, git
- **있으면 좋음**: Node 18+와 `librsvg`(미리보기), `poppler`(쪽 빈칸 측정), 한컴오피스(PDF 확인)
  - macOS: `brew install node librsvg poppler` (꼬리 줄 검사 `tail`은 poppler가 필요)

Claude Code 플러그인으로도 설치할 수 있다. 이 경우 스킬 이름 앞에 `hwp-report:`가 붙는다.

```bash
claude plugin marketplace add Chihun-Lee/hwp-report-skills
claude plugin install hwp-report@hwp-report-skills
bash ~/.claude/plugins/marketplaces/hwp-report-skills/skills/hwp_report/scripts/setup.sh   # 파이썬 패키지
```

## 쓰기

Claude Code에서 다음처럼 말하면 된다.
- 「연차보고서 만들어줘」, 「국책보고서 써줘」 또는 `/hwp_report`
- 「주관기관이 보낸 통합 양식에 우리 파트 옮겨 적어줘」
- 「내가 한컴에서 고친 거 반영해서 v02 만들어줘」, 「내가 고친 포인트 정리해줘」

주요 명령(`bash skills/hwp_report/scripts/hwp_report.sh <명령>`):

| 명령 | 하는 일 |
|---|---|
| `build` · `check` | spec → hwpx, 게이트(구조 + 작성 규칙 + 제출 전 잔여물). `check --form 원본양식.hwpx`는 통합 양식의 우리 글만 검사 |
| `learn 이전.hwpx 수정본.hwpx` | 작성자가 무엇을 어떻게 고쳤는지 표로(유형별 횟수, 반복 치환 = 규칙 후보) |
| `extract` · `diff` | 수정본 → spec 왕복, 차이 0 확인 |
| `dump 문서.hwpx` | 모든 구역의 문단·표 칸·모양 번호·메모 덤프(통합 양식에서 우리 칸 찾기) |
| `pdf` · `tail` · `fill` | 한컴 PDF(사본으로, 입력 중엔 기다림) → 꼬리 줄 → 쪽 빈칸 |

**처음 쓸 때**는 Claude가 두 가지를 묻는다.
1. **문체**: 기본(기관 보고서 표준 개조식) / 내 문체 만들기(직접 쓴 보고서 3~10개를 주면 분석) / 설치된 문체 스킬
2. **양식**: 기본(양식1 구조 예시) / 다른 양식(기관에서 받은 실제 양식 hwpx를 주면 등록)

설정은 `~/.hwp_report/config.yaml`에 저장된다. 나중에 「문체 바꿔줘」, 「양식 바꿔줘」로 바꾸면 된다.

| 경로 | 내용 |
|---|---|
| `~/.hwp_report/config.yaml` | 문체·양식 설정 |
| `~/.hwp_report/style.md` | 내 문체 가이드(만든 경우) |
| `~/.hwp_report/forms/<이름>/` | 등록한 양식 |

## 업데이트·삭제

```bash
cd ~/hwp-report-skills && git pull           # 심링크 설치면 이것으로 끝
rm ~/.claude/skills/hwp_report ~/.claude/skills/report-figure && rm -rf ~/.hwp_report   # 삭제
```

## 주의

- 요약표에는 연락처·국가연구자번호가 들어간다. **보고서 spec(YAML)을 남과 나눌 때는 그 칸을 지운다.**
- 보고서 내용은 Claude(Anthropic)로 전송된다. 보안 등급이 있는 과제는 기관 보안 기준을 먼저 확인한다.
- 이 도구는 파일만 만든다. 상신·제출은 사람이 한다.

## 라이선스·출처

- 스킬 코드·문서: Chihun Lee, 2026.
- `skills/hwp_report/vendor/rhwp/`: rhwp(@rhwp/core 0.7.10, Edward Kim), MIT. 원문은 같은 폴더 LICENSE.
- 예시 양식: 연차점검 보고서 양식1의 구조만 남기고 기관명·사업명·안내문을 ○○로 바꾼 것. 실제 자료는 들어 있지 않다.
