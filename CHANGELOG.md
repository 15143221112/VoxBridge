# Changelog

本项目所有重要变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-10-18

### 初始发布

首个公开版本，作为独立通用语音服务中间件发布。

#### 新增

- **TTS（文本转语音）**：双引擎混合路由
  - `edge-tts` 在线主引擎（微软 Azure Neural TTS，免费，无需密钥）
  - Sherpa-ONNX Kokoro 离线降级（网络故障时自动切换，CPU 推理）
  - 8 个中文/方言音色可选，支持语速/音调/音量调节
- **ASR（语音转文本）**：Sherpa-ONNX Streaming Zipformer 离线识别
  - 中英双语流式识别
  - 文件上传（`POST /asr`）+ WebSocket 实时流（`WS /asr/stream`）
- **KWS（唤醒词检测）**：Sherpa-ONNX Zipformer 3.3M 离线检测
  - 仅 3.3MB 模型，自定义关键词（txt 配置，无需重训）
  - 文件检测 + WebSocket 实时流
- **VAD（语音活动检测）**：Silero VAD 可选启用，用于 ASR 降噪/切分
- **智能路由降级**：TTS 超时 10s 自动降级离线引擎，保证服务可用性
- **模型管理**：`scripts/download_models.py` 按需下载，`--check` 查看状态
- **健康检查**：`/health` 总健康 + 各引擎独立 `/tts/health` `/asr/health` `/kws/health`
- **API 文档**：Swagger UI（`/docs`）+ OpenAPI 规范
- **完整测试**：接口测试 + TTS 质量测试
- **多平台部署**：Windows（`run.bat`）+ Linux（systemd 单元 + `run.sh`）

#### 技术栈

- Python 3.11+，FastAPI 0.115.6，uvicorn 0.34.0
- edge-tts ≥ 7.2.8（Chromium 143+，解决微软 WSS 端点 403）
- sherpa-onnx 1.11.4，numpy 1.26.4，librosa 0.10.2

[1.0.0]: https://github.com/15143221112/xh-voice-server/releases/tag/v1.0.0
