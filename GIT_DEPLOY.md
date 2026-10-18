# xh-voice-server — Git 部署与更新指南

> 语音服务中间件（TTS / ASR / KWS）。本文档说明如何把本项目推送到 GitHub、日常更新，以及同步到服务器。

---

## 1. 环境要求

| 组件 | 说明 |
|---|---|
| Git | 必需。Windows 可用 `winget install Git.Git` |
| GitHub CLI `gh` | 可选，方便认证/查仓库。`winget install GitHub.cli` |
| 网络 | **优先直连 GitHub**（`git push origin master`）。若直连被阻断，可临时设代理（实测端口波动，见 §6.1）；不要开启代理却无服务监听（会报 `Could not connect to server`） |

---

## 2. 仓库信息

- 远程仓库：`https://github.com/15143221112/xh-voice-server.git`（Public）
- 默认分支：`master`
- 本地目录：`D:\zhihong\xh-voice-server`

---

## 3. 首次部署 / 克隆

```bash
git clone https://github.com/15143221112/xh-voice-server.git
cd xh-voice-server
```

若本地已有仓库，只需关联远程：

```bash
git remote add origin https://github.com/15143221112/xh-voice-server.git
git branch --set-upstream-to=origin/master master   # 设置追踪
```

---

## 4. 日常更新流程（每次修改代码后）

```bash
cd D:\zhihong\xh-voice-server

# 1. 查看改动
git status
git diff

# 2. 暂存并提交
git add -A
git commit -m "类型: 说明，例如 fix/feat/docs/refactor"

# 3. 推送到 GitHub（master）
git push origin master
```

> 推送失败时通常是网络波动，多试几次或先设置代理再推（见第 6 节）。

---

## 5. 服务器同步（生产环境 /opt/voice_server）

服务器运行的是独立副本，改代码后需同步并重启：

```bash
# 关键文件：app/、config.yaml、requirements.txt、run.sh、deploy/voice-server.service
# 上传到 /opt/voice_server/ 对应路径

# 重启服务（SSH 无 tty 时必须带密码，否则 systemd 静默失败）
echo '密码' | sudo -S systemctl restart voice-server

# 验证
systemctl is-active voice-server          # 期望 active
curl -s http://127.0.0.1:8090/health      # 期望 {"status":"ok",...}
```

> 注意：服务器上的 `config.yaml` 与本地不一致时，**以服务器为准**（模型路径、启用的引擎），勿整文件覆盖。

---

## 6. 网络与认证说明（重要）

### 6.1 代理

本机直连 `github.com` 超时被墙。实测代理端口会波动（`7897` / `7890` / `33210` 等），先探测再使用：

```powershell
# 探测哪个代理能通 GitHub
$ports = @(7897, 7890, 33210)
foreach($p in $ports){
  try { Invoke-WebRequest -Uri "https://api.github.com" -Head -Proxy "http://127.0.0.1:$p" -TimeoutSec 10 -UseBasicParsing; "端口 $p 可用" } catch { "端口 $p 不可用" }
}
```

设置代理：

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:7897"   # 用探测到的可用端口
$env:HTTP_PROXY  = "http://127.0.0.1:7897"
```

> git 走 socks 代理（实测 7897 通）：
> ```powershell
> git config http.proxy "socks5://127.0.0.1:7897"
> ```

### 6.2 认证（Personal Access Token）

- HTTPS 推送需要 **PAT**，不能用账号密码。
- 生成：GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)
- 权限勾选：**`repo` + `workflow`**（`workflow` 必须有，否则推送含 `.github/workflows/ci.yml` 会被拒）
- Token 只在生成页显示一次，请妥善保存。

一次性带 Token 推送（不写入仓库配置，避免泄露）：

```powershell
git push "https://用户名:TOKEN@github.com/15143221112/xh-voice-server.git" master
```

正常已配好 origin 时直接 `git push origin master`（凭据走凭证管理器）。

### 6.3 常见报错与处理

| 报错 | 原因 / 处理 |
|---|---|
| `schannel: failed to receive handshake` / `EOF` | 网络波动，设置代理后重试 |
| `refusing to allow a Personal Access Token to create or update workflow ... without workflow scope` | Token 缺 `workflow` 权限，重新生成勾选 |
| `remote origin already exists` | remote 已存在，用 `git remote set-url origin <url>` 修正 |
| `unable to access ... SSL` | 代理未生效/端口错，按 6.1 探测正确端口 |

---

## 7. 分支与回滚

```bash
git log --oneline -10                      # 查看历史
git reset --hard <commit>                  # 回滚（谨慎，会改写历史）
git reset --soft HEAD~1                    # 撤销最后一次提交但保留改动
git push origin master --force             # 强制推送（仅自己分支/确认后）
```

---

## 8. CI / 质量检查

- 仓库自带 GitHub Actions（`.github/workflows/ci.yml`），推送后自动运行：
  - Python 3.11 / 3.12 语法编译检查（`compileall`）
  - `app.config` + `app.utils.logger` 导入冒烟测试
  - `config.yaml` 有效性校验
- 本地快速检查：
  ```bash
  pip install -r requirements.txt
  python -m compileall app scripts tests
  ```
- **完整接口测试**（需要已运行的服务器 + 模型 + 联网）：
  ```bash
  run.bat                                   # 先启动服务
  python tests/test_server.py               # 接口 + WebSocket 测试
  ```

---

## 9. 目录速览

```
xh-voice-server/
├── app/
│   ├── main.py              # FastAPI 主程序
│   ├── config.py            # 配置加载 (YAML → Pydantic)
│   ├── routers/             # tts.py / asr.py / kws.py API 路由
│   ├── services/            # 业务服务 + model_manager
│   └── utils/logger.py      # loguru 日志
├── scripts/
│   └── download_models.py   # 模型按需下载
├── tests/                   # 接口 + TTS 质量测试
├── deploy/                  # systemd 单元 + Linux 部署说明
├── config.yaml              # 配置文件
├── requirements.txt
├── run.bat / run.sh / start_all.bat
└── README.md / README.en.md / CHANGELOG.md / LICENSE
```

---

## 10. 快速命令速查

```bash
git status                                   # 查看改动
git add -A && git commit -m "feat: xxx"      # 提交
git push origin master                       # 推送（优先直连，被阻断才设代理）
git log --oneline                            # 查看历史
```

---

## 11. 发布注意（重要）

- **模型文件不上传**：`models/`、`*.onnx`、`*.bin` 已加入 `.gitignore`，通过 `scripts/download_models.py` 按需下载。
- **虚拟环境不上传**：`.venv/`、`.venv_conda/` 已排除。
- **凭据不进仓库**：本项目无任何 API Key / Token / 账号密码（TTS 在线引擎 edge-tts 免费免密钥），检查过全库。
- **模型词表 `tokens.txt`**：这是语音模型的词表文件（拼音 token），不是认证凭据，位于 `models/` 内随模型下载，不进仓库。
