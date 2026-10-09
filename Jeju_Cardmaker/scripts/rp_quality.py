"""Optional fail-closed quality layer for Jeju_Cardmaker 1.1.1.

No networking, AI calls, OCR, source execution, or approval automation.
A passing report is NOT factual verification, authentication, or publication consent.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import zipfile
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path, PurePosixPath
from typing import Any

ADDON_VERSION = "2026.10.09.1"
ENGINE = "Jeju_Cardmaker-quality-v1"
MAX_JSON = 2 * 1024 * 1024
MAX_FILE = 80 * 1024 * 1024
MAX_ZIP = 400 * 1024 * 1024
PRESETS = {(1000, 1350), (1080, 1350), (2160, 2700)}
QUALIFIERS = ("이상", "이하", "미만", "초과", "최대", "최소", "이내", "제외", "본인부담", "비급여")
SCALE_VALUES = {"조": Decimal(10**12), "억": Decimal(10**8), "천만": Decimal(10**7),
                "백만": Decimal(10**6), "십만": Decimal(10**5), "만": Decimal(10**4),
                "천": Decimal(10**3), "백": Decimal(10**2), "십": Decimal(10)}
NUMERIC = re.compile(r"(?<![0-9])(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)[ \t]*(조|억|천만|백만|십만|만|천|백|십)?[ \t]*(퍼센트|개월|시간|세|명|개|건|년|월|일|분|회|배|원|%)?")


class QualityError(ValueError):
    """A missing, inconsistent, or unsafe quality input."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def object_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise QualityError("JSON에 중복 키가 있습니다.")
        result[key] = value
    return result


def decode_json(raw: bytes) -> Any:
    if len(raw) > MAX_JSON:
        raise QualityError("JSON 크기 제한을 초과했습니다.")
    def bad_constant(_: str) -> None:
        raise QualityError("NaN/Infinity는 허용하지 않습니다.")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=object_pairs, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QualityError("올바른 UTF-8 JSON이 필요합니다.") from exc


