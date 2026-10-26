# 직원 AI 카드뉴스 v1.3.0 검증

검사일: 2026-10-27. Windows, Python 3.14.6, Pillow 12.3.0, python-pptx 1.0.2, fonttools 4.66.1 환경에서 실행함. 기존 사용자 설치본의 실행 환경만 이용했으며 설치된 스킬 파일은 교체하지 않음.

## 실행 결과

| 검사 | 결과 |
|---|---|
| 전체 unittest | 103개 중 100개 통과, 3개 건너뜀, 실패·오류 없음 |
| 새 템플릿 시험 | 8개 통과. 기본 프로필, 문안 보존, 캐릭터, 폰트, 비교 입력, 넘침, 원본 변경 검사 |
| 1080×1350 | 8장 이미지·PPTX·ZIP 생성 및 무결성 검사 통과 |
| 2160×2700 | 8장 이미지·PPTX·ZIP 생성, 최종 결과 31개 파일과 ZIP 내용 대조 통과 |
| 실제 폰트 | Pretendard-Regular.otf, Pretendard-Bold.otf 사용 |
| 캐릭터 원본 | 귤귤·하르방·한라 PNG의 원본 SHA-256 일치 |
| 편집형 PPTX | 본문·핵심 정리·각주가 텍스트 개체로 유지됨. 캐릭터 이미지 바이트와 원본 일치 |
| 글자 경계·대비 | 예제 전 페이지 넘침·겹침 없음, 텍스트 대비 4.5 이상 |
| 직접 시각 검수 | 고해상도 8장 확인. 마지막 문구 수정 후 해당 4·8장 재확인 |
| 기존 기능 | jeju·neutral 및 이전 render/package 회귀 검사 통과 |

재현 명령:

```text
python -m unittest discover -s Jeju_Cardmaker/tests -q
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py doctor
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py build --project Jeju_Cardmaker/assets/seogwipo-ai-example --out output-example
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py verify-build --run output-example
python verify_package.py
```

## 문장 검수

Test-Slop.ps1을 문서 technical/team 30개 규칙, README general/general 32개 규칙, 예제 general/slides 34개 규칙, 호출 예시 technical/prompt 31개 규칙, 추가 코드 문구 technical/general 30개 규칙으로 실행함. 코드의 새 한국어 문자열은 파일·행 위치와 함께 텍스트로 추출하여 검사함.

검출된 항목은 문맥 검토 후 수정하거나 위치·파일 해시·이유를 기록한 예외로 처리함. 제주 펫이라는 원본 세트명, 핵심 정리라는 화면 항목명, 프롬프트를 같은 문장에서 설명한 정의, 수정하지 않은 과거 기록의 표기를 보존함. 예제의 수량 표현은 1건으로 수정함. 최종 문구는 실제 PNG에서 확인함.

## 호환성과 미검증 범위

- 기존 호출명 Jeju_Cardmaker 유지. skill-creator의 quick_validate는 이 기존 이름의 대문자·밑줄을 허용하지 않음. 이름만 소문자 하이픈 형태로 바꾼 임시 사본에서는 나머지 검사 통과. 실제 호출명이나 설치 경로는 변경하지 않음.
- 3개 건너뜀은 심볼릭 링크 권한에 따른 기존 테스트임.
- PowerPoint 앱에서 실제 열기와 편집 후 외관은 미검증. 글꼴은 임베딩하지 않으며 대상 PC에도 Pretendard 필요.
- 실제 Windows 설치기 클릭, macOS/Linux 실행, 유료 API, SNS 게시 미수행.
- 예제는 가상 업무를 사용한 디자인·기능 시험 자료임. 교육 원고의 승인 또는 기관 정책 검증을 의미하지 않음.
- TEST_REPORT.md, TEST_LOG.txt, TEST_DETAILS.json은 과거 버전 기록이며 이번 결과로 바꾸지 않음.
