#!/usr/bin/env python3
"""Search the curated official-source registry for commercial disputes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "references" / "commercial" / "authority-registry.json"


def load_registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def searchable(item: dict) -> str:
    fields = [
        item.get("id"), item.get("title"), item.get("authority"), item.get("type"),
        item.get("effective"), item.get("status"), item.get("usageNote"),
        *item.get("topics", []),
    ]
    return "\n".join(str(value or "") for value in fields).casefold()


def score(item: dict, authority_id: str | None, authority_type: str | None,
          status: str | None, keywords: list[str]) -> int:
    result = 0
    if authority_id:
        if item["id"].casefold() != authority_id.casefold():
            return -1
        result += 100
    if authority_type:
        if authority_type.casefold() not in item["type"].casefold():
            return -1
        result += 20
    if status:
        if item["status"] != status:
            return -1
        result += 20
    haystack = searchable(item)
    for keyword in keywords:
        needle = keyword.strip().casefold()
        if not needle or needle not in haystack:
            return -1
        result += min(10, haystack.count(needle))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="检索已核验的商事权威公开来源")
    parser.add_argument("--id", help="来源编号，如 CA19")
    parser.add_argument("--type", help="来源类型，如 法律、司法解释、典型案例")
    parser.add_argument(
        "--status", choices=("official_source_located", "official_text_verified"),
        help="核验状态",
    )
    parser.add_argument("--keyword", action="append", default=[], help="必须同时命中的关键词，可重复")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not any((args.id, args.type, args.status, args.keyword)):
        parser.error("至少提供 --id、--type、--status 或 --keyword")
    if args.limit < 1:
        parser.error("--limit 必须为正整数")

    ranked = []
    for item in load_registry():
        value = score(item, args.id, args.type, args.status, args.keyword)
        if value >= 0:
            ranked.append((value, item))
    if not ranked:
        raise SystemExit("登记册未命中；这不等于没有相关权威来源，须继续外部检索")
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    for value, item in ranked[:args.limit]:
        print(f"{item['id']}｜{item['title']}")
        print(f"机关：{item['authority']}｜类型：{item['type']}｜生效或发布：{item['effective']}")
        print(f"专题：{'；'.join(item['topics'])}")
        print(f"历史来源状态：{item['status']}（不是本次核验）")
        print("本次使用仍须记录核验日期、实际读取范围及适用版本；来源卡不等于全文已读。")
        print(f"使用边界：{item['usageNote']}")
        print(f"官方来源：{item['url']}")
        print(f"匹配分：{value}（仅用于本地检索排序）")
        print()


if __name__ == "__main__":
    main()
