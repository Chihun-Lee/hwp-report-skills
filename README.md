# hwp-report-skills

국책 R&D 연구보고서를 한글(hwpx) 양식에 맞춰 Claude Code로 쓰는 스킬 묶음이다. **Windows·macOS** 모두 쓸 수 있다.

| 스킬 | 하는 일 |
|---|---|
| `hwp_report` | 국책 R&D 연구보고서(연차·연차점검·단계·최종)를 한글(hwpx)로 쓴다. 실제 보고서 두 건에서 작성자가 판마다 고친 곳과 최종 제출본을 대조해 뽑은 **작성 규칙·장별 작성법**을 따른다. 단독 양식은 YAML(spec) 한 장으로 hwpx를 만들고, 주관기관이 보낸 통합 양식에는 남의 글·표·메모를 그대로 둔 채 우리 칸만 채운다. 한컴 PDF로 꼬리 줄·쪽 빈칸을 확인하고, 작성자가 고친 판을 거둬들여 수정 포인트를 규칙으로 쌓는다 |
| `report-figure` | 보고서용 그림을 실데이터 논문식으로 만든다(matplotlib, 한글 라벨, 400 dpi) |

## 설치 — Claude에게 맡기기 (권장)

Claude Code(Windows·macOS)에 링크를 주며 이렇게 말한다.

```
https://github.com/Chihun-Lee/hwp-report-skills 이 스킬 설치해서 쓰게 해줘
```

- Claude가 이 레포를 받아 [INSTALL.md](INSTALL.md) 절차대로 설치한다. 3분 안팎 걸린다.
- Python이 없으면 설치해도 되는지 묻는다.
- 끝나면 **Claude Code를 다시 시작**하고 「연차보고서 만들어줘」라고 말한다.
- 최신판으로 바꿀 때는 「hwp_report 업데이트해줘」라고 말한다.

### Claude Code로 설치하는 절차 (요약 — 상세는 INSTALL.md)

1. 받기: `git clone --depth 1 https://github.com/Chihun-Lee/hwp-report-skills.git "$HOME/.hwp_report/src"`
2. 설치
   - Windows: `py -3 "$HOME/.hwp_report/src/install.py"`
   - macOS·Linux: `python3 "$HOME/.hwp_report/src/install.py"`
   - Bash timeout은 10분으로 준다. 끝에 `selftest OK`가 나오면 된다.
3. Windows에 한글이 있으면 `py -3 "$HOME/.claude/skills/hwp_report/scripts/hr.py" selftest --pdf`로 한컴 PDF를 시험한다.
4. 사용자에게 Claude Code를 다시 시작하라고 알린다.

Python이 없을 때, git이 없을 때, 회사망 SSL 오류 등은 [INSTALL.md](INSTALL.md)의 「문제 해결」에 있다.

## 필요한 것

