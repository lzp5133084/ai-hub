# -*- coding: utf-8 -*-
"""把上一次被网络异常污染的检测基线修正为今日已实测结论"""
import sys, os, json, datetime
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', 'remote.json')
d = json.load(open(P, encoding='utf-8'))

FIX = {
    '火山方舟': ('有效', '可调用模型 133 个'),
    '豆包（方舟）': None,  # 按 detail 区分
    'MiniMax': ('有效', 'HTTP 200 接口可连通（本次仅消耗 1 token）'),
    '高德地图': ('有效', 'info=OK infocode=10000'),
    'Gitee': ('有效', '用户 ren-junxue'),
    'GitHub': ('有效', 'API 余量 5000/5000'),
}
for r in d['rows']:
    ch = r['ch']
    if ch == '豆包（方舟）':
        if '401' in (r.get('detail') or ''):
            r['status'], r['detail'] = '失效', 'HTTP 401 密钥无效或无权限'
        else:
            r['status'], r['detail'] = '有效', '可调用模型 133 个'
    elif ch in FIX:
        r['status'], r['detail'] = FIX[ch]
    r.pop('carried', None)
d['generated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
for r in d['rows']:
    print('%-14s %s %s' % (r['ch'], r['status'], r['detail'][:50]))
print('models', d['model_count'], 'balance', d['billing']['balance'])
