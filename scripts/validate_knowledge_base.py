#!/usr/bin/env python3
"""Validate catalog, index, article files, and critical version updates."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


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

    file_cache: dict[str, str] = {}
    for item in index:
        text = file_cache.setdefault(item["file"], (ROOT / item["file"]).read_text(encoding="utf-8"))
        heading = re.escape(f"**{item['articleCn']}**")
        assert re.search(rf"(?m)^{heading}(?:\s|$)", text), (
            f"missing heading: {item['law']} {item['articleCn']} in {item['file']}"
        )

    criminal = (ROOT / "references" / "法律法规" / "中华人民共和国刑法.md").read_text(encoding="utf-8")
    assert "有下列情形之一的，从重处罚" in criminal
    assert "（七）将违法所得用于行贿的。" in criminal
    assert "附件下载" not in criminal and "全国人民代表大会常务委员会制定的下列条例" not in criminal

    competition = (ROOT / "references" / "法律法规" / "中华人民共和国反不正当竞争法.md").read_text(encoding="utf-8")
    assert "2025年第二次修订" in competition
    assert "**第四十一条**" in competition

    constitution = (ROOT / "references" / "法律法规" / "中华人民共和国宪法.md").read_text(encoding="utf-8")
    assert "## 序言" in constitution and "**第一百四十三条**" in constitution

    print("知识库校验通过：10部法律，2,476条索引记录。")


if __name__ == "__main__":
    main()
