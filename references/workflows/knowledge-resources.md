# 知识库与维护工具

用于查找资源、维护和校验；普通咨询不必通读。数量以结构校验脚本输出为准。

- [法律目录](../law-catalog.json)：当前快照为23部法律、48部司法解释、1部行政法规和3部部门规章；以后以结构校验脚本输出为准。
- [统一索引](../law-index.json)：当前快照为6,639条可定位记录；以后以结构校验脚本输出为准。
- [来源清单](../source-manifest.json)：公开来源、下载日期与文件哈希。
- `references/民法典/`、`references/法律法规/`、`references/行政法规/`、`references/部门规章/`、`references/司法解释/`：结构化原文。
- `references/cases/`：官方来源核验的案例学习卡，不是完整案卷。
- `references/experience/`：案件原型、常见失败模式和案例经验迁移方法。
- `references/practice/`：案件体检、证据工程、庭审、和解执行、上诉复盘和高风险案件控制。
- `references/commercial/`：合同履行、公司股权、授权印章、担保融资、损失核算、保全破产和商事仲裁专项流程。
- 商事全景专项：统一覆盖合同、融资担保、公司诉讼、金融证券、票据保险、竞争数据、破产清算和涉外商事；权威来源登记册明确法源层级、核验状态和使用边界。
- 公司控制权专项：决议三种救济、逐项票权及门槛、代持内外效力、诉讼代表冲突、证照保管与证据保存、已登记后的程序协同；[来源卡](../commercial/control-sources.md)记录在线核验及访问缺口。
- `references/常用法律文书/`：备忘录、证据目录和案件时间线模板。
- `scripts/search_law.py`：确定性检索。
- `scripts/search_commercial_authorities.py`：按专题、效力状态和关键词检索商事权威来源登记册。
- `scripts/search_cases.py`：按编号、法域、标签和关键词检索案例卡。
- `scripts/audit_matter.py`：检查案件工作台的结构错误和准备缺口，不输出胜诉分数。
- `scripts/audit_reasoning.py`：由工作台审计调用，检查可选推理记录的引用完整性，不判断法律结论正确性。
- `scripts/audit_sources.py`：来源元数据审计；加 `--online` 可检查网址可达性。
- `scripts/validate_knowledge_base.py`：目录、索引、原文和关键版本一致性检查。
- `evals/` 与 `tests/`：行为评估和回归测试。
