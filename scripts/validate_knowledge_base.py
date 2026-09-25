#!/usr/bin/env python3
"""Validate catalog, index, article files, and critical version updates."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from search_law import file_articles


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))


def main() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---", skill, re.DOTALL)
    assert frontmatter, "SKILL.md frontmatter is missing or malformed"
    fields = {}
    for line in frontmatter.group(1).splitlines():
        key, separator, value = line.partition(":")
        assert separator, f"invalid frontmatter line: {line}"
        fields[key.strip()] = value.strip()
    assert set(fields) == {"name", "description"}, f"unexpected frontmatter keys: {set(fields)}"
    assert re.fullmatch(r"[a-z0-9-]{1,64}", fields["name"]), "invalid skill name"
    assert 1 <= len(fields["description"]) <= 1024, "invalid skill description length"
    assert "<" not in fields["description"] and ">" not in fields["description"], "angle brackets in description"
    assert "[TODO:" not in skill, "unfinished TODO marker"

    catalog = load("law-catalog.json")
    index = load("law-index.json")
    assert len(catalog) == 10, f"expected 10 laws, got {len(catalog)}"
    assert len(index) == 2476, f"expected 2476 records, got {len(index)}"

    counts = Counter(item["lawSlug"] for item in index)
    keys = [(item["lawSlug"], item["article"], item.get("articleSuffix")) for item in index]
    assert len(keys) == len(set(keys)), "duplicate law/article index key"

    for law in catalog:
        assert counts[law["slug"]] == law["articleCount"], f"count mismatch: {law['name']}"
        for relative in law["files"]:
            assert (ROOT / relative).is_file(), f"missing file: {relative}"

    for item in index:
        body = file_articles(item["file"]).get(item["articleCn"])
        assert body, (
            f"missing or empty article: {item['law']} {item['articleCn']} in {item['file']}"
        )
    for relative in {item["file"] for item in index}:
        indexed = {item["articleCn"] for item in index if item["file"] == relative}
        assert indexed == set(file_articles(relative)), f"unindexed article or incorrect index: {relative}"

    for law in catalog:
        maximum = law.get("baseArticleMax", law["articleCount"])
        bases = {item["article"] for item in index if item["lawSlug"] == law["slug"] and item["articleSuffix"] is None}
        assert bases == set(range(1, maximum + 1)), f"base article gaps: {law['name']}"

    for relative in re.findall(r"\]\(([^)]+)\)", skill):
        if "://" not in relative:
            assert (ROOT / relative).is_file(), f"missing routed reference: {relative}"

    cases = load("cases/catalog.json")
    assert len({case["id"] for case in cases}) == len(cases), "duplicate case id"
    for case in cases:
        assert all(case.get(key) for key in ("id", "title", "caseNumber", "court", "decisionDate", "checkedAt", "verification", "file", "source"))
        address = urlparse(case["source"])
        assert address.scheme == "https" and address.hostname and address.hostname.endswith(".court.gov.cn")
        assert (ROOT / case["file"]).is_file(), f"missing case card: {case['id']}"

    criminal = (ROOT / "references" / "法律法规" / "中华人民共和国刑法.md").read_text(encoding="utf-8")
    assert "有下列情形之一的，从重处罚" in criminal
    assert "（七）将违法所得用于行贿的。" in criminal
    assert "附件下载" not in criminal and "全国人民代表大会常务委员会制定的下列条例" not in criminal

    competition = (ROOT / "references" / "法律法规" / "中华人民共和国反不正当竞争法.md").read_text(encoding="utf-8")
    assert "2025年第二次修订" in competition
    assert "**第四十一条**" in competition

    constitution = (ROOT / "references" / "法律法规" / "中华人民共和国宪法.md").read_text(encoding="utf-8")
    assert "## 序言" in constitution and "**第一百四十三条**" in constitution

    print(f"知识库结构校验通过：10部法律，2,476条完整可提取记录，{len(cases)}个案例卡；不代表法律适用正确性认证。")


if __name__ == "__main__":
    main()
