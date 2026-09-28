#!/usr/bin/env python3
"""Compare subprocess retrieval time and output, without network dependencies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
QUERIES = [
    ['--law', '民法典', '--article', '577'],
    ['--law', '刑法', '--article', '133', '--suffix', '1'],
    ['--law', '民事证据规定', '--keyword', '电子数据'],
    ['--keyword', '电子送达'],
    ['--keyword', '举证责任', '--limit', '10'],
    ['--keyword', '不存在的检索词XYZ'],
    ['--keyword', '印章', '--limit', '200'],
]


def run(query: list[str]):
    start = time.perf_counter()
    result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/search_law.py'), *query],
                            capture_output=True, encoding='utf-8', timeout=120)
    return (time.perf_counter() - start) * 1000, (result.returncode, result.stdout, result.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=7)
    parser.add_argument('--json', action='store_true', help='输出JSON，便于保存比较')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs 必须为正整数')
    cold_ms, cold_output = run([*QUERIES[0], '--rebuild-cache'])
    _, expected = run([*QUERIES[0], '--no-cache'])
    if cold_output != expected or cold_output[0] != 0 or cold_output[2]:
        raise SystemExit('缓存重建或结果一致性检查失败：' + cold_output[2])
    rows = []
    for query in QUERIES:
        durations = {'direct': [], 'cached': []}
        for iteration in range(args.runs):
            outputs = {}
            # Alternate order to reduce warm filesystem / process-order bias.
            modes = ('direct', 'cached') if iteration % 2 == 0 else ('cached', 'direct')
            for mode in modes:
                elapsed, output = run(query + (['--no-cache'] if mode == 'direct' else []))
                durations[mode].append(elapsed)
                outputs[mode] = output
            if outputs['direct'] != outputs['cached']:
                raise SystemExit('缓存与原始检索结果不一致：' + ' '.join(query))
        direct, cached = (statistics.median(durations[mode]) for mode in ('direct', 'cached'))
        rows.append(dict(query=query, direct_ms=round(direct, 2), cached_ms=round(cached, 2),
                         reduction_percent=round((1 - cached / direct) * 100, 1), identical=True))
    report = dict(runs=args.runs, python=sys.version, rebuild_ms=round(cold_ms, 2), queries=rows,
                  note='独立Python进程的本地检索耗时；不代表AI回答速度。')
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'首次强制重建并查询：{cold_ms:.2f} ms；每组 {args.runs} 次中位数')
        for row in rows:
            print(f"{row['direct_ms']:8.2f} -> {row['cached_ms']:8.2f} ms "
                  f"({row['reduction_percent']:+.1f}% 缩短) | {' '.join(row['query'])}")
        print(report['note'])


if __name__ == '__main__':
    main()
