# 확인 자료

확인 기준: 2026-09-18. 저장소 main의 웹 공개 파일 내용을 읽어 인터페이스를 조사했다. 실제 저장소를 이 컨테이너에 복제해 원본을 실행한 것은 아니다. 내려받은 원본 전체 커밋을 고정했다고 주장하지 않는다. 이후 사용자의 bootstrap 실행은 실제 HEAD와 파일 SHA-256을 기록한다.

## OpenAI 공식 문서

- https://developers.openai.com/codex/skills
- 조회 시 연결된 문서: https://learn.chatgpt.com/docs/build-skills
- 확인 사항: SKILL.md의 name/description, 선택 scripts/references/assets, agents/openai.yaml, `$` 명시 호출, 사용자/프로젝트 `.agents/skills` 설치 경로, 암묵 호출 비활성화 옵션.

## 원본 ReleasePick

- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/blob/main/README.md?ref_type=heads
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/models.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/render_cards.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/package_export.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/export_plan_pptx.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/pdf_extract.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/hwpx_extract.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/plan_llm.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/image_gen.py
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/requirements.txt
- https://gitlab.aigov.go.kr/chaeun74/Releasepick/-/raw/main/code/content_filter.py

README의 흐름/제약/권리 문구, 모델 필드, 공개 함수 시그니처, 원본 렌더링의 넘침 처리, 원본 이미지 생성의 브랜딩 및 재시도를 확인했다. `content_filter.py`는 도구가 제공한 앞부분만 확인했으며 전체 감사를 수행하지 않았다. 웹 추출본은 코드 실행용 원본 바이트로 사용하지 않았다.

## 연결 및 실행 제한

DESKTOP 커넥터의 agent_guide와 runtime_diagnostics 호출은 모두 `FORBIDDEN: This conversation does not support developer MCPs`를 반환했다. 이 패키지 제작은 별도 작업 컨테이너에서 수행했다. 사용자 PC의 Codex 설치 상태, 파일 시스템, Python 버전은 확인하지 못했다.

컨테이너의 원본 Git clone 시도는 호스트 이름 해석 실패로 종료됐다. 이후 실제 공개 파일 텍스트는 웹 콘텐츠 조회 도구로 읽었다. 이 차이를 TEST_REPORT.md에 구분하여 기록했다.
