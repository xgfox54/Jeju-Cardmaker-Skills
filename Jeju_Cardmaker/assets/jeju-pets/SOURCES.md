# 제주 펫 원본 기록

- 원본 저장소: https://gitlab.aigov.go.kr/memory365/codex-pet-3jeju
- 확인 커밋: ebca32e8f78a530c6010d1f4a429b14341f8572b
- 확인일: 2026-10-27
- 파일: docs/previews/gyulmo.png, harubang.png, halla.png
- 동작 시트: src/payload/gyulmo.spritesheet.png, harubang.spritesheet.png, halla.spritesheet.png
- 이름: src/payload/*.pet.json의 displayName 기준으로 귤귤, 하르방, 한라 사용
- 반영 범위: 사용자가 지정한 카드뉴스 제작을 위해 원본 PNG를 변경 없이 포함함
- 표시 방식: 원본 비율과 투명도 유지, 픽셀 형태를 유지하는 크기 조정만 적용함
- 이용 조건: 원본의 권리를 유지하며, 이 파일로 새로운 라이선스를 부여하지 않음

캐릭터별 7종, 총 21종의 동작 포즈는 원본 시트의 192×208 프레임을 추출한 투명 배경 PNG임. 손 인사, 좌우 걷기, 설명, 생각, 기쁨, 주의 표정을 포함함. 그림을 새로 생성하거나 색을 수정하지 않음. 원본 정면 PNG 3종은 호환용으로 보존함.

manifest.json은 원본 PNG와 시트의 SHA-256, 출처 커밋, 포즈별 행·열·추출 영역과 PNG 해시를 기록함. 캐릭터가 없거나 해시가 다르면 제작을 중단하며 임의 캐릭터로 대체하지 않음. 행·열은 0부터 시작함. 포함된 추출 스크립트는 원본 시트의 해시와 추출 결과의 RGBA 픽셀 일치를 확인함.
