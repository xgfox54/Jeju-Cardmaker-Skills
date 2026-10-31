# 장 유형(scene)으로 그림 만들기

## 기본 경로

`diagrams.json`에 장마다 scene 하나를 고르면 `scripts/scene_build.py`가 글자를 실측하여 배치함. 좌표를 직접 쓰는 주제별 렌더러는 장 유형으로 표현할 수 없는 그림에만 사용함.

```text
python <SKILL>/scripts/scene_build.py --project <PROJECT> --out <PROJECT>/draft/run-01
```

`plan.json`은 제목·본문·각주, `diagrams.json`은 그림 문구와 장 유형을 담당함. 실행 예시는 `assets/scene-example/`에 있음.

## 장 유형

| scene | 쓰는 곳 | 필수 항목 | 개수 |
|---|---|---|---|
| hero | 표지 전용 | question, note, number+number_caption 또는 facts | facts 3개 |
| steps | 순서·절차 | steps: [제목, 설명] | 2~4개. 4개는 2×2 |
| compare | 두 대상 비교 | panels: [제목, 설명] | 2개 |
| pillars | 세 가지 요구·원칙 | panels: [제목, 설명] | 3개 |
| rows | 기관·사례 목록 | rows: [이름, 내용, 결과] | 2~5개 |
| flow | 전달 경로·처리 흐름 | flow: [제목, 설명], 선택 detail | 2~4개 |
| stat | 숫자 하나 강조 | number, caption | 1개 |
| checklist | 마지막 장 전용 | title, items, captions | items 2~5개, captions 3개 |

모든 장에 badge(분류 라벨)가 필요함. 선택 항목은 speech(캐릭터 말), note(그림 아래 메모), tones(상자 색 순서), alt(미리보기 대체 텍스트), character(place·pet·pose 직접 지정)임. 미리보기 문구는 최상위 preview_intro, preview_note로 지정함.

## 배치 규칙

- 같은 역할의 글자는 모든 장에서 같은 크기를 사용함. 제목 54px(표지 56px), 본문 32px, 상자 제목 29px, 상자 설명 28px, 말풍선 30px, 표 27·26px, 메모 26px, 큰 숫자 150px, 숫자 설명 32px.
- 제목과 본문은 모든 장에서 같은 높이에서 시작함. 그림은 본문 아래 586px에서 시작하고, 남는 공간이 60px보다 크면 그림을 가운데로 옮김.
- 내용이 넘치면 글자를 줄이지 않고 오류로 멈춤. 오류 문구의 장 번호와 초과 높이를 보고 문구를 줄이거나 장을 나눔.
- 상자 설명은 위에서부터 채움. 같은 줄의 상자는 가장 긴 상자에 높이를 맞춤.

## 캐릭터 자리

| place | 모양 | 조건 |
|---|---|---|
| bottom-left | 왼쪽 아래 캐릭터, 오른쪽 말풍선 | 모든 장면 |
| bottom-right | 왼쪽 말풍선, 오른쪽 아래 캐릭터 | 모든 장면 |
| side-right | 그림 오른쪽 세로 칸, 말풍선 아래 캐릭터 | rows·flow·pillars 제외 |
| title-right | 제목 오른쪽 | 말풍선 없는 장. 제목이 길면 아래쪽 자리로 바뀜 |

자리를 지정하지 않으면 앞 장과 다른 자리, 다른 캐릭터를 자동으로 고름. 말이 물음표로 끝나면 think, layout이 caution인 장은 caution, 제목 옆은 wave 포즈를 사용함. 제목 옆 장에서 아래 공간이 220px 넘게 남으면 note를 캐릭터의 말풍선으로 옮기고 아래쪽 자리로 바꿈. 표지는 귤귤이 질문하고 하르방·한라가 아래에서 소개하며, 마지막 장은 세 캐릭터가 점검 항목 이름과 함께 등장함.

## 표지

주제를 대표하는 숫자가 있으면 number로 크게 표시함. 숫자에는 출처가 있는 값만 사용하고, number_caption에 기준을 적음. 숫자가 없는 개념 주제는 facts 세 칸을 사용함. question은 독자가 실제로 궁금해할 짧은 질문으로 작성함.

## 참고한 오픈소스

2026-10-31에 코드와 문서를 직접 확인함. 코드·글꼴·이미지는 가져오지 않았고 원리만 적용함.

- [instagram-carousel-skill](https://github.com/social-media-skills/instagram-carousel-skill) 커밋 a780161: 장마다 type을 지정하는 JSON 명세, 모든 장에서 같은 높이에서 시작하는 글자, 넘치면 줄이지 말고 장을 나누는 원칙, 숫자 하나를 크게 보여주는 stat 장, 표지의 질문·숫자 패턴.
- [public-cardnews](https://github.com/mouseco/public-cardnews) 커밋 0d91e22: 같은 의미 위계의 글자 크기 통일, 긴 문구는 글자 축소 대신 영역과 줄 수 조정, 어절 단위 줄바꿈, 숫자와 단위 묶음 유지.
