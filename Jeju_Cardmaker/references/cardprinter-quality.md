# CardPrinter 참고 품질 보완 경로

모듈 버전: **2026.10.09.1**. 호환 기준: **Jeju_Cardmaker v1.1.1**.
기존 `Jeju_Cardmaker.py build`의 동작을 바꾸지 않는 선택형 강화 경로입니다.
기존 명령을 그대로 실행하면 새 검사가 자동 적용되지 않습니다.

## 유지하는 원칙

`plan.json`의 `series_title`, `head_copy`, `slides` 구조와 기존 렌더러를 유지합니다.
원문·문안·출력물을 조용히 수정하거나 글자를 잘라내지 않습니다. 인터넷, LLM, 유료 API,
OCR, Codex 실행, SNS 게시, 전역 설치를 호출하지 않습니다. 검사를 통과했다는 이유로
문안 승인을 생성하지 않습니다. 폰트 파일은 어느 배포 패키지에도 추가하지 않습니다.

본 모듈은 접근성 인증 도구나 사실 검증 서비스가 아닙니다. 수작업으로 입력한 확인자·확인일의
진위를 입증하지 않으며, 원문 자체가 정확한지 또는 현재 공식 자료인지 네트워크로 확인하지 않습니다.

## 필요한 입력

작업 폴더에 다음 네 파일을 준비합니다. `source.json`은 기존 `extract` 명령의 결과를 사용합니다.

```text
project/
  plan.json
  source.json
  SOURCES.md
  evidence.json
```

`SOURCES.md`의 출처 번호 `[1]`, `[2]`와 `evidence.json`의 `sources[].id`를 연결합니다.
`evidence.json` 예시는 `assets/quality-example/`에 있습니다. **예시의 지원 조건은 가상 데이터입니다.**
실제 보도자료에는 그 예시를 그대로 사용하지 마세요.

### evidence 작성

`schema_version`은 1, `as_of`는 검토 기준일입니다.
`source_record_sha256`은 원문의 `source_sha256`과 `units`를 기존 core와 같은 방식으로
정규화해 계산합니다. 다음 코드는 계산만 하며 원문을 고치거나 확인했다고 승인하지 않습니다.

```python
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path("Jeju_Cardmaker/scripts").resolve()))
from rp_quality import source_digest
source = json.loads(Path("project/source.json").read_text(encoding="utf-8-sig"))
print(source_digest(source))
```

`sources`에는 실제 확인한 출처의 `id`, `title`, `reference`, `checked_on`, `checked_by`를
기록합니다. 확인하지 않은 자료에 확인자·확인일을 만들어 넣지 않습니다.
`published_on`, `valid_from`, `valid_until`은 원문에서 확인된 때만 기입하고, 알 수 없으면
생략합니다. 미래 시행 안내와 현행 안내는 별도의 문안·기준일로 관리합니다.

`claims`는 비어 있지 않은 모든 문안 필드를 하나씩 분류합니다. `/series_title`, `/head_copy`,
`/slides/0/title`, `/slides/0/bullets/0`, `/slides/0/footnote`와 같은 JSON Pointer를 사용합니다.
`text`는 해당 필드의 문안 전체와 정확히 같아야 합니다.

- `fact`: `source_id`, `locator`, `quote`가 필요합니다. `quote`는 지정한 원문 단위에 실제로
  존재하는 인용문이어야 합니다. 해당 카드 각주에 같은 출처 번호가 있어야 합니다.
- `editorial`: 수치 없는 제목·편집 문구용입니다. **사실 주장을 임의로 editorial로 분류해
  검사를 피하면 안 됩니다.** 분류의 타당성과 정성적 의미는 사람이 검토합니다.
- `attribution`: 각주의 출처 표기용입니다. 출처 번호 밖에 수치가 있으면 fact로 연결해야 합니다.

`required_terms`에는 빠지면 의미가 달라지는 신청 자격·기간·제외 대상 등 실제 원문의 표현을
적습니다. `이상`, `이하`, `미만`, `초과`, `최대`, `최소`, `이내`, `제외`, `본인부담`, `비급여`는
인용문에 있으면 자동으로 보존 여부를 검사합니다. 넓은 원문을 한 번에 인용하면 관련 없는 조건도
잡힐 수 있으므로 문안에 직접 대응하는 짧고 정확한 인용문을 사용합니다.

### 숫자 검사 범위

한 자리 숫자, 연도, 소수, 퍼센트와 명·건·원·세 등 지원하는 단위를 확인합니다.
`10만원`과 `100,000원`, `1만 명`과 `10,000명`처럼 지원하는 축약 단위는 환산합니다.
`65`가 `165`의 일부라는 이유로 통과하지 않습니다. `10만원`과 `10억원`, `1만명`과 `1만건`은
같은 값으로 취급하지 않습니다. 잘못된 쉼표 묶음과 인식할 수 없는 일부 복합 단위는 중단합니다.
모든 자연어 수량 표현을 이해하는 파서는 아니므로 한글로 풀어 쓴 수, 비율의 의미, 추론·증감률,
여러 지표 사이의 인과관계는 별도로 대조해야 합니다.

## 명령

아래 경로는 저장소 루트 기준입니다. 설치된 스킬에서는 해당 스킬의 `scripts/` 경로를 사용합니다.
예시의 `2026-10-09`는 재현용 기준일이며 실제 업무는 실제 확인 기준일로 바꿉니다.

