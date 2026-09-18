# -*- coding: utf-8 -*-
"""本地模型 / 本地 AI 应用 / 本地服务探测

仅使用标准库，无第三方依赖。结果写入 data/local.json
"""
import os, sys, json, socket, ssl, urllib.request, urllib.error
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HOME = os.path.expanduser('~')
TOOLS = r'D:\ai-tools'

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def http_json(url, timeout=4):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, json.loads(r.read(300000).decode('utf-8', 'ignore'))
    except Exception as e:
        return 0, {'err': '%s %s' % (type(e).__name__, str(e)[:110])}


def port_open(port, host='127.0.0.1', timeout=0.6):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def fsize_gb(path):
    try:
        return round(os.path.getsize(path) / 1024.0 / 1024 / 1024, 2)
    except Exception:
        return 0


def first_exist(*paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return ''


def ability_of(name):
    n = (name or '').lower()
    if any(k in n for k in ('vl', 'llava', 'moondream', 'vision')):
        return '视觉理解（图文对话）'
    if 'embed' in n:
        return '向量 Embedding'
    if any(k in n for k in ('code', 'coder')):
        return '代码生成'
    return '文本对话 / 推理'


def status_of(alive, installed):
    if alive:
        return '运行中'
    return '已安装未启动' if installed else '未检测到'


# ---------------- 1. Ollama ----------------
def scan_ollama():
    exe = first_exist(os.path.join(HOME, 'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'))
    model_dir = first_exist(os.path.join(HOME, '.ollama', 'models'))
    alive = port_open(11434)
    svc = {
        'name': 'Ollama',
        'category': '本地大模型服务',
        'version': '',
        'location': exe or '未找到 ollama.exe',
        'data': model_dir,
        'endpoint': 'http://127.0.0.1:11434',
        'api_base': 'http://127.0.0.1:11434/v1（OpenAI 兼容）',
        'status': status_of(alive, bool(exe)),
        'capability': '本地大模型推理：对话 / 补全 / 向量 Embedding / 多模态视觉 / OpenAI 兼容接口',
        'invoke': 'ollama run <模型>   或   POST http://127.0.0.1:11434/api/chat',
        'note': '默认端口 11434；提供 /api/chat、/api/generate、/api/embeddings、/v1/* 四类接口'
    }
    models, running = [], []
    if alive:
        _, tags = http_json('http://127.0.0.1:11434/api/tags')
        for m in (tags.get('models') or []):
            d = m.get('details') or {}
            models.append({
                'name': m.get('name'),
                'family': d.get('family', ''),
                'params': d.get('parameter_size', ''),
                'quant': d.get('quantization_level', ''),
                'size_gb': round((m.get('size') or 0) / 1024.0 ** 3, 2),
                'ability': ability_of(m.get('name'))
            })
        _, ps = http_json('http://127.0.0.1:11434/api/ps')
        running = [m.get('name') for m in (ps.get('models') or [])]
    return svc, models, running


# ---------------- 2. stable-diffusion.cpp ----------------
def scan_sdcpp():
    d = first_exist(os.path.join(TOOLS, 'sdcpp'))
    cli = first_exist(os.path.join(TOOLS, 'sdcpp', 'sd-cli.exe')) if d else ''
    srv = first_exist(os.path.join(TOOLS, 'sdcpp', 'sd-server.exe')) if d else ''
    model = ''
    model_files = []
    if d:
        for f in os.listdir(d):
            if f.lower().endswith(('.safetensors', '.ckpt', '.gguf')):
                model_files.append({'file': f, 'size_gb': fsize_gb(os.path.join(d, f))})
        if model_files:
            model = model_files[0]['file']
    alive = port_open(7860)
    svc = {
        'name': 'stable-diffusion.cpp',
        'category': '本地图像生成',
        'version': '',
        'location': d or 'D:\\ai-tools\\sdcpp（未找到）',
        'data': os.path.join(TOOLS, 'sdcpp') if d else '',
        'endpoint': 'http://127.0.0.1:7860',
        'api_base': 'sd-server.exe 启动后 http://127.0.0.1:7860',
        'status': status_of(alive, bool(d)),
        'capability': 'Stable Diffusion 文生图 / 图生图（GGML 版，CPU / Vulkan GPU 推理）',
        'invoke': r'D:\ai-tools\sdcpp\sd-cli.exe -m D:\ai-tools\sdcpp\sd15.safetensors -p "提示词" -o out.png',
        'note': ('含模型 ' + '、'.join('%s(%.2fGB)' % (x['file'], x['size_gb']) for x in model_files)
                 if model_files else '未发现模型文件')
    }
    return svc, model_files


# ---------------- 3. faster-whisper ----------------
def scan_whisper():
    cache = first_exist(os.path.join(TOOLS, 'whisper-models'),
                        os.path.join(HOME, '.cache', 'huggingface', 'hub'))
    models = []
    src = ''
    for base in (os.path.join(TOOLS, 'whisper-models'), os.path.join(HOME, '.cache', 'huggingface', 'hub')):
        if os.path.isdir(base):
            for n in os.listdir(base):
                if n.startswith('models--Systran--faster-whisper-'):
                    models.append(n.split('faster-whisper-')[-1])
                    src = base
    py = first_exist(os.path.join(TOOLS, 'Python311', 'python.exe'))
    pkg = first_exist(os.path.join(TOOLS, 'Python311', 'Lib', 'site-packages', 'faster_whisper'))
    svc = {
        'name': 'faster-whisper (CTranslate2)',
        'category': '本地语音识别 ASR',
        'version': 'faster-whisper 1.2.1 / ctranslate2 4.8.2',
        'location': py or 'Python311 未找到',
        'data': cache,
        'endpoint': '无（Python 库直接调用，非 HTTP 服务）',
        'api_base': 'Python API：faster_whisper.WhisperModel',
        'status': status_of(bool(pkg and pkg), bool(pkg)),
        'capability': '离线语音转文字，支持中文，可选 tiny / base / small / medium 精度档',
        'invoke': r'D:\ai-tools\Python311\python.exe 转写脚本.py',
        'note': ('可用模型档位：' + '、'.join(sorted(set(models))) if models else '未发现本地模型缓存')
               + '；缓存目录 ' + (src or '无')
    }
    return svc, sorted(set(models))


# ---------------- 4. edge-tts ----------------
def scan_edge_tts():
    py = first_exist(os.path.join(TOOLS, 'Python311', 'python.exe'))
    pkg = first_exist(os.path.join(TOOLS, 'Python311', 'Lib', 'site-packages', 'edge_tts'))
    return {
        'name': 'edge-tts',
        'category': '本地语音合成 TTS',
        'version': 'edge-tts 7.2.8',
        'location': py or 'Python311 未找到',
        'data': '',
        'endpoint': '无（Python 库）',
        'api_base': 'edge_tts.Communicate',
        'status': status_of(False, bool(pkg)),
        'capability': '文本转语音，支持 zh-CN-XiaoxiaoNeural 等中文多音色，输出 mp3 + 字幕',
        'invoke': r'D:\ai-tools\Python311\python.exe -m edge_tts --voice zh-CN-XiaoxiaoNeural --text "你好" --write-media out.mp3',
        'note': '无需密钥，联网调用微软 Edge 在线发音服务'
    }


# ---------------- 5. Wav2Lip ----------------
def scan_wav2lip():
    d = first_exist(os.path.join(TOOLS, 'Wav2Lip'))
    ckpt = first_exist(os.path.join(TOOLS, 'Wav2Lip', 'checkpoints', 'wav2lip_gan.pth'))
    det = first_exist(os.path.join(TOOLS, 'Wav2Lip', 'face_detection', 'detection', 'sfd', 's3fd.pth'))
    py = first_exist(os.path.join(TOOLS, 'Python311', 'python.exe'))
    files = []
    if d and os.path.isdir(os.path.join(d, 'checkpoints')):
        files = [{'file': f, 'size_gb': fsize_gb(os.path.join(d, 'checkpoints', f))}
                 for f in os.listdir(os.path.join(d, 'checkpoints'))]
    return {
        'name': 'Wav2Lip',
        'category': '本地数字人 / 对口型',
        'version': '',
        'location': d or 'D:\\ai-tools\\Wav2Lip（未找到）',
        'data': os.path.join(TOOLS, 'Wav2Lip', 'checkpoints') if d else '',
        'endpoint': '无（命令行脚本调用）',
        'api_base': 'inference.py',
        'status': status_of(False, bool(ckpt)),
        'capability': '把任意音频与人物视频合成唇形同步视频（数字人口播、本地配音对口型）',
        'invoke': r'D:\ai-tools\Python311\python.exe D:\ai-tools\Wav2Lip\inference.py --checkpoint_path D:\ai-tools\Wav2Lip\checkpoints\wav2lip_gan.pth --face 人像.mp4 --audio 语音.wav --outfile out.mp4',
        'note': ('权重：' + '、'.join('%s(%.2fGB)' % (x['file'], x['size_gb']) for x in files)
                 if files else '未发现权重文件')
               + ('；人脸检测 s3fd.pth 已就位' if det else '；缺少 s3fd.pth')
    }


# ---------------- 6. 其它运行时 ----------------
def scan_runtimes():
    out = []
    cand = [
        ('Python 3.11 (便携版)', os.path.join(TOOLS, 'Python311', 'python.exe')),
        ('Python 3.12 (便携版)', os.path.join(TOOLS, 'Python312', 'python.exe')),
        ('Node.js 24', os.path.join(TOOLS, 'node24', 'node.exe')),
        ('openclaw (Node CLI)', os.path.join(TOOLS, 'node24', 'openclaw.cmd')),
        ('Chatbox 安装包', os.path.join(TOOLS, 'chatbox-setup.exe')),
    ]
    for name, p in cand:
        out.append({'name': name, 'path': p, 'status': '已安装' if os.path.exists(p) else '未检测到'})
    return out


def main():
    if not os.path.isdir(DATA):
        os.makedirs(DATA)
    oll, models, running = scan_ollama()
    sdcpp, sdmodels = scan_sdcpp()
    whisper, wmodels = scan_whisper()
    services = [oll, sdcpp, whisper, scan_edge_tts(), scan_wav2lip()]

    out = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'host': os.environ.get('COMPUTERNAME', ''),
        'user': os.environ.get('USERNAME', ''),
        'services': services,
        'ollama_models': models,
        'ollama_running': running,
        'sd_models': sdmodels,
        'whisper_models': wmodels,
        'runtimes': scan_runtimes(),
        'ports': [
            {'port': 11434, 'service': 'Ollama', 'open': port_open(11434)},
            {'port': 7860, 'service': 'stable-diffusion.cpp sd-server', 'open': port_open(7860)},
            {'port': 1234, 'service': 'LM Studio (未安装)', 'open': port_open(1234)},
            {'port': 8188, 'service': 'ComfyUI (未安装)', 'open': port_open(8188)},
        ]
    }
    with open(os.path.join(DATA, 'local.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('[local_scan] services=%d  ollama_models=%d  whisper_models=%d' %
          (len(services), len(models), len(wmodels)))
    print('[local_scan] -> data/local.json')


if __name__ == '__main__':
    main()
