"""Optional reference-integrity checks; never grades the merits of a case."""

from collections import Counter


def audit_reasoning(data: dict) -> tuple[list[str], list[str]]:
    errors, gaps = [], []
    if "reasoning" not in data:  # Existing schemaVersion 2 files remain supported.
        return errors, gaps
    rows = data["reasoning"]
    if not isinstance(rows, list):
        return ["reasoning必须是数组"], gaps
    if not rows:
        return errors, ["尚未记录结论与争点、事实、证据及法源的关联"]
    targets = {}
    for field in ("issues", "facts", "evidence", "authorities"):
        values = data.get(field, [])
        if not isinstance(values, list):
            errors.append(f"关联目标{field}必须是数组")
            values = []
        targets[field] = Counter(
            item["id"] for item in values
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
    ids = set()
    for number, row in enumerate(rows, 1):
        label = f"reasoning第{number}项"
        if not isinstance(row, dict):
            errors.append(f"{label}必须是对象")
            continue
        required = {"id", "issueId", "kind", "factIds", "evidenceIds", "opposingEvidenceIds",
                    "authorityIds", "burdenOn", "standard", "conclusionStatus", "conclusion"}
        missing = required - row.keys()
        if missing:
            errors.append(f"{label}缺少字段：{'、'.join(sorted(missing))}")
        for key in ("id", "issueId", "burdenOn", "standard", "conclusion"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"{label}.{key}必须是非空字符串")
        rid = row.get("id")
        if isinstance(rid, str):
            if rid in ids:
                errors.append(f"{label}重复id：{rid}")
            ids.add(rid)
        if row.get("kind") not in ("fact", "law", "mixed"):
            errors.append(f"{label}.kind无效")
        if row.get("conclusionStatus") not in ("supported", "conditional", "disputed", "insufficient"):
            errors.append(f"{label}.conclusionStatus无效")
        for key, target in (("factIds", "facts"), ("evidenceIds", "evidence"),
                            ("opposingEvidenceIds", "evidence"), ("authorityIds", "authorities")):
            refs = row.get(key)
            if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                errors.append(f"{label}.{key}必须是非空字符串组成的数组（可空数组）")
                continue
            if len(refs) != len(set(refs)):
                errors.append(f"{label}.{key}存在重复引用")
            for ref in refs:
                count = targets[target][ref]
                if count != 1:
                    errors.append(f"{label}.{key}引用{ref}无法唯一定位（{count}项）")
        issue = row.get("issueId")
        if isinstance(issue, str) and targets["issues"][issue] != 1:
            errors.append(f"{label}.issueId引用{issue}无法唯一定位")
        if row.get("conclusionStatus") == "supported" and row.get("kind") in ("fact", "mixed"):
            if any(str(row.get(key, '')).strip().lower() in {'待核', '待确认', 'unknown', 'pending', 'tbd'} for key in ('burdenOn', 'standard')):
                gaps.append(f"{label}标为supported但举证责任或证明标准尚待核；应补核或降低结论状态")
            if not row.get("factIds") or not row.get("evidenceIds"):
                gaps.append(f"{label}事实性结论标为supported但事实或证据关联为空")
        if row.get("kind") in ("law", "mixed") and not row.get("authorityIds"):
            gaps.append(f"{label}法律性结论尚无法源关联")
    return errors, gaps
