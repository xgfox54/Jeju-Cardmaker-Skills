# Jeju_Cardmaker Codex Skill v1.3.1

보도자료·사업 안내문·기획 JSON으로 카드뉴스를 만드는 **로컬 Codex용 설치 패키지**입니다. 호출명은 **`$Jeju_Cardmaker`**입니다. 이전 이름은 ReleasePick(`$releasepick`)이었습니다.

기존 v1.0.0 ZIP을 바탕으로 업그레이드했습니다. 공유 Drive 폴더의 JEV plan.json·preview.html·SOURCES.md는 설치 소스가 아니라 제작 사례이므로 reference-projects에 원본 그대로 보관했습니다. 공유 Drive나 사용자 PC를 수정·설치하지 않았습니다.

## 직원 AI 학습 기본값

서귀포시 직원에게 AI 개념과 업무 활용 방법을 쉽게 설명하는 카드뉴스를 제작함. 기본 프로필은 seogwipo-ai이며, 귤귤·하르방·한라와 제주그린·제주블루·제주오렌지 테두리를 사용함. 일반 안내문을 기존 모양으로 만들려면 --profile jeju를 명시함. 새 형식의 layout/takeaway 필드는 기존 프로필에서 지원하지 않음.

기획과 입력 규칙: [직원 AI 학습 기준](Jeju_Cardmaker/references/seogwipo-ai.md). 예제: [8장 기획안](Jeju_Cardmaker/assets/seogwipo-ai-example/plan.json).

## 1. Windows 설치

**Python 3.11 이상**과 로컬 Codex가 필요합니다. Python 3.12를 우선 권장합니다. ZIP을 먼저 모두 풀고 실행하세요.

처음 설치는 **INSTALL.cmd**, 기존 ReleasePick 또는 Jeju_Cardmaker 업데이트는 **UPDATE.cmd**를 실행합니다. 업데이트는 기존 스킬 전체를 별도 백업한 뒤 교체하며, 기존 가상환경도 백업으로 이동하므로 새 환경을 준비합니다. 설치 중 Python 의존성을 내려받습니다. 유료 AI API 호출이나 SNS 게시를 하지 않습니다.

PowerShell에서 직접 실행하려면 압축을 푼 폴더에서 다음 명령을 사용합니다.

```powershell
# 처음 설치
powershell -NoProfile -File .\install.ps1 -WithRuntime

# 기존 v1.0.0 등을 백업하고 교체
powershell -NoProfile -File .\install.ps1 -Replace -WithRuntime
```

설치 위치는 `%USERPROFILE%\.agents\skills\Jeju_Cardmaker`입니다. 기존 버전 백업은 `%USERPROFILE%\.agents\skill-backups\Jeju_Cardmaker-시각`에 둡니다. 이전 이름의 `skills\releasepick` 폴더가 있으면 업데이트할 때 `Jeju_Cardmaker-legacy-시각`으로 함께 백업하여 스킬이 두 개 표시되지 않게 합니다. 다른 스킬이나 Codex 설정, API 키는 수정하지 않습니다. 사용자 전역과 프로젝트에 같은 이름의 스킬이 동시에 있으면 중복 표시될 수 있으므로 설치 범위를 확인하세요.

패키지가 이미 준비된 Python을 사용한다면 -WithRuntime을 생략해 파일만 설치합니다. PowerShell 실행이 기관 정책으로 제한되면 정책을 바꾸거나 우회하지 말고 허용된 Python에서 실행합니다.

```powershell
py -3.12 .\install.py
# 기존 버전은 다음 명령
py -3.12 .\install.py --replace
```

별도 가상환경을 준비할 때만 다음 명령을 실행합니다. 인터넷 접근이 필요합니다.

```powershell
py -3.12 "$HOME\.agents\skills\Jeju_Cardmaker\scripts\bootstrap.py" core --allow-network
```

기관 인터넷 차단 PC에는 승인된 패키지 반입 절차가 필요합니다. 패키지 자체에 Python, 의존성 휠, 모델, 폰트를 넣지 않았습니다. 런타임 설치 실패 시 스킬 파일은 설치되어 있을 수 있으므로 출력 메시지를 확인하세요.

프로젝트 전용 설치도 가능합니다. 프로젝트 폴더는 먼저 있어야 합니다.

```powershell
powershell -NoProfile -File .\install.ps1 -ProjectPath "C:\CardNewsProject" -WithRuntime
```

macOS/Linux는 `python3 install.py`를 사용하고 필요하면 설치된 scripts/bootstrap.py로 환경을 준비합니다. v1.3.1은 Windows에서 렌더링과 자동 테스트를 실행했습니다. macOS/Linux 실행과 설치기 클릭은 이번 검증에 포함하지 않았습니다.

## 2. Codex에 요청

설치 후 새 대화에서 다음과 같이 요청합니다. 스킬이 보이지 않으면 Codex를 재시작합니다.

```text
$Jeju_Cardmaker
첨부한 보도자료로 카드뉴스 5장 초안을 만들어줘.
제주 포인트 컬러 #0173bc, #f18101, #00a074를 사용해.
기관명과 로고는 넣지 마.
2160×2700 PNG와 JPEG, 편집 가능한 PPTX, ZIP으로 만들어줘.
각 장의 근거를 SOURCES.md에 정리하고 글자 넘침을 검사해줘.
유료 API 호출과 SNS 게시는 하지 마.
```

