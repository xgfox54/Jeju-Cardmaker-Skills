# 직원 AI 카드뉴스 v1.3.1 검증

검사일: 2026-10-27. Windows, Python 3.14.6, Pillow 12.3.0, python-pptx 1.0.2 환경에서 실행함. 기존 사용자 설치본의 실행 환경만 이용했으며 설치된 스킬 파일은 교체하지 않음.

| 검사 | 결과 |
|---|---|
| 전체 unittest | 104개 중 101개 통과, 심볼릭 링크 권한으로 3개 건너뜀, 실패·오류 없음 |
| 직원 AI 템플릿 | 9개 통과. 원 3개의 색상 순서·픽셀, 하단 단색 테두리, 동작 포즈·투명도·출처 포함 |
| PNG와 편집형 PPTX | 오렌지·블루·그린 원 3개와 동작 포즈 일치. PPTX 원은 타원 개체, 캐릭터는 이미지 개체로 유지 |
| 1080×1350 | 8장 이미지·PPTX·ZIP 제작, 폰트·문안·대비·글자와 캐릭터의 겹침 검사 통과 |
| 2160×2700 | 8장 이미지·PPTX·ZIP 제작 및 verify-build 통과 |
| 원본 재현 | 고정 커밋의 시트 해시 확인. 21개 포즈를 다시 추출하여 원본 프레임과 RGBA 픽셀 일치 확인 |
| 포즈 목록 | 캐릭터별 7종, 192×208 투명 PNG. 행·열·추출 영역·시트 해시·PNG 해시 기록 |
| 직접 시각 검수 | 8장 PNG와 포즈 21종 목록 확인. 하단 띠 없음, 왼쪽 위 원 순서 일치, 글자 잘림·캐릭터 겹침 없음 |
| 글꼴 | Pretendard Regular/Bold 유지 |

## 재현 명령

```text
python -m unittest discover -s Jeju_Cardmaker/tests -v
python Jeju_Cardmaker/scripts/extract_pet_poses.py --source-root <원본 저장소> --out <새 출력 폴더>
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py build --project Jeju_Cardmaker/assets/seogwipo-ai-example --out <새 출력 폴더>
python Jeju_Cardmaker/scripts/Jeju_Cardmaker.py verify-build --run <출력 폴더>
python verify_package.py
```

## 검수 범위

새 문서·수정 문구는 Test-Slop.ps1과 문맥 검토를 함께 적용함. 문서 technical/team 30개, README general/general 32개, 포즈 화면 general/ui 34개, 카드 문안 general/slides 34개, 새 코드 문자열 technical/general 30개 규칙으로 구분함. 원본 세트명인 제주 펫, 실제 화면 항목명인 핵심 정리와 주의 포즈, 수정하지 않은 이전 기록은 위치와 사유를 기록하여 보존함.

PowerPoint 앱에서 열어 편집한 외관, 새 설치기 실행, macOS/Linux 실행은 이번 검증에 포함하지 않음. 예제는 디자인 검토용 초안이며 게시용 문안 승인을 의미하지 않음. 기존 jeju·neutral 프로필은 유지함. 포즈 PNG는 애니메이션 시트에서 뽑은 정지 이미지임.
