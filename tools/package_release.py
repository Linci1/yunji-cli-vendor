#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path


VERSION = "2.6.0"
PACKAGE_FILES = (
    "README.md",
    "install.sh",
    "install.cmd",
    "docs/vendor-api-2.6-guide.md",
    "docs/vendor-cli-2.6-guide.md",
    "scripts/yunji",
    "scripts/yunji.cmd",
    "scripts/yunji_vendor.py",
    "tools/install-windows.ps1",
)
FORBIDDEN_PATTERNS = {
    "internal Git service": re.compile(r"git\.in\.", re.I),
    "test environment endpoint": re.compile(r"yunji\.huabeiapi\.com", re.I),
    "internal person": re.compile(r"于爽|shuang\.yu|张珈铨|jiaquan\.zhang"),
    "vendor access token": re.compile(r"yunji_[A-Za-z0-9_-]{20,}"),
    "DingTalk webhook credential": re.compile(r"oapi\.dingtalk\.com/robot/send\?access_token=", re.I),
    "machine-specific user path": re.compile(r"/Users/[A-Za-z0-9._-]+|C:\\Users\\[A-Za-z0-9._-]+"),
}
TEXT_SUFFIXES = {".cmd", ".md", ".ps1", ".py", ".sh", ".txt"}


def run_git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_clean_source(root: Path, allow_dirty: bool) -> None:
    status = run_git("status", "--porcelain", "--untracked-files=all")
    if status and not allow_dirty:
        raise RuntimeError("工作区包含未提交变更；请先提交或显式使用 --allow-dirty。")


def ensure_allowed_files(root: Path) -> None:
    tracked = set(run_git("ls-files").splitlines())
    missing = [name for name in PACKAGE_FILES if name not in tracked]
    if missing:
        raise RuntimeError("以下发布文件未被 Git 跟踪：" + "、".join(missing))


def normalize_bytes(name: str, data: bytes) -> bytes:
    suffix = Path(name).suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        return data
    text = data.decode("utf-8")
    if suffix in {".cmd", ".bat", ".ps1"}:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    else:
        text = text.replace("\r\n", "\n")
    return text.encode("utf-8")


def scan_source(root: Path) -> None:
    findings: list[str] = []
    for name in PACKAGE_FILES:
        text = (root / name).read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{name}:{line}: {label}")
    if findings:
        raise RuntimeError("发布包内容未通过脱敏扫描：\n" + "\n".join(findings))


def create_zip(root: Path, output: Path) -> None:
    source_epoch = int(run_git("show", "-s", "--format=%ct", "HEAD"))
    timestamp = time.gmtime(source_epoch)[:6]
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)

    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in PACKAGE_FILES:
            source = root / name
            data = normalize_bytes(name, source.read_bytes())
            info = zipfile.ZipInfo(name, timestamp)
            info.create_system = 3
            mode = source.stat().st_mode
            executable = bool(mode & stat.S_IXUSR)
            info.external_attr = ((0o755 if executable else 0o644) << 16)
            archive.writestr(info, data)

        file_list = "\n".join(PACKAGE_FILES)
        manifest = (
            f"yunji-cli-vendor {VERSION}\n"
            "source: sanitized release archive\n"
            "python: >=3.10\n"
            f"files:\n{file_list}\n"
        ).encode("utf-8")
        info = zipfile.ZipInfo("MANIFEST.txt", timestamp)
        info.create_system = 3
        info.external_attr = 0o644 << 16
        archive.writestr(info, manifest)

    temporary.replace(output)


def validate_zip(output: Path, root: Path) -> None:
    expected = set(PACKAGE_FILES) | {"MANIFEST.txt"}
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        if names != expected:
            raise RuntimeError(f"发布包文件列表异常：{sorted(names)}")
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            raise RuntimeError("发布包包含不安全路径。")
        for name in names:
            archive.read(name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.with_suffix(output.suffix + ".sha256")).write_text(f"{digest}  {output.name}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the sanitized vendor release package.")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--allow-dirty", action="store_true")
    arguments = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    ensure_clean_source(root, arguments.allow_dirty)
    ensure_allowed_files(root)
    scan_source(root)

    output_dir = arguments.output_dir if arguments.output_dir.is_absolute() else root / arguments.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"yunji-cli-vendor-{VERSION}.zip"
    create_zip(root, output)
    validate_zip(output, root)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"package: {output}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
