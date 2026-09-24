# v1.1 명령 안내

스킬 루트의 `.venv/Scripts/python.exe`(Windows) 또는 `.venv/bin/python`을 사용한다. 아래 python은 그 실행 파일을 뜻한다.

## 권장: 한 번의 build

```text
python scripts/Jeju_Cardmaker.py build --project <plan.json이 있는 폴더> --out <새 결과폴더>
```

| 옵션 | 의미 |
|---|---|
| --preset portrait-2x | 기본값. 2160×2700, 4:5 |
| --preset portrait | 1080×1350, 4:5 |
| --preset legacy | 1000×1350. 새 레이아웃의 이전 규격 |
| --profile jeju | 기본값. 제주 사용자 팔레트, 기관명·로고는 공란 |
| --profile neutral | 기존 중립 팔레트 |
| --profile <JSON> | 사용자 프로필 파일. 기존 프로필 필드 사용 |
| --source <source.json> | extract 결과 연결. 지정하지 않으면 초안의 원문 미연결 표시 |
| --approval <approval.json> --final | 실제 문안 승인 기록을 확인하고 승인본 생성 |
| --hide-status | --final과 함께만 사용. 카드 위 상태 글자 제거 |
| --font <TTF/OTF/TTC> --bold-font <폰트> | 해당 PC에 설치된 폰트 참조, 폰트 파일 미포함 |
| --logo <이미지> | 사용자 승인 로고. 색과 투명도 보존 |
| --no-pptx | PPTX 두 종류를 제외하고 이미지·HTML·ZIP 생성 |

SOURCES.md가 있으면 자동 포함한다. 기존 preview.html은 입력하지 않는다. source.json의 원문 전체, .env와 기타 이웃 파일은 ZIP에 넣지 않는다. SOURCES.md 자체에 비공개 내용이 있으면 ZIP 공유 전 제거/검토한다.

## 출력 검사

```text
python scripts/Jeju_Cardmaker.py verify-build --run <결과폴더>
```

이미지뿐 아니라 원고·출처·HTML·PPTX가 생성 후 바뀌었는지 확인한다. ZIP 내용도 대조한다. 승인된 파일을 일부러 편집한 경우에도 변경으로 판정한다. 검증 성공은 전자서명이나 사실 검증이 아니다.

## 이전 명령 호환

v1.0의 extract, validate, review, approve, render, package, doctor와 선택적 upstream 명령은 유지한다. `references/commands.md`는 이 이전 명령의 안내다. 기존 render 결과를 package에 넘기고, 새 build 결과는 이미 cardnews.zip을 포함하므로 verify-build로 검사한다. 두 결과 형식을 혼용하지 않는다.

## Windows 예시

명령어를 직접 입력하는 대신 Codex에서 `$Jeju_Cardmaker`으로 요청하면 된다. 수동 실행 예시는 아래와 같다.

```powershell
python "$HOME\.agents\skills\Jeju_Cardmaker\scripts\Jeju_Cardmaker.py" doctor
python "$HOME\.agents\skills\Jeju_Cardmaker\scripts\Jeju_Cardmaker.py" build --project "C:\CardNews\source" --out "C:\CardNews\draft-01"
```

일반 python에 의존성이 없는 경우 스킬 전용 Python을 실행 환경으로 선택한다. PowerShell에서 문자열 형태 실행 파일 경로를 직접 호출하는 문법 대신, 해당 .venv\Scripts 폴더로 이동하여 `.\python.exe`로 실행해도 된다.
