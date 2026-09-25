#!/usr/bin/env python3
"""Audit source metadata; optionally verify that official source URLs remain reachable."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SUFFIXES = (".gov.cn", ".court.gov.cn", ".spp.gov.cn")


def audit(online: bool = False) -> list[str]:
    manifest = json.loads((ROOT / "references/source-manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in manifest:
        label = f"{item.get('law', '?')} / {item.get('file', '?')}"
        missing = [key for key in ("law", "file", "url", "organization", "sha256", "downloadedAt") if not item.get(key)]
        if missing:
            errors.append(f"{label}: 缺少字段 {', '.join(missing)}")
            continue
        key = (item["law"], item["file"])
        if key in seen:
            errors.append(f"{label}: 重复来源记录")
        seen.add(key)
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            errors.append(f"{label}: SHA-256 格式错误")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["downloadedAt"]):
            errors.append(f"{label}: 下载日期格式错误")
        if not item["url"].startswith("https://"):
            errors.append(f"{label}: 来源不是 HTTPS")
        hostname = item["url"].split("/", 3)[2].split(":", 1)[0].lower()
        if not any(hostname.endswith(suffix) for suffix in OFFICIAL_SUFFIXES):
            errors.append(f"{label}: 来源域名未识别为中国政府或司法机关域名：{hostname}")
        if online:
            request = Request(item["url"], headers={"User-Agent": "Mozilla/5.0 source-audit"})
            try:
                with urlopen(request, timeout=20) as response:
                    if response.status >= 400:
                        errors.append(f"{label}: HTTP {response.status}")
            except HTTPError as exc:
                errors.append(f"{label}: HTTP {exc.code}")
            except Exception as exc:
                errors.append(f"{label}: 在线核验失败：{type(exc).__name__}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="校验法源清单")
    parser.add_argument("--online", action="store_true", help="联网检查来源网址是否仍可访问")
    args = parser.parse_args()
    errors = audit(args.online)
    if errors:
        print("来源审计未通过：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    mode = "含在线可达性" if args.online else "离线元数据"
    print(f"来源审计通过（{mode}）。")


if __name__ == "__main__":
    main()
