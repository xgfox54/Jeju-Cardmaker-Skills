"""ReleasePick-compatible data handling. No network calls or LLM calls."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.1.1"
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_PLAN_BYTES = 2 * 1024 * 1024


class SkillError(ValueError):
    """A user-actionable input, approval, layout or compatibility error."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_json(path: str | Path) -> Any:
    p = Path(path).expanduser()
    if p.stat().st_size > MAX_PLAN_BYTES:
        raise SkillError(f"JSON 파일이 너무 큽니다: {p.name}")
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise SkillError(f"올바른 UTF-8 JSON이 아닙니다: {p.name}") from exc


def write_json(path: str | Path, data: Any) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def new_json(path: str | Path, data: Any) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _text(value: Any, label: str, limit: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise SkillError(f"{label}: 비어 있지 않은 문자열이어야 합니다.")
    if len(value) > limit:
        raise SkillError(f"{label}: {limit}자 제한을 초과했습니다. 문구를 줄이거나 페이지를 나누세요.")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise SkillError(f"{label}: 지원하지 않는 제어문자가 있습니다.")
    return value


def validate_plan(data: Any, expected_pages: int | None = None) -> dict[str, Any]:
    """Strict structural validation; never truncate/repair or assert factual accuracy."""
    if not isinstance(data, dict):
        raise SkillError("기획안 최상위는 JSON 객체여야 합니다.")
    allowed = {"series_title", "head_copy", "slides"}
    if set(data) != allowed:
        raise SkillError("최상위 키는 series_title, head_copy, slides 세 개만 사용하세요. 출처는 별도 파일에 저장하세요.")
    _text(data["series_title"], "series_title", 200)
    _text(data["head_copy"], "head_copy", 300, empty=True)
    slides = data["slides"]
    if not isinstance(slides, list) or not 1 <= len(slides) <= 12:
        raise SkillError("slides는 1~12장의 배열이어야 합니다.")
    if expected_pages is not None and len(slides) != expected_pages:
        raise SkillError(f"요청한 {expected_pages}장과 실제 {len(slides)}장이 다릅니다.")
    for i, slide in enumerate(slides):
        label = f"slides[{i}]"
        if not isinstance(slide, dict) or set(slide) - {"role", "title", "bullets", "footnote"}:
            raise SkillError(f"{label}: 잘못된 키 또는 객체 형식입니다.")
        required_role = "cover" if i == 0 else "closing" if i == len(slides) - 1 else "body"
        if slide.get("role") != required_role:
            raise SkillError(f"{label}.role은 {required_role}여야 합니다.")
        _text(slide.get("title"), f"{label}.title", 500)
        bullets = slide.get("bullets", [])
        if not isinstance(bullets, list) or len(bullets) > 8:
            raise SkillError(f"{label}.bullets는 8개 이하 문자열 배열이어야 합니다.")
        for j, bullet in enumerate(bullets):
            _text(bullet, f"{label}.bullets[{j}]", 1000)
        footnote = slide.get("footnote")
        if footnote is not None:
            _text(footnote, f"{label}.footnote", 300, empty=True)
    # Normalize only optional defaults; preserve all user-supplied text verbatim.
    out = json.loads(json.dumps(data, ensure_ascii=False))
    for slide in out["slides"]:
        slide.setdefault("bullets", [])
        slide.setdefault("footnote", None)
    return out


def plan_hash(plan: dict[str, Any]) -> str:
    return sha256(canonical(validate_plan(plan)))


def plan_strings(plan: dict[str, Any]) -> list[str]:
    values = [plan["series_title"], plan["head_copy"]]
    for slide in plan["slides"]:
        values += [slide["title"], *slide.get("bullets", []), slide.get("footnote") or ""]
    return values


def _natural_key(value: str) -> list[Any]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


def extract_document(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.stat().st_size > MAX_INPUT_BYTES:
        raise SkillError("입력은 50MB 이하의 일반 파일이어야 합니다.")
    raw = p.read_bytes()
    suffix = p.suffix.lower()
    units: list[dict[str, str]] = []
    warnings: list[str] = []
    if suffix in {".txt", ".md"}:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp949")
            except UnicodeDecodeError as exc:
                raise SkillError("UTF-8 또는 CP949 텍스트 파일이 필요합니다.") from exc
        units.append({"locator": "text:1", "text": text})
    elif suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise SkillError("PyMuPDF가 없습니다. bootstrap.py core --allow-network를 실행하세요.") from exc
        with fitz.open(stream=raw, filetype="pdf") as doc:
            if doc.needs_pass:
                raise SkillError("암호화 PDF는 지원하지 않습니다. 열람 권한이 있는 해제본을 사용하세요.")
            if len(doc) > 500:
                raise SkillError("PDF는 한 번에 500페이지 이하로 나누세요.")
            for i, page in enumerate(doc):
                text = page.get_text("text", sort=True).strip()
                units.append({"locator": f"page:{i + 1}", "text": text})
                if not text:
                    warnings.append(f"page:{i + 1}: 텍스트가 없습니다. 스캔/그림 페이지를 직접 확인하세요.")
    elif suffix == ".hwpx":
        from defusedxml.ElementTree import fromstring
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                infos = zf.infolist()
                if len(infos) > 10000 or sum(i.file_size for i in infos) > 150 * 1024 * 1024:
                    raise SkillError("HWPX 압축 해제 크기/항목 수 제한을 초과했습니다.")
                sections = [i for i in infos if re.fullmatch(r"Contents/section\d+\.xml", i.filename, re.I)]
                if not sections or len({i.filename.lower() for i in sections}) != len(sections):
                    raise SkillError("HWPX 본문 섹션이 없거나 중복됩니다.")
                for info in sorted(sections, key=lambda i: _natural_key(i.filename)):
                    if info.file_size > 30 * 1024 * 1024:
                        raise SkillError("HWPX 단일 XML 크기 제한을 초과했습니다.")
                    try:
                        root = fromstring(zf.read(info), forbid_dtd=True, forbid_entities=True, forbid_external=True)
                    except Exception as exc:
                        raise SkillError(f"{info.filename} XML을 안전하게 해석할 수 없습니다.") from exc
                    texts = ["".join(el.itertext()) for el in root.iter() if isinstance(el.tag, str) and el.tag.rsplit("}", 1)[-1] == "t"]
                    units.append({"locator": info.filename, "text": "\n".join(texts).strip()})
        except zipfile.BadZipFile as exc:
            raise SkillError("유효한 HWPX ZIP 파일이 아닙니다.") from exc
        warnings.append("HWPX 표의 행·열 관계, 도형 안 글자와 이미지 내용은 원문 대조가 필요합니다.")
    elif suffix == ".hwp":
        raise SkillError("구형 HWP는 지원하지 않습니다. HWPX 또는 텍스트 PDF로 변환하세요.")
    else:
        raise SkillError("지원 형식: PDF, HWPX, TXT, MD. URL은 브라우저 도구로 원문을 확인·저장한 뒤 사용하세요.")
    text = "\n\n".join(f"[{u['locator']}]\n{u['text']}" for u in units)
    if not any(u["text"].strip() for u in units):
        raise SkillError("추출 가능한 텍스트가 없습니다. 빈 내용으로 기획하지 않습니다. OCR은 별도 승인 작업입니다.")
    return {"schema_version": 1, "source_name": p.name, "source_sha256": sha256(raw), "extracted_at": now(),
            "format": suffix.lstrip("."), "units": units, "text": text, "warnings": warnings,
            "complete_text_layer": all(bool(u["text"].strip()) for u in units)}


def validate_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or not isinstance(source.get("units"), list):
        raise SkillError("extract 명령으로 생성한 source.json이 필요합니다.")
    if not re.fullmatch(r"[a-f0-9]{64}", str(source.get("source_sha256", ""))):
        raise SkillError("source_sha256이 없거나 잘못되었습니다.")
    if not isinstance(source.get("text"), str) or not source["text"].strip():
        raise SkillError("추출 본문이 비어 있습니다.")
    for unit in source["units"]:
        if not isinstance(unit, dict) or not all(isinstance(unit.get(k), str) for k in ("locator", "text")):
            raise SkillError("source.json의 본문 단위 형식이 잘못되었습니다.")
    if source["text"] != "\n\n".join(f"[{u['locator']}]\n{u['text']}" for u in source["units"]):
        raise SkillError("source.json의 text와 units가 불일치합니다. 원본에서 다시 추출하세요.")
    return source


def source_hash(source: dict[str, Any]) -> str:
    validate_source(source)
    return sha256(canonical({"source_sha256": source["source_sha256"], "units": source["units"]}))


def review_markdown(plan: dict[str, Any], source: dict[str, Any] | None = None) -> str:
    lines = ["# Jeju_Cardmaker 기획안 검토", "", f"기획안 SHA-256: `{plan_hash(plan)}`", "",
             "구조 검증은 사실 검증이 아닙니다. 금액·기간·대상·예외·연락처를 원문과 대조하세요.", "",
             f"## {plan['series_title']}", "", plan["head_copy"], ""]
    if source:
        lines += [f"원문 파일: {source['source_name']}", f"원문 SHA-256: `{source['source_sha256']}`", ""]
        lines += [f"주의: {w}" for w in source.get("warnings", [])]
    for i, slide in enumerate(plan["slides"], 1):
        lines += ["", f"### {i}. [{slide['role']}] {slide['title']}", ""]
        lines += [f"- {b}" for b in slide.get("bullets", [])]
        if slide.get("footnote"):
            lines += ["", f"출처/각주: {slide['footnote']}"]
    lines += ["", "## 검수 항목", "", "- 원문과 수치·단위·시점·신청 조건이 일치하는가?",
              "- 출처 위치와 담당 연락처가 확인되는가?", "- 글자 잘림·겹침·오탈자·잘못된 기관 표시가 없는가?",
              "- 외부 API 전송·과금·대외 게시 승인이 각각 있는가?", ""]
    return "\n".join(lines)


def approve(plan: dict[str, Any], source: dict[str, Any], reviewer: str, confirmed: bool) -> dict[str, Any]:
    if not confirmed or not reviewer.strip():
        raise SkillError("실제 사용자의 문안 승인 후 --confirmed --reviewer를 지정하세요.")
    return {"schema_version": 1, "copy_approved": True, "plan_sha256": plan_hash(plan),
            "source_record_sha256": source_hash(source), "source_sha256": source["source_sha256"],
            "approved_at": now(), "reviewer": reviewer, "notice": "문안 승인 기록이며 전자서명·게시 승인·API 과금 승인이 아닙니다."}


def require_approval(plan: dict[str, Any], source: dict[str, Any], approval: Any) -> None:
    if not isinstance(approval, dict) or approval.get("copy_approved") is not True:
        raise SkillError("문안 승인 기록이 필요합니다.")
    if approval.get("plan_sha256") != plan_hash(plan) or approval.get("source_record_sha256") != source_hash(source):
        raise SkillError("승인 후 기획안 또는 출처가 변경되었습니다. 다시 검토·승인해야 합니다.")


def source_summary(source: dict[str, Any] | None) -> dict[str, Any]:
    if not source:
        return {"source_verified": False, "notice": "출처 미연결 초안"}
    return {k: source[k] for k in ("source_name", "source_sha256", "format", "warnings", "complete_text_layer")}
