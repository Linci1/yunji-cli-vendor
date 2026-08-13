#!/usr/bin/env python3
"""Fail a vendor release when internal-only content is present."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {"", ".md", ".py", ".sh", ".txt", ".json", ".toml", ".yaml", ".yml"}
RELEASE_PATHS = (ROOT / "README.md", ROOT / "install.sh", ROOT / "scripts")
FORBIDDEN = {
    "internal Git service": re.compile(r"git\.in\.", re.I),
    "internal Yunji hostname": re.compile(r"yunji\.chaitin\.", re.I),
    "internal API reference": re.compile(r"references/api\.md", re.I),
    "direct token flag": re.compile(r"--token\b"),
    "stdin token flag": re.compile(r"--stdin\b"),
    "API discovery command": re.compile(r"api (list|schema|call)\b", re.I),
    "internal role command": re.compile(
        r"requirement-(create|update|audit)|dispatch-|purchase-audit|payment-|remind-approval|review-api",
        re.I,
    ),
    "known internal person": re.compile(r"于爽|shuang\.yu|张珈铨|jiaquan\.zhang"),
    "access token": re.compile(r"yunji_[A-Za-z0-9_-]{20,}"),
    "DingTalk webhook": re.compile(r"oapi\.dingtalk\.com/robot/send\?access_token=", re.I),
}


def main() -> int:
    findings: list[str] = []
    paths: list[Path] = []
    for release_path in RELEASE_PATHS:
        paths.extend(release_path.rglob("*") if release_path.is_dir() else [release_path])
    for path in sorted(paths):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in FORBIDDEN.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {label}")
    if findings:
        print("Vendor release security scan failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Vendor release security scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
