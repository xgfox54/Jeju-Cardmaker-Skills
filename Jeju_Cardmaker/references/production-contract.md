# 카드뉴스 제작 계약

| 파일 | 용도 |
|---|---|
| brief.json | 주제·독자·목적·업무 예시·요청 장수 |
| storyboard.md | 장별 메시지·그림 종류·캐릭터 역할 |
| plan.json | 기존 스키마의 제목·본문·각주·layout/takeaway |
| SOURCES.md, source.json | 근거 대조와 원문 또는 조사 요약 추출 |
| diagrams.json | 그림 문구·사례·관계·단계 |
| visual_renderer.py, build.py | 그림 배치와 제작 실행 |
| draft/run-NN | 새로 제작한 초안 |
| qc/run-NN | 검사 보고·전체 장 축소 이미지·review.json |
| delivery/run-NN | 검사한 카드 파일과 검수 기록 |

brief.json과 storyboard.md는 기획 자료이며 기존 build에 새 기능을 자동 추가하지 않음. 원문·폰트·환경 설정·인증 정보는 전달 폴더에 복사하지 않음.

## 그림 원고

그림 문구는 diagrams.json 등 별도 원고에 정리하고 같은 내용으로 PNG와 편집형 PPTX를 만듦. 현행 예제는 일부 장면 문구를 렌더러에 포함함. 새 주제에서는 해당 문구도 수정하고 render-report.json의 모든 text 항목을 검사함. 범용 자동 그림 배치 엔진으로 설명하지 않음.

주제별 실행기는 render-report.json의 renderer_sources에 build.py·visual_renderer.py·diagrams.json 등 제작 파일의 SHA-256을 기록함. 현재 원고나 렌더러와 제작 기록이 다르면 이전 결과를 전달하지 않음.

한 장에 한 가지 내용과 읽을 수 있는 크기를 먼저 확보함. 넘침을 숨기려고 조건이나 그림 라벨을 삭제하지 않음. 아래 여백은 설명 그림과 예시에 사용하며 반복 문장·장식으로 채우지 않음.

## bookforge 참고 범위

로컬 bookforge의 SKILL.md, modes/topic.md, modes/manuscript.md, references/diagrams.md를 참고함. 입력 모드 분리, 콘텐츠·조판 역할 구분, 초안·전달 단계 구분, 검사 후 실제 화면 확인을 적용함.

책 전용 판형·목차·쪽수·긴 원고·Typst 엔진은 도입하지 않음. 카드뉴스는 기존 렌더러와 Pretendard·제주 펫 기준을 사용함. bookforge 코드를 복제하지 않고 기존 build 검증과 실제 좌표 정보를 활용함.
