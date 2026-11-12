import argparse
from pathlib import Path
from backend.backup import restore_backup

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='将本程序导出的备份恢复到新目录，不覆盖原有数据')
    p.add_argument('archive', type=Path)
    p.add_argument('--target', required=True, type=Path)
    args = p.parse_args()
    try:
        restored = restore_backup(args.archive, args.target)
        print(f'备份已恢复到：{restored}')
        print('可使用 run.py --data-dir 指定这个新目录，先检查后再决定是否替换原数据。')
    except Exception as e:
        p.exit(1, f'未完成恢复：{e}\n')
