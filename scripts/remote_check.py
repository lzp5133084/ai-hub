# -*- coding: utf-8 -*-
"""在线 API 可用性 + 火山账户余额账单检测

密钥来源优先级：
  1) config/keys.local.json  （本地私密文件，已 gitignore）
  2) 环境变量 AIHUB_KEYS_JSON（GitHub Actions 可用 secrets 注入）

结果写入 data/remote.json。默认只输出脱敏密钥，
设置环境变量 AIHUB_FULL_KEYS=1 才写入完整密钥。
"""
import os, sys, json, ssl, hmac, hashlib, datetime, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
KEYS_FILE = os.path.join(ROOT, 'config', 'keys.local.json')
TIMEOUT = 15
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIHub-Checker/1.0'

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# 多链路重试：先走本机代理，再试直连，最后尝试 TUN/DNS 兜底
PROXY = os.environ.get('AIHUB_PROXY') or 'http://127.0.0.1:7897'
os.environ.setdefault('no_proxy', '')

OPENERS = [
    urllib.request.build_opener(urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY}),
                                urllib.request.HTTPSHandler(context=CTX)),
    urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                urllib.request.HTTPSHandler(context=CTX)),
]


def mask(k):
    if not k or len(k) < 14:
        return k
    return k[:10] + '········' + k[-6:]


MAXREAD = 4000000


def _open(op, url, body, timeout=TIMEOUT):
    with op.open(url, body, timeout=timeout) as r:
        return r.status, r.read(MAXREAD).decode('utf-8', 'ignore')


def http(method, url, headers=None, data=None, timeout=TIMEOUT):
    body = data.encode('utf-8') if isinstance(data, str) else data
    last = 'no-opener'
    for op in OPENERS:
        try:
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header('User-Agent', UA)
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            return _open(op, req, None, timeout)
        except urllib.error.HTTPError as e:
            raw = ''
            try:
                raw = e.read(1500).decode('utf-8', 'ignore')
            except Exception:
                pass
            if e.code in (401, 403, 404, 429):
                return e.code, raw
            last = 'HTTP %s %s' % (e.code, raw[:120])
        except Exception as e:
            last = '%s %s' % (type(e).__name__, str(e)[:110])
    return 0, last


def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, encoding='utf-8') as f:
            return json.load(f)
    raw = os.environ.get('AIHUB_KEYS_JSON')
    if raw:
        return json.loads(raw)
    return None


def fetch_ark_models(key, timeout=25):
    """分页拉取方舟可用模型，返回 (状态, 说明, 模型ID列表)"""
    base = 'https://ark.cn-beijing.volces.com/api/v3/models'
    models, cursor, st_last = [], '', 0
    for _ in range(12):
        url = base + '?limit=100' + (('&after=' + urllib.parse.quote(cursor)) if cursor else '')
        st, body = http('GET', url, {'Authorization': 'Bearer ' + key}, timeout=timeout)
        st_last = st
        if st != 200:
            break
        try:
            j = json.loads(body)
        except Exception:
            break
        page = [m.get('id') for m in j.get('data', []) if m.get('id')]
        models += page
        if not j.get('has_more') or not j.get('last_id') or not page:
            break
        if j.get('last_id') == cursor:
            break
        cursor = j['last_id']
    return st_last, models


def check_ark(key):
    st, models = fetch_ark_models(key)
    if st == 200:
        return '有效', '可调用模型 %d 个' % len(models), models
    if st in (401, 403):
        return '失效', 'HTTP %d 密钥无效或无权限' % st, models
    return '未验证', 'HTTP %d' % st, models
    if st == 200:
        return '有效', '可调用模型 %d 个' % len(models), models
    if st in (401, 403):
        return '失效', 'HTTP %d %s' % (st, body[:150]), models
    return '未验证', 'HTTP %d %s' % (st, body[:150]), models


