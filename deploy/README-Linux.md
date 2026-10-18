# Voice Server - Linux 部署指南

## 1. 系统要求

- Python 3.10+
- Linux x86_64（Ubuntu 20.04+ / CentOS 8+ / Debian 11+）
- 内存: 最低 2GB（加载 ASR 模型约 500MB）
- 磁盘: ~600MB（模型文件）

## 2. 安装系统依赖

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libsndfile1

# CentOS / RHEL / Rocky Linux
sudo dnf install -y python3 python3-devel libsndfile

# 可选: ffmpeg（处理非 WAV 音频格式时需要）
sudo apt install -y ffmpeg   # Ubuntu
sudo dnf install -y ffmpeg   # CentOS
```

> `libsndfile1` 是 librosa/soundfile 读取音频文件的底层库，**必须安装**。

## 3. 部署步骤

```bash
# 3.1 复制项目到服务器
sudo mkdir -p /opt/voice_server
sudo chown $USER:$USER /opt/voice_server
# 将项目文件复制到 /opt/voice_server（不含 .venv 和 models）

# 3.2 创建虚拟环境并安装依赖
cd /opt/voice_server
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3.3 下载模型（首次部署，约 535MB）
python scripts/download_models.py

# 3.4 验证配置
# 编辑 config.yaml，确认各模型 enabled: true
vim config.yaml

# 3.5 测试启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 1
# 看到 "Voice Server ready" 后 Ctrl+C 退出
```

## 4. 快速启动（开发/测试）

```bash
cd /opt/voice_server
chmod +x run.sh
./run.sh
```

## 5. 生产部署（systemd 服务）

```bash
# 5.1 安装服务文件
sudo cp deploy/voice-server.service /etc/systemd/system/

# 5.2 修改服务文件中的路径（如果部署路径不是 /opt/voice_server）
sudo vim /etc/systemd/system/voice-server.service

# 5.3 启动服务
sudo systemctl daemon-reload
sudo systemctl enable voice-server
sudo systemctl start voice-server

# 5.4 查看状态和日志
sudo systemctl status voice-server
sudo journalctl -u voice-server -f    # 实时日志
```

## 6. 防火墙配置

```bash
# 开放 8090 端口
# Ubuntu (ufw)
sudo ufw allow 8090/tcp

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-port=8090/tcp
sudo firewall-cmd --reload
```

## 7. Nginx 反向代理（可选，HTTPS/WSS）

```nginx
server {
    listen 443 ssl;
    server_name voice.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket 支持（ASR/KWS 流式）
    location ~ ^/(asr|kws)/stream$ {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

## 8. 常见问题

### Q: sherpa-onnx 安装失败？
```bash
# 确认系统架构
uname -m   # 应为 x86_64 或 aarch64

# 手动安装指定版本
pip install sherpa-onnx==1.11.4 --no-cache-dir
```

### Q: librosa 导入报错 `OSError: libsndfile.so.1`？
```bash
sudo apt install libsndfile1       # Ubuntu/Debian
sudo dnf install libsndfile         # CentOS/RHEL
```

### Q: edge-tts 连接超时？
edge-tts 需要访问微软 Azure 服务，确保服务器能访问外网。
如果在国内服务器，可能需要配置代理或仅使用离线 Sherpa-ONNX TTS：
```yaml
# config.yaml
routing:
  tts:
    primary: "sherpa_tts"    # 改为离线优先
    fallback: "edge_tts"
```

### Q: 如何更新模型？
```bash
cd /opt/voice_server
source .venv/bin/activate
python scripts/download_models.py --check    # 查看当前状态
python scripts/download_models.py --asr      # 重新下载指定模型
```

### Q: 从 Windows 复制模型文件到 Linux？
ONNX 模型文件是平台无关的二进制文件，可以直接复制：
```bash
# 从 Windows 复制 models/ 目录到 Linux 服务器
scp -r models/ user@server:/opt/voice_server/
```
