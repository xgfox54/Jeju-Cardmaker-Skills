# 원본 ReleasePick 연결

## 원본을 포함하지 않은 이유

원본 README §12.3은 내부 시연/행정 활용을 설명하고 외부 공개·재배포에 앞선 권리 검토를 요구한다. 공개 GitLab에서 읽힌다는 사실만으로 자유 재배포 허가를 단정하지 않는다. 이 패키지에는 새로 작성한 스킬/CLI만 들어 있다. 원본 코드·테마·로고는 별도 원본 저장소에서 받는다.

확인한 원본 주소:
`https://gitlab.aigov.go.kr/chaeun74/Releasepick.git`

## 다운로드와 확인

```powershell
$S = Join-Path $HOME '.agents\skills\Jeju_Cardmaker'
py -3.12 "$S\scripts\bootstrap.py" upstream --allow-network --install-deps
$P = Join-Path $S '.venv\Scripts\python.exe'
$C = Join-Path $S 'scripts\Jeju_Cardmaker.py'
$R = Join-Path $S 'runtime\Jeju_Cardmaker'
& $P $C upstream-check --repo $R
```

기본 브랜치는 main이다. 재현성이 필요하면 확인된 태그를 `--ref`로 지정한다. 실제 전체 커밋 SHA는 다운로드 뒤 `runtime/upstream.json`에 기록된다. 이 배포본에는 원본 전체 커밋을 고정하지 않았다. 기존 저장소는 자동 pull/덮어쓰기하지 않는다. 별도 확보한 저장소는 `--repo`에 지정하면 된다.

추가 패키지 설치는 PyPI 네트워크 접근과 저장 공간을 사용한다. `--install-deps`가 없으면 원본 코드만 받고 원본 코드를 실행하지 않는다. 함수 이름/필드가 달라졌으면 실패한다. AST 검사는 악성 코드 검사나 라이선스 판단을 대신하지 않는다. 원본을 실제 실행하려면 검토 후 `--trust-upstream`을 명시한다.

## 어댑터가 확인한 함수 계약

- `models.CardNewsPlan`: series_title, head_copy, slides.
- `models.SlidePlan`: role, title, bullets, footnote.
- `plan_llm.generate_plan(client, press_text, *, target_pages, model, ...)`.
- `image_gen.generate_plan_card_jpegs(client, model, plan_dict, *, theme_desc, out_dir, cover_template_full, body_template_full, ...)`.
- `package_export.build_export_zip_bytes(plan_dict, jpeg_paths, *, cards_root=None)`.

원본 `render_cards.render_plan_to_jpegs`도 AST 호환성 검사 대상이다. 그러나 기본 로컬 모드는 긴 본문을 조용히 생략하지 않는 새 렌더러를 사용한다. 원본 함수의 시그니처는 웹에서 읽고 어댑터를 작성했지만, 실제 원본 저장소를 내려받아 유료 API까지 실행한 것은 아니다. 모의 함수 테스트와 실제 API 테스트를 혼동하지 않는다.

## 원본 문안 PPTX 내보내기

```powershell
& $P $C upstream-export --repo $R --run .\sample-draft --out .\original-export.zip --trust-upstream
```

원본의 PPTX는 텍스트 기획안이며 카드와 픽셀 단위로 같지 않다. 긴 문안의 넘침은 별도 검수한다. 이 내보내기 함수는 외부 API를 호출하지 않지만, 원본 Python 모듈을 로컬 실행한다.

## 유료 API 모드

`OPENAI_API_KEY`는 사용자가 로컬 환경에서 설정한다. 대화에 키를 보내거나 저장된 구독 세션/쿠키를 추출하지 않는다. 모델 이름은 현재 계정에서 사용할 수 있는 모델을 확인하고 지정한다. 이 문서의 `YOUR_TEXT_MODEL`, `YOUR_IMAGE_MODEL`은 실재 모델명이 아니다.

```powershell
& $P $C api-plan --repo $R --source .\source.json --pages 3 --model YOUR_TEXT_MODEL --out .\api-plan.json --trust-upstream --allow-paid-api --max-api-calls 1
```

원본 기획 함수는 필터에 걸리면 재호출할 수 있으나 한도는 실제 SDK 호출 시도를 합산해 제한한다. 1회 한도면 재호출 전에 멈춘다. 기획 후에는 실제 사용자 승인 기록을 별도로 만든다.

```powershell
& $P $C api-render --repo $R --source .\source.json --plan .\api-plan.json --approval .\approval.json --model YOUR_IMAGE_MODEL --out .\api-images --trust-upstream --allow-paid-api --max-api-calls 3 --accept-mofe-branding
```

원본 이미지 함수는 재정경제부 브랜딩을 사용한다. 다른 기관에는 임의 사용하지 않는다. 호출 횟수 제한은 가격 상한이 아니며 실패한 요청도 서비스 측 처리 상태에 따라 과금될 수 있다. SDK의 자동 재시도는 끄고 원본 내부 재시도도 같은 한도에 포함한다. API 이미지 작업 중 실패하면 부분 결과와 `api-operation.json`을 남기고 자동으로 전체 재실행하지 않는다.

API 이미지 명령의 결과는 `jpeg/ko` 또는 `jpeg/en`과 작업 기록이며 기본 `render` 결과 폴더와 같지 않다. v1.0.0의 `package` 명령은 기본 로컬 렌더 결과를 대상으로 한다. API JPEG를 묶거나 원본 UI의 ZIP 내보내기를 쓰려면 사용자 검수 후 별도 작업이 필요하다.

## 원본 앱과 미이식 범위

원본 웹앱을 직접 사용하려면 설치된 가상환경에서 `code` 폴더로 이동한 뒤 `python -m streamlit run app.py`를 실행한다. API 키가 필요한 단계와 선택적 Supabase/Buffer 기능은 원본 설정에 따른다. 이 스킬의 설치만으로 구독 계정이 원본 API에 연결되지는 않는다.

원본의 화면, RSS 수집, 표지 A/B/C 선택 UI, 세션 SQLite 복구, Instagram 게시를 모두 CLI로 복제하지는 않았다. 자동 SNS 게시 명령은 의도적으로 제공하지 않는다. 사용자가 게시를 요청하더라도 계정·콘텐츠·대상 채널과 게시 승인을 확인한 별도의 실행 경로가 필요하다.
