#!/usr/bin/env python3
"""Create a private, structured matter workspace outside the Skill repository."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


SECTIONS = (
    "目标与委托边界",
    "紧急事项与不可逆风险",
    "当事人与程序地位",
    "事实时间线",
    "请求、抗辩与法律后果",
    "争点树",
    "要件—事实—证据矩阵",
    "证据来源、完整性与矛盾表",
    "法律依据与版本核验",
    "程序、期限与送达",
    "对方最强论点与反证",
    "保全、和解与执行地图",
    "庭审及询问计划",
    "风险、缺口与行动计划",
)


def enclosing_git_repo(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def create_workspace(output: Path, title: str, allow_git_repo: bool = False) -> tuple[Path, Path]:
    output = output.resolve()
    git_repo = enclosing_git_repo(output)
    if git_repo and not allow_git_repo:
        raise SystemExit(
            f"拒绝在 Git 仓库内创建案件工作台：{git_repo}\n"
            "请改用仓库外的私有目录；确有需要时显式传入 --allow-git-repo。"
        )
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"拒绝覆盖非空目录：{output}")
    output.mkdir(parents=True, exist_ok=True)
    created = date.today().isoformat()
    model = {
        "schemaVersion": 2,
        "title": title,
        "createdAt": created,
        "confidentiality": "用户工作区；默认不得提交到公开仓库",
        "asOf": None,
        "goals": [],
        "urgentRisks": [],
        "proceduralPosture": None,
        "parties": [],
        "facts": [],
        "claimsAndDefenses": [],
        "issues": [],
        "evidence": [],
        "contradictions": [],
        "authorities": [],
        "deadlines": [],
        "preservationAndExecution": [],
        "settlement": [],
        "hearingPlan": [],
        "risks": [],
        "actions": [],
        "openQuestions": [],
    }
    json_path = output / "matter.json"
    json_path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# {title}",
        "",
        f"> 建立日期：{created}",
        "> 保密提示：本目录用于用户工作区，默认不得提交到公开仓库。录入前对身份证号、联系方式等非必要信息脱敏。",
        "> 时间提示：任何期限结论都要记录起算事件、送达方式、收到日期、适用规则、节假日处理和核验日期。",
        "",
    ]
    for section in SECTIONS:
        lines.extend([f"## {section}", "", "- 待填写", ""])
    lines.extend(
        [
            "## 核心矩阵模板",
            "",
            "| 争点/要件 | 我方事实 | 对方事实 | 现有证据 | 证据缺口 | 举证责任 | 法律依据及版本 | 可信度 | 下一步 |",
            "|---|---|---|---|---|---|---|---|---|",
            "| 待填写 |  |  |  |  |  |  |  |  |",
            "",
            "## 期限核验模板",
            "",
            "| 事项 | 起算事件 | 送达/收到日期 | 法定期间 | 工作日/自然日 | 届满处理 | 依据 | 复核人/时间 |",
            "|---|---|---|---|---|---|---|---|",
            "| 待填写 |  |  |  |  |  |  |  |",
            "",
            "## 证据台账模板",
            "",
            "| 编号 | 原文件/原件状态 | 来源与取得方式 | 形成时间 | 拟证明事实 | 完整性 | 对方异议 | 补强/保全动作 | 提交状态 |",
            "|---|---|---|---|---|---|---|---|---|",
            "| E01 |  |  |  |  |  |  |  |  |",
            "",
            "## 矛盾核查模板",
            "",
            "| 编号 | 命题 | 支持材料 | 冲突材料 | 是否影响核心要件 | 解释与验证动作 |",
            "|---|---|---|---|---|---|",
            "| C01 |  |  |  |  |  |",
            "",
        ]
    )
    md_path = output / "matter.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="新建结构化案件工作区")
    parser.add_argument("--output", type=Path, required=True, help="新目录或空目录")
    parser.add_argument("--title", default="未命名案件", help="案件或项目名称")
    parser.add_argument("--allow-git-repo", action="store_true", help="明确允许写入 Git 仓库（可能泄露案件材料）")
    args = parser.parse_args()
    md_path, json_path = create_workspace(
        args.output, args.title.strip() or "未命名案件", allow_git_repo=args.allow_git_repo
    )
    print(f"已创建：{md_path}")
    print(f"已创建：{json_path}")


if __name__ == "__main__":
    main()
