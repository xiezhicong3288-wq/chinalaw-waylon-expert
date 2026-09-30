"""Compare explicit local release states; never infers a push, merge, or installation."""
import argparse
import json
from pathlib import Path
from release_guard import inventory, tree_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--pr-tree', type=Path)
    parser.add_argument('--main-tree', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Private report outside all compared roots')
    args = parser.parse_args()
    roots = {k: v.resolve() for k, v in {'candidate': args.candidate, 'installed': args.installed, 'pr': args.pr_tree, 'main': args.main_tree}.items() if v is not None}
    output = args.output.resolve()
    if any(output.is_relative_to(root) for root in roots.values()):
        parser.error('状态报告必须保存在比较目录之外的私人位置')
    states = {}
    for name, root in roots.items():
        if not root.is_dir():
            parser.error(f'{name}目录不存在')
        files = inventory(root)
        states[name] = {'treeSha256': tree_hash(files), 'files': len(files)}
    for name in ('candidate', 'installed', 'pr', 'main'):
        states.setdefault(name, {'status': 'not_read'})
    report = {'states': states, 'installedMatchesCandidate': states['installed']['treeSha256'] == states['candidate']['treeSha256'],
              'scope': 'Local byte-content snapshots; remote refs must be read and recorded separately.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
