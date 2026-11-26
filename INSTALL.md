# 설치 절차 — Claude Code가 실행하는 순서

사용자가 이 레포 링크(`https://github.com/Chihun-Lee/hwp-report-skills`)를 주며 「이 스킬 쓰게 해줘」, 「설치해줘」라고 하면 Claude Code가 아래 명령을 순서대로 실행해 설치한다. 사용자가 명령을 직접 칠 필요는 없다.

- 명령은 Windows의 Git Bash·PowerShell과 macOS·Linux 셸에서 그대로 돌아가도록 `$HOME`으로 썼다.
- 단계마다 출력을 확인한다. 실패하면 맨 아래 「문제 해결」을 본다.

## 설치가 바꾸는 것

| 위치 | 내용 |
|---|---|
| `~/.claude/skills/hwp_report`, `~/.claude/skills/report-figure` | 스킬 두 개. Windows는 복사, macOS·Linux는 연결(심링크)이다 |
| `~/.hwp_report/` | 받은 원본(`src/`), 파이썬 가상환경(`venv/`), 사용자 설정, 설치 기록(`install.json`) |
| Windows 레지스트리 `HKCU\Software\HNC\HwpAutomation\Modules` | 값 `FilePathCheckerModule` 하나. 한글 자동화 때 「파일 접근 허용」 창이 뜨지 않게 하는 보안 모듈 DLL의 경로다. DLL은 pyhwpx(MIT) 패키지에서 받는다 |

- 전역 파이썬, 시스템 설정, 관리자 권한은 쓰지 않는다.
- 같은 이름의 스킬이 이미 있으면 지우지 않고 `~/.hwp_report/backup/`으로 옮긴다.

## 1. Python 3.9 이상 확인

| OS | 명령 |
|---|---|
| Windows | `py -3 --version` (안 되면 `python --version`) |
| macOS·Linux | `python3 --version` |

- 「Python 3.x」가 나오면 2단계로 간다. 아래 명령의 `py -3`(Windows)·`python3`(macOS·Linux)은 여기서 된 명령으로 바꿔 쓴다.
- Windows에서 「Python was not found … Microsoft Store」가 나오면 설치되지 않은 것이다. 그 메시지는 스토어로 보내는 바로가기가 낸다.
- Python이 없으면 **사용자에게 설치해도 되는지 묻고** 설치한다.
  - Windows (관리자 권한 불필요)
    ```bash
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    ```
    지금 세션에는 새 PATH가 반영되지 않는다. 그래서 이후 `py -3` 자리에 `"$HOME/AppData/Local/Programs/Python/Python312/python.exe"`를 쓴다.
  - winget이 없으면 사용자에게 https://www.python.org/downloads/ 설치를 안내한다. 첫 화면에서 「Add python.exe to PATH」를 체크하고, 설치 뒤 Claude Code를 다시 시작한다.
  - macOS: `brew install python` 또는 python.org.

## 2. 받기

```bash
git clone --depth 1 https://github.com/Chihun-Lee/hwp-report-skills.git "$HOME/.hwp_report/src"
```

- 이미 `~/.hwp_report/src`가 있으면 새로 받지 않고 갱신한다: `git -C "$HOME/.hwp_report/src" pull --ff-only`
- git이 없으면 zip으로 받는다. macOS·Linux는 `curl.exe` 대신 `curl`, `py -3` 대신 `python3`을 쓴다.
  ```bash
  curl.exe -fL -o "$HOME/hwp-report-skills.zip" https://github.com/Chihun-Lee/hwp-report-skills/archive/refs/heads/main.zip
  py -3 -m zipfile -e "$HOME/hwp-report-skills.zip" "$HOME/.hwp_report"
  ```
  원본 폴더는 `$HOME/.hwp_report/hwp-report-skills-main`이 된다. 3단계의 `src`를 이 경로로 바꾼다.

## 3. 설치

```bash
py -3 "$HOME/.hwp_report/src/install.py"          # Windows
python3 "$HOME/.hwp_report/src/install.py"        # macOS·Linux
```

- 파이썬 패키지를 내려받으므로 1~3분 걸린다. **Bash 도구 timeout을 600000(10분)으로 준다.**
- 하는 일
  1. 스킬을 넣는다.
  2. `~/.hwp_report/venv`에 lxml·pyyaml·pillow·numpy·PyMuPDF·matplotlib을 설치한다. Windows는 pywin32도 설치한다.
  3. Windows는 한글 보안 모듈을 등록한다.
  4. `doctor`(설치 상태)와 `selftest`(예시 보고서 빌드·검사)를 돌린다.
- 성공: 출력 끝에 `selftest OK`와 `✓ 설치 완료`가 나온다.
- pip가 SSL·프록시 오류로 실패하면(회사망) 다음으로 다시 실행한다.
  ```bash
  py -3 "$HOME/.hwp_report/src/install.py" --pip-args "--trusted-host pypi.org --trusted-host files.pythonhosted.org"
  ```

