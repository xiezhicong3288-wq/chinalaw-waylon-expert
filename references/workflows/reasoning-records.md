# 可选推理关联审计

深度案件可在schemaVersion 2的matter.json增加reasoning数组；旧文件无需迁移，新建工作台默认提供空数组。目的在于发现不存在的引用、重复编号及尚无证据联系的结论，不判断真实性、现行性、举证责任或胜诉。

每个关联记录引用已有issues、facts、evidence、authorities条目的id。authorities被引用时应有唯一编号（建议L01）、法律名称、条文、版本、官方网址或本地路径及核验状态；这些法源内容须人工检查，工具只验证编号。

```json
{
  "id": "R01",
  "issueId": "I01",
  "kind": "mixed",
  "factIds": ["F01"],
  "evidenceIds": ["E01"],
  "opposingEvidenceIds": ["E02"],
  "authorityIds": ["L01"],
  "burdenOn": "主张给付方；具体分配待核验",
  "standard": "待核验具体命题及特殊规则",
  "conclusionStatus": "conditional",
  "conclusion": "若交付事实经原件及反证核对成立，再评价给付义务"
}
```

这是单个记录示意，需要放入完整工作台的reasoning数组，且先有相应引用条目。kind使用fact、law或mixed；conclusionStatus使用supported、conditional、disputed或insufficient。空引用数组允许表达尚缺资料，不能为让审计通过而补造证据。

运行 `python scripts/audit_matter.py --input <matter.json>`：退出码2表示结构/引用错误，1表示准备缺口，0仅表示没有预设结构缺口。纯法律问题不因没有证据被误判为错误；事实性结论已标supported但没有事实或证据关联时提示补查。空反证列表不意味着已充分调查反方材料。单纯引用存在不表示结论获得证明。
