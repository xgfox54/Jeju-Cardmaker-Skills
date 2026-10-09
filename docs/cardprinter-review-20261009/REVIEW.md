# Jeju Cardmaker × CardPrinter 재검토·보완 결과

검토 기준일: 2026-10-09 (한국시간 기준 작업 요청)
대상: `memory365/codex-codex-skills` / Jeju Cardmaker Codex Skills
확인한 기준 커밋: `1a17f3b38a8d23133358f3f01f339dabde7730a9`
기존 문서·코드 버전: `1.1.1`
보완 모듈 식별자: `2026.10.09.1`

## 1. 완료 상태부터 구분

공개 저장소의 문서·스키마·주요 Python 코드와 테스트 내용을 읽고 정적 검토했습니다.
CardPrinter의 실제 게이트/팩토리 코드도 확인했습니다. 보완 코드, 단위·계약 테스트,
적용 도구, 사용 문서와 가상 시험 입력을 작성했습니다.

**사용자 GitLab 원격 저장소는 변경하지 않았습니다.** Desktop/Laptop의 Connect to Aside는
둘 다 `Session terminated`를 반환했습니다. 현재 환경에서는 원본 저장소 전체를 정상
체크아웃하고 인증된 쓰기 경로로 커밋·푸시할 수 없었습니다. 검토 대상 소스는 공개 읽기
경로로 확인했으며, 아래 보완안은 실제 적용 전 패키지입니다.

검토 결과를 실제 GitLab 수정·릴리스·사용자 PC 설치 완료로 표시하지 않습니다.
추가된 검사 코드의 테스트와 원래 프로젝트의 전체 회귀시험도 구분합니다.
코덱스 세션에 작업을 지시하거나 Codex CLI를 실행하지 않았습니다.

## 2. 기존 프로젝트의 강점: 교체하지 않고 보존

기존 프로젝트는 CardPrinter를 통째로 이식할 대상이 아닙니다. 행정자료를 다루는 데 이미
유용한 안전장치가 있으므로 이를 기반으로 보완하는 편이 적절합니다.

| 확인한 기존 기능 | 유지한 이유 |
|---|---|
| Python 로컬 텍스트 렌더링, 유료 API 없는 기본 경로 | 불필요한 서비스 의존성과 외부 자료 전송을 늘리지 않음 |
| `plan.json`을 단일 문안 원본으로 사용 | PNG/HTML/PPTX 사이의 내용 변경 관리가 명확함 |
| PNG/JPEG와 편집형·이미지형 PPTX 동시 출력 | 기관 내부 수정·검토 절차에 유용함 |
| 실제 글자 경계, 한글 글리프, 최소 본문 크기 검사 | 이미 구현된 기능을 새 기능으로 중복 주장하지 않음 |
| 승인 전 초안 표시, 문안·원문 해시 승인 | 실제 사용자 승인과 자동 제작을 분리함 |
| 임시 폴더에서 제작 후 완료 폴더 이동 | 기존 원자적 제작 흐름을 추가 검사 단계까지 확장함 |
| 허용 목록 기반 ZIP, 폰트·원문·이웃 파일 미동봉 | 공유 범위를 함부로 확대하지 않음 |
| 업데이트 시 기존 스킬 백업 | 기존 사용자 환경 보호 |

## 3. 확인한 보완 지점

### 3.1 수치와 조건의 근거 연결은 사람이 확인하는 수준

`rp_studio.py::citation_audit`는 각주의 `[번호]`가 SOURCES.md에 정의되어 있는지를 확인합니다.
주장의 숫자·단위·대상·기간이 실제 원문과 일치하는지는 검사하지 않습니다. 기존 코드도
`factual_accuracy_verified=False`라고 명확히 밝히고 있어, 이를 자동 사실 검증 기능으로
설명하면 안 됩니다.

보완: 원문 단위의 정확한 인용문과 문안 필드를 연결하는 `evidence.json`을 추가했습니다.
한 자리 숫자·연도·금액 단위·비율 등 지원하는 수량 표현을 비교하고, 지정된 필수 조건 및
일부 상한·자격·예외 표현이 빠지면 중단합니다. 정성적 의미 판단과 근거의 신뢰성 확인까지
자동화했다고 주장하지 않습니다.

### 3.2 낮은 색 대비는 경고이므로 완료 처리가 가능

`rp_studio.py::render_card`는 대비가 4.5 미만인 블록을 warnings에 남깁니다.
`build_project`는 이 경고를 별도의 실패 조건으로 사용하지 않습니다. 기본 프로필이 항상
문제라는 뜻이 아니라, 사용자 정의 저대비 프로필을 주었을 때 차단 규칙이 부족하다는 뜻입니다.

보완: 선택형 강화 경로에서 색상 메타데이터를 다시 계산하고 기준 미달이면 산출물 공개를
중단합니다. 사진 배경의 픽셀 실측이나 WCAG 인증으로 표현하지 않습니다.

