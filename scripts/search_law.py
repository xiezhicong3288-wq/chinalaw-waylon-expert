#!/usr/bin/env python3
"""Search the bundled law index and print verified local article text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_HEADING = re.compile(r"^\*\*(第[^*]+条(?:之[^*]+)?)\*\*(?:\s*(.*))?$")


def load_json(name: str):
    return json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))


def choose_laws(query: str | None, catalog: list[dict]) -> set[str]:
    if not query:
        return {item["slug"] for item in catalog}
    normalized = query.casefold()
    matches = set()
    for item in catalog:
        names = [item["name"], item["slug"], *item.get("aliases", [])]
        if any(normalized in value.casefold() or value.casefold() in normalized for value in names):
            matches.add(item["slug"])
    if not matches:
        raise SystemExit(f"未识别法律：{query}")
    return matches


def article_text(relative_file: str, article_cn: str) -> str:
    lines = (ROOT / relative_file).read_text(encoding="utf-8").splitlines()
    collecting = False
    result: list[str] = []
    for line in lines:
        match = ARTICLE_HEADING.match(line.strip())
        if match:
            if collecting:
                break
            if match.group(1) == article_cn:
                collecting = True
                if match.group(2):
                    result.append(match.group(2).strip())
                continue
        if collecting:
            if line.startswith("## ") or line.startswith("### "):
                break
            if line.strip():
                result.append(line.strip())
    return "\n".join(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="检索本地中国法律知识库")
    parser.add_argument("--law", help="法律名称、简称或 slug")
    parser.add_argument("--article", type=int, help="阿拉伯数字基础条号")
    parser.add_argument("--suffix", type=int, help="增补条款序号，如之一传 1")
    parser.add_argument("--keyword", help="在条文原文中检索关键词")
    parser.add_argument("--limit", type=int, default=20, help="关键词结果上限，默认20")
    args = parser.parse_args()
    if args.article is None and not args.keyword:
        parser.error("必须提供 --article 或 --keyword")

    catalog = load_json("law-catalog.json")
    index = load_json("law-index.json")
    law_slugs = choose_laws(args.law, catalog)
    candidates = [item for item in index if item["lawSlug"] in law_slugs]

    if args.article is not None:
        candidates = [
            item for item in candidates
            if item["article"] == args.article and item.get("articleSuffix") == args.suffix
        ]
        if not candidates:
            raise SystemExit("未找到对应法律和条号")
        for item in candidates:
            body = article_text(item["file"], item["articleCn"])
            print(f"《{item['law']}》{item['articleCn']}")
            print(f"结构：{item.get('part') or '-'} / {item.get('chapter') or '-'} / {item.get('section') or '-'}")
            print(f"文件：{item['file']}")
            print(body or "[未能从原文文件提取正文]")
            print()
        return

    needle = args.keyword.casefold()
    found = 0
    for item in candidates:
        body = article_text(item["file"], item["articleCn"])
        haystack = " ".join(
            str(value or "") for value in (
                item["law"], item["articleCn"], item.get("part"), item.get("chapter"),
                item.get("section"), item.get("topic"), body,
            )
        ).casefold()
        if needle not in haystack:
            continue
        compact = re.sub(r"\s+", " ", body)
        position = compact.casefold().find(needle)
        start = max(0, position - 45)
        snippet = compact[start:start + 150]
        print(f"《{item['law']}》{item['articleCn']} | {item['file']}")
        print(snippet)
        print()
        found += 1
        if found >= args.limit:
            break
    if not found:
        raise SystemExit("未检索到匹配条文")


if __name__ == "__main__":
    main()
