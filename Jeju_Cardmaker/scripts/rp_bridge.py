"""Adapters for the actual upstream ReleasePick public function contracts.

Upstream is fetched separately, never redistributed here. API integration is
opt-in and MUST be authorized separately from document approval.
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from rp_core import SkillError, now, sha256, validate_plan, validate_source

UPSTREAM_URL = "https://gitlab.aigov.go.kr/chaeun74/Releasepick.git"
EXPECTED = {
    "models.py": {"CardNewsPlan": {"series_title", "head_copy", "slides"},
                  "SlidePlan": {"role", "title", "bullets", "footnote"}},
    "render_cards.py": {"render_plan_to_jpegs": {"plan_dict", "out_dir", "options"}},
    "plan_llm.py": {"generate_plan": {"client", "press_text", "target_pages", "model"}},
    "image_gen.py": {"generate_plan_card_jpegs": {"client", "model", "plan_dict", "theme_desc", "out_dir", "cover_template_full", "body_template_full"}},
    "package_export.py": {"build_export_zip_bytes": {"plan_dict", "jpeg_paths", "cards_root"}},
}


def inspect_upstream(repo: str | Path) -> dict[str, Any]:
    root = Path(repo).expanduser().resolve(strict=True)
    code = root / "code"
    findings: list[dict[str, Any]] = []
    compatible = True
    for filename, contracts in EXPECTED.items():
        path = code / filename
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            compatible = False
            findings.append({"file": filename, "ok": False, "error": "missing or unsafe path"})
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeError):
            compatible = False
            findings.append({"file": filename, "ok": False, "error": "source parse failed"})
            continue
        declarations = {n.name: n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        checks = []
        for name, required in contracts.items():
            node = declarations.get(name)
            actual: set[str] = set()
            if isinstance(node, ast.ClassDef):
                actual = {n.target.id for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                actual = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
            ok = required <= actual
            checks.append({"name": name, "ok": ok, "missing": sorted(required - actual)})
            compatible = compatible and ok
        findings.append({"file": filename, "ok": all(c["ok"] for c in checks), "sha256": sha256(path.read_bytes()), "contracts": checks})
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True)
        commit = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {"checked_at": now(), "repo": str(root), "commit": commit, "compatible": compatible,
            "checks": findings, "note": "AST signature check only; not an end-to-end runtime test or security audit."}


@contextmanager
def upstream_modules(repo: str | Path, trusted: bool) -> Iterator[Path]:
    if not trusted:
        raise SkillError("원본 코드를 검토한 뒤 --trust-upstream을 명시하세요. 다운로드한 코드를 자동 실행하지 않습니다.")
    report = inspect_upstream(repo)
    if not report["compatible"]:
        raise SkillError("원본의 함수/스키마가 확인한 계약과 다릅니다. upstream-check 결과를 검토하세요.")
    code = Path(report["repo"]) / "code"
    old_path = list(sys.path)
    # Protect the host interpreter from upstream's generic names such as models.
    names = {p.stem for p in code.glob("*.py")}
    saved = {name: sys.modules[name] for name in names if name in sys.modules}
    for name in names:
        sys.modules.pop(name, None)
    before = set(sys.modules)
    sys.path.insert(0, str(code))
    try:
        yield code
    finally:
        sys.path[:] = old_path
        for name in set(sys.modules) - before | names:
            module = sys.modules.get(name)
            file = getattr(module, "__file__", None)
            if name in names or (file and Path(file).resolve().is_relative_to(code)):
                sys.modules.pop(name, None)
        sys.modules.update(saved)


class BudgetClient:
    """Cap SDK method attempts, including retries made by upstream itself.

    SDK transport retries are disabled separately. An attempted call may still
    be billable on the service side; this counter is not a price estimate.
    """
    def __init__(self, client: Any, limit: int):
        if not 1 <= limit <= 36:
            raise SkillError("--max-api-calls는 1~36이어야 합니다.")
        self.limit = limit
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._wrap(client.chat.completions.create)))
        self.images = SimpleNamespace(generate=self._wrap(client.images.generate))

    def _wrap(self, function: Any) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            if self.calls >= self.limit:
                raise SkillError("승인한 API 호출 횟수 한도에 도달했습니다. 자동 재시도하지 않습니다.")
            self.calls += 1
            return function(*args, **kwargs)
        return call


def paid_client(allowed: bool, limit: int | None) -> BudgetClient:
    if not allowed:
        raise SkillError("API 과금/외부 전송은 기본 비활성입니다. 사용자의 명시적 승인 후 --allow-paid-api를 지정하세요.")
    if limit is None or not 1 <= limit <= 36:
        raise SkillError("사용자가 승인한 --max-api-calls(1~36)를 명시하세요.")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SkillError("OPENAI_API_KEY 환경변수가 없습니다. 키를 대화·로그·파일 결과에 출력하지 마세요.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SkillError("원본 API 모드 의존성이 없습니다. bootstrap.py upstream --install-deps --allow-network를 실행하세요.") from exc
    return BudgetClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=180), limit)


def generate_upstream_plan(repo: str, source: dict[str, Any], *, pages: int, model: str,
                           trusted: bool, allowed: bool, max_calls: int | None) -> tuple[dict[str, Any], int]:
    if not allowed:
        raise SkillError("API 계획 생성은 --allow-paid-api 승인이 필요합니다.")
    validate_source(source)
    if not 1 <= pages <= 12 or not model.strip():
        raise SkillError("페이지는 1~12, 모델은 명시적으로 지정해야 합니다.")
    if len(source["text"]) > 120000:
        raise SkillError("원본 API는 120,000자를 넘어가면 자릅니다. 누락 방지를 위해 이 입력을 거부했습니다.")
    with upstream_modules(repo, trusted):
        module = importlib.import_module("plan_llm")
        client = paid_client(allowed, max_calls)
        result = module.generate_plan(client, source["text"], target_pages=pages, model=model)
        return validate_plan(result.model_dump(mode="json"), pages), client.calls


def render_upstream_api(repo: str, plan: dict[str, Any], output: Path, *, model: str,
                        trusted: bool, allowed: bool, max_calls: int | None,
                        accept_branding: bool, locale: str = "ko") -> tuple[list[Path], int]:
    if not allowed:
        raise SkillError("이미지 API 실행은 --allow-paid-api 승인이 필요합니다.")
    if not accept_branding:
        raise SkillError("원본 이미지 API는 재정경제부 로고·문구를 포함합니다. --accept-mofe-branding을 명시해야 합니다. 타 기관은 local 모드를 사용하세요.")
    if max_calls is None or max_calls < len(plan["slides"]):
        raise SkillError("API 호출 한도가 페이지 수보다 작습니다. 실행하지 않았습니다.")
    if output.exists():
        raise SkillError("기존 API 결과를 덮어쓰지 않습니다. 새 출력 폴더를 지정하세요.")
    with upstream_modules(repo, trusted):
        module = importlib.import_module("image_gen")
        client = paid_client(allowed, max_calls)
        output.mkdir(parents=True, exist_ok=False)
        record = {"status": "running", "started_at": now(), "model": model, "limit": max_calls,
                  "api_calls_attempted": 0, "notice": "호출 횟수는 청구 금액이 아닙니다. 원본 API 브랜딩을 사용합니다."}
        try:
            paths = module.generate_plan_card_jpegs(client, model, plan, theme_desc="mofe_body / blue / bottom_center",
                      out_dir=output / "jpeg" / locale, cover_template_full="", body_template_full="",
                      copy_locale=locale, single_page_template=len(plan["slides"]) == 1)
            if len(paths) != len(plan["slides"]) or not all(p.is_file() for p in paths):
                raise SkillError("API 이미지 생성 결과 수가 기획안과 다릅니다.")
            record["status"] = "generated-needs-visual-review"
            return paths, client.calls
        except Exception:
            record["status"] = "failed-partial-output-preserved"
            raise
        finally:
            record["api_calls_attempted"] = client.calls
            record["finished_at"] = now()
            (output / "api-operation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def original_export(repo: str, plan: dict[str, Any], images: list[Path], cards_root: Path, trusted: bool) -> bytes:
    with upstream_modules(repo, trusted):
        module = importlib.import_module("package_export")
        return module.build_export_zip_bytes(plan, images, cards_root=cards_root)
