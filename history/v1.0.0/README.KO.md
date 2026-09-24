# ReleasePick Codex Skill v1.0.0

보도자료를 읽어 카드뉴스 기획안과 파일로 만드는 Codex 스킬입니다. 호출 이름은 **`$releasepick`**입니다.

**제작 범위:** 원본 ReleasePick의 기획안 스키마와 주요 함수 인터페이스를 확인하여, Codex 실행 지침·로컬 CLI·선택적 원본 연동 어댑터를 작성했습니다. 원본 전체 웹앱을 스킬 폴더에 복사한 패키지는 아닙니다.

**설치 상태:** 이 파일을 전달한 대화에서는 DESKTOP 커넥터가 `FORBIDDEN: This conversation does not support developer MCPs` 오류를 반환했습니다. 사용자 PC에 파일을 쓰거나 스킬을 직접 설치하지 않았습니다. 아래 설치 프로그램은 다운로드한 PC에서 실행하는 용도입니다.

## 1. Windows 설치

Python 3.11 이상이 필요합니다. 원본 API 기능까지 사용할 경우 원본 README가 권장하는 Python 3.11 또는 3.12를 우선 사용하세요. 압축을 풀고 `install.ps1`이 있는 폴더에서 PowerShell을 열어 실행합니다.

```powershell
powershell -NoProfile -File .\install.ps1 -WithRuntime
```

기본 설치 위치는 다음과 같습니다.

```text
%USERPROFILE%\.agents\skills\releasepick
```

`-WithRuntime`은 스킬 전용 `.venv`를 만들고 기본 Python 패키지를 다운로드합니다. 원본 저장소나 로고를 내려받지 않으며 LLM API 호출·SNS 게시도 하지 않습니다. 관리자 권한과 전역 실행 정책 변경은 요구하지 않습니다.

PowerShell 스크립트 실행이 기관 정책으로 차단되면 정책을 우회하지 말고, 허용된 Python 실행 환경에서 아래 동일 작업을 수행하세요. Python 3.12가 설치된 경우의 예시입니다.

```powershell
py -3.12 .\install.py
py -3.12 "$HOME\.agents\skills\releasepick\scripts\bootstrap.py" core --allow-network
```

Python 패키지가 이미 준비되어 있다면 `-WithRuntime` 없이 스킬 파일만 설치할 수 있습니다. 인터넷이 제한된 PC에서는 승인된 패키지 반입 절차를 사용하세요.

### 프로젝트 전용 설치 / 업데이트

```powershell
# 기존 프로젝트 폴더 아래에만 설치
powershell -NoProfile -File .\install.ps1 -ProjectPath "C:\Users\USER\Documents\Codex\ReleasePickWork" -WithRuntime

# 기존 releasepick 스킬을 백업한 뒤 교체
powershell -NoProfile -File .\install.ps1 -Replace -WithRuntime
```

프로젝트 폴더는 미리 존재해야 합니다. 업데이트 시 기존 스킬 전체는 `.agents\skill-backups\releasepick-시간`에 보관합니다. 기존 가상환경/원본 저장소도 백업 폴더로 이동하며 새 설치에 자동 병합하지 않습니다. 다른 스킬, Codex 설정, API 키 파일은 수정하지 않습니다.

이 설치 경로와 SKILL.md 형식은 OpenAI의 공식 스킬 문서에서 확인했습니다. 출처 주소와 확인 범위는 `SOURCES.md`에 있습니다. 설치 후 Codex에서 새 대화를 열고 `$releasepick`을 호출합니다. 표시되지 않으면 Codex를 다시 시작하여 스킬을 다시 읽게 하세요. 자동 암묵 호출은 꺼 두었습니다.

## 2. Codex 사용 예시

```text
$releasepick
첨부한 보도자료로 카드뉴스 5장 초안을 만들어줘.
원문에 없는 숫자나 조건은 넣지 마.
기본 로컬 텍스트 템플릿을 쓰고, API 호출과 SNS 게시는 하지 마.
```

```text
$releasepick
이 안내문으로 카드뉴스 3장을 만들어줘.
jeju 색상 프로필을 쓰되 기관명과 로고는 넣지 말고,
JPEG와 검수용 PPTX가 포함된 ZIP으로 저장해줘.
```

Codex는 원문을 읽고 `plan.json`과 근거 대조 문서를 작성한 다음 로컬 스크립트로 렌더링합니다. 기본 모드의 별도 OpenAI API 키는 필요 없습니다. 단, Codex 자체의 사용 한도/요금, 원문을 Codex에 전달하는 정보보안 검토는 별개입니다. 완전한 오프라인 AI 추론 프로그램은 아닙니다.

문안은 초안으로 표시합니다. 실제 사용자 승인 후에만 해시가 연결된 승인 기록을 만들고 `문안 승인본`으로 렌더링합니다. 승인 기록은 전자서명, 게시 승인, 법률 검토 또는 사실 검증을 대신하지 않습니다.

## 3. 제공 기능과 한계

