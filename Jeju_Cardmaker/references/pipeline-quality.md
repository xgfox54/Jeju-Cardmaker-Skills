# 검수와 전달

scripts/card_pipeline.py는 서귀포시 직원 AI 카드 결과를 검사하고 전달 폴더를 만드는 도구임. 기존 build·승인 명령은 그대로 사용함. 일반 jeju·neutral 프로필은 기존 verify-build와 수동 검수 경로를 사용함.

| 구분 | 자동 검사 |
|---|---|
| 파일 | manifest와 ZIP, PNG 크기·장수 |
| 현재 원고 | plan.json·SOURCES.md·기록된 렌더러 해시 |
| 글자 | 경계, 글자끼리·캐릭터와의 겹침, 대비 |
| 글꼴·크기 | Pretendard, 본문 최소 30px, 그림 라벨 최소 24px |
| 디자인 | 제주 테두리, 상자 밖 원 3개, 중앙 라벨 |
| 캐릭터 | 원본 PNG 해시, 첫·마지막 장의 3종 |
| 편집본 | 제작 기록과 PPTX 텍스트·캐릭터 개수 |

px 기준은 1080px 논리 너비임. quality-policy.json은 기존 디자인을 검증하는 기준이며 이 파일만 바꾼다고 모든 배치가 자동 변경되지는 않음. 실패하면 위치·줄바꿈·문장 길이를 조정하고 새 초안을 제작함.

출처 누락과 합니다체 잔존은 문맥 검토 경고로 남김. 원문 인용까지 일괄 치환하지 않음. 원문 대조, 그림 의미, 캐릭터 역할, 여백은 실제로 확인함.

## 검수 기록

inspect는 gate-report.json, review.json, contact-*.png와 각 장의 축소 이미지를 새 qc 폴더에 만듦. review.json은 미검수 상태로 시작함. 전체 장을 확인한 후 reviewer·sources_checked와 페이지별 visual_checked·copy_checked·diagram_checked·character_checked·spacing_checked를 채움. 경고는 warning_notes에 위치와 처리 내용을 기록함.

run_id는 결과 manifest, 현재 제작 입력, 검사 기준과 검사 코드의 해시에 연결됨. 각 장은 PNG 해시에도 연결됨. 내용이나 기준이 바뀌면 이전 기록으로 전달할 수 없음. 해시는 수정 감지용이며 서명이나 검수자 신원 인증이 아님.

## 전달

deliver는 현재 상태를 다시 검사하고 모든 장의 기록을 확인함. 실패하면 전달 폴더를 만들지 않음. 성공하면 허용된 파일만 cards/에 복사하고 qc/에 검수 기록을 보관함. 기존 폴더를 덮어쓰지 않음.

검수 기록이 있다는 사실만으로 실제 화면을 보았다는 것을 도구가 증명하지는 못함. 확인하지 않은 항목을 통과로 기록하지 않음. 검사 통과와 문안 승인·기관 게시 승인·접근성 인증은 별개임. 실제 PowerPoint 화면을 확인하지 않았으면 완료 보고에 남김.
