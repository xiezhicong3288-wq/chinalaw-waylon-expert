#!/usr/bin/env python3
"""Search the bundled law index and print verified local article text."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

from law_search_cache import candidates as cached_candidates, open_cache, searchable


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_HEADING = re.compile(r"^\*\*(第[^*]+条(?:之[^*]+)?)\*\*(?:\s*(.*))?$")
KEYWORD_ALIASES = {
    "电子送达": ("电子送达", "电子方式送达"),
    "网络送达": ("网络送达", "电子方式送达"),
    "聊天记录": ("聊天记录", "即时通信", "通讯群组"),
}


def load_json(name: str):
    return json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))


def normalized_law_name(value: str) -> str:
    """Treat single/double Chinese book-title marks as equivalent in law names."""
    return value.casefold().translate(str.maketrans({"《": "〈", "》": "〉"}))


def choose_laws(query: str | None, catalog: list[dict]) -> set[str]:
    if not query:
        return {item["slug"] for item in catalog}
    normalized = normalized_law_name(query)
    exact = {
        item["slug"] for item in catalog
        if normalized in [normalized_law_name(value) for value in [item["name"], item["slug"], *item.get("aliases", [])]]
    }
    if exact:
        return exact
    matches = set()
    for item in catalog:
        names = [item["name"], item["slug"], *item.get("aliases", [])]
        if any(normalized in normalized_law_name(value) for value in names):
            matches.add(item["slug"])
    if not matches:
        raise SystemExit(f"未识别法律：{query}")
    return matches


@lru_cache(maxsize=32)
def file_articles(relative_file: str) -> dict[str, str]:
    """Parse a file once; chapter headings are never part of an article."""
    path = (ROOT / relative_file).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Article path escapes the skill directory")
    lines = path.read_text(encoding="utf-8").splitlines()
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        match = ARTICLE_HEADING.match(line.strip())
        if match:
            current = match.group(1)
            if current in sections:
                raise ValueError(f"Duplicate article heading: {relative_file} {current}")
            sections[current] = [match.group(2).strip()] if match.group(2) else []
        elif line.startswith("#") or re.sub(r"\s+", "", line) in {"附则", "附件一", "附件二"}:
            current = None
        elif current and line.strip():
            sections[current].append(line.strip())
    return {key: "\n".join(value) for key, value in sections.items()}


def article_text(relative_file: str, article_cn: str) -> str:
    return file_articles(relative_file).get(article_cn, "")


def query_candidates(law_slugs: set[str], article=None, suffix=None, needles=(),
                     use_cache=True, rebuild=False, all_laws=False) -> list[dict]:
    # Exact article lookups are cheap in the JSON index; building or checking
    # the full-text cache for one article only adds startup cost.
    if use_cache and (article is None or rebuild):
        connection = None
        try:
            connection = open_cache(ROOT, lambda: load_json("law-index.json"), file_articles,
                                    rebuild, check_sources=bool(needles))
            return cached_candidates(connection, law_slugs, article, suffix, needles, all_laws)
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
            print(f"检索缓存不可用，改用原文检索：{error}", file=sys.stderr)
        finally:
            if connection is not None:
                connection.close()
    items = [item for item in load_json("law-index.json") if item["lawSlug"] in law_slugs]
    if article is not None:
        items = [item for item in items if item["article"] == article and item.get("articleSuffix") == suffix]
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="检索本地中国法律知识库")
    parser.add_argument("--law", help="法律名称、简称或 slug")
    parser.add_argument("--article", type=int, help="阿拉伯数字基础条号")
    parser.add_argument("--suffix", type=int, help="增补条款序号，如之一传 1")
    parser.add_argument("--keyword", help="在条文原文中检索关键词")
    parser.add_argument("--limit", type=int, default=20, help="关键词结果上限，默认20")
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument("--no-cache", action="store_true", help="跳过本地缓存，直接检索JSON和原文")
    cache_group.add_argument("--rebuild-cache", action="store_true", help="重新构建本地缓存后查询")
    args = parser.parse_args()
    if args.article is None and not args.keyword:
        parser.error("必须提供 --article 或 --keyword")
    if args.article is not None and (args.article < 1 or not args.law):
        parser.error("按条号查询必须提供 --law 和正整数 --article")
    if args.article is not None and args.keyword:
        parser.error("--article 与 --keyword 请分别使用")
    if args.suffix is not None and (args.article is None or args.suffix < 1):
        parser.error("--suffix 必须配合 --article 使用，且为正整数")
    if args.limit < 1 or (args.keyword is not None and not args.keyword.strip()):
        parser.error("结果上限须为正整数，关键词不能为空")

    catalog = load_json("law-catalog.json")
    law_slugs = choose_laws(args.law, catalog)
    if args.article is not None and len(law_slugs) != 1:
        parser.error("法律名称有歧义，请明确具体法律：" + "、".join(sorted(law_slugs)))
    original_needle = args.keyword.strip().casefold() if args.keyword else ""
    needles = tuple(value.casefold() for value in KEYWORD_ALIASES.get(original_needle, (original_needle,))) if args.keyword else ()
    candidates = query_candidates(law_slugs, args.article, args.suffix, needles,
                                  not args.no_cache, args.rebuild_cache, not args.law)

    if args.article is not None:
        if not candidates:
            raise SystemExit("未找到对应法律和条号")
        for item in candidates:
            body = article_text(item["file"], item["articleCn"])
            if not body:
                raise SystemExit("索引对应的原文缺失，停止引用")
            version = next(law["version"] for law in catalog if law["slug"] == item["lawSlug"])
            print(f"《{item['law']}》{item['articleCn']}")
            print(f"本地收录版本：{version}；不代表已核验本案适用版本或当前效力")
            print(f"结构：{item.get('part') or '-'} / {item.get('chapter') or '-'} / {item.get('section') or '-'}")
            print(f"文件：{item['file']}")
            print(body or "[未能从原文文件提取正文]")
            print()
        return

    if len(needles) > 1:
        print(f"检索扩展：{args.keyword.strip()} → {'、'.join(KEYWORD_ALIASES[original_needle])}")
        print()
    found = 0
    for item in candidates:
        body = article_text(item["file"], item["articleCn"])
        haystack = searchable(item, body)
        matched = next((needle for needle in needles if needle in haystack), None)
        if matched is None:
            continue
        compact = re.sub(r"\s+", " ", body)
        position = compact.casefold().find(matched)
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
