#!/usr/bin/env python3
"""Audit source metadata; optionally verify that official source URLs remain reachable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SUFFIXES = (".gov.cn", ".court.gov.cn", ".spp.gov.cn")


def inspect(online: bool = False, snapshot_root: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    gaps: list[str] = []
    try:
        manifest = json.loads((ROOT / "references/source-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ['来源清单无法读取或不是有效JSON'], gaps
    if not isinstance(manifest, list) or not manifest:
        return ['来源清单必须为非空数组'], gaps
    seen: set[tuple[str, str]] = set()
    for item in manifest:
        if not isinstance(item, dict):
            errors.append('来源记录必须为对象')
            continue
        label = f"{item.get('law', '?')} / {item.get('file', '?')}"
        missing = [key for key in ("law", "file", "url", "organization", "sha256", "downloadedAt") if not isinstance(item.get(key), str) or not item[key].strip()]
        if missing:
            errors.append(f"{label}: 缺少字段 {', '.join(missing)}")
            continue
        key = (item["law"], item["file"])
        if key in seen:
            errors.append(f"{label}: 重复来源记录")
        seen.add(key)
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or item['sha256'] == '0' * 64:
            errors.append(f"{label}: SHA-256 格式错误")
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['downloadedAt']):
                raise ValueError
            date.fromisoformat(item['downloadedAt'])
        except ValueError:
            errors.append(f"{label}: 下载日期不是有效日历日期")
        try:
            url = urlsplit(item['url'])
            hostname = (url.hostname or '').lower()
            if url.scheme != 'https' or not hostname or url.username or url.password or url.port not in (None, 443):
                raise ValueError
        except ValueError:
            errors.append(f'{label}: 来源URL无效或不是无凭证HTTPS网址')
            continue
        if not any(hostname.endswith(suffix) for suffix in OFFICIAL_SUFFIXES):
            errors.append(f"{label}: 来源域名未识别为中国政府或司法机关域名：{hostname}")
            continue
        if snapshot_root is None:
            gaps.append(f'{label}: 未提供私人原始快照目录，下载哈希未与内容比对')
        else:
            root = snapshot_root.resolve()
            file = (root / item['file']).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                errors.append(f'{label}: 原始快照缺失或路径越界')
            elif hashlib.sha256(file.read_bytes()).hexdigest() != item['sha256']:
                errors.append(f'{label}: 原始下载哈希不一致')
        # Optional normalized text integrity is separate from the downloaded HTML/PDF hash.
        if 'textFile' in item or 'textSha256' in item:
            value = item.get('textFile')
            digest = item.get('textSha256')
            if not isinstance(value, str) or not isinstance(digest, str):
                errors.append(f'{label}: 规范化文本路径与哈希必须成对提供')
            else:
                file = (ROOT / value).resolve()
                if not file.is_relative_to(ROOT.resolve()) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                    errors.append(f'{label}: 规范化文本缺失、越界或哈希不一致')
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
    return errors, gaps


def audit(online: bool = False) -> list[str]:
    """Legacy structural API; use inspect() for content-verification gaps."""
    return inspect(online)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="校验法源清单")
    parser.add_argument("--online", action="store_true", help="联网检查来源网址是否仍可访问")
    parser.add_argument('--snapshot-root', type=Path, help='私人原始下载目录；不得将原始过程材料打包发布')
    parser.add_argument('--require-content', action='store_true', help='内容未核验也返回非零退出码')
    args = parser.parse_args()
    errors, gaps = inspect(args.online, args.snapshot_root)
    if errors:
        print("来源审计未通过：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    mode = "含在线可达性" if args.online else "离线元数据"
    print(f"来源结构审计通过（{mode}）；内容比对未完成{len(gaps)}项，不能据此认定现行效力。")
    if args.require_content and gaps:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