### 3.3 SOURCES.md 변경은 기존 문안 승인 해시에 묶이지 않음

`rp_core.py::approve/require_approval`은 plan과 추출 source 레코드를 바인딩합니다.
SOURCES.md는 별도 기록이므로 변경 시 재검토하라는 지침은 있으나 자동 재승인 차단에
포함되지 않습니다. 기존 build manifest의 notes 해시는 **생성 후 변경 감지**용이지,
**승인 후 제작 전 근거 변경 차단**과 같은 기능이 아닙니다.

보완: 기존 승인 필드에 `quality_binding`을 추가하여 plan/source/SOURCES.md/evidence/검사정책을
함께 묶습니다. 이전 승인을 자동 변환하지 않고 실제 승인 후 새 강화 승인 기록을 만듭니다.

### 3.4 무결성 검사와 필수 산출물 완전성 검사는 다름

`verify_build`는 manifest에 선언된 파일과 ZIP 내용이 일치하는지 검사합니다.
그러나 manifest·ZIP이 함께 불완전한 상태로 구성된 경우, 모든 카드에 필요한 PNG/JPEG가
반드시 존재하는지를 독립적으로 재구성하여 확인하는 검사는 부족합니다. 단순 파일 수정은
기존 해시 검사로 이미 잡히므로, 기존 검사 전체가 무용하다는 뜻은 아닙니다.

보완: 기획 장수·카드 역할에서 필수 파일 목록을 다시 만들고 실제 파일 형식/해상도 및
페이지·문안·검사 기록의 일치를 추가 검사합니다. 해시는 여전히 전자서명이 아닙니다.

### 3.5 기존 문안 스키마는 의도적으로 엄격함

`validate_plan`과 JSON Schema는 최상위 세 키와 slide의 role/title/bullets/footnote만
허용합니다. CardPrinter의 chart/layout/image 키를 여기에 바로 넣으면 기존 검증과 PPTX
제작 흐름이 깨집니다.

보완: 근거 메타데이터를 `evidence.json`으로 분리했습니다. 미래의 디자인 확장도 별도
`visual.json` 등으로 설계하고 구버전 스키마와 명시적으로 연결하는 것이 적절합니다.

## 4. CardPrinter에서 채택·변경·제외한 사항

| CardPrinter의 접근 | 이번 반영 |
|---|---|
| 단계별 JSON 계약 | 기존 plan 유지 + evidence 별도 계약 |
| 실패 시 다음 완료 단계로 넘기지 않는 게이트 | preflight → 기존 렌더 → postflight → 완료 공개 |
| 숫자가 선언된 근거에 있는지 검사 | 원문 단위 인용 일치 + 완전한 숫자/단위 토큰 비교로 강화 |
| 카드·영상의 동일한 문안 원본 | 기존 PNG/HTML/PPTX의 문안 일치 검사에 적용; 영상은 미구현 |
| 브랜드/폰트/레이아웃 관리 | 기존 제주·neutral 프로필과 로고 승인 방식을 유지 |
| 실패 피드백 재생성 | 이번에는 자동 문안 수정·AI 재시도 없이 명확하게 중단 |
| AI 이미지·누끼·OCR | 업무 범위와 기존 환경을 고려해 미도입 |
| 승인·샌드박스 우회 팩토리 실행 | 도입하지 않음 |

CardPrinter의 G10은 자체 선언된 facts의 문자열에 숫자가 포함되는지 검사합니다.
원문 진위 검증이 아니며 부분 문자열 검사만으로 의미·단위·조건의 정확성을 보장할 수 없습니다.
따라서 ‘수치 날조 불가능’이라는 표현을 그대로 받아들이지 않았습니다.

## 5. 작성한 보완 코드

| 파일 | 내용 |
|---|---|
| `Jeju_Cardmaker/scripts/rp_quality.py` | 입력·근거·숫자·단위·기간·승인·출력 게이트 |
| `Jeju_Cardmaker/scripts/quality_cli.py` | 기존 렌더러를 감싸는 별도 CLI, 입력 스냅샷·실패 정리·검사 ZIP |
| `Jeju_Cardmaker/tests/test_quality.py` | 합성 입력·출력 계약·오류·차단 테스트 |
| `Jeju_Cardmaker/tests/test_quality_integration.py` | 실제 원본 코드가 있을 때 실행할 통합 테스트 |
| `Jeju_Cardmaker/references/cardprinter-quality.md` | 입력 규칙, 실행 절차, 실제 기능과 한계 |
| `Jeju_Cardmaker/assets/quality-example/` | 실제 정책이 아닌 재현용 가상 입력 |
| 패키지 루트 `apply_cardprinter_review.py` | 원본 커밋/원격/작업트리 확인, 추가 파일 반입·설명 보완·체크섬 갱신 |
| 패키지 루트 `tests/test_apply.py` | 임시 Git 저장소를 이용한 적용·충돌·롤백 검사 |