- [Claude Code](https://claude.com/claude-code). Windows에서 쓰려면 Git for Windows도 있어야 한다.
- **Python 3.9 이상**
  - Windows: `winget install -e --id Python.Python.3.12`. 또는 [python.org](https://www.python.org/downloads/)에서 받는다. 설치 첫 화면에서 「Add python.exe to PATH」를 체크한다.
  - macOS: `brew install python`, 또는 python.org에서 받는다.
- 있으면 좋음
  - **한컴오피스 한글**: 최종 쪽 배치와 꼬리 줄을 한컴 PDF로 확인한다.
  - **Node.js 18+**: 한글 없이 쪽 미리보기를 만든다.

## 직접 설치

### Windows

1. 이 레포를 받는다. 둘 중 하나를 고른다.
   - zip: GitHub의 「Code → Download ZIP」으로 받거나 전달받은 zip을 쓴다. 압축은 꼭 풀어야 한다.
   - git: `git clone https://github.com/Chihun-Lee/hwp-report-skills.git`
2. 압축을 푼 폴더에서 **`install.cmd`를 더블클릭**한다.
3. 다음이 자동으로 진행된다.
   - 스킬 두 개를 `C:\Users\<이름>\.claude\skills\`에 복사한다.
   - 파이썬 패키지를 `C:\Users\<이름>\.hwp_report\venv`에 설치한다. 1~2분 걸린다.
   - 한글 자동화 보안 모듈을 등록한다.
   - 자가검사를 돌린다. 마지막 줄에 `selftest OK`가 나오면 성공이다.
4. Claude Code를 새로 연다.

명령 창에서 설치할 때 쓰는 옵션:

```bat
install.cmd --no-figures   :: 보고서 그림(matplotlib)은 빼고 설치
install.cmd --link         :: 복사 대신 연결 (git clone 폴더에서 git pull 하면 바로 최신)
```

### macOS · Linux

```bash
git clone https://github.com/Chihun-Lee/hwp-report-skills.git ~/hwp-report-skills
bash ~/hwp-report-skills/install.sh
```

macOS·Linux에서는 기본으로 `~/.claude/skills/`에 연결(심링크)하므로, `git pull`만 하면 최신이 된다.

### Claude Code 플러그인으로 설치

```bash
claude plugin marketplace add Chihun-Lee/hwp-report-skills
claude plugin install hwp-report@hwp-report-skills
```

- 이렇게 설치하면 스킬 이름 앞에 `hwp-report:`가 붙는다.
- 파이썬 패키지는 처음 쓸 때 Claude가 설치한다(`hr.py setup`).
- 플러그인과 `install` 중 **하나만** 쓴다. 둘 다 쓰면 스킬이 두 번 잡힌다.

## 쓰기

Claude Code에서 이렇게 말하면 된다.
- 「연차보고서 만들어줘」, 「국책보고서 써줘」, 또는 `/hwp_report`
- 「주관기관이 보낸 통합 양식에 우리 파트 옮겨 적어줘」
- 「내가 한컴에서 고친 거 반영해서 v02 만들어줘」, 「내가 고친 포인트 정리해줘」

**처음 쓸 때**는 Claude가 두 가지를 묻는다.
1. **문체**: 다음 중 하나를 고른다.
   - 기본: 기관 보고서 표준 개조식
   - 내 문체 만들기: 직접 쓴 보고서 3~10개를 주면 분석한다
   - 설치된 문체 스킬
2. **양식**: 다음 중 하나를 고른다.
   - 기본: 연차점검 보고서 양식1 구조
   - 다른 양식: 기관에서 받은 실제 양식 hwpx를 주면 등록한다

설정은 `~/.hwp_report/config.yaml`에 저장된다(Windows: `C:\Users\<이름>\.hwp_report\config.yaml`). 바꾸려면 Claude에게 「문체 바꿔줘」, 「양식 바꿔줘」라고 말한다.

### 명령

Claude가 대신 실행하므로 직접 칠 일은 드물다. 직접 실행할 때는 다음처럼 쓴다.
- Windows: `py -3 "%USERPROFILE%\.claude\skills\hwp_report\scripts\hr.py" <명령>`
- macOS: `python3 ~/.claude/skills/hwp_report/scripts/hr.py <명령>`

| 명령 | 하는 일 |
|---|---|
| `doctor` | 설치 상태를 점검한다: 버전, 파이썬 패키지, PDF 읽기, 한글, 미리보기, 그림 글꼴 |
| `update` | 스킬을 최신판으로 바꾼다 |
| `selftest [--pdf]` | 예시 보고서로 빌드·검사·왕복을 시험한다. `--pdf`는 한컴 PDF와 꼬리 줄까지 시험한다 |
| `build` · `check` | spec으로 hwpx를 만들고, 게이트(구조, 작성 규칙, 제출 전 잔여물)를 돌린다. `check --form 원본양식.hwpx`는 통합 양식에서 우리 글만 검사한다 |
| `learn 이전.hwpx 수정본.hwpx` | 작성자가 무엇을 어떻게 고쳤는지 표로 정리한다. 유형별 횟수와 반복된 치환(규칙 후보)을 보여 준다 |
| `extract` · `diff` | 수정본을 spec으로 되돌리고, 다시 만든 결과와 차이가 0인지 확인한다 |
| `dump 문서.hwpx` | 모든 구역의 문단, 표 칸, 모양 번호, 메모를 덤프한다. 통합 양식에서 우리 칸을 찾을 때 쓴다 |
| `pdf` · `tail` · `fill` | 한컴 PDF를 만들고(사본으로), 꼬리 줄과 쪽 아래 빈칸을 찾는다 |
| `render` | 한글 없이 쪽 미리보기 PNG를 만든다(node 필요) |

### 한컴 PDF 확인

- **Windows**
  - 한글을 COM으로 새로 띄우고(창은 숨김) 보고서 사본을 열어 PDF로 저장한다. 사용자가 열어 둔 한글 창은 건드리지 않는다.
  - 「한글을 이용하여 파일에 접근하려는 시도」 창이 뜨면 「모두 허용」을 누른다. 설치 때 보안 모듈이 등록됐으면 뜨지 않는다.
- **macOS**
  - 한컴오피스 앱으로 사본을 열어 PDF를 뽑는다. 키보드·마우스 입력이 멈췄을 때만 잠깐 앞으로 올라온다.
  - 화면이 꺼져 있거나 잠겨 있으면 기다린다.

## 문제 해결

| 증상 | 해결 |
|---|---|
| `install.cmd`가 「Python 3.9 or later was not found」 | 「필요한 것」의 Python을 설치한다. 새 창을 열고 다시 실행한다 |
| pip 설치 실패(SSL·프록시, 회사망) | `install.cmd --pip-args "--trusted-host pypi.org --trusted-host files.pythonhosted.org"` |
| 「파이썬 패키지 없음」 | `py -3 "<스킬>\scripts\hr.py" setup` (macOS는 `python3 …`) |
| 한컴 PDF 종료 코드 5(한글 COM 없음) | 한글을 설치한 뒤 한 번 직접 실행해 초기 설정을 마친다 |
| 한컴 PDF 종료 코드 7(시간 초과) | 작업 표시줄의 한글 창에 확인 창이 떠 있는지 보고 닫는다 |
| 그림의 한글이 네모(□)로 나온다 | 맑은 고딕(Windows 기본)이나 나눔고딕을 설치한다. `doctor`가 쓸 수 있는 글꼴을 보여 준다 |
| 스킬이 안 보인다 | Claude Code를 새로 연다. `~/.claude/skills/hwp_report/SKILL.md`가 있는지 확인한다 |

## 업데이트·삭제

- 업데이트: Claude에게 「hwp_report 업데이트해줘」라고 말한다. 직접 하려면 `py -3 "%USERPROFILE%\.claude\skills\hwp_report\scripts\hr.py" update`(macOS는 `python3 ~/.claude/skills/hwp_report/scripts/hr.py update`)를 실행한다.
  - 최신본을 받아(git pull 또는 zip 다시 받기) 다시 설치하고 자가검사까지 한다.
  - 설정·문체·양식은 그대로 남는다.
- 삭제: `install.cmd --uninstall`(macOS: `bash install.sh --uninstall`)은 스킬만 지운다. 설정과 가상환경까지 지우려면 `~/.hwp_report` 폴더도 지운다.

## 주의

- 요약표에는 연락처와 국가연구자번호가 들어간다. **보고서 spec(YAML)을 남과 나눌 때는 그 칸을 지운다.**
- 보고서 내용은 Claude(Anthropic)로 전송된다. 보안 등급이 있는 과제는 기관 보안 기준을 먼저 확인한다.
- 이 도구는 파일만 만든다. 상신·제출은 사람이 한다.

## 라이선스·출처

- 스킬 코드·문서: Chihun Lee, 2026.
- `skills/hwp_report/vendor/rhwp/`: rhwp(@rhwp/core 0.7.10, Edward Kim), MIT. 원문은 같은 폴더의 LICENSE에 있다.
- Windows 한글 자동화: 보안 모듈 DLL은 설치할 때 [pyhwpx](https://github.com/martiniifun/pyhwpx)(MIT) 패키지에서 받는다. 이 레포에는 넣지 않았다. PDF 저장 순서는 pyhwpx를 참고했다.
- 예시 양식: 연차점검 보고서 양식1의 구조만 남기고 기관명·사업명·안내문을 ○○로 바꾼 것이다. 실제 자료는 들어 있지 않다.

## 변경 기록

- 1.2.0 (2026-11): Windows 지원을 추가했다.
  - Claude Code에 레포 링크만 주면 설치되게 했다(`INSTALL.md`). `update`, `selftest --pdf`를 추가했다.
  - 공통 진입점 `hr.py`를 두고, 설치는 `install.cmd`·`install.py`로 한다. 그림용 matplotlib은 기본으로 설치한다.
  - 한컴 PDF는 Windows COM으로 만들고, PDF는 PyMuPDF로 읽는다(poppler 불필요).
  - 그림 한글 글꼴을 자동으로 고르고, `doctor` 명령을 추가했다.
- 1.1.0 (2026-11): 국책보고서 작성 규칙과 장별 작성법, 통합 양식 병합, `learn`·`tail`·`dump`를 추가했다.