| 기능 | 제공 내용 |
|---|---|
| 문서 추출 | 텍스트 PDF, HWPX, UTF-8/CP949 TXT·MD; 원문 위치·해시·경고 기록 |
| 기획 | Codex가 원문을 바탕으로 작성; 원본 CardNewsPlan과 호환되는 JSON |
| 검증 | 1~12장, 역할 순서, 필드 형식, 길이 제한; 내용 임의 잘라내기 없음 |
| 기본 이미지 | 1000×1350 JPEG; 로컬 텍스트 템플릿; 기본/제주 팔레트 |
| 검수 | HTML 미리보기, 문안 Markdown, 픽셀 측정 기반 넘침 검사 |
| 산출물 | JPEG·기획 JSON·검토 문서·검사 결과 ZIP + 이미지형 PPTX |
| 보호 | 기존 결과 덮어쓰기 거부, 승인 후 변경 감지, 정해진 파일만 ZIP에 포함 |
| 원본 연동 | 선택 다운로드, 함수 계약 검사, 원본 API 기획/이미지, 원본 문안 PPTX 내보내기 |

기본 PPTX는 **카드 이미지를 넣은 검수용**이며 카드 안 글자가 편집되는 슬라이드는 아닙니다. 글자는 `plan.json`에서 수정하고 다시 렌더링합니다. 원본 `upstream-export`는 원본의 텍스트형 기획 PPTX를 호출합니다. 이 둘을 구분하세요.

기본 모드는 생성형 그림/캐릭터를 만들지 않습니다. `jeju`는 `#0173bc`, `#f18101`, `#00a074`을 넣은 사용자 정의 색상 프로필일 뿐 공식 인증 템플릿이 아닙니다. 로고와 폰트는 포함하지 않습니다. 로고는 사용자가 승인한 파일만 선택하여 합성합니다.

스캔 PDF OCR, 구형 HWP, 복잡한 표의 완전한 구조 보존, SNS 자동 게시, 원본 A/B/C UI 및 SQLite 세션 복구는 내장하지 않았습니다. 공식 홈페이지 검색/RSS는 스킬에 별도 수집기를 복제하지 않았으며 Codex 세션에 실제로 제공되는 브라우저/검색 도구가 필요합니다.

## 4. 원본 OpenAI API 기능까지 연결할 때

처음 설치할 때 `-WithUpstream`을 지정하면 기본 의존성 설치에 이어 원본 Git 저장소를 별도로 복제합니다. Git과 인터넷 접근이 필요합니다.

```powershell
powershell -NoProfile -File .\install.ps1 -WithUpstream
```

이미 설치한 경우에는 위 설치를 재실행하지 말고 아래 명령만 실행합니다.

```powershell
py -3.12 "$HOME\.agents\skills\releasepick\scripts\bootstrap.py" upstream --allow-network --install-deps
```

API 실행은 이 설치 명령만으로 시작되지 않습니다. 이후 `--allow-paid-api`, 허용 호출 횟수, 원본 실행 허용, 모델명과 `OPENAI_API_KEY` 환경변수가 필요합니다. 원본 이미지 함수는 재정경제부 브랜딩을 사용하므로 별도 확인 옵션을 요구합니다. 타 기관 자료에 자동 적용하지 마세요.

원본 저장소는 이 패키지에 재배포하지 않습니다. README의 사용/재배포 조건과 로고 권리 등을 직접 확인하세요. API 어댑터는 확인한 함수 인터페이스를 호출하도록 구현했지만 이번 제작 환경에서는 실제 원본 Git clone과 유료 API 실행을 끝까지 검증하지 못했습니다. 상세 명령과 제약은 `releasepick/references/upstream.md`에 있습니다.

## 5. 검사와 파일 구성

```text
ReleasePick-Codex-Skill-v1.0.0/
├─ install.ps1                 Windows 설치 진입점
├─ install.py                  실제 복사·백업 설치 로직
├─ README.KO.md                이 안내
├─ TEST_REPORT.md              실제 검사 결과와 미검증 범위
├─ TEST_LOG.txt                테스트 실행 로그
├─ SOURCES.md                  확인한 원본 및 공식 문서
├─ NOTICE.md                   출처·권리·배포 범위
└─ releasepick/
   ├─ SKILL.md                 Codex 실행 지침
   ├─ agents/openai.yaml       이름·기본 요청·명시 호출 설정
   ├─ scripts/                CLI, 추출/승인/렌더/원본 어댑터/환경 준비
   ├─ assets/                 프로필과 가상 테스트 자료
   ├─ references/             명령 안내·JSON 스키마·원본 연동
   ├─ tests/                  자동 테스트
   └─ requirements-core.txt   기본 Python 의존성
```

압축을 푼 패키지 루트에서 기본 의존성이 설치된 Python으로 다음 명령을 실행하면 테스트를 재현할 수 있습니다.

```powershell
python -m unittest discover -s releasepick/tests -v
```

테스트의 `upstream-mock`, `mock` 항목은 가상 원본 함수 계약 검사용입니다. 실제 원본 API 테스트라는 뜻이 아닙니다. 테스트에는 외부 API 요청이나 SNS 게시가 없습니다.

설치 제거는 설치된 `releasepick` 폴더만 대상으로 하며, 필요한 결과물/원본/가상환경을 먼저 백업하세요. 자동 삭제 스크립트는 제공하지 않습니다.
