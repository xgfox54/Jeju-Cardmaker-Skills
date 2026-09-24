# 명령과 Windows 실행 예시

아래는 사용자 공통 설치 기준이다. 프로젝트 전용 설치에서는 `$S`를 해당 프로젝트의 `.agents\skills\Jeju_Cardmaker`으로 바꾼다.

```powershell
$S = Join-Path $HOME '.agents\skills\Jeju_Cardmaker'
$P = Join-Path $S '.venv\Scripts\python.exe'
$C = Join-Path $S 'scripts\Jeju_Cardmaker.py'
& $P $C doctor
```

## 재현 가능한 샘플 실행

빈 작업 폴더에서 실행한다. 같은 파일명으로 재실행하면 기존 산출물을 보호하기 위해 실패한다.

```powershell
& $P $C extract --input "$S\assets\sample.source.txt" --out .\source.json
& $P $C validate --plan "$S\assets\sample.plan.json" --pages 3
& $P $C render --plan "$S\assets\sample.plan.json" --source .\source.json --profile jeju --out .\sample-draft
& $P $C package --run .\sample-draft --out .\sample-draft.zip
```

## 주요 명령

| 명령 | 입력 | 결과 |
|---|---|---|
| doctor | 없음 | Python/패키지/폰트 상태. 네트워크 호출 없음 |
| extract | PDF/HWPX/TXT/MD | source.json: 파일 해시, 본문 위치, 추출 경고 |
| validate | plan.json, 선택한 페이지 수 | 엄격한 구조 검사. 사실 검증 아님 |
| review | plan.json + 선택 source.json | Markdown 기획안/검수 체크리스트 |
| approve | 계획+원문+실제 승인 | 변경 감지용 승인 기록 |
| render | 계획+프로필, 선택 원문/로고 | 1000×1350 JPEG, HTML, 검토 문서, 검사 보고 |
| package | render 결과 폴더 | 정해진 파일만 ZIP + 이미지형 PPTX |
| upstream-check | 별도 확보한 원본 저장소 | AST 기반 함수 계약 및 현재 커밋 확인 |
| upstream-export | 원본 저장소+로컬 결과 폴더 | 원본의 편집 가능한 문안 PPTX가 포함된 ZIP |
| api-plan | 원본+원문+모델+호출 승인 | 원본 OpenAI 함수로 생성한 미승인 기획안 |
| api-render | 원본+승인된 계획+API 승인 | 원본 GPT Image 카드 JPEG. 별도 시각 검수 필수 |

`--help`로 실제 옵션을 확인한다. `render --font <TTF/OTF/TTC> --bold-font <굵은 폰트>`로 설치된 폰트를 지정할 수 있다. `--logo <PNG>`는 승인된 로고를 합성하고 검은색 글자/픽셀을 제거하지 않는다.

## 출력물 성격과 개인정보

`plan.json`, `review.md`, JPEG에는 사용자 원문에서 작성한 문안이 들어간다. ZIP은 원본 파일과 전체 `source.json`, `.env`, 폰트, 임의 추가 파일을 포함하지 않지만 카드 문안 자체를 비식별화하지는 않는다. 기관 밖 전달 전 내용을 직접 검토한다. 출처 증빙 `evidence.md`와 원문은 기본적으로 작업 폴더에 별도 보관한다.

일반적인 텍스트/이미지 카드 미리보기를 만든다. 공인 KRDS 적합성 검사, 법률/자격 자동 판정, 실제 인쇄물 교정, 생성형 그림의 품질 보증은 하지 않는다. 영어 카드를 만들 때는 같은 스키마로 영어 `plan.json`을 별도 작성하고 `--locale en`을 사용한다.

## 문제 해결

- `글자가 넘칩니다`: 내용은 잘라내지 않았다. 페이지 분리 또는 더 짧고 정확한 문구가 필요하다.
- `폰트에 없는 글자`: 이모지 제거 또는 해당 글리프가 있는 로컬 폰트를 지정한다.
- `승인 후 ... 변경`: 수정된 문안/출처로 사용자 재승인을 받는다.
- `파일이 이미 있습니다`: 새 파일/폴더명을 지정한다. 자동 삭제하지 않는다.
- `PyMuPDF/Pillow 없음`: 스킬용 가상환경을 준비하거나 해당 가상환경의 Python으로 실행한다.
- 이미지 전용 PDF/HWP: 본문이 없는 상태에서 내용을 추측하지 않는다.
