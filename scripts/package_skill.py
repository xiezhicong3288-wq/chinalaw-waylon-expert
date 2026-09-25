#!/usr/bin/env python3
"""Build a ZIP with redundant Unicode path metadata for broad extractor compatibility."""

from __future__ import annotations

import argparse
import os
import struct
import tempfile
import zipfile
import zlib
from datetime import datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
UNICODE_PATH_EXTRA_ID = 0x7075


def unicode_path_extra(filename: str) -> bytes:
    encoded = filename.encode("utf-8")
    payload = struct.pack("<BI", 1, zlib.crc32(encoded) & 0xFFFFFFFF) + encoded
    return struct.pack("<HH", UNICODE_PATH_EXTRA_ID, len(payload)) + payload


def extra_fields(extra: bytes):
    offset = 0
    while offset + 4 <= len(extra):
        field_id, size = struct.unpack_from("<HH", extra, offset)
        start = offset + 4
        end = start + size
        if end > len(extra):
            raise ValueError("ZIP extra field is truncated")
        yield field_id, extra[start:end]
        offset = end
    if offset != len(extra):
        raise ValueError("ZIP extra field has trailing bytes")


def source_files(source: Path) -> list[Path]:
    return [
        path for path in sorted(source.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(source).parts
        and "__pycache__" not in path.relative_to(source).parts
    ]


def build_package(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if source in destination.parents:
        raise SystemExit("输出ZIP不能位于待打包Skill目录内")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(source):
            relative = PurePosixPath(source.name, *path.relative_to(source).parts).as_posix()
            modified = datetime.fromtimestamp(path.stat().st_mtime)
            info = zipfile.ZipInfo(relative, date_time=modified.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix host avoids legacy DOS-code-page assumptions.
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            if not relative.isascii():
                # Bit 11 is added by zipfile for UTF-8 names. The Info-ZIP Unicode Path
                # extra field is redundant metadata for extractors that mishandle it.
                info.extra = unicode_path_extra(relative)
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verify_package(source, destination)


def verify_package(source: Path, destination: Path) -> None:
    expected = {
        PurePosixPath(source.name, *path.relative_to(source).parts).as_posix()
        for path in source_files(source)
    }
    with zipfile.ZipFile(destination) as archive:
        infos = archive.infolist()
        actual = {info.filename for info in infos}
        if len(actual) != len(infos):
            raise SystemExit("ZIP包含重复路径")
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise SystemExit(f"ZIP路径不一致；缺少={missing[:3]}，多出={unexpected[:3]}")
        for info in infos:
            if info.create_system != 3:
                raise SystemExit(f"ZIP条目未使用跨平台Unix主机标识：{info.filename}")
            if not info.filename.isascii():
                if not info.flag_bits & 0x800:
                    raise SystemExit(f"中文路径缺少UTF-8标志：{info.filename}")
                fields = dict(extra_fields(info.extra))
                payload = fields.get(UNICODE_PATH_EXTRA_ID)
                encoded = info.filename.encode("utf-8")
                expected_payload = struct.pack("<BI", 1, zlib.crc32(encoded) & 0xFFFFFFFF) + encoded
                if payload != expected_payload:
                    raise SystemExit(f"中文路径缺少有效Unicode Path额外字段：{info.filename}")
        with tempfile.TemporaryDirectory(prefix="chinalaw-package-") as temp:
            archive.extractall(temp)
            extracted = Path(temp) / source.name
            extracted_files = {
                PurePosixPath(*path.relative_to(extracted).parts).as_posix()
                for path in extracted.rglob("*") if path.is_file()
            }
            expected_relative = {
                PurePosixPath(*path.relative_to(source).parts).as_posix()
                for path in source_files(source)
            }
            if extracted_files != expected_relative:
                raise SystemExit("ZIP解压后的路径与源码不一致")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成兼容中文路径的Skill ZIP并自检")
    parser.add_argument("--output", type=Path, default=ROOT.parent / f"{ROOT.name}.zip")
    args = parser.parse_args()
    build_package(ROOT, args.output)
    print(f"Created and verified {args.output.resolve()} ({args.output.resolve().stat().st_size} bytes)")


if __name__ == "__main__":
    main()
