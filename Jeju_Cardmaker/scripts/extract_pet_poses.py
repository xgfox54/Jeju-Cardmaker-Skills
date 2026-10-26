"""Reproduce bundled poses from the pinned animation sheets without redrawing."""
from __future__ import annotations

import argparse
import io
from pathlib import Path

from rp_core import SkillError, sha256
from rp_seogwipo import PET_ROOT, validate_pets


def extract(source_root: Path, output: Path) -> int:
    from PIL import Image

    manifest = validate_pets()
    if output.exists():
        raise SkillError("출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")
    images = {}
    for pet, spec in manifest["spritesheets"].items():
        path = source_root / manifest["sprite_directory"] / spec["file"]
        if sha256(path.read_bytes()) != spec["sha256"]:
            raise SkillError("캐릭터 시트가 기록된 원본과 다릅니다.")
        with Image.open(path) as sheet:
            images[pet] = sheet.convert("RGBA")
    frames = {}
    for filename, spec in manifest["poses"].items():
        frame = images[spec["pet"]].crop(spec["box"])
        with Image.open(PET_ROOT / filename) as bundled:
            if frame.size != bundled.size or frame.tobytes() != bundled.convert("RGBA").tobytes():
                raise SkillError("추출 프레임과 포함된 PNG 픽셀이 다릅니다.")
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG")
        frames[filename] = buffer.getvalue()
    output.mkdir(parents=True)
    for filename, data in frames.items():
        (output / filename).write_bytes(data)
    return len(frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = extract(args.source_root, args.out)
    except (OSError, SkillError):
        print("FAILED: 원본 시트, 포함된 PNG, 출력 경로를 확인하세요.")
        return 2
    print(f"OK: {count} poses match the original RGBA frame pixels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
