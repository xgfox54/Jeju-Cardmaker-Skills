# 변경 이력

## v1.2.0 (보완 모듈 2026.10.09.1) — 2026-10-09

CardPrinter 참고 품질 보완 모듈(quality_cli.py, rp_quality.py) 통합 및 안정화 릴리스.

### 추가
- 선택형 품질 게이트 파이프라인 (scripts/quality_cli.py): preflight -> build -> postflight -> verify.
- 근거 검증(evidence.json): 원문 단위 인용문 대조, 수치·단위·기간 일치, 필수 자격·상한·제외 조건 누락 자동 차단.
- 강화 승인 바인딩: 기획(plan.json), 원문(source.json), 근거문서(SOURCES.md), 증빙(evidence.json), 검사정책의 해시를 묶어 승인 후 변경 시 재승인 요구.
- 품질 보완 산출물: cardnews-checked.zip, quality-report.json, quality-manifest.json 생성.
- 단색 배경 텍스트 색 대비 재계산 및 기준 미달 차단 (산출물 미공개).
- 가상 시험 데이터 및 참조 문서: Jeju_Cardmaker/assets/quality-example/, Jeju_Cardmaker/references/cardprinter-quality.md, docs/cardprinter-review-20261009/.

### 수정
- quality_cli.py: 기존 코어의 SkillError 발생 시 상세 오류 메시지가 축약되던 문제 수정 (원인 메시지 보존).

### 유지 및 호환성
- 기존 Jeju_Cardmaker v1.1.1 코어 렌더러, Jeju_Cardmaker.py build CLI, plan.json 스키마 및 출력 형식 완전 호환 유지.
- 유료 API 미호출, 로컬 텍스트 렌더링, 외부 SNS 미게시 원칙 유지.
- INSTALL.cmd, UPDATE.cmd, install.py, install.ps1 설치·업데이트 호환성 유지.

## v1.1.1 — 2026-09-24

기준 패키지: ReleasePick-Codex-Skill-v1.1.0.zip. 이름 변경과 Windows 글자 경계 버그 수정입니다.

### 이름 변경
- 스킬 이름과 호출명을 `Jeju_Cardmaker`(`$Jeju_Cardmaker`)로 바꿨습니다. Codex 화면 이름은 "Jeju_Cardmaker 카드뉴스"입니다.
- 스킬 폴더 `releasepick/` → `Jeju_Cardmaker/`, 실행 파일 `scripts/releasepick.py` → `scripts/Jeju_Cardmaker.py`. 설치 위치는 `.agents/skills/Jeju_Cardmaker`이고 백업·임시 폴더 이름도 `Jeju_Cardmaker-`로 시작합니다.
- 업데이트(`--replace`, UPDATE.cmd) 때 이전 이름의 `skills/releasepick` 폴더가 있으면 `skill-backups/Jeju_Cardmaker-legacy-시각`으로 옮겨 스킬이 두 개 표시되지 않게 합니다. `--replace` 없이 설치하면 덮어쓰지 않고 중단합니다.
- 결과 폴더 manifest의 engine 값이 `Jeju_Cardmaker-studio-v1`로 바뀌었습니다. v1.1.0으로 만든 결과 폴더는 이 버전의 verify-build에서 형식이 다르다고 판정됩니다.
- 외부 원본 프로젝트(chaeun74/Releasepick) 주소·출처 고지와 v1.1.0 이전의 기록 문서(NOTICE, SOURCES, IMPROVEMENTS, TEST_REPORT, history)는 사실 기록이므로 명령 경로 외에는 그대로 두었습니다.

### 수정
- 줄이 소문자 j처럼 시작점보다 왼쪽으로 그려지는 글자로 시작하면, 실제로 넘치지 않아도 "실제 글자 영역이 경계를 초과했습니다" 오류로 build가 중단되던 문제를 고쳤습니다. 맑은 고딕의 j는 6~7px 왼쪽으로 나옵니다. 이제 줄바꿈 계산에 그 폭을 포함하고, 해당 줄을 튀어나온 만큼 오른쪽으로 옮겨 그립니다. 경계 검사 기준은 그대로입니다.
- 회귀 테스트 2개 추가: j로 시작하는 제목·본문의 글자 경계, 이전 설치 폴더 백업 이동.

### 검증 (Windows, Python 3.12.10, 맑은 고딕)
- 자동 테스트 95개 통과, 3개 건너뜀(심볼릭 링크 권한 없음).
- reference-projects/jev-20260918 8장 build와 verify-build 성공. v1.1.0에서는 같은 PC에서 5장 본문 오류로 실패했습니다.
- INSTALL/UPDATE 스크립트로 실제 사용자 PC에 설치하고 Codex 스킬 목록 인식을 확인했습니다.

## v1.1.0 — 2026-09-24

기준 패키지: 사용자의 ReleasePick-Codex-Skill-v1.0.0(1).zip. 원본 외부 웹앱의 새 릴리스가 아니라 **Codex 스킬 패키지 자체의 업데이트**입니다.

### 추가
- `build` 명령: 프로젝트의 plan.json을 읽어 PNG·JPEG·미리보기·문안·검사 보고·ZIP을 일괄 생성합니다.
- 2160×2700(기본), 1080×1350, 기존 1000×1350 출력 규격. 큰 규격은 해당 해상도에서 직접 렌더링합니다.
- 네이티브 텍스트·도형을 포함한 편집형 PPTX 및 기존처럼 이미지로 확인하는 검토용 PPTX를 별도로 제공합니다.
- SOURCES.md 근거 기록 동봉 및 각주 `[번호]` 연결 검사. 사실의 진위나 웹페이지 최신성을 자동 판정하지 않습니다.
- 실제 글리프 경계, 본문 최소 글자 크기, 색 대비 경고, 이미지 대체 텍스트를 포함한 미리보기.
- `verify-build`: 산출물 해시 및 ZIP 내부 파일의 일치 검사. 전자서명이나 위·변조 방지 인증은 아닙니다.
- INSTALL.cmd, UPDATE.cmd, 설치 패키지 SHA-256 확인 스크립트, 추가 자동 테스트 32개.
- 공유 Drive의 JEV 사례 3파일을 reference-projects에 원본 그대로 보관했습니다.

### 유지
- 호출명 `$releasepick`, 사용자/프로젝트 `.agents/skills` 경로, 설치 시 기존 폴더 백업.
- 이전 문서 추출·기획 검증·render/package 명령, 승인 후 문안/원문 변경 검사.
- 제주 사용자 정의 팔레트 #0173bc / #f18101 / #00a074. 기관 로고·폰트는 배포하지 않습니다.
- 선택적 upstream 어댑터: 이번에 외부 원본의 최신 실행 호환성을 추가 검증한 것은 아닙니다.

### 명확히 남아 있는 제약
- HTML은 산출 이미지의 미리보기입니다. 파일 감시나 실시간 편집기가 아니며 수정 후 다시 build해야 합니다.
- PPTX 수정 내용을 plan.json으로 가져오는 역방향 동기화는 없습니다.
- 텍스트 중심 카드 템플릿입니다. 사진·일러스트 자동 생성이나 다양한 인포그래픽 레이아웃을 추가하지 않았습니다.
- Windows 실제 설치와 Windows PowerPoint 표시는 이번 제작 환경에서 검증하지 않았습니다.

## v1.0.0

당시 README·출처·시험 보고·시험 로그·배포 범위는 history/v1.0.0에 별도 보존했습니다. 현재 검사 결과와 혼동하지 마세요.


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