기존 core/renderer/CLI 구현은 덮어쓰지 않습니다. 적용 도구는 README.md, README.KO.md,
SKILL.md, CHANGELOG.md에 보완 안내를 추가하고 SHA256SUMS.txt를 갱신합니다.
본체 VERSION을 임의로 올리지 않으며 자동 커밋·푸시·설치도 하지 않습니다.

## 6. 테스트와 미검증 범위

실제 실행 결과는 함께 제공하는 `TEST_REPORT.md`, `TEST_RESULTS.json`, `TEST_LOG.txt`에
기록합니다. 합성 렌더 계약을 이용한 검사를 실제 `rp_studio` 렌더링 시험으로 표시하지 않습니다.
원본 코드가 없는 환경에서 통합 테스트는 skip으로 남기며 성공 건수에 넣지 않습니다.

Windows 설치·한글 폰트 실제 표시·PPTX 외관·실제 원본 전체 회귀시험·GitLab 배포·사용자 PC
설치는 이번 실행에서 검증하지 못했습니다. 원본에 적용한 뒤 기존 테스트 전체와 추가 통합
테스트를 실행하고 카드 전 페이지를 사람이 확인해야 합니다.

## 7. 후속 보완 범위 — 이번 코드에는 미구현

**디자인 다양화:** 표지/요약/체크리스트/비교/타임라인/수치 카드의 명시적 레이아웃 계약과
레이아웃별 글자·차트·로고 안전영역 테스트가 필요합니다. 기관 색상은 장식에 사용하고 본문
대비는 별도로 검사해야 합니다. 사진과 그림을 도입할 때에는 라이선스·실제 로고 출처·실제
지도/기관명·생성물 표시를 별도로 관리해야 합니다.

**차트:** 출처 필드, 단위, 기준연도, 정렬/축/0 기준과 표시 숫자의 동일성을 검증하는
독립 계약이 필요합니다. 서로 다른 사업·회계연도·지자체 범위를 임의로 합치면 안 됩니다.

**릴스:** 동일 plan에서 생성한 storyboard, 실제 파일 존재·9:16 규격·길이·자막 일치,
읽기 시간 및 카드가 잘리지 않는 배치 검사가 필요합니다. 선택적 FFmpeg 의존성과 실제
MP4 재생 검증을 추가한 뒤에만 지원 기능으로 표시해야 합니다. TTS·과금·게시 권한은 별도입니다.

**일괄 제작:** 로컬 큐·동시성 제한·실패 항목 분리와 명시적 자원 한도가 필요합니다.
조건을 삭제하거나 승인된 문안을 바꿔서 게이트를 억지로 통과시키는 self-heal은 금지해야 합니다.
재생성으로 문안이 바뀌면 재승인을 받아야 합니다.

## 8. 검토 출처

아래 GitLab 링크는 검토한 **고정 커밋**을 가리킵니다. 현재 main 전체가 이후에도 같다고
가정하지 않습니다. 적용 도구 역시 커밋이 다르면 자동 적용하지 않습니다.

- 대상 프로젝트: https://gitlab.aigov.go.kr/memory365/codex-codex-skills
- 기준 커밋: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/commit/1a17f3b38a8d23133358f3f01f339dabde7730a9
- README.KO.md: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/README.KO.md
- SKILL.md: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/SKILL.md
- rp_core.py: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/scripts/rp_core.py
- rp_studio.py: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/scripts/rp_studio.py
- rp_render.py: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/scripts/rp_render.py
- 기존 test_studio.py: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/tests/test_studio.py
- plan schema: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/Jeju_Cardmaker/references/plan.schema.json
- verify_package.py: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/verify_package.py
- 설치 코드: https://gitlab.aigov.go.kr/memory365/codex-codex-skills/-/raw/1a17f3b38a8d23133358f3f01f339dabde7730a9/install.py
- CardPrinter G10: https://github.com/gongnyang/cardprinter/blob/main/scripts/gates/g10_fact_fidelity.mjs
  (확인된 blob: `545a90c93f283dd86a4766ba926916c345e65db9`)
- CardPrinter factory: https://github.com/gongnyang/cardprinter/blob/main/scripts/factory/worker.sh
  (확인된 blob: `0afd2b6a4a23e9d8d83a9e9cc817589394de413f`)

새 Python 모듈은 이 프로젝트를 위해 작성한 보완 코드이며 CardPrinter의 소스·폰트·이미지·모델을
그대로 복사하여 배포하지 않았습니다. 이 문서는 대상 프로젝트의 기존 라이선스 조건을
임의로 변경하거나 새로운 라이선스를 대신 선언하지 않습니다.
