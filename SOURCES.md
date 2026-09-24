# 제작 근거 및 확인 범위 — v1.1.0

확인일: 2026-09-24. 이 문서는 스킬 패키지의 제작 근거이며 JEV에 관한 최신 제품 안내가 아닙니다.

## 1. 사용자 제공 자료

공유 폴더: https://drive.google.com/drive/folders/18liyurGsvjnHOURWVK5L9m_Ipwoft2uX

Google Drive 커넥터로 폴더 목록과 3파일을 읽고 원본 바이트를 확보했습니다. Drive에 저장하거나 변경하지 않았습니다.

- plan.json: 파일 ID 1vIL8l66szoy27l3y0WDYWqMYYfiTX2Lh
- preview.html: 파일 ID 1gG2-7nKU9LDtxAJtortnzLOfiv_tVLNx
- SOURCES.md: 파일 ID 1KeJklnpGayxOp880XOXxc8tM1lrJSPin

reference-projects/jev-20260918에 보존한 원본 SHA-256:

- `plan.json`: `568aab67bb004a50de17edd2114428c65f862a780496beb0bd524e46f2e22b69`
- `preview.html`: `2400536d6b0d7bc202879ee42dbdf3eff9936f28288ef235fa0361d42c6a7de8`
- `SOURCES.md`: `e463869ca5e133ea077ea95d1603c7f64f28c5e3f55cc09255065e627e825efb`

preview.html은 별도 기획 사본을 포함하여 plan.json 수정이 자동 반영되지 않는다고 명시합니다. SOURCES.md에는 당시 카드별 근거, 초기 접근/회사 발표 수치라는 한계, 이미지형 PPTX라는 설명이 있습니다. 이는 당시 기록의 내용이지 이번에 해당 웹 출처를 다시 검증했다는 뜻이 아닙니다.

## 2. 업그레이드 기준

사용자 라이브러리에서 확보한 ReleasePick-Codex-Skill-v1.0.0(1).zip, 55,010바이트.

- SHA-256: `aee6878eed648aeaeeee51244f9dbd4cd5c5cdc366c7eaa47740359945b99d33`
- 실제 설치기·스킬 지침·CLI·렌더러·승인 및 추출 함수·시험 코드를 읽어 변경했습니다.
- 외부 원본 웹앱 ReleasePick의 최신 릴리스 번호를 확인하거나 변경한 것이 아닙니다.
- 이전 문서/보고서는 history/v1.0.0에 보존했습니다.

## 3. OpenAI 공식 문서

- https://developers.openai.com/codex/build-skills
- https://developers.openai.com/codex/customization/overview
- 연결된 문서 https://learn.chatgpt.com/docs/build-skills

확인한 내용: SKILL.md의 name/description, scripts/references/assets 구성, agents/openai.yaml, 명시적 $skill 호출, .agents/skills 로컬 설치 경로, allow_implicit_invocation 설정. 현재 문서는 더 넓은 배포를 위한 플러그인 구성도 안내하지만, 이번 요청은 로컬 스킬 설치 ZIP으로 구현했습니다. 별도 플러그인 등록은 수행하지 않았습니다.

## 4. 실행과 미검증 범위

코드 검사는 제작용 Linux 컨테이너에서 수행했습니다. 사용자의 Windows PC/Codex/PowerPoint를 조작하거나 그 환경에서 설치 완료를 확인하지 않았습니다. 로컬 빌더의 네트워크/API 동작은 없으며 선택적 upstream은 실제 유료 호출이나 최신 서버 연동 검증을 하지 않았습니다. 세부 시험 결과는 TEST_REPORT.md를 보세요.
