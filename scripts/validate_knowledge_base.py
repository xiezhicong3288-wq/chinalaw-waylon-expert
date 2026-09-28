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
        "中华人民共和国消费者权益保护法", "中华人民共和国企业破产法",
        "中华人民共和国票据法", "中华人民共和国保险法",
        "中华人民共和国证券法", "中华人民共和国合伙企业法",
        "中华人民共和国涉外民事关系法律适用法", "中华人民共和国电子签名法",
        "最高人民法院关于民事诉讼证据的若干规定",
        "最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释（二）",
        "最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释（一）",
        "最高人民法院关于适用〈中华人民共和国民法典〉合同编通则若干问题的解释",
        "最高人民法院关于适用〈中华人民共和国民法典〉有关担保制度的解释",
        "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（二）",
        "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（三）",
        "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（四）",
        "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（五）",
        "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（一）",
        "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（二）",
        "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（三）",
        "最高人民法院关于审理买卖合同纠纷案件适用法律问题的解释",
        "最高人民法院关于审理票据纠纷案件若干问题的规定",
        "最高人民法院关于审理执行异议之诉案件适用法律问题的解释",
        "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（一）",
        "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（二）",
        "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（三）",
        "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（四）",
        "最高人民法院关于审理证券市场虚假陈述侵权民事赔偿案件的若干规定",
        "最高人民法院关于适用〈中华人民共和国涉外民事关系法律适用法〉若干问题的解释（一）",
        "最高人民法院关于适用〈中华人民共和国涉外民事关系法律适用法〉若干问题的解释（二）",
        "最高人民法院关于审理涉外民商事案件适用国际条约和国际惯例若干问题的解释",
        "最高人民法院关于适用〈中华人民共和国民事诉讼法〉的解释",
        "最高人民法院关于人民法院民事执行中查封、扣押、冻结财产的规定",
        "最高人民法院关于人民法院民事执行中拍卖、变卖财产的规定",
        "最高人民法院关于适用〈中华人民共和国民事诉讼法〉执行程序若干问题的解释",
        "最高人民法院关于人民法院办理执行异议和复议案件若干问题的规定",
        "最高人民法院关于民事执行中变更、追加当事人若干问题的规定",
        "最高人民法院关于人民法院办理财产保全案件若干问题的规定",
        "最高人民法院关于民事执行中财产调查若干问题的规定",
        "最高人民法院关于执行和解若干问题的规定",
        "最高人民法院关于执行担保若干问题的规定",
        "最高人民法院关于适用〈中华人民共和国民法典〉总则编若干问题的解释",
        "最高人民法院关于适用〈中华人民共和国公司法〉时间效力的若干规定",
        "最高人民法院关于审理民间借贷案件适用法律若干问题的规定",
        "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（一）",
        "最高人民法院关于审理存单纠纷案件的若干规定",
        "最高人民法院关于审理与企业改制相关的民事纠纷案件若干问题的规定",
        "最高人民法院关于审理外商投资企业纠纷案件若干问题的规定（一）",
        "最高人民法院关于审理期货纠纷案件若干问题的规定",
        "最高人民法院关于审理期货纠纷案件若干问题的规定（二）",
        "最高人民法院关于审理信用证纠纷案件若干问题的规定",
        "最高人民法院关于审理独立保函纠纷案件若干问题的规定",
        "最高人民法院关于审理银行卡民事纠纷案件若干问题的规定",
        "最高人民法院关于审理融资租赁合同纠纷案件适用法律问题的解释",
        "中华人民共和国市场主体登记管理条例",
        "中华人民共和国市场主体登记管理条例实施细则",
        "公司登记管理实施办法",
        "市场监督管理行政处罚程序规定",
        "最高人民法院关于适用〈中华人民共和国民法典〉物权编的解释（一）",
        "最高人民法院关于审理预付式消费民事纠纷案件适用法律若干问题的解释",
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
    assert len(cases) == 13, f"expected 13 verified case cards, got {len(cases)}"
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

    practice_files = {
        "README.md", "matter-triage.md", "evidence-engineering.md", "hearing-preparation.md",
        "settlement-execution.md", "appeal-review.md", "high-risk-matters.md",
    }
    practice_dir = ROOT / "references" / "practice"
    assert {path.name for path in practice_dir.glob("*.md")} == practice_files, "practice workflow set mismatch"
    for path in practice_dir.glob("*.md"):
        assert len(path.read_text(encoding="utf-8")) >= 200, f"practice workflow is unexpectedly short: {path.name}"
    assert (ROOT / "scripts" / "audit_matter.py").is_file(), "missing matter audit tool"
    assert (ROOT / "scripts" / "package_skill.py").is_file(), "missing Unicode-safe package tool"

    commercial_files = {
        "README.md", "contract-performance.md", "corporate-equity.md", "authority-seals.md",
        "security-finance.md", "damages-accounting.md", "preservation-insolvency.md",
        "arbitration-crossborder.md",
        "control-disputes.md", "resolution-review.md", "seals-litigation.md",
        "linked-proceedings.md", "registration-remedies.md", "control-sources.md", "commercial-disputes-map.md",
        "company-litigation-map.md",
    }
    commercial_dir = ROOT / "references" / "commercial"
    assert {path.name for path in commercial_dir.glob("*.md")} == commercial_files, "commercial workflow set mismatch"
    scenarios = json.loads((ROOT / "evals" / "scenarios.json").read_text(encoding="utf-8"))
    rubric = json.loads((ROOT / "evals" / "rubric.json").read_text(encoding="utf-8"))
    scenario_ids = [item["id"] for item in scenarios]
    assert len(scenario_ids) == len(set(scenario_ids)), "duplicate evaluation id"
    assert set(scenario_ids) == set(rubric), "evaluation prompts/rubrics mismatch"
    assert all(item.get("prompt") and item.get("mode") for item in scenarios), "empty evaluation"
    assert all(isinstance(value, list) and value for value in rubric.values()), "empty rubric"
    patterns = json.loads((commercial_dir / "decision-patterns.json").read_text(encoding="utf-8"))
    assert len(patterns) == 12 and len({item["id"] for item in patterns}) == 12
    for item in patterns:
        assert all(item.get(key) for key in (
            "id", "name", "decisiveQuestions", "evidence", "opposingArguments", "failureMode",
        ))
        assert re.fullmatch(r"C\d{2}", item["id"]), f"invalid commercial pattern id: {item['id']}"

    authorities = json.loads((commercial_dir / "authority-registry.json").read_text(encoding="utf-8"))
    assert len(authorities) >= 74, "commercial authority registry is unexpectedly small"
    authority_ids = [item["id"] for item in authorities]
    assert len(authority_ids) == len(set(authority_ids)), "duplicate commercial authority id"
    allowed_statuses = {"official_source_located", "official_text_verified"}
    for item in authorities:
        assert all(item.get(key) for key in (
            "id", "title", "authority", "type", "effective", "url", "topics", "status", "usageNote",
        )), f"incomplete commercial authority record: {item.get('id')}"
        assert re.fullmatch(r"CA\d{2}", item["id"]), f"invalid commercial authority id: {item['id']}"
        assert item["status"] in allowed_statuses, f"unknown authority status: {item['id']}"
        assert isinstance(item["topics"], list) and item["topics"], f"empty authority topics: {item['id']}"
        address = urlparse(item["url"])
        assert address.scheme == "https" and address.hostname, f"invalid authority URL: {item['id']}"
        assert address.hostname.endswith(("gov.cn", "court.gov.cn", "npc.gov.cn", "samr.gov.cn", "moj.gov.cn", "chinatax.gov.cn", "miit.gov.cn")), (
            f"non-official authority host: {item['id']}"
        )

    criminal = (ROOT / "references" / "法律法规" / "中华人民共和国刑法.md").read_text(encoding="utf-8")
    assert "有下列情形之一的，从重处罚" in criminal
    assert "（七）将违法所得用于行贿的。" in criminal
    assert "附件下载" not in criminal and "全国人民代表大会常务委员会制定的下列条例" not in criminal

    competition = (ROOT / "references" / "法律法规" / "中华人民共和国反不正当竞争法.md").read_text(encoding="utf-8")
    assert "2025年第二次修订" in competition
    assert "**第四十一条**" in competition

    construction_two = (ROOT / "references" / "司法解释" / "最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释（二）.md").read_text(encoding="utf-8")
    assert "法释〔2026〕12号" in construction_two
    assert "本解释自2026年6月30日起施行" in construction_two
    assert "本解释施行后，人民法院新受理的一审建设工程施工合同纠纷案件" in construction_two

    contract_general = (ROOT / "references" / "司法解释" / "最高人民法院关于适用中华人民共和国民法典合同编通则若干问题的解释.md").read_text(encoding="utf-8")
    assert "法释〔2023〕13号" in contract_general
    assert "## 三、合同的效力" in contract_general
    assert "法定代表人、负责人或者工作人员以法人、非法人组织的名义订立合同且未超越权限" in contract_general

    guarantee = (ROOT / "references" / "司法解释" / "最高人民法院关于适用中华人民共和国民法典有关担保制度的解释.md").read_text(encoding="utf-8")
    assert "法释〔2020〕28号" in guarantee
    assert "## 二、关于保证合同" in guarantee
    assert "相对人有证据证明已对公司决议进行了合理审查" in guarantee
    assert "\n二、关于保证合同\n" not in guarantee

    company_four = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（四）.md").read_text(encoding="utf-8")
    assert "会议召集程序或者表决方式仅有轻微瑕疵" in company_four
    assert "会议未对决议事项进行表决" in company_four
    assert "公司依据该决议与善意相对人形成的民事法律关系不受影响" in company_four

    company_five = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国公司法〉若干问题的规定（五）.md").read_text(encoding="utf-8")
    assert "关联交易损害公司利益" in company_five
    assert "董事任期届满前被股东会或者股东大会有效决议解除职务" in company_five
    assert "公司回购部分股东股份" in company_five

    bankruptcy = (ROOT / "references" / "法律法规" / "中华人民共和国企业破产法.md").read_text(encoding="utf-8")
    assert "修订草案正在立法审议，尚未生效" in bankruptcy
    assert "妥善保管其占有和管理的财产、印章和账簿、文书等资料" in bankruptcy
    assert "拒不向管理人移交财产、印章和账簿、文书等资料" in bankruptcy
    assert "**第一百三十六条**" in bankruptcy

    bankruptcy_two = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（二）.md").read_text(encoding="utf-8")
    assert "依法执行回转的财产" in bankruptcy_two
    assert "及时解除对债务人财产的保全措施" in bankruptcy_two
    assert "拒绝追收" in bankruptcy_two

    bankruptcy_one = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（一）.md").read_text(encoding="utf-8")
    assert "经人民法院强制执行,无法清偿债务" in bankruptcy_one
    assert "向申请人出具收到申请及所附证据的书面凭证" in bankruptcy_one
    assert "申请人未预先交纳诉讼费用" in bankruptcy_one

    bankruptcy_three = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国企业破产法〉若干问题的规定（三）.md").read_text(encoding="utf-8")
    assert "优先于普通破产债权清偿" in bankruptcy_three
    assert "提前十日书面报告债权人委员会或者人民法院" in bankruptcy_three

    sale_contract = (ROOT / "references" / "司法解释" / "最高人民法院关于审理买卖合同纠纷案件适用法律问题的解释.md").read_text(encoding="utf-8")
    assert "送货单、收货单、结算单、发票" in sale_contract
    assert "一年期贷款市场报价利率（LPR）标准为基础，加计30—50%" in sale_contract
    assert "已经支付标的物总价款的百分之七十五以上" in sale_contract

    bills = (ROOT / "references" / "法律法规" / "中华人民共和国票据法.md").read_text(encoding="utf-8")
    assert "全文有效" in bills
    assert "法人和其他使用票据的单位在票据上的签章" in bills
    assert "票据上有伪造、变造的签章的，不影响票据上其他真实签章的效力" in bills
    assert "**第一百一十条**" in bills

    bills_disputes = (ROOT / "references" / "司法解释" / "最高人民法院关于审理票据纠纷案件若干问题的规定.md").read_text(encoding="utf-8")
    assert "票据诉讼的举证责任由提出主张的一方当事人承担" in bills_disputes
    assert "签章人应当承担票据责任" in bills_disputes
    assert "被伪造签章者不承担票据责任" in bills_disputes
    assert "票据纠纷案件不应因此而中止审理" in bills_disputes

    execution_objection = (ROOT / "references" / "司法解释" / "最高人民法院关于审理执行异议之诉案件适用法律问题的解释.md").read_text(encoding="utf-8")
    assert "自裁定送达之日起十五日内" in execution_objection
    assert "同时判决解除执行措施" in execution_objection
    assert "管理人接管债务人财产后" in execution_objection
    assert "非因案外人自身原因未办理不动产所有权转移登记" in execution_objection
    assert "通过伪造证据，或者单方捏造案件基本事实" in execution_objection

    insurance = (ROOT / "references" / "法律法规" / "中华人民共和国保险法.md").read_text(encoding="utf-8")
    assert "未作提示或者明确说明的，该条款不产生效力" in insurance
    assert "应当在三十日内作出核定" in insurance
    assert "第三者有权就其应获赔偿部分直接向保险人请求赔偿保险金" in insurance
    assert "**第一百八十五条**" in insurance

    partnership = (ROOT / "references" / "法律法规" / "中华人民共和国合伙企业法.md").read_text(encoding="utf-8")
    assert "对外代表合伙企业权利的限制，不得对抗善意第三人" in partnership
    assert "有限合伙人不执行合伙事务，不得对外代表有限合伙企业" in partnership
    assert "**第一百零九条**" in partnership

    securities = (ROOT / "references" / "法律法规" / "中华人民共和国证券法.md").read_text(encoding="utf-8")
    assert "信息披露义务人应当承担赔偿责任" in securities
    assert "销售、提供与投资者上述状况相匹配的证券、服务" in securities
    assert "投资者保护机构受五十名以上投资者委托" in securities
    assert "**第二百二十六条**" in securities

    insurance_one = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（一）.md").read_text(encoding="utf-8")
    assert "认定保险合同是否成立，适用合同订立时的法律" in insurance_one
    assert "已经终审的案件" in insurance_one

    insurance_two = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（二）.md").read_text(encoding="utf-8")
    assert "视为其对代签字或者盖章行为的追认" in insurance_two
    assert "保险人对其履行了明确说明义务负举证责任" in insurance_two

    insurance_three = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（三）.md").read_text(encoding="utf-8")
    assert "投保人指定受益人未经被保险人同意" in insurance_three
    assert "应当证明被保险人的死亡、伤残结果" in insurance_three

    insurance_four = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国保险法〉若干问题的解释（四）.md").read_text(encoding="utf-8")
    assert "危险程度显著增加" in insurance_four
    assert "保险人以其已向被保险人赔偿为由拒绝赔偿保险金的" in insurance_four

    securities_false = (ROOT / "references" / "司法解释" / "最高人民法院关于审理证券市场虚假陈述侵权民事赔偿案件的若干规定.md").read_text(encoding="utf-8")
    assert "不得仅以虚假陈述未经监管部门行政处罚" in securities_false
    assert "交易因果关系成立" in securities_false
    assert "不能提供勤勉尽责的相应证据" in securities_false
    assert "投资差额损失、投资差额损失部分的佣金和印花税" in securities_false
    assert "证券市场的风险" in securities_false

    foreign_law = (ROOT / "references" / "法律法规" / "中华人民共和国涉外民事关系法律适用法.md").read_text(encoding="utf-8")
    assert "可以明示选择涉外民事关系适用的法律" in foreign_law
    assert "当事人可以协议选择合同适用的法律" in foreign_law
    assert "不能查明外国法律或者该国法律没有规定的" in foreign_law

    foreign_one = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国涉外民事关系法律适用法〉若干问题的解释（一）.md").read_text(encoding="utf-8")
    assert "商事领域法律的特别规定" in foreign_one
    assert "涉及外汇管制等金融安全" in foreign_one

    foreign_two = (ROOT / "references" / "司法解释" / "最高人民法院关于适用〈中华人民共和国涉外民事关系法律适用法〉若干问题的解释（二）.md").read_text(encoding="utf-8")
    assert "当事人未选择适用外国法律的，由人民法院查明该国法律" in foreign_two
    assert "不得仅以当事人未予协助提供为由" in foreign_two

    treaties = (ROOT / "references" / "司法解释" / "最高人民法院关于审理涉外民商事案件适用国际条约和国际惯例若干问题的解释.md").read_text(encoding="utf-8")
    assert "在合同中援引尚未对中华人民共和国生效的国际条约" in treaties
    assert "当事人仅以未明示选择为由主张排除适用国际惯例" in treaties

    esign = (ROOT / "references" / "法律法规" / "中华人民共和国电子签名法.md").read_text(encoding="utf-8")
    assert "不得仅因为其采用电子签名、数据电文的形式而否定其法律效力" in esign
    assert "审查数据电文作为证据的真实性" in esign
    assert "电子签名制作数据仅由电子签名人控制" in esign

    market_penalty_procedure = (ROOT / "references" / "部门规章" / "市场监督管理行政处罚程序规定.md").read_text(encoding="utf-8")
    assert "根据第42号令、第61号令两次修正" in market_penalty_procedure
    assert "自发现线索或者收到材料之日起十五个工作日内予以核查" in market_penalty_procedure
    assert "自立案之日起九十日内作出处理决定" in market_penalty_procedure
    assert "自公告发布之日起经过三十日，即视为送达" in market_penalty_procedure

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

    document_counts = Counter(item.get("documentType", "法律") for item in catalog)
    assert document_counts == {"法律": 23, "司法解释": 48, "行政法规": 1, "部门规章": 3}
    print(f"知识库结构校验通过：{document_counts['法律']}部法律、{document_counts['司法解释']}部司法解释、{document_counts['行政法规']}部行政法规、{document_counts['部门规章']}部部门规章，{len(index):,}条完整可提取记录，{len(cases)}个案例卡、{len(archetypes)}类案件原型、{len(failure_numbers)}类失败模式、{len(practice_files)}份通用办案工作流、{len(commercial_files)}份商事工作流、{len(patterns)}类商事决策模式、{len(authorities)}项商事权威法源；不代表法律适用正确性认证。")


if __name__ == "__main__":
    main()
