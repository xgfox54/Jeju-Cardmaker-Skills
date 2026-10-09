<p align="center">
  <img src="./Jeju_Cardmaker_Codex_Skills.png" alt="Jeju Cardmaker Codex Skills 표지" width="100%">
</p>

# Codex 용 카드뉴스 생성 스킬 - Codex Skills

보도자료나 사업 안내문(PDF, HWPX, TXT, MD)을 읽고 카드뉴스를 만드는 Codex 스킬 **Jeju_Cardmaker**입니다. 원문과 대조한 기획안(plan.json)을 바탕으로 2160×2700 PNG·JPEG, 편집 가능한 PPTX, 미리보기 HTML을 만들고 ZIP으로 묶습니다. 이미지는 PC 안에서 그리며 별도 AI API 호출이나 SNS 게시를 하지 않습니다.

현재 버전은 **v1.2.0** (보완 모듈 2026.10.09.1 포함)입니다. 변경 내용은 CHANGELOG.md에 있습니다.

## 필요한 것

- Codex 데스크톱 앱 또는 Codex CLI (Windows 기준으로 시험했습니다)
- Python 3.11 이상, 3.12 권장
- 설치할 때 Python 패키지를 내려받을 인터넷 연결

## 설치

1. 이 페이지의 **Code → zip**으로 내려받아 압축을 모두 풉니다. git clone으로 받아도 됩니다.
2. 압축을 푼 폴더에서 **INSTALL.cmd**를 실행합니다. 이전 버전(ReleasePick 포함)을 쓰고 있었다면 **UPDATE.cmd**를 실행합니다. 이전 설치본은 지우지 않고 백업 폴더로 옮깁니다.
3. Codex에서 새 작업을 열고 **$Jeju_Cardmaker**를 호출합니다. 스킬이 보이지 않으면 Codex를 다시 시작합니다.

스킬은 %USERPROFILE%\.agents\skills\Jeju_Cardmaker 에 설치됩니다. 내려받은 파일이 바뀌지 않았는지 확인하려면 압축을 푼 폴더에서 python verify_package.py 를 실행합니다.

## 사용 예

~~~text
$Jeju_Cardmaker
첨부한 보도자료로 카드뉴스 5장 초안을 만들어줘.
제주 색상(#0173bc, #f18101, #00a074), 기관명·로고 없음.
2160×2700 PNG·JPEG와 편집 가능한 PPTX를 ZIP으로 만들어줘.
각 장의 출처와 글자 넘침을 확인하고, 유료 API와 SNS 게시는 하지 마.
~~~

초안을 검토하고 문안을 승인한 뒤 승인본을 요청하면 상태 문구가 없는 최종 이미지를 만듭니다.

## 문서

- README.KO.md: 설치, 명령, 결과 파일, 한계에 대한 자세한 설명
- START-HERE.md: 빠른 시작
- CHANGELOG.md: 변경 이력
- NOTICE.md, SOURCES.md: 출처와 배포 범위

## 알아둘 점

- 텍스트 중심의 카드 템플릿입니다. 생성형 그림, 스캔 문서 OCR, 구형 HWP는 지원하지 않습니다.
- 자동 검사는 글자 넘침과 출처 번호 연결을 확인할 뿐, 내용이 사실인지 검증하지 않습니다. 게시 전에 원문과 대조해 주세요.
- ReleasePick Codex Skill v1.1.0을 바탕으로 이름을 바꾸고 Windows 글자 경계 버그를 고친 버전입니다. 외부 원본 프로젝트(chaeun74/Releasepick)의 공식 배포가 아닙니다.


<!-- cardprinter-quality-review-20261009 -->
## CardPrinter 참고 품질 보완 모듈 (2026-10-09)

기존 v1.1.1 렌더러와 `plan.json` 구조는 유지합니다. 별도 `scripts/quality_cli.py`가
근거·수치·단위·조건·기준일, 승인 이후 근거 변경, 출력 누락과 낮은 색 대비를
검사하는 선택형 강화 제작 경로를 제공합니다. 기존 `build`에 자동 적용된 기능이 아닙니다.

새 강화 경로에서는 `source.json`, `SOURCES.md`, `evidence.json`을 원문 대조 후 준비하고,
사전검사 → 기존 렌더러 → 사후검사 → `cardnews-checked.zip` 생성 순서로 처리합니다.
검사 실패 결과는 완료 폴더로 옮기지 않습니다. 사실·법률·접근성 인증 또는 게시 승인을
대신하지 않으며, 승인 기록은 실제 사용자 승인 후에만 만듭니다.

설명과 명령: `Jeju_Cardmaker/references/cardprinter-quality.md`
(스킬 설치 폴더에서는 `references/cardprinter-quality.md`).
검토 근거와 미구현 범위: 저장소의 `docs/cardprinter-review-20261009/REVIEW.md`.
보완 모듈 버전은 `2026.10.09.1`이며 기존 본체 버전은 임의로 변경하지 않습니다.
