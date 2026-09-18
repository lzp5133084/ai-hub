# -*- coding: utf-8 -*-
"""每日一键刷新：本地扫描 → 在线检测 → 生成报告 → 推送 GitHub

本机用时：会额外生成一份含完整密钥的 local-report.html（不上传 Git）
"""
import os, sys, json, subprocess, datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
HOME = os.path.expanduser('~')
TOKEN_CANDIDATES = [
    os.path.join(HOME, '.aihub', 'github_token'),
    os.path.join(ROOT, 'config', 'github_token'),
]
LOG = os.path.join(ROOT, 'logs')

PY = sys.executable


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    try:
        print(line)
    except Exception:
        pass
    try:
        if not os.path.isdir(LOG):
            os.makedirs(LOG)
        with open(os.path.join(LOG, 'run_daily.log'), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def run(args, env=None, cwd=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([PY] + args, cwd=cwd or ROOT, env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'ignore')
    if out.strip():
        log(out.strip().replace('\n', ' | ')[:400])
    return p.returncode


def read_token():
    for p in TOKEN_CANDIDATES:
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                t = f.read().strip()
                if t:
                    return t
    return os.environ.get('GITHUB_TOKEN', '')


def push():
    token = read_token()
    if not token:
        log('未找到 GitHub token，跳过推送（可放于 %s）' % TOKEN_CANDIDATES[0])
        return 1
    p = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, stdout=subprocess.PIPE)
    changed = [x for x in p.stdout.decode('utf-8', 'ignore').splitlines() if x.strip()]
    if not changed:
        log('无文件变化，无需提交')
        return 0
    subprocess.run(['git', 'add', 'data', 'index.html'], cwd=ROOT, stdout=subprocess.PIPE)
    msg = 'chore: daily refresh %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    subprocess.run(['git', 'commit', '-m', msg], cwd=ROOT, stdout=subprocess.PIPE)
    p = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, stdout=subprocess.PIPE)
    remote = p.stdout.decode('utf-8', 'ignore').strip()
    if remote.startswith('https://github.com/') and '@' not in remote:
        repo = remote.replace('https://github.com/', '')
        auth = 'https://x-access-token:%s@github.com/%s' % (token, repo)
        rc = subprocess.run(['git', 'push', auth, 'HEAD'], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = rc.stdout.decode('utf-8', 'ignore')
        log('推送成功' if rc.returncode == 0 else '推送失败: ' + out[:200])
        return rc.returncode
    log('远端地址异常：%s' % remote)
    return 1


def main():
    log('=== 开始每日检测 ===')
    run([os.path.join(SCRIPTS, 'local_scan.py')])
    run([os.path.join(SCRIPTS, 'remote_check.py')])          # 脱敏结果 → data/remote.json
    run([os.path.join(SCRIPTS, 'build.py')])                 # → index.html（脱敏版，用于发布）

    env_full = {'AIHUB_FULL_KEYS': '1',
                'AIHUB_REMOTE_OUT': os.path.join(ROOT, 'data', 'remote_full.json')}
    run([os.path.join(SCRIPTS, 'remote_check.py')], env=env_full)
    run([os.path.join(SCRIPTS, 'build.py'), '--full', '--out',
         os.path.join(ROOT, 'local-report.html')],
        env={'AIHUB_REMOTE_FILE': 'remote_full.json'})

    push()
    log('=== 完成 ===')


if __name__ == '__main__':
    main()
