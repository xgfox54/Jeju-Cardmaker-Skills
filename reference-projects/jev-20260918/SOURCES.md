# JEV 카드뉴스 — 출처와 검증 메모

확인 기준일: 2026년 9월 18일. 아래 내용은 공식 웹자료 대조 메모이며 원문 전체를 보존한 문서가 아닙니다.

## 공식 자료

[1] TypeSafe AI, Introducing System One Models & Jev
https://typesafe.ai/blog/introducing-system-one-models-and-jev
공식 게시일: 2026년 9월 15일. Jev는 초기 접근(Early Access) 모델이며 개발자를 대기 목록에서 순차적으로 받는다고 설명합니다. 회사는 응답 시간 70~500ms, 입력 100만 토큰당 0.042달러, 출력 토큰 무료를 발표했습니다. 측정 환경과 작업에 따라 달라지며 독립적인 범용 성능 보장으로 해석하지 않습니다. 형식 보장과 판단의 정확성은 구분합니다.

[2] TypeSafe AI, Introduction
https://docs.typesafe.ai/introduction
입력은 상태와 타입이 정해진 질문입니다. 출력은 구조화된 판단값입니다. Choice는 후보 선택, Score는 정해진 단계 기준의 평가, Noul은 예/아니오 질문에 대한 예의 확률(0~1)입니다. 여러 독립 질문을 한 번의 호출에서 병렬로 평가하며, 복잡한 판단은 구체적인 질문으로 나누도록 안내합니다.

[3] TypeSafe AI, Quick start
https://docs.typesafe.ai/introduction/quickstart
로그인 후 Playground에서 상태와 질문을 입력할 수 있습니다. API 키는 Dashboard에서 발급합니다. SDK는 TYPESAFE_API_KEY 환경변수를 사용하며 기본 모델은 jev-latest입니다. 이 카드뉴스 제작에서는 실제 가입·키 발급·API 호출을 하지 않았습니다.

[4] TypeSafe Console
https://console.typesafe.ai/
확인 당시 로그인 페이지로 연결되었습니다. 개인 계정의 승인 상태나 즉시 사용 가능 여부는 확인하지 않았습니다.

[5] browser-use, jev-ultrafast README
https://github.com/browser-use/jev-ultrafast
https://github.com/browser-use/jev-ultrafast/blob/main/README.md
Jev를 활용하는 브라우저 에이전트 데모입니다. 관찰된 웹 요소와 가능한 동작을 후보로 제공하고 Jev가 동작과 대상을 선택합니다. TYPE_TEXT 동작에서 별도 작은 LLM이 입력 문자열을 만듭니다. 기본 에이전트 루프는 스크린샷이 아니라 구조화된 상태를 사용합니다. DONE은 성공의 증거가 아니며 실제 결과를 별도로 검증해야 한다고 명시합니다.

## 카드별 근거

| 카드 | 주요 내용 | 근거 |
|---|---|---|
| 1 | TypeSafe의 첫 System One 모델, 구조화된 판단값 | [1] 첫 소개, [2] Introduction |
| 2 | 상태·질문 입력 및 텍스트 생성과의 목적 차이 | [2] Introduction |
| 3 | Choice·Score·Noul | [2] TypeSafe primitives, [3] Quick start |
| 4 | 회사 발표 속도·가격 및 병렬 질문 처리 | [1] 비교표와 측정 조건 설명, [2] TypeSafe primitives |
| 5 | Jev 모델과 브라우저 데모의 구분, 별도 텍스트 모델 | [5] The action space·Try it |
| 6 | 로그인·초기 접근·Playground·API 키 | [1] What's next, [3] Try it·Call it, [4] 로그인 화면 |
| 7 | 형식 일치와 판단 정확성 구분, 실행 결과 확인 | [1] Hallucination and Type-safety, [5] Evidence and limits |
| 8 | 분류·선택·평가 활용, 생성형 AI와 분업, 시작 경로 | [2][3][5] 종합 정리 |

## 중요한 구분

- 문의 유형·우선순위·긴급도는 가상의 설명용 예시입니다. 한국어 실무 성능을 직접 측정한 결과가 아닙니다.
- Noul 값은 모델이 제시하는 확률입니다. 모든 실제 상황에서의 정답률 또는 안전성 보장과 같지 않습니다.
- 제7장의 한국어·업무 검증과 사람 검토는 제작자가 제시한 적용 제안입니다.
- 앞선 대화의 공개일 2026년 9월 14일은 공식 발표 페이지의 2026년 9월 15일로 정정했습니다.
- 이 결과는 검토용 초안입니다. 문안 승인·게시 승인으로 간주하지 않습니다. 외부 API 호출 및 SNS 게시를 하지 않았습니다.

## 실행·저장 구분

데스크톱에는 plan.json, preview.html, SOURCES.md를 GPT-chat connect 직접 파일 생성으로 저장했습니다. PC 명령 실행은 별도 승인 대기 상태여서 데스크톱에서 Python 렌더러를 실행하지 않았습니다. preview.html은 사용자가 직접 열어 8장을 보고 JPEG·PNG를 저장할 수 있는 오프라인 미리보기입니다. 실제 Windows 브라우저 화면은 아직 검증하지 않았습니다.

채팅에 첨부된 JPEG와 검토용 PPTX는 확보한 ReleasePick v1.0.0 패키지의 로컬 렌더러를 대화 작업환경에서 실행해 생성했습니다. PPTX는 카드 이미지를 넣은 검토용으로 내부 글자를 직접 편집할 수 없습니다. 폰트 파일은 포함하지 않습니다.