def check_minimax(key):
    payload = json.dumps({'model': 'MiniMax-Text-01',
                          'messages': [{'role': 'user', 'content': 'hi'}],
                          'max_tokens': 1})
    st, body = http('POST', 'https://api.minimax.chat/v1/text/chatcompletion_v2',
                    {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, payload)
    if st in (200, 400):
        return '有效', 'HTTP %d 接口可连通（本次仅消耗 1 token）' % st, []
    if st in (401, 403):
        return '失效', 'HTTP %d %s' % (st, body[:150]), []
    return '未验证', 'HTTP %d %s' % (st, body[:150]), []


def check_amap(key):
    st, body = http('GET', 'https://restapi.amap.com/v3/ip?key=%s&ip=114.247.50.2' % urllib.parse.quote(key))
    if st == 200 and 'INVALID_USER_KEY' not in body:
        try:
            j = json.loads(body)
            return '有效', 'info=%s infocode=%s' % (j.get('info'), j.get('infocode')), []
        except Exception:
            return '有效', body[:120], []
    return '失效', 'HTTP %d %s' % (st, body[:150]), []


def check_gitee(key):
    st, body = http('GET', 'https://gitee.com/api/v5/user?access_token=' + urllib.parse.quote(key))
    if st == 200:
        try:
            j = json.loads(body)
            return '有效', '用户 %s' % (j.get('login') or j.get('name') or ''), []
        except Exception:
            return '有效', body[:120], []
    return '失效', 'HTTP %d %s' % (st, body[:150]), []


def check_github(key):
    st, body = http('GET', 'https://api.github.com/rate_limit', {'Authorization': 'token ' + key})
    if st == 200:
        try:
            core = json.loads(body)['resources']['core']
            return '有效', 'API 余量 %s/%s' % (core.get('remaining'), core.get('limit')), []
        except Exception:
            return '有效', body[:120], []
    return '失效', 'HTTP %d %s' % (st, body[:150]), []


CHECKERS = {'ark': check_ark, 'minimax': check_minimax, 'amap': check_amap,
            'gitee': check_gitee, 'github': check_github}


def volc_call(ak, sk, action, version, payload, host='billing.volcengineapi.com', service='billing'):
    def hs(k, m):
        return hmac.new(k, m.encode('utf-8'), hashlib.sha256).digest()

    payload = json.dumps(payload, ensure_ascii=False)
    now = datetime.datetime.utcnow()
    x_date = now.strftime('%Y%m%dT%H%M%SZ')
    short = now.strftime('%Y%m%d')
    region = 'cn-beijing'
    query = 'Action=%s&Version=%s' % (action, version)
    ph = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    allh = {'host': host, 'x-date': x_date, 'x-content-sha256': ph, 'content-type': 'application/json'}
    names = sorted(allh)
    can_h = ''.join('%s:%s\n' % (n, allh[n]) for n in names)
    signed = ';'.join(names)
    can_req = 'POST\n/\n%s\n%s\n%s\n%s' % (query, can_h, signed, ph)
    scope = '%s/%s/%s/request' % (short, region, service)
    sts = 'HMAC-SHA256\n%s\n%s\n%s' % (x_date, scope, hashlib.sha256(can_req.encode('utf-8')).hexdigest())
    k = hs(sk.encode('utf-8'), short)
    k = hs(k, region)
    k = hs(k, service)
    k = hs(k, 'request')
    sig = hmac.new(k, sts.encode('utf-8'), hashlib.sha256).hexdigest()
    auth = 'HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (ak, scope, signed, sig)
    url = 'https://%s/?%s' % (host, query)
    req = urllib.request.Request(url, data=payload.encode('utf-8'), method='POST')
    req.add_header('Host', host)
    req.add_header('Content-Type', 'application/json')
    req.add_header('X-Date', x_date)
    req.add_header('X-Content-Sha256', ph)
    req.add_header('Authorization', auth)
    req.add_header('User-Agent', UA)
    last = 'no-opener'
    for op in OPENERS:
        try:
            with op.open(req, timeout=25) as r:
                return r.status, r.read(30000).decode('utf-8', 'ignore')
        except urllib.error.HTTPError as e:
            raw = ''
            try:
                raw = e.read(2000).decode('utf-8', 'ignore')
            except Exception:
                pass
            return e.code, raw
        except Exception as e:
            last = '%s %s' % (type(e).__name__, str(e)[:110])
    return 0, last


BILL_HOSTS = [('billing.volcengineapi.com', 'billing'),
              ('billing.cn-beijing.volcengineapi.com', 'billing'),
              ('open.volcengine.com', 'billing')]


def get_billing(ak, sk):
    info = {'balance': None, 'frozen': None, 'credit': None, 'months': [], 'error': ''}
    if not ak or not sk:
        info['error'] = '未提供 AK/SK'
        return info

    # 1) 余额：QueryBalanceAcct（多 host 兜底）
    for host, service in BILL_HOSTS:
        st, body = volc_call(ak, sk, 'QueryBalanceAcct', '2022-01-01', {}, host=host, service=service)
        try:
            j = json.loads(body)
            r = j.get('Result') or {}
            bal = r.get('AvailableBalance') or r.get('CashBalance') or r.get('AvailableAmount') or r.get('Balance')
            if bal is not None:
                info['balance'] = bal
                info['frozen'] = r.get('FreezeAmount')
                info['credit'] = r.get('CreditLimit')
                break
            err = (j.get('ResponseMetadata') or {}).get('Error')
            if err:
                info['error'] = json.dumps(err, ensure_ascii=False)[:200]
        except Exception:
            info['error'] = body[:200]

    # 2) 近四个月账单
    now = datetime.datetime.now()
    for i in range(4):
        period = (now - datetime.timedelta(days=30 * i)).strftime('%Y-%m')
        payload = {'BillPeriod': period}
        for host, service in BILL_HOSTS:
            st, body = volc_call(ak, sk, 'ListBillOverviewByCategory', '2022-01-01', payload,
                                 host=host, service=service)
            amt = None
            try:
                j = json.loads(body)
                lst = (j.get('Result') or {}).get('List') or []
                if lst:
                    inner = lst[0].get('List') or []
                    pay = [x for x in inner if x.get('BillCategoryParent') == '合计']
                    if pay:
                        amt = pay[0].get('PayableAmount')
            except Exception:
                pass
            if amt is not None:
                info['months'].append({'period': period, 'amount': amt, 'desc': '账单已出具'})
                break
        else:
            info['months'].append({'period': period, 'amount': '-', 'desc': '无消费或账单未出'})
    return info


def carry_prev(out, prev):
    """本次网络不通时，沿用上一次的有效结果，避免数据倒退"""
    if not prev:
        return out, 0
    n = 0
    prev_rows = {r.get('key_masked'): r for r in prev.get('rows', [])}
    for r in out['rows']:
        p = prev_rows.get(r.get('key_masked'))
        if r.get('status') == '未验证' and p and p.get('status') in ('有效', '失效'):
            r['status'] = p['status']
            r['detail'] = p.get('detail', '') + '（本次网络不可达，沿用上次结果）'
            r['carried'] = True
            n += 1
    if not out.get('models') and prev.get('models'):
        out['models'] = prev['models']
        out['model_count'] = prev.get('model_count', 0)
        n += 1
    if out['billing'].get('balance') is None and (prev.get('billing') or {}).get('balance') is not None:
        out['billing'] = prev['billing']
        out['billing']['error'] = (out['billing'].get('error', '') or '') + '（余额沿用上次结果）'
        n += 1
    return out, n


def categorize(models):
    cats = {}

    def put(c, m):
        cats.setdefault(c, [])
        cats[c].append(m)

    for m in models:
        n = m.lower()
        if n.startswith('doubao-seedream') or n.startswith('doubao-seededit'):
            put('图片生成 / 编辑', m)
        elif n.startswith('doubao-seedance') or n.startswith('wan2-') or n.startswith('doubao-seaweed'):
            put('视频生成', m)
        elif n.startswith('doubao-seed3d') or n.startswith('hitem3d') or n.startswith('hyper3d'):
            put('3D 生成', m)
        elif 'embedding' in n:
            put('向量 Embedding', m)
        elif 'character' in n:
            put('角色扮演 / 人设', m)
        elif 'functioncall' in n or 'code' in n:
            put('函数调用 / Agent / 代码', m)
        elif 'ui-tars' in n:
            put('UI 自动化操作', m)
        elif any(k in n for k in ('vision', 'vl', 'moondream')):
            put('视觉理解', m)
        else:
            put('文本对话 / 推理', m)
    for c in cats:
        cats[c].sort()
    return cats


def main():
    if not os.path.isdir(DATA):
        os.makedirs(DATA)
    cfg = load_keys()
    full = os.environ.get('AIHUB_FULL_KEYS') == '1'
    if not cfg:
        print('[remote_check] 未找到密钥配置，跳过在线检测（使用上一次结果）')
        return

    items = cfg.get('keys', [])
    rows = []
    all_models = []

    def work(it):
        fn = CHECKERS.get(it.get('type'))
        if not fn:
            return dict(it, status='未验证', detail='未知类型，未在云端核销', models=[])
        stt, detail, models = fn(it['key'])
        return dict(it, status=stt, detail=detail, models=models)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(work, items):
            rows.append(r)
            if r.get('models'):
                all_models = r['models'] if len(r['models']) > len(all_models) else all_models

    ak = cfg.get('volc_ak', '')
    sk = cfg.get('volc_sk', '')
    billing = get_billing(ak, sk)

    for r in rows:
        r.pop('models', None)
        k = r.get('key', '')
        r['key_masked'] = mask(k)
        r['key'] = k if full else mask(k)

    out = {
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'rows': rows,
        'models': categorize(all_models),
        'model_count': len(all_models),
        'billing': billing,
        'full_keys': full
    }
    outfile = os.environ.get('AIHUB_REMOTE_OUT') or os.path.join(DATA, 'remote.json')
    prev = None
    if os.path.exists(outfile):
        try:
            with open(outfile, encoding='utf-8') as f:
                prev = json.load(f)
        except Exception:
            prev = None
    out, carried = carry_prev(out, prev)
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('[remote_check] rows=%d models=%d balance=%s carried=%d' %
          (len(rows), len(all_models), billing.get('balance'), carried))


if __name__ == '__main__':
    main()
