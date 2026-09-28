"""Regression tests for observed retrieval risks; no external dependencies."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from search_law import article_text, choose_laws, file_articles, load_json
from audit_sources import audit as audit_sources
from new_matter import create_workspace
from search_cases import card_text, load_catalog as load_case_catalog
from search_commercial_authorities import load_registry as load_authority_registry
from audit_matter import audit as audit_matter
from package_skill import build_package


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_json("law-index.json")
        cls.catalog = load_json("law-catalog.json")

    def get_article(self, slug, number, suffix=None):
        item = next(x for x in self.index if x["lawSlug"] == slug and x["article"] == number and x["articleSuffix"] == suffix)
        return article_text(item["file"], item["articleCn"])

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/search_law.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def case_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/search_cases.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def authority_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "scripts/search_commercial_authorities.py"), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_exact_civil_article(self):
        self.assertEqual(self.get_article("civil-code", 577),
                         "当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。")

    def test_inserted_article_separate_from_base(self):
        ordinary = self.get_article("criminal-law", 133)
        inserted = self.get_article("criminal-law", 133, 1)
        self.assertNotEqual(ordinary, inserted)
        self.assertIn("追逐竞驶", inserted)
        self.assertNotIn("追逐竞驶", ordinary)

    def test_chapter_boundary_is_not_article_content(self):
        self.assertNotIn("附 则", self.get_article("criminal-law", 451))
        last = self.get_article("criminal-law", 452)
        self.assertIn("列于本法附件一", last)
        self.assertIn("列于本法附件二", last)

    def test_criminal_2024_amendment_retrievable(self):
        body = self.get_article("criminal-law", 390)
        self.assertIn("处三年以下有期徒刑或者拘役", body)
        self.assertIn("（七）将违法所得用于行贿的。", body)
        self.assertIn("可以减轻或者免除处罚", body)

    def test_competition_effective_date(self):
        self.assertEqual(self.get_article("anti-unfair-competition-law", 41),
                         "本法自2025年10月15日起施行。")

    def test_missing_law_is_rejected(self):
        self.assertNotEqual(self.cli("--article", "39").returncode, 0)

    def test_ambiguous_law_is_rejected(self):
        self.assertNotEqual(self.cli("--law", "行政", "--article", "39").returncode, 0)

    def test_unknown_law_does_not_silently_match(self):
        with self.assertRaises(SystemExit):
            choose_laws("中华人民共和国税收征收管理法", self.catalog)

    def test_exact_alias(self):
        self.assertEqual(choose_laws("消保法", self.catalog), {"consumer-rights-law"})

    def test_market_supervision_penalty_procedure_is_retrievable(self):
        slug = "market-supervision-administrative-penalty-procedure"
        self.assertEqual(choose_laws("市场监管处罚程序", self.catalog), {slug})
        self.assertIn("十五个工作日", self.get_article(slug, 18))
        self.assertIn("九十日", self.get_article(slug, 64))
        self.assertIn("经过三十日，即视为送达", self.get_article(slug, 82))
        self.assertIn("2019年4月1日起施行", self.get_article(slug, 87))

    def test_invalid_queries_fail(self):
        for args in [("--law", "刑法", "--article", "0"),
                     ("--law", "刑法", "--article", "9999"),
                     ("--keyword", " "), ("--keyword", "证据", "--limit", "0"),
                     ("--keyword", "证据", "--suffix", "1")]:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args).returncode, 0)

    def test_keyword_scoping(self):
        result = self.cli("--law", "社会保险法", "--keyword", "骗取", "--limit", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("第八十七条", result.stdout)
        self.assertIn("第八十八条", result.stdout)
        self.assertNotIn("中华人民共和国刑法", result.stdout)

    def test_no_query_must_fail(self):
        self.assertNotEqual(self.cli().returncode, 0)

    def test_file_path_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            file_articles("../not-in-skill.md")

    def test_phase_two_last_articles(self):
        expectations = {
            ("civil-procedure-law", 305): "外国国家豁免",
            ("criminal-procedure-law", 308): "中国海警局",
            ("administrative-reconsideration-law", 90): "2024年1月1日起施行",
            ("company-law", 266): "2024年7月1日起施行",
            ("labor-contract-law", 98): "2008年1月1日起施行",
            ("arbitration-law", 96): "2026年3月1日起施行",
            ("civil-evidence-provisions", 100): "2020年5月1日起施行",
        }
        for (slug, number), phrase in expectations.items():
            with self.subTest(slug=slug):
                self.assertIn(phrase, self.get_article(slug, number))

    def test_2026_construction_interpretation_is_retrievable(self):
        self.assertIn("债权的受让人", self.get_article("construction-contract-interpretation-2", 19))
        self.assertIn("新受理的一审", self.get_article("construction-contract-interpretation-2", 23))
        self.assertEqual(
            choose_laws("建工解释二", self.catalog),
            {"construction-contract-interpretation-2"},
        )

    def test_contract_general_interpretation_covers_company_authority_and_seals(self):
        article_20 = self.get_article("civil-code-contract-general-interpretation", 20)
        article_22 = self.get_article("civil-code-contract-general-interpretation", 22)
        self.assertIn("决策机构决议", article_20)
        self.assertIn("合理审查义务", article_20)
        self.assertIn("备案印章", article_22)
        self.assertIn("伪造的印章", article_22)
        self.assertEqual(
            choose_laws("合同编通则解释", self.catalog),
            {"civil-code-contract-general-interpretation"},
        )

    def test_guarantee_interpretation_covers_company_resolutions(self):
        article_7 = self.get_article("civil-code-guarantee-system-interpretation", 7)
        article_9 = self.get_article("civil-code-guarantee-system-interpretation", 9)
        self.assertIn("公司对外担保决议程序", article_7)
        self.assertIn("合理审查", article_7)
        self.assertIn("伪造、变造", article_7)
        self.assertIn("公开披露", article_9)
        self.assertEqual(
            choose_laws("担保制度解释", self.catalog),
            {"civil-code-guarantee-system-interpretation"},
        )

    def test_company_interpretation_four_covers_resolution_review(self):
        standing = self.get_article("company-law-interpretation-4", 2)
        minor_defect = self.get_article("company-law-interpretation-4", 4)
        nonexistence = self.get_article("company-law-interpretation-4", 5)
        third_party = self.get_article("company-law-interpretation-4", 6)
        self.assertIn("起诉时具有公司股东资格", standing)
        self.assertIn("仅有轻微瑕疵", minor_defect)
        self.assertIn("会议未对决议事项进行表决", nonexistence)
        self.assertIn("善意相对人", third_party)
        self.assertEqual(
            choose_laws("公司法解释四", self.catalog),
            {"company-law-interpretation-4"},
        )

    def test_company_interpretation_five_covers_control_exit_tools(self):
        related_party = self.get_article("company-law-interpretation-5", 1)
        director_removal = self.get_article("company-law-interpretation-5", 3)
        deadlock = self.get_article("company-law-interpretation-5", 5)
        self.assertIn("关联交易损害公司利益", related_party)
        self.assertIn("有效决议解除职务", director_removal)
        self.assertIn("公司回购部分股东股份", deadlock)
        self.assertIn("公司减资", deadlock)

    def test_enterprise_bankruptcy_law_connects_seals_litigation_and_execution(self):
        preservation = self.get_article("enterprise-bankruptcy-law", 15)
        execution = self.get_article("enterprise-bankruptcy-law", 19)
        pending_litigation = self.get_article("enterprise-bankruptcy-law", 20)
        refusal = self.get_article("enterprise-bankruptcy-law", 127)
        self.assertIn("财产、印章和账簿、文书", preservation)
        self.assertIn("执行程序应当中止", execution)
        self.assertIn("民事诉讼或者仲裁应当中止", pending_litigation)
        self.assertIn("拒不向管理人移交", refusal)
        self.assertEqual(
            choose_laws("破产法", self.catalog),
            {"enterprise-bankruptcy-law"},
        )

    def test_bankruptcy_interpretations_cover_recovery_and_asset_disposition(self):
        execution = self.get_article("enterprise-bankruptcy-law-interpretation-2", 5)
        preservation = self.get_article("enterprise-bankruptcy-law-interpretation-2", 7)
        disposition = self.get_article("enterprise-bankruptcy-law-interpretation-3", 15)
        self.assertIn("依法予以纠正", execution)
        self.assertIn("及时解除", preservation)
        self.assertIn("债权人会议进行表决", disposition)
        self.assertIn("停止处分行为", disposition)
        self.assertEqual(
            choose_laws("破产法解释三", self.catalog),
            {"enterprise-bankruptcy-law-interpretation-3"},
        )

    def test_bankruptcy_interpretation_one_covers_acceptance_evidence(self):
        insolvency = self.get_article("enterprise-bankruptcy-law-interpretation-1", 4)
        receipt = self.get_article("enterprise-bankruptcy-law-interpretation-1", 7)
        costs = self.get_article("enterprise-bankruptcy-law-interpretation-1", 8)
        self.assertIn("经人民法院强制执行,无法清偿债务", insolvency)
        self.assertIn("书面凭证", receipt)
        self.assertIn("补充、补正", receipt)
        self.assertIn("未预先交纳诉讼费用", costs)
        self.assertEqual(
            choose_laws("破产法解释一", self.catalog),
            {"enterprise-bankruptcy-law-interpretation-1"},
        )

    def test_sale_contract_interpretation_covers_evidence_and_remedies(self):
        formation = self.get_article("sale-contract-interpretation", 1)
        invoice = self.get_article("sale-contract-interpretation", 5)
        delay = self.get_article("sale-contract-interpretation", 18)
        retention = self.get_article("sale-contract-interpretation", 26)
        pleading = self.get_article("sale-contract-interpretation", 31)
        self.assertIn("送货单、收货单、结算单、发票", formation)
        self.assertIn("其他证据证明交付", invoice)
        self.assertIn("加计30—50%", delay)
        self.assertIn("百分之七十五以上", retention)
        self.assertIn("应当提起反诉", pleading)
        self.assertEqual(
            choose_laws("买卖合同解释", self.catalog),
            {"sale-contract-interpretation"},
        )

    def test_negotiable_instruments_law_covers_seals_defenses_and_time_limits(self):
        seal = self.get_article("negotiable-instruments-law", 7)
        defense = self.get_article("negotiable-instruments-law", 13)
        forgery = self.get_article("negotiable-instruments-law", 14)
        limitation = self.get_article("negotiable-instruments-law", 17)
        endorsement = self.get_article("negotiable-instruments-law", 31)
        self.assertIn("单位的盖章加其法定代表人或者其授权的代理人的签章", seal)
        self.assertIn("持票人明知存在抗辩事由", defense)
        self.assertIn("不影响票据上其他真实签章的效力", forgery)
        self.assertIn("自出票日起六个月", limitation)
        self.assertIn("背书应当连续", endorsement)
        self.assertEqual(choose_laws("票据法", self.catalog), {"negotiable-instruments-law"})

    def test_negotiable_instruments_disputes_provisions_covers_seals_proof_and_parallel_cases(self):
        preservation = self.get_article("negotiable-instruments-disputes-provisions", 7)
        proof = self.get_article("negotiable-instruments-disputes-provisions", 8)
        wrong_seal = self.get_article("negotiable-instruments-disputes-provisions", 41)
        forgery = self.get_article("negotiable-instruments-disputes-provisions", 66)
        parallel_case = self.get_article("negotiable-instruments-disputes-provisions", 73)
        self.assertIn("保全措施或者执行措施", preservation)
        self.assertIn("持票人对持票的合法性应当负责举证", proof)
        self.assertIn("签章人应当承担票据责任", wrong_seal)
        self.assertIn("被伪造签章者不承担票据责任", forgery)
        self.assertIn("票据纠纷案件不应因此而中止审理", parallel_case)
        self.assertEqual(
            choose_laws("票据司法解释", self.catalog),
            {"negotiable-instruments-disputes-provisions"},
        )

    def test_execution_objection_litigation_interpretation_covers_deadline_relief_and_bankruptcy(self):
        filing = self.get_article("execution-objection-litigation-interpretation", 1)
        relief = self.get_article("execution-objection-litigation-interpretation", 3)
        combined = self.get_article("execution-objection-litigation-interpretation", 5)
        bankruptcy = self.get_article("execution-objection-litigation-interpretation", 9)
        purchaser = self.get_article("execution-objection-litigation-interpretation", 14)
        false_case = self.get_article("execution-objection-litigation-interpretation", 21)
        self.assertIn("自裁定送达之日起十五日内", filing)
        self.assertIn("同时判决解除执行措施", relief)
        self.assertIn("返还原物、返还价款", combined)
        self.assertIn("管理人接管债务人财产后", bankruptcy)
        self.assertIn("非因案外人自身原因", purchaser)
        self.assertIn("伪造证据", false_case)
        self.assertEqual(
            choose_laws("执行异议之诉解释", self.catalog),
            {"execution-objection-litigation-interpretation"},
        )

    def test_insurance_law_covers_exclusions_claims_and_third_party_rights(self):
        exclusion = self.get_article("insurance-law", 17)
        claim = self.get_article("insurance-law", 23)
        liability = self.get_article("insurance-law", 65)
        self.assertIn("未作提示或者明确说明的，该条款不产生效力", exclusion)
        self.assertIn("应当在三十日内作出核定", claim)
        self.assertIn("第三者有权就其应获赔偿部分直接向保险人请求赔偿保险金", liability)
        self.assertEqual(choose_laws("保险法", self.catalog), {"insurance-law"})

    def test_partnership_enterprise_law_covers_authority_and_limited_partner_boundary(self):
        authority = self.get_article("partnership-enterprise-law", 37)
        limited = self.get_article("partnership-enterprise-law", 68)
        self.assertIn("不得对抗善意第三人", authority)
        self.assertIn("有限合伙人不执行合伙事务", limited)
        self.assertIn("不视为执行合伙事务", limited)
        self.assertEqual(choose_laws("合伙企业法", self.catalog), {"partnership-enterprise-law"})

    def test_securities_law_covers_disclosure_suitability_and_representative_actions(self):
        disclosure = self.get_article("securities-law", 85)
        suitability = self.get_article("securities-law", 88)
        representation = self.get_article("securities-law", 95)
        self.assertIn("信息披露义务人应当承担赔偿责任", disclosure)
        self.assertIn("相匹配的证券、服务", suitability)
        self.assertIn("投资者保护机构受五十名以上投资者委托", representation)
        self.assertNotIn("第七章", representation)
        self.assertEqual(choose_laws("证券法", self.catalog), {"securities-law"})

    def test_insurance_interpretations_cover_time_effect_signatures_proof_and_third_parties(self):
        time_effect = self.get_article("insurance-law-interpretation-1", 1)
        signature = self.get_article("insurance-law-interpretation-2", 3)
        proof = self.get_article("insurance-law-interpretation-2", 13)
        beneficiary = self.get_article("insurance-law-interpretation-3", 9)
        causation = self.get_article("insurance-law-interpretation-3", 23)
        increased_risk = self.get_article("insurance-law-interpretation-4", 4)
        third_party = self.get_article("insurance-law-interpretation-4", 20)
        self.assertIn("适用合同订立时的法律", time_effect)
        self.assertIn("代签字或者盖章行为的追认", signature)
        self.assertIn("明确说明义务负举证责任", proof)
        self.assertIn("指定受益人未经被保险人同意", beneficiary)
        self.assertIn("存在因果关系", causation)
        self.assertIn("危险程度显著增加", increased_risk)
        self.assertIn("第三者依照保险法第六十五条第二款", third_party)
        self.assertEqual(choose_laws("保险法解释二", self.catalog), {"insurance-law-interpretation-2"})

    def test_securities_false_statements_provisions_cover_elements_fault_loss_and_limitations(self):
        filing = self.get_article("securities-false-statements-provisions", 2)
        causation = self.get_article("securities-false-statements-provisions", 11)
        diligence = self.get_article("securities-false-statements-provisions", 14)
        controller = self.get_article("securities-false-statements-provisions", 20)
        loss = self.get_article("securities-false-statements-provisions", 25)
        other_causes = self.get_article("securities-false-statements-provisions", 31)
        limitation = self.get_article("securities-false-statements-provisions", 32)
        self.assertIn("未经监管部门行政处罚", filing)
        self.assertIn("交易因果关系成立", causation)
        self.assertIn("勤勉尽责的相应证据", diligence)
        self.assertIn("控股股东、实际控制人", controller)
        self.assertIn("佣金和印花税", loss)
        self.assertIn("证券市场的风险", other_causes)
        self.assertIn("以在先的为准", limitation)
        self.assertEqual(choose_laws("证券虚假陈述规定", self.catalog), {"securities-false-statements-provisions"})

    def test_crossborder_law_and_interpretations_cover_choice_mandatory_rules_and_foreign_law_proof(self):
        choice = self.get_article("foreign-related-civil-relations-law-application-law", 41)
        mandatory = self.get_article("foreign-law-application-interpretation-1", 8)
        proof = self.get_article("foreign-law-application-interpretation-2", 1)
        self.assertIn("当事人可以协议选择合同适用的法律", choice)
        self.assertIn("外汇管制等金融安全", mandatory)
        self.assertIn("当事人未选择适用外国法律的，由人民法院查明", proof)
        self.assertEqual(choose_laws("法律适用法解释二", self.catalog), {"foreign-law-application-interpretation-2"})

    def test_international_treaties_and_customs_interpretation_distinguishes_incorporation_and_custom(self):
        incorporation = self.get_article("international-treaties-customs-interpretation", 4)
        custom = self.get_article("international-treaties-customs-interpretation", 6)
        self.assertIn("合同中援引尚未对中华人民共和国生效的国际条约", incorporation)
        self.assertIn("可以适用国际惯例", custom)
        self.assertIn("仅以未明示选择为由", custom)

    def test_electronic_signature_law_covers_form_authenticity_and_reliability(self):
        form = self.get_article("electronic-signature-law", 3)
        authenticity = self.get_article("electronic-signature-law", 8)
        reliability = self.get_article("electronic-signature-law", 13)
        self.assertIn("不得仅因为其采用电子签名", form)
        self.assertIn("生成、储存或者传递数据电文方法的可靠性", authenticity)
        self.assertIn("签署时电子签名制作数据仅由电子签名人控制", reliability)
        self.assertEqual(choose_laws("电子签名法", self.catalog), {"electronic-signature-law"})

    def test_civil_procedure_interpretation_covers_proof_and_repeat_litigation(self):
        burden = self.get_article("civil-procedure-law-interpretation", 90)
        standard = self.get_article("civil-procedure-law-interpretation", 108)
        repeat = self.get_article("civil-procedure-law-interpretation", 247)
        self.assertIn("由负有举证证明责任的当事人承担不利的后果", burden)
        self.assertIn("存在具有高度可能性的", standard)
        self.assertIn("同时符合下列条件的，构成重复起诉", repeat)
        self.assertEqual(choose_laws("民诉法解释", self.catalog), {"civil-procedure-law-interpretation"})

    def test_civil_procedure_first_chapter_and_boundary_are_preserved(self):
        records = {x["article"]: x for x in self.index if x["lawSlug"] == "civil-procedure-law-interpretation"}
        self.assertTrue(all(records[n]["chapter"] == "一、管辖" for n in range(1, 43)))
        self.assertEqual(records[43]["chapter"], "二、回避")
        self.assertNotIn("一、管辖", self.get_article("civil-procedure-law-interpretation", 1))

    def test_execution_objection_and_party_addition_rules_are_retrievable(self):
        objection = self.get_article("execution-objection-review-provisions", 24)
        contribution = self.get_article("execution-change-add-parties-provisions", 17)
        single_member = self.get_article("execution-change-add-parties-provisions", 20)
        self.assertIn("该权利能否排除执行", objection)
        self.assertIn("未缴纳或未足额缴纳出资的股东", contribution)
        self.assertIn("不能证明公司财产独立于自己的财产", single_member)
        self.assertEqual(choose_laws("执行异议复议规定", self.catalog), {"execution-objection-review-provisions"})
        self.assertEqual(choose_laws("变更追加当事人规定", self.catalog), {"execution-change-add-parties-provisions"})

    def test_preservation_investigation_seizure_and_auction_rules_are_retrievable(self):
        security = self.get_article("property-preservation-provisions", 5)
        investigation = self.get_article("execution-property-investigation-provisions", 1)
        seizure = self.get_article("civil-execution-seizure-freeze-provisions", 2)
        appraisal = self.get_article("civil-execution-auction-sale-provisions", 4)
        self.assertIn("不超过请求保全数额的百分之三十", security)
        self.assertIn("网络执行查控系统", investigation)
        self.assertIn("登记在被执行人名下", seizure)
        self.assertIn("被执行人的股权进行评估", appraisal)

    def test_execution_settlement_and_guarantee_preserve_distinct_remedies(self):
        settlement = self.get_article("execution-settlement-provisions", 9)
        guarantee = self.get_article("execution-guarantee-provisions", 11)
        self.assertIn("申请恢复执行原生效法律文书", settlement)
        self.assertIn("就履行执行和解协议向执行法院提起诉讼", settlement)
        self.assertIn("不得将担保人变更、追加为被执行人", guarantee)
        self.assertEqual(choose_laws("执行担保规定", self.catalog), {"execution-guarantee-provisions"})

    def test_civil_code_general_interpretation_covers_abuse_and_agency_proof(self):
        abuse = self.get_article("civil-code-general-provisions-interpretation", 3)
        unauthorized = self.get_article("civil-code-general-provisions-interpretation", 27)
        apparent = self.get_article("civil-code-general-provisions-interpretation", 28)
        self.assertIn("构成滥用民事权利", abuse)
        self.assertNotIn("二、民事权利能力", abuse)
        self.assertIn("由行为人就相对人知道或者应当知道", unauthorized)
        self.assertIn("存在代理权的外观", apparent)
        self.assertIn("被代理人应当就相对人不符合", apparent)

    def test_company_time_effect_and_interpretation_one_are_retrievable(self):
        effect = self.get_article("company-law-time-effect-provisions", 1)
        finality = self.get_article("company-law-time-effect-provisions", 7)
        derivative = self.get_article("company-law-interpretation-1", 4)
        self.assertIn("股东会召集程序不当", effect)
        self.assertIn("适用当时的法律、司法解释", finality)
        self.assertIn("180日以上连续持股期间", derivative)
        self.assertEqual(choose_laws("公司法时间效力规定", self.catalog), {"company-law-time-effect-provisions"})
        self.assertEqual(choose_laws("公司法解释一", self.catalog), {"company-law-interpretation-1"})

    def test_private_lending_rules_cover_proof_principal_and_interest_cap(self):
        voucher = self.get_article("private-lending-interpretation", 2)
        transfer = self.get_article("private-lending-interpretation", 16)
        principal = self.get_article("private-lending-interpretation", 26)
        interest = self.get_article("private-lending-interpretation", 25)
        self.assertIn("其他能够证明借贷法律关系存在的证据", voucher)
        self.assertIn("原告仍应就借贷关系的成立承担举证责任", transfer)
        self.assertIn("实际出借的金额认定为本金", principal)
        self.assertIn("合同成立时一年期贷款市场报价利率四倍", interest)
        self.assertEqual(choose_laws("民间借贷司法解释", self.catalog), {"private-lending-interpretation"})

    def test_deposit_certificate_and_enterprise_restructuring_rules_are_retrievable(self):
        deposit = self.get_article("deposit-certificate-disputes-provisions", 5)
        transfer = self.get_article("enterprise-restructuring-disputes-provisions", 6)
        stripping = self.get_article("enterprise-restructuring-disputes-provisions", 7)
        self.assertIn("存款关系的真实性", deposit)
        self.assertIn("金融机构应当对持有人与金融机构间是否存在存款关系负举证责任", deposit)
        self.assertIn("新设公司在所接收的财产范围内", transfer)
        self.assertIn("将债务留在原企业", stripping)

    def test_foreign_investment_and_futures_rules_cover_control_and_asset_separation(self):
        investor = self.get_article("foreign-invested-enterprise-disputes-interpretation-1", 14)
        direct_right = self.get_article("foreign-invested-enterprise-disputes-interpretation-1", 17)
        forced_close = self.get_article("futures-disputes-provisions", 39)
        segregation = self.get_article("futures-disputes-provisions-2", 4)
        self.assertIn("一方实际投资、另一方作为外商投资企业名义股东", investor)
        self.assertIn("直接向外商投资企业请求分配利润", direct_right)
        self.assertIn("强行平仓数额", forced_close)
        self.assertIn("客户在期货公司保证金账户中的资金", segregation)

    def test_letter_of_credit_preserves_independence_and_fraud_exception(self):
        independence = self.get_article("letter-of-credit-disputes-provisions", 5)
        fraud = self.get_article("letter-of-credit-disputes-provisions", 8)
        exception = self.get_article("letter-of-credit-disputes-provisions", 10)
        self.assertIn("在表面上相符", independence)
        self.assertIn("基础交易提出抗辩的，人民法院不予支持", independence)
        self.assertIn("应当认定存在信用证欺诈", fraud)
        self.assertIn("善意地进行了付款", exception)

    def test_independent_guarantee_distinguishes_definition_fraud_and_stop_payment(self):
        definition = self.get_article("independent-guarantee-disputes-provisions", 1)
        fraud = self.get_article("independent-guarantee-disputes-provisions", 12)
        stop = self.get_article("independent-guarantee-disputes-provisions", 16)
        self.assertIn("银行或非银行金融机构作为开立人", definition)
        self.assertIn("应当认定构成独立保函欺诈", fraud)
        self.assertIn("三十日内未依法提起", stop)
        self.assertEqual(choose_laws("独立保函司法解释", self.catalog), {"independent-guarantee-disputes-provisions"})

    def test_bank_card_rules_cover_terms_proof_and_missing_transaction_data(self):
        terms = self.get_article("bank-card-civil-disputes-provisions", 2)
        proof = self.get_article("bank-card-civil-disputes-provisions", 4)
        missing_data = self.get_article("bank-card-civil-disputes-provisions", 5)
        self.assertIn("格式条款未履行提示或者说明义务", terms)
        self.assertIn("本人交易或者其授权交易", proof)
        self.assertIn("应当承担举证责任", proof)
        self.assertIn("交易单据、监控录像", missing_data)
        self.assertIn("举证不能的法律后果", missing_data)
        self.assertEqual(choose_laws("银行卡司法解释", self.catalog), {"bank-card-civil-disputes-provisions"})

    def test_financial_leasing_rules_cover_characterization_and_remedy_election(self):
        characterization = self.get_article("financial-leasing-contract-interpretation", 1)
        leaseback = self.get_article("financial-leasing-contract-interpretation", 2)
        election = self.get_article("financial-leasing-contract-interpretation", 10)
        damages = self.get_article("financial-leasing-contract-interpretation", 11)
        self.assertIn("实际不构成融资租赁法律关系", characterization)
        self.assertIn("承租人和出卖人系同一人", leaseback)
        self.assertIn("作出选择", election)
        self.assertIn("全部未付租金及其他费用与收回租赁物价值的差额", damages)
        self.assertEqual(choose_laws("融资租赁司法解释", self.catalog), {"financial-leasing-contract-interpretation"})

    def test_registration_rules_distinguish_change_false_registration_and_judgment_relief(self):
        change = self.get_article("market-entity-registration-regulation", 24)
        license_return = self.get_article("market-entity-registration-regulation", 37)
        false_registration = self.get_article("market-entity-registration-regulation", 40)
        new_signer = self.get_article("market-entity-registration-implementation-rules", 33)
        suspension = self.get_article("market-entity-registration-implementation-rules", 54)
        assistance = self.get_article("market-entity-registration-implementation-rules", 79)
        abusive_change = self.get_article("company-registration-management-measures", 20)
        erasure = self.get_article("company-registration-management-measures", 23)
        self.assertIn("作出变更决议、决定", change)
        self.assertIn("应当缴回营业执照", license_return)
        self.assertIn("受虚假市场主体登记影响", false_registration)
        self.assertIn("由新任法定代表人", new_signer)
        self.assertIn("相关的民事权利存在争议", suspension)
        self.assertIn("生效法律文书和协助执行通知书", assistance)
        self.assertIn("恶意转移财产、逃避债务", abusive_change)
        self.assertIn("协助涤除", erasure)
        self.assertEqual(choose_laws("市场主体登记管理条例", self.catalog), {"market-entity-registration-regulation"})
        self.assertEqual(choose_laws("登记管理实施细则", self.catalog), {"market-entity-registration-implementation-rules"})
        self.assertEqual(choose_laws("公司登记管理办法", self.catalog), {"company-registration-management-measures"})

    def test_property_interpretation_covers_registration_judgment_and_good_faith(self):
        civil_action = self.get_article("civil-code-property-book-interpretation-1", 1)
        true_right = self.get_article("civil-code-property-book-interpretation-1", 2)
        judgment = self.get_article("civil-code-property-book-interpretation-1", 7)
        burden = self.get_article("civil-code-property-book-interpretation-1", 14)
        no_good_faith = self.get_article("civil-code-property-book-interpretation-1", 15)
        invalid_contract = self.get_article("civil-code-property-book-interpretation-1", 20)
        self.assertIn("提起民事诉讼的，应当依法受理", civil_action)
        self.assertIn("登记簿的记载与真实权利状态不符", true_right)
        self.assertIn("拍卖成交裁定书", judgment)
        self.assertIn("真实权利人主张受让人不构成善意", burden)
        self.assertIn("知道转让人无处分权", no_good_faith)
        self.assertIn("转让合同被认定无效", invalid_contract)
        self.assertEqual(choose_laws("物权编解释一", self.catalog), {"civil-code-property-book-interpretation-1"})

    def test_prepaid_consumption_rules_cover_identity_refund_fraud_and_evidence(self):
        borrowed_name = self.get_article("prepaid-consumption-disputes-interpretation", 4)
        unfair_terms = self.get_article("prepaid-consumption-disputes-interpretation", 9)
        cooling_off = self.get_article("prepaid-consumption-disputes-interpretation", 14)
        refund = self.get_article("prepaid-consumption-disputes-interpretation", 15)
        fraud = self.get_article("prepaid-consumption-disputes-interpretation", 23)
        evidence = self.get_article("prepaid-consumption-disputes-interpretation", 25)
        self.assertIn("允许他人使用其营业执照", borrowed_name)
        self.assertIn("排除消费者依法解除合同或者请求返还预付款的权利", unfair_terms)
        self.assertIn("七日内请求经营者返还预付款本金", cooling_off)
        self.assertIn("返还剩余预付款并支付利息", refund)
        self.assertIn("恶意逃避消费者申请退款", fraud)
        self.assertIn("无正当理由拒不提交", evidence)
        self.assertEqual(choose_laws("预付式消费司法解释", self.catalog), {"prepaid-consumption-disputes-interpretation"})

    def test_new_authority_aliases(self):
        self.assertEqual(choose_laws("民诉法", self.catalog), {"civil-procedure-law"})
        self.assertEqual(choose_laws("民事证据规定", self.catalog), {"civil-evidence-provisions"})
        self.assertEqual(choose_laws("仲裁法", self.catalog), {"arbitration-law"})

    def test_official_title_book_marks_do_not_block_retrieval(self):
        for title, slug in [
            ("最高人民法院关于适用《中华人民共和国民事诉讼法》的解释", "civil-procedure-law-interpretation"),
            ("最高人民法院关于适用《中华人民共和国民事诉讼法》执行程序若干问题的解释", "civil-procedure-execution-interpretation"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(choose_laws(title, self.catalog), {slug})
        self.assertNotEqual(
            choose_laws("公司法解释四", self.catalog),
            choose_laws("公司法解释五", self.catalog),
        )

    def test_source_manifest_offline_audit(self):
        self.assertEqual(audit_sources(), [])

    def test_matter_workspace_is_structured_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "matter"
            markdown, data = create_workspace(output, "测试案件")
            self.assertIn("要件—事实—证据矩阵", markdown.read_text(encoding="utf-8"))
            document = json.loads(data.read_text(encoding="utf-8"))
            self.assertEqual(document["title"], "测试案件")
            self.assertEqual(document["schemaVersion"], 2)
            self.assertIn("contradictions", document)
            with self.assertRaises(SystemExit):
                create_workspace(output, "覆盖")

    def test_new_matter_audit_reports_preparation_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data = create_workspace(Path(temp) / "matter", "待准备案件")
            errors, gaps = audit_matter(json.loads(data.read_text(encoding="utf-8")))
            self.assertEqual(errors, [])
            self.assertIn("尚未建立证据来源、原件、完整性和证明目的台账", gaps)
            self.assertIn("尚未完成送达、起算事件和期限核查", gaps)

    def test_matter_audit_rejects_duplicate_or_invalid_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data = create_workspace(Path(temp) / "matter", "编号审计")
            document = json.loads(data.read_text(encoding="utf-8"))
            document["facts"] = [{"id": "F01"}, {"id": "F01"}]
            errors, _ = audit_matter(document)
            self.assertIn("facts存在重复id", errors)

    def test_matter_audit_checks_evidence_provenance_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data = create_workspace(Path(temp) / "matter", "证据字段审计")
            document = json.loads(data.read_text(encoding="utf-8"))
            document["evidence"] = [{"id": "E01", "name": "聊天截图"}]
            errors, _ = audit_matter(document)
            joined = "\n".join(errors)
            self.assertIn("originalStatus", joined)
            self.assertIn("completeness", joined)
            self.assertIn("source", joined)

    def test_matter_audit_cli_uses_gap_exit_code(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data = create_workspace(Path(temp) / "matter", "退出码审计")
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(ROOT / "scripts/audit_matter.py"), "--input", str(data)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("待补工作", result.stdout)
            self.assertIn("尚未评估保全、财产线索和实际执行路径", result.stdout)

    def test_commercial_matter_profile_and_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            markdown, data = create_workspace(Path(temp) / "matter", "商事案件", profile="commercial")
            document = json.loads(data.read_text(encoding="utf-8"))
            self.assertEqual(document["commercialProfileVersion"], 1)
            self.assertIn("performanceLedger", document["commercial"])
            self.assertIn("商事专项台账", markdown.read_text(encoding="utf-8"))
            errors, gaps = audit_matter(document)
            self.assertEqual(errors, [])
            self.assertIn("商事模块尚未评估：交易结构（transactionStructure）", gaps)

    def test_unknown_matter_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SystemExit):
                create_workspace(Path(temp) / "matter", "未知类型", profile="unknown")

    def test_commercial_audit_rejects_placeholder_records(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data = create_workspace(Path(temp) / "matter", "商事占位审计", profile="commercial")
            document = json.loads(data.read_text(encoding="utf-8"))
            document["commercial"]["performanceLedger"] = [{"id": "B01"}]
            errors, _ = audit_matter(document)
            message = "\n".join(errors)
            self.assertIn("commercial.performanceLedger第1项缺少字段", message)
            self.assertIn("evidence", message)
            self.assertIn("performance", message)

    def test_commercial_authority_registry_uses_official_sources(self):
        registry = load_authority_registry()
        self.assertGreaterEqual(len(registry), 74)
        self.assertEqual(len({item["id"] for item in registry}), len(registry))
        allowed_hosts = ("gov.cn", "court.gov.cn", "npc.gov.cn", "samr.gov.cn", "moj.gov.cn", "chinatax.gov.cn", "miit.gov.cn")
        for item in registry:
            with self.subTest(authority=item["id"]):
                self.assertTrue(item["url"].startswith("https://"))
                self.assertTrue(any(host in item["url"] for host in allowed_hosts))
                self.assertIn(item["status"], {"official_source_located", "official_text_verified"})
                self.assertTrue(item["usageNote"])

    def test_construction_rules_preserve_settlement_and_version_boundaries(self):
        first = "construction-contract-interpretation-1"
        self.assertIn("按照约定处理", self.get_article(first, 21))
        self.assertIn("一方当事人申请对工程造价进行鉴定", self.get_article(first, 29))
        self.assertIn("十八个月", self.get_article(first, 41))
        second = "construction-contract-interpretation-2"
        self.assertIn("没有合同关系的发包人", self.get_article(second, 6))
        self.assertIn("代位权", self.get_article(second, 7))
        self.assertIn("新受理的一审", self.get_article(second, 23))
        self.assertEqual(choose_laws("建工解释一", self.catalog), {first})
        entry = next(x for x in load_authority_registry() if x["id"] == "CA75")
        self.assertIn("第六、七条", entry["usageNote"])

    def test_certificate_return_preservation_case_keeps_current_official_entry_and_limits(self):
        registry = load_authority_registry()
        item = next(entry for entry in registry if entry["id"] == "CA15")
        self.assertEqual(item["url"], "https://cicc.court.gov.cn/html/1/218/62/163/425/12926.html")
        self.assertIn("不是指导性案例", item["usageNote"])
        self.assertIn("独资股东决定", item["usageNote"])
        self.assertIn("行为保全", item["topics"])

    def test_commercial_authority_search_preserves_source_limits(self):
        result = self.authority_cli("--keyword", "建设工程", "--status", "official_text_verified")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CA19", result.stdout)
        self.assertIn("2026-06-30", result.stdout)
        self.assertIn("官方来源", result.stdout)
        self.assertIn("使用边界", result.stdout)

    def test_commercial_authority_search_rejects_empty_query(self):
        self.assertNotEqual(self.authority_cli().returncode, 0)

    def test_commercial_maps_cover_resolution_and_certificate_return(self):
        commercial = ROOT / "references" / "commercial"
        disputes = (commercial / "commercial-disputes-map.md").read_text(encoding="utf-8")
        company = (commercial / "company-litigation-map.md").read_text(encoding="utf-8")
        self.assertIn("证照返还", disputes)
        self.assertIn("公司决议", disputes)
        self.assertIn("决议不成立", company)
        self.assertIn("行为保全", company)

    def test_package_preserves_unicode_paths_with_redundant_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "skill.zip"
            build_package(ROOT, package)
            with zipfile.ZipFile(package) as archive:
                info = archive.getinfo(f"{ROOT.name}/references/法律法规/中华人民共和国刑法.md")
                self.assertEqual(info.create_system, 3)
                self.assertTrue(info.flag_bits & 0x800)
                self.assertIn(b"up", info.extra)

    def test_matter_workspace_refuses_git_repo_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "public-repo"
            (repo / ".git").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                create_workspace(repo / "matter", "敏感案件")
            markdown, _ = create_workspace(repo / "matter", "明确允许", allow_git_repo=True)
            self.assertTrue(markdown.is_file())

    def test_keyword_alias_finds_electronic_service(self):
        result = self.cli("--law", "民事诉讼法", "--keyword", "电子送达", "--limit", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("检索扩展", result.stdout)
        self.assertIn("第九十条", result.stdout)

    def test_case_catalog_and_domain_search(self):
        catalog = load_case_catalog()
        self.assertEqual(len(catalog), 13)
        result = self.case_cli("--domain", "劳动")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GC179", result.stdout)
        self.assertIn("GC180", result.stdout)
        self.assertIn("GC184", result.stdout)
        resolution = self.case_cli("--keyword", "出资期限", "--keyword", "多数决")
        self.assertEqual(resolution.returncode, 0, resolution.stderr)
        self.assertIn("GC400542", resolution.stdout)

    def test_case_search_uses_decisive_facts(self):
        result = self.case_cli("--keyword", "事故认定书", "--keyword", "因果关系")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GC269", result.stdout)
        self.assertIn("仅用于本地检索排序", result.stdout)

    def test_case_search_rejects_missing_or_unknown_query(self):
        self.assertNotEqual(self.case_cli().returncode, 0)
        self.assertNotEqual(self.case_cli("--id", "GC999999").returncode, 0)

    def test_case_path_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            card_text("../outside.md")


if __name__ == "__main__":
    unittest.main()
