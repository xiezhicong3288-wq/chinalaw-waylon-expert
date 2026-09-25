#!/usr/bin/env python3
"""Audit a matter.json workspace for structural and preparation gaps.

This tool reports missing work; it does not predict outcomes or provide a legal score.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_FIELDS = {
    "schemaVersion", "title", "createdAt", "confidentiality", "asOf", "goals",
    "urgentRisks", "proceduralPosture", "parties", "facts", "claimsAndDefenses",
    "issues", "evidence", "contradictions", "authorities", "deadlines",
    "preservationAndExecution", "settlement", "hearingPlan", "risks", "actions",
    "openQuestions",
}

ITEM_REQUIRED_KEYS = {
    "facts": {"id", "statement", "source", "status"},
    "issues": {"id", "question", "elements"},
    "evidence": {"id", "name", "source", "originalStatus", "proves", "completeness"},
    "contradictions": {"id", "proposition", "support", "conflict", "impact"},
    "deadlines": {"id", "event", "eventDate", "rule", "status"},
    "actions": {"id", "action", "priority", "status"},
}


def read_matter(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"案件文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"案件文件不是有效JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("案件文件顶层必须是对象")
    return data


def audit(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    gaps: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(data))
    if missing:
        errors.append("缺少结构字段：" + "、".join(missing))
        return errors, gaps
    if data["schemaVersion"] != 2:
        errors.append("schemaVersion必须为2")
    if not isinstance(data["title"], str) or not data["title"].strip():
        errors.append("title不能为空")

    list_fields = REQUIRED_FIELDS - {
        "schemaVersion", "title", "createdAt", "confidentiality", "asOf", "proceduralPosture"
    }
    for field in sorted(list_fields):
        if not isinstance(data[field], list):
            errors.append(f"{field}必须是数组")

    if errors:
        return errors, gaps

    checks = (
        ("goals", "尚未写明希望实现的具体结果"),
        ("parties", "尚未核对当事人、程序地位和责任主体"),
        ("facts", "尚未建立带来源的事实时间线"),
        ("claimsAndDefenses", "尚未列出主位/备位请求和对方抗辩"),
        ("issues", "尚未把请求拆成法律要件和争点"),
        ("evidence", "尚未建立证据来源、原件、完整性和证明目的台账"),
        ("urgentRisks", "尚未评估期限、证据灭失、资产转移或人身等紧急风险"),
        ("contradictions", "尚未完成支持材料与冲突材料的矛盾审计"),
        ("authorities", "尚未记录法律依据、版本和核验状态"),
        ("deadlines", "尚未完成送达、起算事件和期限核查"),
        ("preservationAndExecution", "尚未评估保全、财产线索和实际执行路径"),
        ("settlement", "尚未记录和解是否适用及其履约保障评估"),
        ("hearingPlan", "尚未记录庭审或听证是否适用及准备状态"),
        ("risks", "尚未记录不利事实、程序和执行风险"),
        ("actions", "尚未形成按紧迫性排序的行动计划"),
    )
    for field, message in checks:
        if not data[field]:
            gaps.append(message)
    if data["asOf"] is None:
        gaps.append("尚未设置分析基准日期asOf")
    if data["proceduralPosture"] is None:
        gaps.append("尚未确定当前程序阶段proceduralPosture")

    id_specs = {
        "facts": r"F\d+", "issues": r"I\d+", "evidence": r"E\d+",
        "contradictions": r"C\d+", "deadlines": r"D\d+", "actions": r"A\d+",
    }
    for field, pattern in id_specs.items():
        values = data[field]
        ids = [item.get("id") for item in values if isinstance(item, dict)]
        if len(ids) != len(values):
            errors.append(f"{field}中的每项必须是带id的对象")
        elif any(not isinstance(value, str) or not re.fullmatch(pattern, value) for value in ids):
            errors.append(f"{field}的id格式无效")
        elif len(ids) != len(set(ids)):
            errors.append(f"{field}存在重复id")
        for index, item in enumerate(values, start=1):
            if isinstance(item, dict):
                missing_keys = sorted(ITEM_REQUIRED_KEYS[field] - set(item))
                if missing_keys:
                    errors.append(f"{field}第{index}项缺少字段：{'、'.join(missing_keys)}")
                empty_keys = sorted(
                    key for key in ITEM_REQUIRED_KEYS[field] & set(item)
                    if item[key] is None or item[key] == "" or item[key] == []
                )
                if empty_keys:
                    errors.append(f"{field}第{index}项字段为空：{'、'.join(empty_keys)}")
    return errors, gaps


def render(errors: list[str], gaps: list[str]) -> str:
    lines = ["案件工作台审计（仅检查结构与准备缺口，不预测结果）"]
    if errors:
        lines.append("\n结构错误：")
        lines.extend(f"- {item}" for item in errors)
    if gaps:
        lines.append("\n待补工作：")
        lines.extend(f"- {item}" for item in gaps)
    if not errors and not gaps:
        lines.append("\n未发现预设结构缺口；仍需人工核对材料真实性、法律适用和策略判断。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="审计matter.json的结构和办案准备缺口")
    parser.add_argument("--input", type=Path, required=True, help="matter.json路径")
    args = parser.parse_args()
    errors, gaps = audit(read_matter(args.input))
    print(render(errors, gaps))
    raise SystemExit(2 if errors else (1 if gaps else 0))


if __name__ == "__main__":
    main()
