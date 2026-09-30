"""Fail closed on unlisted files; pattern checks supplement human publication review."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

MANIFEST = 'release-files.json'
IGNORED = {'.git', '.cache', '__pycache__'}
BLOCKED = {'outputs', 'work', 'private', 'logs', '.env', '.ssh', '.aws'}
PATTERNS = {
    'local-user-path': re.compile(r'[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\s<>]+', re.I),
    'credential': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'email': re.compile(r'[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})'),
}


def inventory(root: Path) -> dict[str, Path]:
    root = root.resolve()
    found = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs) + files:
            path = Path(directory) / name
            # Reject redirected paths even if their names would otherwise be ignored.
            if path.is_symlink() or path.is_junction():
                raise ValueError('发布目录含链接或联接，须先移除重定向')
        dirs[:] = [name for name in dirs if name not in IGNORED]
        for name in files:
            if name in IGNORED:
                continue
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            found[relative] = path
    return found


def approved_files(root: Path) -> dict[str, Path]:
    try:
        raw = json.loads((root / MANIFEST).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError('缺少或无法解析发布文件清单') from exc
    names = raw.get('files') if isinstance(raw, dict) else None
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names):
        raise ValueError('发布清单files必须为非空路径数组')
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError('发布清单存在重复或大小写冲突路径')
    for name in names:
        p = PurePosixPath(name)
        if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or p.as_posix() != name:
            raise ValueError('发布清单含非规范相对路径')
        if any(part.lower() in BLOCKED or part.lower().startswith('.env.') for part in p.parts):
            raise ValueError('发布清单含私人或凭证目录/文件')
    actual = inventory(root)
    if set(actual) != set(names):
        raise ValueError(f'发布清单与目录不一致：未列入{len(set(actual)-set(names))}项，缺少{len(set(names)-set(actual))}项；须人工审阅差异')
    if MANIFEST not in actual or 'SKILL.md' not in actual:
        raise ValueError('发布清单必须包含自身和SKILL.md')
    return actual


def findings(files: dict[str, Path]) -> list[dict]:
    result = []
    for name, path in files.items():
        try:
            body = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            result.append({'file': name, 'rule': 'binary-needs-separate-review'})
            continue
        for rule, pattern in PATTERNS.items():
            for match in pattern.finditer(body):
                if rule == 'email':
                    domain = match.group(1).lower()
                    if domain.endswith(('.gov.cn', '.court.gov.cn', '.spp.gov.cn')) or domain == 'users.noreply.github.com':
                        continue
                result.append({'file': name, 'line': body.count('\n', 0, match.start()) + 1, 'rule': rule})
    return result


def tree_hash(files: dict[str, Path]) -> str:
    rows = [(name, hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in sorted(files.items())]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def check(root: Path) -> dict[str, Path]:
    files = approved_files(root)
    issues = findings(files)
    if issues:
        raise ValueError(f'发布内容审查发现{len(issues)}项待处理；运行release_guard查看位置，不应公开审计原文')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    try:
        files = approved_files(args.source.resolve())
        issues = findings(files)
        print(json.dumps({'files': len(files), 'treeSha256': tree_hash(files), 'findings': issues,
                         'scope': 'file list and patterns only; human content/metadata review required'}, ensure_ascii=False, indent=2))
        return 1 if issues else 0
    except (ValueError, OSError) as exc:
        print(str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