### 사전검사

```text
python Jeju_Cardmaker/scripts/quality_cli.py preflight --project <작업폴더> --as-of 2026-10-09
```

기본 확인일 허용 기간은 30일입니다. 이는 본 보완안의 보수적인 운영 기본값이지 법정 기간이
아닙니다. `--max-age-days 7`처럼 변경할 수 있으며, 정책을 바꾸면 기존 강화 승인 기록도
무효가 됩니다. 민감한 법령·사업기준은 허용 기간과 무관하게 실제 최신 공식 자료를 확인하세요.

### 강화 초안 제작

```text
python Jeju_Cardmaker/scripts/quality_cli.py build --project <작업폴더> --out <새결과폴더> --as-of 2026-10-09 --preset portrait-2x
```

기존과 같이 `--profile`, `--font`, `--bold-font`, `--logo`, `--no-pptx`를 사용할 수 있습니다.
이미 있는 출력 폴더나 원문 프로젝트 안에는 저장하지 않습니다.
사전검사를 통과한 입력을 임시 스냅샷으로 만든 뒤 기존 렌더러를 호출합니다.
사후검사 또는 무결성 검사가 실패하면 완료 폴더로 공개하지 않습니다.
제작 중 원문·문안·근거 파일이 바뀌어도 완료 처리를 중단합니다.

### 실제 사용자 문안 승인 후

다음 명령은 **사용자가 문안을 실제로 승인한 뒤에만** 실행합니다. 시험 예시에는 실사용 승인
기록을 넣지 않았습니다. 자동 테스트의 승인자는 명시적으로 가상의 테스트 값입니다.

```text
python Jeju_Cardmaker/scripts/quality_cli.py approve --project <작업폴더> --as-of 2026-10-09 --out <새승인기록.json> --reviewer "실제 승인자" --confirmed
python Jeju_Cardmaker/scripts/quality_cli.py build --project <작업폴더> --out <새승인본폴더> --as-of 2026-10-09 --approval <승인기록.json> --final
```

기존 core의 승인 형식에 `quality_binding`을 추가합니다. plan·추출 원문뿐 아니라 SOURCES.md,
evidence, 검사 정책의 해시를 함께 확인합니다. 예전 승인 기록을 강화 승인 기록으로 자동
승격하지 않습니다. 문안 승인과 디자인 승인·기관 대외 게시 승인은 여전히 구분합니다.
승인본의 상태 표시 제거는 실제 요청이 있을 때만 `--hide-status`를 추가합니다.

### 결과 검증

```text
python Jeju_Cardmaker/scripts/quality_cli.py verify --run <결과폴더>
```

기존 ZIP과 manifest를 기존 검증기로 확인한 뒤 보완 ZIP도 대조합니다. 파일을 추출하지 않고
항목 목록·중복·해시·제한 크기를 검사합니다. 배포 ZIP에 들어 있지 않은 source/evidence의
원문 재검증은 하지 않았다고 명시합니다.

## 출력

기존 PNG/JPEG/HTML/PPTX/`cardnews.zip`은 기존 형식을 유지합니다. 여기에 다음 세 파일이 추가됩니다.

| 파일 | 역할 |
|---|---|
| `quality-report.json` | 사전·사후 검사 결과, 정책, 입력 해시, 미검증 범위 |
| `quality-manifest.json` | 기존 산출물과 보완 보고서의 변경 감지용 해시 |
| `cardnews-checked.zip` | 기존 산출물에 보완 검사 기록을 함께 넣은 전달용 ZIP |

기존 `cardnews.zip`을 보완 ZIP 안에 다시 넣지는 않습니다. `source.json`, `evidence.json`,
API 키, 폰트, 작업 폴더의 이웃 파일을 자동 동봉하지 않습니다. 기존 정책대로 `SOURCES.md`는
동봉하므로 개인·비공개 정보가 있는지 공유 전에 반드시 확인해야 합니다.

## 실제 사후검사와 한계

필수 파일·이미지 수·역할·실제 PNG/JPEG 해상도·해시, 모든 문안 필드와 렌더링 텍스트의 일치,
줄바꿈 과정의 누락, 실제 글자 경계와 상자/안전영역, 본문 최소 크기를 확인합니다.
색 대비는 기존 **단색 배경 렌더러의 색상 메타데이터를 재계산**합니다. 사진 배경의 픽셀 실측이
아니며 임의로 수정된 이미지에서 OCR로 글자를 다시 읽는 검사도 아닙니다.
PPTX는 기존 편집형/이미지형 파일 생성을 유지할 뿐 대상 PC에서의 외관을 인증하지 않습니다.

사진·캐릭터 생성, 새 레이아웃 엔진, 차트, MP4, TTS, 병렬 AI 재시도, 자동 게시 기능은
이번 모듈에 들어 있지 않습니다. 해당 기능은 검토보고서의 후속 구현 범위로 구분했습니다.

## 테스트

```text
python -m unittest discover -s Jeju_Cardmaker/tests -v
python verify_package.py
```

`test_quality.py`는 합성 데이터/렌더 보고서 기반 검사입니다. `test_quality_integration.py`는
실제 기존 core/renderer가 있어야 실행되며, 없으면 명시적으로 skip합니다. 새 테스트 성공을
기존 전체 회귀시험·Windows 실행·시각 검수 성공으로 확대 해석하지 않습니다.