## 4. 한컴 PDF 시험 (Windows, 한글이 설치된 경우)

3단계의 `doctor` 출력에 「한컴오피스 한글 COM(HWPFrame.HwpObject) 등록됨」이 있으면 이 시험을 한다. 먼저 사용자에게 「한글이 잠깐 백그라운드에서 실행된다」고 알린다.

```bash
py -3 "$HOME/.claude/skills/hwp_report/scripts/hr.py" selftest --pdf
```

- 결과 읽기
  - `한컴 PDF OK`와 `selftest OK`가 나오면 한컴 PDF로 쪽·꼬리 줄을 검수할 수 있다.
  - 한글 창에 「한글을 이용하여 파일에 접근하려는 시도」가 뜨면, 사용자에게 「모두 허용」을 눌러 달라고 한다.
  - 실패해도 hwpx 작성과 게이트 검사는 된다. 출력과 종료 코드(5 한글 COM 없음 · 6 열기·저장 실패 · 7 시간 초과)를 사용자에게 그대로 보여 준다.
- 언제 건너뛰는가
  - 한글이 없으면 건너뛴다.
  - macOS에서도 건너뛴다. 한컴 창이 화면 앞으로 올라오기 때문이다. 사용자가 원할 때만 한다.

## 5. 사용자에게 알리기

- 설치가 끝났고, 몇 판(버전)이 설치됐는지 알린다. 버전은 `✓ 설치 완료 (hwp-report-skills x.y.z)` 줄에 있다.
- **Claude Code를 다시 시작하면 `/hwp_report`가 보인다.** 터미널에서는 `/exit` 뒤 `claude`, VS Code·데스크톱 앱에서는 새 대화를 연다.
- 이렇게 말하면 된다.
  - 「연차보고서 만들어줘」
  - 「주관기관 통합 양식에 우리 파트 넣어줘」
  - 「내가 한컴에서 고친 거 반영해줘」
  - 처음 쓸 때 Claude가 문체(기본 또는 내 문체)와 양식(기본 또는 받은 양식)을 묻는다.
- 한글이 없거나 4단계가 실패했으면 이렇게 알린다: hwpx는 만들어지지만 쪽 확인(PDF)은 사용자가 한글에서 직접 한다.

## 업데이트·삭제

- **업데이트**: 사용자가 「hwp_report 업데이트해줘」라고 하면 다음을 실행한다. 최신본을 받아(git pull, 또는 zip을 다시 받음) 다시 설치하고 자가검사까지 한다.
  ```bash
  py -3 "$HOME/.claude/skills/hwp_report/scripts/hr.py" update
  ```
  - `~/.hwp_report`의 설정·문체·양식은 그대로 남는다.
- **삭제**: `py -3 "$HOME/.hwp_report/src/install.py" --uninstall`은 스킬 두 개만 지운다. 설정·가상환경까지 지우려면 `~/.hwp_report` 폴더도 지운다.

## 문제 해결

| 증상 | 조치 |
|---|---|
| `py`·`python` 둘 다 없음, 또는 Microsoft Store 메시지 | 1단계의 Python 설치 |
| `git` 없음 | 2단계의 zip 방법 |
| pip `SSL: CERTIFICATE_VERIFY_FAILED`, 프록시 오류 | 3단계의 `--pip-args` |
| `venv를 만들지 못함` (Linux) | `sudo apt install python3-venv` 를 사용자에게 안내 |
| `selftest 실패` | 출력 끝 30줄을 사용자에게 보여 준다. `hr.py doctor`로 빠진 것을 확인 |
| 한컴 PDF 종료 코드 5 | 한글을 설치한 뒤 한 번 직접 실행해 초기 설정을 마치게 하고 다시 4단계 |
| 한컴 PDF 종료 코드 7 (시간 초과) | 작업 표시줄의 한글 창에 확인 창이 떠 있는지 사용자에게 확인. 남은 Hwp.exe는 작업 관리자에서 끝낸다 |
| 다시 시작해도 `/hwp_report`가 안 보임 | `~/.claude/skills/hwp_report/SKILL.md`가 있는지 확인. 없으면 3단계를 다시 실행 |

## 다른 설치 방법

- **Claude Code 플러그인**: `claude plugin marketplace add Chihun-Lee/hwp-report-skills` 뒤 `claude plugin install hwp-report@hwp-report-skills`.
  - 스킬 이름 앞에 `hwp-report:`가 붙는다.
  - 파이썬 패키지는 처음 쓸 때 Claude가 `hr.py setup`으로 설치한다.
  - 위 install.py와 **둘 중 하나만** 쓴다. 둘 다 쓰면 스킬이 두 번 잡힌다.
- **사람이 직접 설치**: [README](README.md)의 「직접 설치」.
