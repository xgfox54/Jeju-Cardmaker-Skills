# 직원 AI 카드뉴스 v1.3.2 검증

검사일: 2026-10-27. Windows, Python 3.14.6, Pillow 12.3.0, python-pptx 1.0.2 환경에서 실행함. 설치된 스킬 파일은 교체하지 않음.

| 검사 | 결과 |
|---|---|
| 전체 unittest | 106개 중 103개 통과, 심볼릭 링크 권한으로 3개 건너뜀, 실패·오류 없음 |
| 직원 AI 템플릿 | 11개 통과. 원의 바깥 배치, 라벨 중앙 정렬, 문안 길이 변경에 따른 캐릭터 이동, 단어 단위 줄바꿈 검사 포함 |
| 원 3개 | PNG·편집형 PPTX에서 오렌지·블루·그린 순서 유지. PNG 좌표에서 원 전체가 테두리 윗선 밖에 있음을 확인 |
| 라벨 | 1080px·2160px 출력에서 실제 글자 경계의 가로·세로 중심 오차 1px 이내. PPTX 텍스트의 중앙 정렬 속성 확인 |
| 캐릭터 | 제목 길이를 바꾼 시험에서 위치 변경 확인. 글자·비교 상자·요약 상자와 겹침 없음 |
| 본문 | 비교 제목과 설명 분리, 번호 중앙 정렬, 단어 경계 줄바꿈, 본문 다음 요약 배치 확인 |
| 2160×2700 예제 | 8장 PNG·JPEG·PPTX·HTML·ZIP 생성. verify-build에서 52개 파일 확인 |
| 직접 시각 검수 | 최종 PNG 8장 확인. 원 위치·색상 순서, 라벨 정렬, 비교 문장의 줄바꿈, 캐릭터 위치 확인 |
| 글꼴·원본 | Pretendard Regular/Bold 및 기존 동작 포즈 21종 유지 |

## 재현 명령

```text
python -m unittest discover -s Jeju_Cardmaker/tests -v
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py build --project Jeju_Cardmaker/assets/seogwipo-ai-example --out <새 출력 폴더>
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py verify-build --run <출력 폴더>
python verify_package.py
```

## 문장과 검수 범위

Test-Slop.ps1을 문서 technical/team 30개, README general/general 32개, 카드 문안 general/slides 34개, 새 코드 문자열 technical/general 30개 규칙으로 실행함. 검출 문구는 실제 문맥과 비교하고 원본 세트명·화면 항목명·이전 기록의 보존 사유를 위치별로 기록함. 최종 PNG의 문구를 직접 확인함.

PowerPoint 앱에서 실제 열기와 편집 후 외관은 미검증임. PPTX 정렬 속성과 이미지·문안 보존을 확인한 범위임. 설치기 실행과 macOS/Linux 실행은 이번 검사에 포함하지 않음. 예제는 디자인 검토용 초안이며 게시 승인을 의미하지 않음.
