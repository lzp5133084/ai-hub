# AI 资产总览面板

本机 AI 能力 + 在线 API 的一张总表，每日自动检测刷新，结果发布到 GitHub Pages。

在线地址：https://lzp5133084.github.io/ai-hub/

## 目录结构

```
ai-hub/
├─ index.html               站点主页（由模板渲染生成，数据已内嵌，可离线双击打开）
├─ local-report.html        本机专用版，含完整密钥（不上传 Git）
├─ template.html            页面模板，占位符 __REPORT_DATA__ 由 build.py 填充
├─ data/
│  ├─ local.json            本机模型/服务扫描结果
│  ├─ remote.json           在线 API 检测结果（脱敏）
│  └─ remote_full.json      本机专用，含完整密钥（不上传）
├─ scripts/
│  ├─ local_scan.py         扫描 Ollama / stable-diffusion.cpp / Wav2Lip / faster-whisper / edge-tts
│  ├─ remote_check.py       实测在线 API 可用性 + 火山余额账单
│  ├─ build.py              合并数据并渲染页面
│  └─ run_daily.py          每日编排：扫描 → 检测 → 渲染 → 推送 GitHub
├─ .github/workflows/daily-refresh.yml   每天 UTC 02:17 自动重建并部署 Pages
├─ daily-refresh.bat        供 Windows 计划任务调用
└─ config/
   ├─ keys.local.json       密钥清单（gitignore，绝不入库）
   └─ keys.example.json     密钥配置格式示例
```

## 一键刷新

```bat
daily-refresh.bat
```

或

```bash
python scripts/run_daily.py
```

流程：
1. `local_scan.py` 探测本机 Ollama（含模型清单）、出图 / 配音 / 唇形工具是否正常
2. `remote_check.py` 逐项实测在线 API，并拉取火山余额与近四个月账单
3. `build.py` 渲染 `index.html`（脱敏）+ `local-report.html`（本机完整密钥）
4. 自动 `git commit && git push`，触发 GitHub Actions 发布 Pages

## 每日自动执行

Windows 计划任务 **AIHub-Daily-Refresh**，每天 09:00：
- 本机扫描 + 在线检测
- 推送仓库 → GitHub Actions 自动发布 Pages

GitHub Actions 侧另有每日 cron（`17 2 * * *`，北京时间 10:17）兜底重建，即使本机没开机也能保证站点最新。

## 密钥安全

- `config/keys.local.json`、`data/remote_full.json`、`data/report_local.json`、`local-report.html`
  均在 `.gitignore` 中排除，**完整密钥不会出现在 GitHub 仓库和公开站点上**
- 公开站点只展示脱敏形式，例如 `ark-cc8e7f77········e0e988`
- 若要在云端也做在线检测，可在仓库 Settings → Secrets 添加 `AIHUB_KEYS_JSON`（内容与 keys.local.json 相同）

## 页面功能

- 七大部分：本地服务 / 本地模型 / 在线 API 密钥 / 方舟模型能力 / 调用示例速查 / 火山账单 / 处理建议
- 密钥搜索与状态筛选、密钥一键复制
- 所有调用示例代码块一键复制
- 导出 **Excel（6 个工作表）**、导出 CSV、打印 / 另存 PDF
