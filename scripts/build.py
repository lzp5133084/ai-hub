# -*- coding: utf-8 -*-
"""把 data/local.json + data/remote.json 合成 data/report.json，
再套用 template.html 渲染出 index.html（数据内嵌，支持 file:// 直接打开）

用法：
    python scripts/build.py                 # 生成 index.html（脱敏）
    python scripts/build.py --full          # 生成含完整密钥的版本
    python scripts/build.py --full --out local-report.html
"""
import os, sys, json, datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
TPL = os.path.join(ROOT, 'template.html')


def load(name, default):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return default


def main():
    args = sys.argv[1:]
    out = None
    if '--out' in args:
        out = args[args.index('--out') + 1]
    remote_name = os.environ.get('AIHUB_REMOTE_FILE') or 'remote.json'
    local = load('local.json', {})
    remote = load(remote_name, {})

    report = {
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'local_generated_at': local.get('generated_at', ''),
        'remote_generated_at': remote.get('generated_at', ''),
        'host': local.get('host', ''),
        'local': local,
        'remote': remote,
        'source': 'local_path'
    }
    if not os.path.isdir(DATA):
        os.makedirs(DATA)
    with open(os.path.join(DATA, 'report.json' if remote_name == 'remote.json' else 'report_local.json'),
              'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(TPL, encoding='utf-8') as f:
        tpl = f.read()
    blob = json.dumps(report, ensure_ascii=False).replace('</', '<\\/')
    html = tpl.replace('__REPORT_DATA__', blob)
    target = out or os.path.join(ROOT, 'index.html')
    with open(target, 'w', encoding='utf-8') as f:
        f.write(html)
    size = os.path.getsize(target)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(target)).strftime('%Y-%m-%d %H:%M:%S')
    with open(target, encoding='utf-8') as f:
        html = f.read()
    html = (html.replace('__PAGE_SIZE__', '%.1f KB' % (size / 1024.0))
                .replace('__PAGE_MTIME__', mtime))
    with open(target, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[build] -> %s (%d bytes)' % (target, size))


if __name__ == '__main__':
    main()
