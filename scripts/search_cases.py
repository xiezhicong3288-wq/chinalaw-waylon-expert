#!/usr/bin/env python3
"""Deterministically search the verified local case-card catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_catalog() -> list[dict]:
    return json.loads((ROOT / "references/cases/catalog.json").read_text(encoding="utf-8"))


def card_text(relative: str) -> str:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Case path escapes the skill directory")
    return path.read_text(encoding="utf-8")


def searchable(case: dict) -> str:
    values = [
        case.get("id"), case.get("title"), case.get("type"), case.get("domain"),
        case.get("caseNumber"), case.get("court"), *case.get("issues", []),
        *case.get("decisiveFacts", []), *case.get("limits", []), *case.get("tags", []),
        card_text(case["file"]),
    ]
    return "\n".join(str(value or "") for value in values).casefold()


def score(case: dict, case_id: str | None, domain: str | None, tag: str | None, keywords: list[str]) -> int:
    result = 0
    if case_id:
        if case["id"].casefold() != case_id.casefold():
            return -1
        result += 100
    if domain:
        needle = domain.casefold()
        if needle not in case.get("domain", "").casefold():
            return -1
        result += 20
    if tag:
        needle = tag.casefold()
        if not any(needle in value.casefold() for value in case.get("tags", [])):
            return -1
        result += 20
    haystack = searchable(case)
    for keyword in keywords:
        needle = keyword.casefold().strip()
        if not needle or needle not in haystack:
            return -1
        result += min(10, haystack.count(needle))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="检索本地官方案例学习卡")
    parser.add_argument("--id", help="案例卡编号，如 GC180")
    parser.add_argument("--domain", help="法域，如 劳动、行政、刑事")
    parser.add_argument("--tag", help="标签，如 举证责任、竞业限制")
    parser.add_argument("--keyword", action="append", default=[], help="必须同时命中的关键词，可重复")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not any((args.id, args.domain, args.tag, args.keyword)):
        parser.error("至少提供 --id、--domain、--tag 或 --keyword")
    if args.limit < 1:
        parser.error("--limit 必须为正整数")
    catalog = load_catalog()
    ranked = []
    for case in catalog:
        value = score(case, args.id, args.domain, args.tag, args.keyword)
        if value >= 0:
            ranked.append((value, case))
    if not ranked:
        raise SystemExit("未检索到匹配案例卡；这不等于没有相关公开案例")
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    for value, case in ranked[: args.limit]:
        rule = "；".join(case.get("issues", []))
        facts = "；".join(case.get("decisiveFacts", [])[:3])
        print(f"{case['id']}｜{case['title']}")
        print(f"法域：{case.get('domain', '-')}｜案号：{case['caseNumber']}｜裁判日期：{case['decisionDate']}")
        print(f"争点：{rule}")
        print(f"决定性事实：{facts}")
        print(f"案例卡：{case['file']}")
        print(f"官方来源：{case['source']}")
        print(f"匹配分：{value}（仅用于本地检索排序，不代表法律相似度）")
        print()


if __name__ == "__main__":
    main()