문안에 실제로 동의한 후 승인본을 요청합니다. 상태 문구 없는 이미지는 실제 문안 승인 후에만 만듭니다. 문안 승인은 게시 승인과 다릅니다.

## 3. 새로 보강한 기능

| 항목 | v1.1 제공 내용 |
|---|---|
| 일괄 제작 | build 명령 하나로 이미지·미리보기·문안·검사·ZIP 제작 |
| 규격 | 기본 2160×2700, 1080×1350, 이전 1000×1350. 고해상도로 직접 렌더링 |
| 이미지 | PNG와 JPEG 동시 생성, 기존 개별 저장보다 일괄 전달 중심 |
| 미리보기 | 실제 생성 PNG를 표시, HTML에 별도 Canvas 문안을 유지하지 않음 |
| PPTX | 편집 가능한 텍스트·도형형 + 이미지형 검토용 두 종류 |
| 출처 | SOURCES.md 동봉, [번호] 참조 누락 검사, 카드별 근거 기록 양식 |
| 품질 | 실제 글자 경계, 한글 글리프, 본문 최소 크기, 색 대비 경고 |
| 변경 검사 | 이미지·출처·문안·HTML·PPTX 해시와 ZIP 내용 대조 |
| 설치 | INSTALL.cmd / UPDATE.cmd, 기존 백업 교체 동작 유지 |

**자동 파일 감시/브라우저 자동 갱신 기능은 아닙니다.** plan.json 수정 후 새 폴더로 다시 build해야 합니다. 편집형 PPTX 수정도 JSON/PNG에 역반영되지 않습니다. 단일 원본을 plan.json으로 유지하는 방식을 권장합니다.

## 4. 결과 파일

```text
결과폴더/
├─ png/                         고해상도 PNG
├─ jpeg/                        JPEG
├─ cardnews-editable.pptx        텍스트·도형 편집형
├─ cardnews-preview.pptx         이미지형 검수용
├─ preview.html                 이미지와 대체 텍스트 미리보기
├─ plan.json / profile.json     생성에 사용한 기획·프로필
├─ SOURCES.md                   있는 경우 동봉한 근거 기록
├─ source-summary.json          연결한 원문 요약 메타데이터
├─ review.md / render-report.json
├─ manifest.json                수정 감지용 해시
├─ ABOUT.txt
└─ cardnews.zip                 위 산출물을 모은 ZIP
```

source.json의 원문 전체와 작업 폴더의 다른 파일, API 키, 폰트는 자동 동봉하지 않습니다. SOURCES.md에 비공개 내용이 있다면 공유 전에 검토하세요.

## 5. 직접 실행과 검증

```text
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py build --project <기획폴더> --out <새 결과폴더>
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py verify-build --run <결과폴더>
python -m unittest discover -s Jeju_Cardmaker/tests -v
python verify_package.py
```

기존 render/package 명령은 계속 지원하지만 새 build 결과와 형식이 다릅니다. build 결과는 이미 ZIP을 포함합니다. 자세한 명령은 Jeju_Cardmaker/references/commands-v1.1.md에 있습니다.

JEV 사례를 재현하려면 압축을 푼 폴더에서 다음 명령을 사용합니다.

```text
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py build --project reference-projects/jev-20260918 --out jev-draft-01 --profile jeju
```

이 사례는 **2026-09-18 당시 작성된 초안**입니다. JEV 가격·성능·이용 권한을 2026-09-24에 재검증한 자료가 아니며, 게시 전에 현재 공식 자료와 다시 대조해야 합니다.

## 6. 한계

기본 렌더링은 본문과 제주 펫을 배치하는 직원 AI 학습 템플릿입니다. 생성형 그림·인포그래픽 자동 디자인·다양한 사진 레이아웃·스캔 OCR·SNS 게시를 추가한 것은 아닙니다. 별도 API 키 없이 동작하지만 Codex 자체의 이용 요금·한도는 별개입니다.

PowerPoint의 폰트 대체와 편집 후 줄바꿈은 대상 PC에서 다시 확인해야 합니다. 자동 검사는 사실 검증·법률 검토·접근성 인증·게시 승인을 대신하지 않습니다. 해시는 임의 조작에 대한 신원 인증 서명이 아닙니다.

v1.0의 선택적 원본 저장소/API 어댑터는 유지했으나 이번에 최신 upstream과 실제 유료 API를 검증하지 않았습니다. 불필요하면 -WithUpstream을 사용하지 마세요. 이번 검증은 TEST_REPORT-v1.3.1.md를 확인하세요. TEST_REPORT.md와 TEST_LOG.txt는 과거 버전의 기록입니다.

직원 AI 학습 기본 폰트는 Pretendard Regular/Bold 정적 폰트임. 공식 배포본: https://github.com/orioncactus/pretendard/releases . 없으면 --font 및 --bold-font를 함께 지정해야 하며 다른 폰트로 대체하지 않음.
