"""Accessible preview and geometric checks for the character-scene example."""
import html


def validate_page(report):
    glyphs = [(block, box) for block in report["blocks"] for box in block["glyph_bounds"]]
    for block, box in glyphs:
        for pet in report["pets"]:
            pet_box = [pet["x"], pet["y"], pet["x"]+pet["width"], pet["y"]+pet["height"]]
            if intersects(box, pet_box):
                raise ValueError(f"Page {report['page']}: character overlaps text: {block['label']}")
    for i, (first, box) in enumerate(glyphs):
        for second, other in glyphs[i+1:]:
            if intersects(box, other):
                raise ValueError(f"Page {report['page']}: text overlaps text")
    if report["warnings"] or report["overflow"]:
        raise ValueError(f"Page {report['page']}: unresolved rendering warnings")


def intersects(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def make_preview(reports):
    def preview(plan, paths, status, notes, digest):
        esc = html.escape
        cards = []
        for i, (slide, rel, report) in enumerate(zip(plan["slides"], paths, reports), 1):
            paragraphs = "".join("<p>"+esc(b["text"]).replace("\n", "<br>")+"</p>"
                                 for b in report["blocks"] if b["text"])
            title = slide["title"].replace("\n", " ")
            jpg = rel.replace("png/", "jpeg/").replace(".png", ".jpg")
            cards.append(f'<article><a href="{esc(rel)}" aria-label="{i}장 크게 보기">'
                         f'<img src="{esc(rel)}" alt="{esc(title)}" width="2160" height="2700"></a>'
                         f'<p class="downloads"><a download href="{esc(rel)}">{i}장 PNG</a>'
                         f' · <a download href="{esc(jpg)}">JPEG</a></p>'
                         f'<details><summary>{i}장 문구 읽기</summary>{paragraphs}</details></article>')
        return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>온톨로지 카드뉴스 · 캐릭터 활용 개선안</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef3f1;color:#172532;font-family:Pretendard,system-ui,sans-serif}}
header,main,footer{{max-width:1180px;margin:auto;padding:28px}}header{{padding-top:48px}}
h1{{font-size:clamp(26px,4vw,38px);line-height:1.35;margin:12px 0}}p{{line-height:1.65}}
main{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:36px}}
article{{min-width:0}}img{{display:block;width:100%;height:auto}}a{{color:#0167a8;text-underline-offset:4px}}
.downloads{{margin:12px 0}}details{{padding:16px;background:#fff}}summary{{cursor:pointer}}
details p{{margin:12px 0}}nav{{display:flex;gap:12px 24px;flex-wrap:wrap}}
footer{{padding-bottom:48px}}@media(max-width:760px){{main{{grid-template-columns:1fr}}header,main,footer{{padding:20px}}}}
</style></head><body><header><p>{esc(plan["series_title"])} · 검토용 초안 · 8장</p>
<h1>온톨로지를 업무 예시로 배워요</h1>
<p>캐릭터가 질문하고 설명하는 장면으로 구성했어요. 이미지를 누르면 크게 볼 수 있어요.</p>
<nav><a download href="cardnews.zip">전체 자료 ZIP</a><a download href="cardnews-editable.pptx">편집용 PPTX</a>
<a href="SOURCES.md">설명 근거</a></nav></header><main>{''.join(cards)}</main>
<footer><p>A팀·B팀·주민설명회는 개념 설명을 위한 가상 예시예요.</p>
<p>편집용 PPTX를 사용하는 PC에는 Pretendard가 필요해요.</p></footer></body></html>'''
    return preview
