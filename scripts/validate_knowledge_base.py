#!/usr/bin/env python3
"""Validate catalog, index, article files, and critical version updates."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from search_law import file_articles
from audit_sources import audit as audit_sources


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
    required = {
        "中华人民共和国民法典", "中华人民共和国宪法", "中华人民共和国刑法",
        "中华人民共和国刑事诉讼法", "中华人民共和国民事诉讼法",
        "中华人民共和国行政诉讼法", "中华人民共和国行政复议法",
        "中华人民共和国行政处罚法", "中华人民共和国公司法",
        "中华人民共和国仲裁法", "中华人民共和国劳动法",
        "中华人民共和国劳动合同法", "中华人民共和国社会保险法",
        "中华人民共和国反垄断法", "中华人民共和国反不正当竞争法",
        "中华人民共和国消费者权益保护法",
        "最高人民法院关于民事诉讼证据的若干规定",
    }
    assert {item["name"] for item in catalog} == required, "authority catalog is incomplete or unexpected"
    expected_records = sum(item["articleCount"] for item in catalog)
    assert len(index) == expected_records, f"expected {expected_records} records, got {len(index)}"

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
    assert len(cases) == 12, f"expected 12 verified case cards, got {len(cases)}"
    assert len({case["id"] for case in cases}) == len(cases), "duplicate case id"
    for case in cases:
        assert all(case.get(key) for key in (
            "id", "title", "type", "domain", "caseNumber", "court", "decisionDate",
            "checkedAt", "verification", "file", "source", "issues", "decisiveFacts", "limits", "tags",
        ))
        assert re.fullmatch(r"GC\d+", case["id"]), f"invalid case id: {case['id']}"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", case["decisionDate"]), f"invalid decision date: {case['id']}"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", case["checkedAt"]), f"invalid checked date: {case['id']}"
        address = urlparse(case["source"])
        assert address.scheme == "https" and address.hostname and address.hostname.endswith(".court.gov.cn")
        assert (ROOT / case["file"]).is_file(), f"missing case card: {case['id']}"
        assert Path(case["file"]).stem == case["id"], f"case file/id mismatch: {case['id']}"
        card = (ROOT / case["file"]).read_text(encoding="utf-8")
        assert case["source"] in card, f"case card omits official source: {case['id']}"

    archetypes = load("experience/case-archetypes.json")
    assert len(archetypes) == 10 and len({item["id"] for item in archetypes}) == 10
    case_ids = {case["id"] for case in cases}
    for archetype in archetypes:
        assert all(archetype.get(key) for key in (
            "id", "name", "domains", "triggers", "decisiveQuestions", "evidencePriorities",
            "opposingArguments", "proceduralRisks", "linkedCases",
        ))
        assert set(archetype["linkedCases"]) <= case_ids, f"unknown linked case: {archetype['id']}"

    failure_text = (ROOT / "references" / "experience" / "failure-patterns.md").read_text(encoding="utf-8")
    failure_numbers = [int(value) for value in re.findall(r"^(\d+)\. \*\*", failure_text, re.MULTILINE)]
    assert failure_numbers == list(range(1, 19)), "expected 18 consecutively numbered failure patterns"

    criminal = (ROOT / "references" / "法律法规" / "中华人民共和国刑法.md").read_text(encoding="utf-8")
    assert "有下列情形之一的，从重处罚" in criminal
    assert "（七）将违法所得用于行贿的。" in criminal
    assert "附件下载" not in criminal and "全国人民代表大会常务委员会制定的下列条例" not in criminal

    competition = (ROOT / "references" / "法律法规" / "中华人民共和国反不正当竞争法.md").read_text(encoding="utf-8")
    assert "2025年第二次修订" in competition
    assert "**第四十一条**" in competition

    constitution = (ROOT / "references" / "法律法规" / "中华人民共和国宪法.md").read_text(encoding="utf-8")
    assert "## 序言" in constitution and "**第一百四十三条**" in constitution

    assert not audit_sources(), "source manifest audit failed"
    criminal_procedure = (ROOT / "references" / "法律法规" / "中华人民共和国刑事诉讼法.md").read_text(encoding="utf-8")
    company = (ROOT / "references" / "法律法规" / "中华人民共和国公司法.md").read_text(encoding="utf-8")
    arbitration = (ROOT / "references" / "法律法规" / "中华人民共和国仲裁法.md").read_text(encoding="utf-8")
    anti_monopoly = (ROOT / "references" / "法律法规" / "中华人民共和国反垄断法.md").read_text(encoding="utf-8")
    assert "Copyrights©" not in criminal_procedure and "相关新闻" not in criminal_procedure
    assert "用户登录" not in company and "网站纠错" not in company
    assert "网站标识码" not in arbitration
    assert "扫一扫在手机打开当前页" not in anti_monopoly and "网站标识码" not in anti_monopoly

    law_count = sum(item.get("documentType", "法律") == "法律" for item in catalog)
    interpretation_count = len(catalog) - law_count
    print(f"知识库结构校验通过：{law_count}部法律、{interpretation_count}部司法解释，{len(index):,}条完整可提取记录，{len(cases)}个案例卡、{len(archetypes)}类案件原型、{len(failure_numbers)}类失败模式；不代表法律适用正确性认证。")


if __name__ == "__main__":
    main()