def safe_file(root: Path, name: str, max_bytes: int = MAX_FILE) -> Path:
    """Only allow regular, confined, relative files; reject parent symlinks."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise QualityError("허용되지 않는 파일 경로입니다.")
    rel = PurePosixPath(name)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
        raise QualityError("상대 경로만 사용할 수 있습니다.")
    root = root.absolute()
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise QualityError("심볼릭 링크를 통과하는 루트는 허용하지 않습니다.")
    target = root.joinpath(*rel.parts)
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise QualityError("필수 일반 파일이 없거나 허용된 폴더 밖에 있습니다.")
    if any(p.is_symlink() for p in target.parents if p != root and p.is_relative_to(root)):
        raise QualityError("파일 경로의 심볼릭 링크는 허용하지 않습니다.")
    if target.stat().st_size > max_bytes:
        raise QualityError("파일 크기 제한을 초과했습니다.")
    return target


def read_json(root: Path, name: str) -> Any:
    return decode_json(safe_file(root, name, MAX_JSON).read_bytes())


def normalized_plan(plan: Any) -> dict:
    if not isinstance(plan, dict) or set(plan) != {"series_title", "head_copy", "slides"}:
        raise QualityError("기존 plan.json의 세 최상위 키를 유지해야 합니다.")
    def text(value: Any, limit: int, empty: bool = False) -> None:
        if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
            raise QualityError("문안 문자열 형식/길이가 잘못되었습니다.")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise QualityError("문안에 허용되지 않는 제어문자가 있습니다.")
    text(plan["series_title"], 200)
    text(plan["head_copy"], 300, True)
    slides = plan["slides"]
    if not isinstance(slides, list) or not 1 <= len(slides) <= 12:
        raise QualityError("카드 수는 1~12장이어야 합니다.")
    out = json.loads(json.dumps(plan, ensure_ascii=False))
    for i, slide in enumerate(out["slides"]):
        if not isinstance(slide, dict) or set(slide) - {"role", "title", "bullets", "footnote"}:
            raise QualityError("기존 slide 스키마와 맞지 않습니다.")
        role = "cover" if i == 0 else "closing" if i == len(slides)-1 else "body"
        if slide.get("role") != role:
            raise QualityError("카드 순서/역할이 맞지 않습니다.")
        text(slide.get("title"), 500)
        slide.setdefault("bullets", [])
        slide.setdefault("footnote", None)
        if not isinstance(slide["bullets"], list) or len(slide["bullets"]) > 8:
            raise QualityError("본문 배열이 잘못되었습니다.")
        for bullet in slide["bullets"]:
            text(bullet, 1000)
        if slide["footnote"] is not None:
            text(slide["footnote"], 300, True)
    return out


def plan_fields(plan: dict) -> dict[str, str]:
    values = {"/series_title": plan["series_title"], "/head_copy": plan["head_copy"]}
    for i, slide in enumerate(plan["slides"]):
        values[f"/slides/{i}/title"] = slide["title"]
        values[f"/slides/{i}/footnote"] = slide.get("footnote") or ""
        for j, text in enumerate(slide["bullets"]):
            values[f"/slides/{i}/bullets/{j}"] = text
    return {key: text for key, text in values.items() if text.strip()}


def validate_source(source: Any) -> dict:
    if not isinstance(source, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(source.get("source_sha256", ""))):
        raise QualityError("추출 원문의 source_sha256이 필요합니다.")
    units = source.get("units")
    if not isinstance(units, list) or not units or len(units) > 10000:
        raise QualityError("비어 있지 않은 원문 단위 배열이 필요합니다.")
    locators = set()
    for unit in units:
        if not isinstance(unit, dict) or not all(isinstance(unit.get(k), str) for k in ("locator", "text")):
            raise QualityError("원문 단위 형식이 잘못되었습니다.")
        if not unit["locator"].strip() or unit["locator"] in locators:
            raise QualityError("원문 위치가 없거나 중복됩니다.")
        locators.add(unit["locator"])
    assembled = "\n\n".join(f"[{u['locator']}]\n{u['text']}" for u in units)
    if source.get("text") != assembled or not any(u["text"].strip() for u in units):
        raise QualityError("원문 text/units가 일치하지 않습니다.")
    return source


def source_digest(source: dict) -> str:
    validate_source(source)
    return sha(canonical({"source_sha256": source["source_sha256"], "units": source["units"]}))


def numeric_tokens(text: str) -> set[tuple[str, str]]:
    """Compare complete numeric values and units, never substring membership."""
    result = set()
    normalized = unicodedata.normalize("NFKC", text)
    for token in re.findall(r"\d+(?:,\d+)+", normalized):
        if not re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
            raise QualityError("숫자 쉼표 묶음이 올바르지 않습니다.")
    for match in NUMERIC.finditer(normalized):
        number, scale_name, unit = match.groups()
        if len(number.replace(",", "")) > 128:
            raise QualityError("지원 범위를 초과하는 긴 숫자입니다.")
        value = Decimal(number.replace(",", ""))
        scale = SCALE_VALUES.get(scale_name, Decimal(1))
        normalized_unit = "%" if unit == "퍼센트" else unit or ""
        # Unrecognized compound multipliers must not silently become a smaller value.
        tail = normalized[match.end():]
        if re.match(r"^(?:조|억|천만|백만|십만|만|천|백|십)(?:원|명|개|건|회|$)", tail):
            raise QualityError("지원하지 않는 복합 단위입니다. 숫자와 기본 단위로 풀어 쓰세요.")
        with localcontext() as context:
            context.prec = max(50, len(number)+20)
            result.add((str((value * scale).normalize()), normalized_unit))
    return result


def iso_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise QualityError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise QualityError("유효하지 않은 날짜입니다.") from exc


def policy(as_of: str, max_age_days: int = 30) -> dict:
    iso_date(as_of)
    if type(max_age_days) is not int or not 0 <= max_age_days <= 365:
        raise QualityError("확인일 허용 기간은 0~365일 정수로 지정하세요.")
    return {"as_of": as_of, "max_age_days": max_age_days, "contrast_min": 4.5,
            "body_min_px_at_1080": 30, "safe_padding_px_at_1080": 24,
            "notice": "운영상 검사 기준이며 법정 기간 또는 접근성 인증 기준을 선언하지 않습니다."}


def binding(plan: dict, source: dict, notes: str, evidence: dict, rules: dict) -> dict:
    return {"plan_sha256": sha(canonical(normalized_plan(plan))),
            "source_record_sha256": source_digest(source),
            "notes_sha256": sha(notes.encode("utf-8")),
            "evidence_sha256": sha(canonical(evidence)), "policy_sha256": sha(canonical(rules))}


def preflight(plan: Any, source: Any, notes: str, evidence: Any, rules: dict) -> dict:
    plan = normalized_plan(plan)
    source = validate_source(source)
    if not isinstance(notes, str) or not notes.strip():
        raise QualityError("SOURCES.md가 필요합니다.")
    if not isinstance(evidence, dict) or type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1:
        raise QualityError("evidence.json schema_version=1이 필요합니다.")
    if evidence.get("as_of") != rules["as_of"]:
        raise QualityError("evidence 기준일과 실행 기준일이 다릅니다.")
    if evidence.get("source_record_sha256") != source_digest(source):
        raise QualityError("evidence와 추출 원문 해시가 다릅니다.")
    as_of = iso_date(rules["as_of"])
    sources = evidence.get("sources")
    claims = evidence.get("claims")
    if not isinstance(sources, list) or not sources or not isinstance(claims, list):
        raise QualityError("evidence sources/claims 배열이 필요합니다.")
    defined_notes = set(re.findall(r"(?m)^\s*(?:#{1,6}\s*)?\[([1-9]\d*)\]", notes))
    source_map = {}
    for item in sources:
        if not isinstance(item, dict) or not re.fullmatch(r"[1-9]\d*", str(item.get("id", ""))):
            raise QualityError("출처 id는 [1] 형태와 연결되는 양의 정수 문자열이어야 합니다.")
        sid = item["id"]
        if not isinstance(sid, str) or sid in source_map or sid not in defined_notes:
            raise QualityError("출처 id가 중복되거나 SOURCES.md에서 정의되지 않았습니다.")
        for key in ("title", "reference", "checked_by"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise QualityError("출처명·참조 위치·실제 확인자 기록이 필요합니다.")
        checked = iso_date(item.get("checked_on"))
        if checked > as_of or (as_of - checked).days > rules["max_age_days"]:
            raise QualityError("출처 확인일이 미래이거나 설정한 허용 기간을 초과했습니다.")
        for key in ("published_on", "valid_from", "valid_until"):
            if item.get(key) is not None:
                iso_date(item[key])
        if item.get("published_on") and iso_date(item["published_on"]) > as_of:
            raise QualityError("기준일 이후 공개 자료입니다.")
        if item.get("valid_from") and iso_date(item["valid_from"]) > as_of:
            raise QualityError("아직 적용 전인 자료입니다. 현행 안내와 별도로 제작하세요.")
        if item.get("valid_until") and iso_date(item["valid_until"]) < as_of:
            raise QualityError("적용 종료일이 지난 자료입니다.")
        if item.get("valid_from") and item.get("valid_until") and item["valid_from"] > item["valid_until"]:
            raise QualityError("적용 기간이 역전되어 있습니다.")
        source_map[sid] = item
    fields = plan_fields(plan)
    units = {u["locator"]: u["text"] for u in source["units"]}
    seen = set()
    counts = {"fact": 0, "editorial": 0, "attribution": 0}
    for claim in claims:
        if not isinstance(claim, dict):
            raise QualityError("claim은 객체여야 합니다.")
        ptr = claim.get("pointer")
        if not isinstance(ptr, str) or ptr not in fields or ptr in seen or claim.get("text") != fields[ptr]:
            raise QualityError("claim 위치가 중복/누락되었거나 실제 문안과 다릅니다.")
        seen.add(ptr)
        kind = claim.get("kind")
        if kind not in counts:
            raise QualityError("claim kind는 fact/editorial/attribution 중 하나여야 합니다.")
        counts[kind] += 1
        if kind == "fact":
            sid = claim.get("source_id")
            quote = claim.get("quote")
            locator = claim.get("locator")
            if sid not in source_map or locator not in units or not isinstance(quote, str) or not quote.strip():
                raise QualityError(f"근거 출처/위치/인용문이 없습니다: {ptr}")
            if quote not in units[locator]:
                raise QualityError(f"인용문이 지정한 원문 단위와 정확히 일치하지 않습니다: {ptr}")
            if numeric_tokens(fields[ptr]) - numeric_tokens(quote):
                raise QualityError(f"숫자 또는 단위가 인용문과 다릅니다: {ptr}")
            required = claim.get("required_terms", [])
            if not isinstance(required, list) or any(not isinstance(t, str) or not t for t in required):
                raise QualityError("required_terms는 비어 있지 않은 문자열 배열이어야 합니다.")
            if any(t not in quote for t in required):
                raise QualityError(f"필수 조건이 인용 근거에 없습니다: {ptr}")
            required = set(required) | {word for word in QUALIFIERS if word in quote}
            if any(word not in fields[ptr] for word in required):
                raise QualityError(f"자격·상한·제외 등 조건이 문안에서 누락되었습니다: {ptr}")
            if ptr.startswith("/slides/"):
                slide = plan["slides"][int(ptr.split("/")[2])]
                if sid not in re.findall(r"\[([1-9]\d*)\]", slide.get("footnote") or ""):
                    raise QualityError(f"해당 카드 각주에 근거 번호가 없습니다: {ptr}")
        else:
            candidate = fields[ptr]
            if kind == "attribution":
                if not ptr.endswith("/footnote"):
                    raise QualityError("attribution은 각주에만 사용할 수 있습니다.")
                ids = re.findall(r"\[([1-9]\d*)\]", candidate)
                if not ids or any(sid not in source_map for sid in ids):
                    raise QualityError("각주 출처 번호가 없거나 정의되지 않았습니다.")
                candidate = re.sub(r"\[[1-9]\d*\]", "", candidate)
            if numeric_tokens(candidate):
                raise QualityError(f"숫자가 있는 문안은 fact로 근거를 연결해야 합니다: {ptr}")
    if seen != set(fields):
        raise QualityError("분류·근거 연결이 빠진 문안 필드가 있습니다.")
    return {"ok": True, "engine": ENGINE, "addon_version": ADDON_VERSION,
            "stage": "preflight", "binding": binding(plan, source, notes, evidence, rules),
            "policy": rules, "claim_counts": counts,
            "factual_accuracy_verified": False, "urls_fetched": False,
            "original_source_file_authenticated": False, "publishing_authorized": False,
            "limitations": ["정성적 주장과 editorial 분류의 타당성은 사람이 검토합니다.",
                            "원문 인용 일치와 숫자/조건 검사이지 사실 확인 또는 신원 인증이 아닙니다."]}


def attach_approval(base: dict, report: dict) -> dict:
    if report.get("ok") is not True or base.get("copy_approved") is not True:
        raise QualityError("실제 문안 승인과 통과한 사전검사가 필요합니다.")
    for key in ("plan_sha256", "source_record_sha256"):
        if base.get(key) != report["binding"][key]:
            raise QualityError("기존 문안 승인과 사전검사의 입력 해시가 다릅니다.")
    result = dict(base)
    result["quality_binding"] = report["binding"]
    result["quality_addon_version"] = ADDON_VERSION
    result["notice"] = "문안·근거 기록의 승인 일치 확인. 전자서명, 디자인 승인 또는 게시 승인이 아닙니다."
    return result


def require_quality_approval(approval: Any, report: dict) -> None:
    if not isinstance(approval, dict) or approval.get("copy_approved") is not True:
        raise QualityError("실제 사용자의 문안 승인 기록이 필요합니다.")
    if not approval.get("reviewer") or not approval.get("approved_at"):
        raise QualityError("실제 승인자와 승인 시점이 필요합니다.")
    if any(approval.get(key) != report["binding"][key] for key in ("plan_sha256", "source_record_sha256")):
        raise QualityError("기존 승인 필드와 강화 검사 입력 해시가 다릅니다.")
    if approval.get("quality_binding") != report["binding"] or approval.get("quality_addon_version") != ADDON_VERSION:
        raise QualityError("문안·원문·SOURCES.md·evidence·검사 기준 변경: 재검토와 재승인이 필요합니다.")


def contrast(a: str, b: str) -> float:
    def luminance(value: str) -> float:
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise QualityError("색상 형식이 올바르지 않습니다.")
        rgb = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(a*b for a, b in zip(linear, (.2126, .7152, .0722)))
    low, high = sorted((luminance(a), luminance(b)))
    return (high+.05)/(low+.05)


def finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def postflight(root: Path, plan: dict, rules: dict) -> dict:
    """Supplement the existing verify_build: completeness, images, measured text."""
    from PIL import Image
    plan = normalized_plan(plan)
    manifest = read_json(root, "manifest.json")
    report = read_json(root, "render-report.json")
    files = manifest.get("files")
    if manifest.get("engine") != "Jeju_Cardmaker-studio-v1" or not isinstance(files, dict):
        raise QualityError("지원하는 v1.1 build manifest가 아닙니다.")
    if read_json(root, "plan.json") != plan or manifest.get("plan_sha256") != sha(canonical(plan)):
        raise QualityError("실제 빌드 문안과 검사 대상이 다릅니다.")
    if manifest.get("pages") != len(plan["slides"]):
        raise QualityError("manifest 카드 수가 다릅니다.")
    size = manifest.get("size")
    if not isinstance(size, list) or tuple(size) not in PRESETS or report.get("size") != size:
        raise QualityError("출력 규격이 다르거나 지원되지 않습니다.")
    required = {"plan.json", "profile.json", "source-summary.json", "render-report.json", "review.md", "preview.html", "ABOUT.txt", "SOURCES.md"}
    for i, slide in enumerate(plan["slides"], 1):
        required |= {f"png/{i:02d}_{slide['role']}.png", f"jpeg/{i:02d}_{slide['role']}.jpg"}
    pptx_files = {"cardnews-editable.pptx", "cardnews-preview.pptx"}
    if set(files) & pptx_files and not pptx_files <= set(files):
        raise QualityError("PPTX 두 종류 중 하나가 누락되었습니다.")
    if manifest.get("status") == "copy-approved":
        required.add("approval.json")
    elif manifest.get("status") != "draft":
        raise QualityError("알 수 없는 문안 승인 상태입니다.")
    allowed = required | pptx_files
    if not required <= set(files) or set(files) - allowed:
        raise QualityError("필수 산출물이 manifest에서 누락되었거나 허용하지 않은 파일이 있습니다.")
    for rel, digest in files.items():
        path = safe_file(root, rel)
        if sha(path.read_bytes()) != digest:
            raise QualityError("산출물 해시가 일치하지 않습니다.")
        if rel.endswith((".png", ".jpg")):
            with Image.open(path) as image:
                if image.size != tuple(size) or image.format != ("PNG" if rel.endswith(".png") else "JPEG"):
                    raise QualityError("실제 이미지 형식/해상도가 다릅니다.")
                image.load()
    profile = read_json(root, "profile.json")
    pages = report.get("pages")
    if not isinstance(pages, list) or len(pages) != len(plan["slides"]):
        raise QualityError("페이지별 검사 기록이 누락되었습니다.")
    scale = size[0]/1080
    pad = rules["safe_padding_px_at_1080"]*scale
    for i, (page, slide) in enumerate(zip(pages, plan["slides"]), 1):
        if page.get("page") != i or page.get("size") != size or page.get("overflow") is not False:
            raise QualityError("페이지 순서/규격/넘침 검사 기록이 올바르지 않습니다.")
        blocks = page.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise QualityError("텍스트 검사 기록이 없습니다.")
        by_label = {}
        legacy_body_index = 0
        for block in blocks:
            if not isinstance(block, dict) or not isinstance(block.get("label"), str):
                raise QualityError("텍스트 블록 형식/라벨이 잘못되었습니다.")
            label = block["label"]
            # v1.1.1 reuses the measured spec with the unnumbered label 'N장 본문'.
            # Match those blocks by their emitted order, without changing the original report.
            if label == f"{i}장 본문":
                legacy_body_index += 1
                label = f"{i}장 본문 {legacy_body_index}"
            if label in by_label:
                raise QualityError("텍스트 블록 라벨이 중복됩니다.")
            by_label[label] = block
            text = block.get("text")
            if not isinstance(text, str):
                raise QualityError("텍스트 블록 원문이 없습니다.")
            if not text:
                continue
            if block.get("overflow") is not False or not finite(block.get("size")) or block["size"] <= 0:
                raise QualityError("텍스트 크기/넘침 검사 기록이 잘못되었습니다.")
            ratio = contrast(block.get("color"), block.get("background"))
            declared = block.get("contrast_ratio")
            if not finite(declared) or abs(declared-ratio) > .002 or ratio < rules["contrast_min"]:
                raise QualityError("텍스트 대비가 기준보다 낮거나 검사 기록과 다릅니다.")
            if re.search(r"장 본문(?: \d+)?$", block["label"]) and block["size"]/scale < rules["body_min_px_at_1080"]:
                raise QualityError("본문이 최소 글자 크기보다 작습니다.")
            lines = block.get("lines")
            bounds = block.get("glyph_bounds")
            if not isinstance(lines, list) or any(not isinstance(v, str) for v in lines):
                raise QualityError("줄바꿈 검사 정보가 없습니다.")
            if not isinstance(bounds, list) or len(bounds) != len(lines):
                raise QualityError("줄별 실제 글자 경계가 누락되었습니다.")
            clean = lambda v: "".join(v.split())
            if clean("".join(lines)) != clean(text):
                raise QualityError("렌더링 줄에서 문안 일부가 누락되었습니다.")
            dims = [block.get(k) for k in ("x", "y", "box_width", "box_height")]
            if not all(finite(v) for v in dims) or dims[2] <= 0 or dims[3] <= 0:
                raise QualityError("텍스트 상자 크기가 올바르지 않습니다.")
            x, y, w, h = dims
            for line, bbox in zip(lines, bounds):
                if not isinstance(bbox, list) or len(bbox) != 4 or not all(finite(v) for v in bbox):
                    raise QualityError("실제 글자 경계 기록이 올바르지 않습니다.")
                left, top, right, bottom = bbox
                if right < left or bottom < top:
                    raise QualityError("실제 글자 경계가 역전되어 있습니다.")
                if not line.strip():
                    continue
                if left < x-1 or top < y-1 or right > x+w+1 or bottom > y+h+1:
                    raise QualityError("실제 글자가 텍스트 상자 밖으로 나갑니다.")
                if left < pad or top < pad or right > size[0]-pad or bottom > size[1]-pad:
                    raise QualityError("실제 글자가 출력 안전영역을 벗어납니다.")
        expected = {f"{i}장 시리즈": plan["series_title"], f"{i}장 제목": slide["title"],
                    f"{i}장 출처/각주": slide.get("footnote") or ""}
        if i == 1 and plan["head_copy"]:
            expected[f"{i}장 헤드카피"] = plan["head_copy"]
        for j, bullet in enumerate(slide["bullets"], 1):
            expected[f"{i}장 본문 {j}"] = bullet
        for label, text in expected.items():
            if label not in by_label or by_label[label]["text"] != text:
                raise QualityError("문안과 렌더링 텍스트가 일치하지 않습니다.")
        expected[f"{i}장 쪽수"] = f"{i:02d} / {len(plan['slides']):02d}"
        expected[f"{i}장 기관/푸터"] = " · ".join(profile.get(k, "") for k in ("agency", "footer") if profile.get(k))
        if manifest["status"] == "draft" or f"{i}장 상태" in by_label:
            expected[f"{i}장 상태"] = "검토용 초안" if manifest["status"] == "draft" else "문안 승인본"
        for label, text in expected.items():
            if label not in by_label or by_label[label]["text"] != text:
                raise QualityError("문안·상태·쪽수·프로필과 렌더링 텍스트가 일치하지 않습니다.")
        permitted = set(expected)
        if set(by_label) - permitted:
            raise QualityError("기획안에 없는 추가 텍스트 블록이 있습니다.")
    return {"ok": True, "stage": "postflight", "pages": len(pages), "size": size,
            "contrast_method": "solid-color metadata recomputation, not pixel sampling",
            "factual_accuracy_verified": False, "pptx_visual_verified": False,
            "pixel_ocr_performed": False}


def write_json_new(path: Path, data: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def seal_checked_build(root: Path, pre: dict, post: dict) -> None:
    """Keep the original ZIP untouched; produce a checked ZIP with bounded contents."""
    if pre.get("ok") is not True or post.get("ok") is not True:
        raise QualityError("검사 실패 결과는 배포 패키지로 만들지 않습니다.")
    report = {"engine": ENGINE, "addon_version": ADDON_VERSION, "ok": True,
              "preflight": pre, "postflight": post, "publishing_authorized": False}
    write_json_new(root/"quality-report.json", report)
    original = read_json(root, "manifest.json")
    names = sorted(set(original["files"]) | {"manifest.json", "quality-report.json"})
    hashes = {name: sha(safe_file(root, name).read_bytes()) for name in names}
    write_json_new(root/"quality-manifest.json", {"engine": ENGINE, "files": hashes,
                   "notice": "변경 감지용 해시. 전자서명 또는 사실 인증이 아닙니다."})
    with zipfile.ZipFile(root/"cardnews-checked.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for name in names + ["quality-manifest.json"]:
            archive.write(safe_file(root, name), name)
    verify_checked(root)


def verify_checked(root: Path) -> dict:
    """Validate outer digest list and archive without extracting untrusted entries."""
    manifest = read_json(root, "quality-manifest.json")
    original = read_json(root, "manifest.json")
    hashes = manifest.get("files")
    expected_files = set(original.get("files", {})) | {"manifest.json", "quality-report.json"}
    if manifest.get("engine") != ENGINE or not isinstance(hashes, dict) or set(hashes) != expected_files:
        raise QualityError("보완 manifest의 파일 목록이 원본 산출물과 다릅니다.")
    for name, digest in hashes.items():
        if sha(safe_file(root, name).read_bytes()) != digest:
            raise QualityError("보완 검사 이후 산출물이 변경되었습니다.")
    report = read_json(root, "quality-report.json")
    if report.get("engine") != ENGINE or report.get("ok") is not True:
        raise QualityError("통과한 보완 검사 보고서가 아닙니다.")
    pre = report.get("preflight", {})
    if pre.get("ok") is not True or report.get("postflight", {}).get("ok") is not True:
        raise QualityError("사전·사후 검사의 통과 기록이 없습니다.")
    declared_policy = pre.get("policy", {})
    rules = policy(declared_policy.get("as_of"), declared_policy.get("max_age_days"))
    if declared_policy != rules or pre["binding"]["policy_sha256"] != sha(canonical(rules)):
        raise QualityError("검사 정책이 변경되었거나 지원되지 않습니다.")
    plan = read_json(root, "plan.json")
    postflight(root, plan, rules)
    if pre["binding"]["plan_sha256"] != sha(canonical(normalized_plan(plan))):
        raise QualityError("검사 보고서와 빌드 문안이 다릅니다.")
    notes = safe_file(root, "SOURCES.md", MAX_JSON).read_text(encoding="utf-8-sig")
    if pre["binding"]["notes_sha256"] != sha(notes.encode("utf-8")):
        raise QualityError("검사 보고서와 근거 기록이 다릅니다.")
    if original.get("status") == "copy-approved":
        require_quality_approval(read_json(root, "approval.json"), pre)
    with zipfile.ZipFile(safe_file(root, "cardnews-checked.zip", MAX_ZIP)) as archive:
        infos = archive.infolist()
        expected = expected_files | {"quality-manifest.json"}
        if len(infos) != len(expected) or {i.filename for i in infos} != expected:
            raise QualityError("보완 ZIP에 중복/누락/추가 항목이 있습니다.")
        if any(i.file_size > MAX_FILE for i in infos) or sum(i.file_size for i in infos) > MAX_ZIP:
            raise QualityError("ZIP 내용 크기 제한을 초과했습니다.")
        for info in infos:
            if sha(archive.read(info)) != sha(safe_file(root, info.filename).read_bytes()):
                raise QualityError("ZIP 내용과 검사 결과가 다릅니다.")
    return {"ok": True, "checked_files": len(hashes), "publishing_authorized": False,
            "evidence_rechecked": False, "notice": "원문과 evidence는 배포 ZIP에 포함하지 않아 여기서는 재검사하지 않습니다."}
