# AGENTS.md

本文件为 AI Agent 提供项目上下文和操作指南。

## 项目概述

MinerU API 是一个 Python 工具，用于解析 PDF 论文为结构化 Markdown，支持三种 API 来源可切换：
- **Modal 本地部署**（默认）— L4 GPU 加速，最稳定
- **MinerU 云端精准 API** — 需 Token，支持 200MB/200页
- **MinerU Agent API** — 免登录，限制 10MB/20页

## 技术栈

- Python 3.10+
- 依赖管理：uv
- 外部依赖：requests, python-dotenv, fastapi
- 部署平台：Modal（L4 GPU）

## 核心文件

| 文件 | 职责 | 修改注意事项 |
|------|------|-------------|
| `parse_pdf.py` | PDF 解析主逻辑，支持三种 API 切换 | API 端点和参数可能随版本变化 |
| `postprocess.py` | Markdown 后处理（图片、页眉、空行） | 重复行检测参数可调 |
| `run.py` | 入口脚本，串联解析和后处理 | 纯胶水代码 |
| `modal/app.py` | Modal 部署脚本（FastAPI 服务） | 修改后需 `modal deploy` |
| `modal/call_mineru.py` | 独立调用 Modal API 的脚本 | 可直接 import 使用 |
| `.env` | 配置文件（API Key 等） | **绝对不能提交到 Git** |
| `.env.example` | 配置模板 | 可提交，不含敏感信息 |

## 常用命令

```bash
# 安装依赖
uv sync

# 运行完整流程（默认使用 Modal API）
python run.py "<PDF路径>" -n "<论文名称>"

# 指定 API 来源
python parse_pdf.py paper.pdf --api modal    # Modal 本地部署
python parse_pdf.py paper.pdf --api cloud    # 云端精准 API
python parse_pdf.py paper.pdf --api agent    # Agent API（免登录）

# 部署 Modal 服务（修改 modal/app.py 后）
modal deploy modal/app.py

# 查看 Modal 日志
modal app logs mineru-api --tail 20
```

## API 来源切换

| 来源 | 环境变量 | 命令行 | 说明 |
|------|----------|--------|------|
| **cloud** | `MINERU_API_SOURCE=cloud` | `--api cloud` | MinerU 云端 API（默认） |
| **modal** | `MINERU_API_SOURCE=modal` | `--api modal` | Modal 本地部署 |
| **agent** | `MINERU_API_SOURCE=agent` | `--api agent` | Agent API（免登录） |

## API 调用流程

### Modal API（默认）
```
本地文件 → POST Modal /parse (X-API-Key 认证)
         → 直接返回 Markdown
```

### Cloud/Agent API
```
本地文件 → POST /api/v4/file-urls/batch → 获取上传 URL
         → PUT 文件到 OSS
         → GET /api/v4/extract-results/batch/{batch_id} → 轮询
         → 下载 ZIP → 解压

URL 文件 → POST /api/v4/extract/task → 获取 task_id
         → GET /api/v4/extract/task/{task_id} → 轮询
         → 下载 ZIP → 解压
```

## 后处理逻辑

1. **图片本地化**：匹配 `![alt](https://...)` 下载到 `images/`，替换为相对路径
2. **重复行检测**：去掉 `#` 前缀后，长度 ≤30 字符且出现 ≥3 次的行自动删除
3. **白名单保护**：`摘要/引言/结论/参考文献/致谢` 等章节标题永不删除
4. **图片复制**：从 MinerU 输出的 `images/` 目录复制到统一输出目录

## Modal 部署说明

- **API 地址**：`https://jhdhhu58--mineru-api-fastapi-app.modal.run`
- **认证方式**：Header `X-API-Key`
- **GPU**：L4（22GB 显存）
- **模型存储**：Modal Volume `mineru-models`（持久化）
- **Secret**：`mineru-api-key`（存储 API Key）

```bash
# 部署命令
modal deploy modal/app.py

# 查看状态
modal app list

# 查看日志
modal app logs mineru-api --tail 20

# 停止服务
modal app stop mineru-api -y
```

## 环境变量配置

```env
# MinerU 官方 Token（cloud 模式需要）
MINERU_API_TOKEN=xxx

# API 来源：cloud / modal / agent
MINERU_API_SOURCE=cloud

# Modal API Key（modal 模式需要）
MINERU_MODAL_API_KEY=xxx
```

## 已知限制

- Modal API 仅支持本地文件，不支持 URL
- Cloud API Token 长度校验 `len(token) > 50` 是魔术数字
- 图片下载为串行，大量图片时较慢
- Modal 冷启动首次请求可能较慢（模型加载约 30 秒）

## 修改指南

- **修改 API 来源**：编辑 `.env` 中的 `MINERU_API_SOURCE`
- **修改后处理参数**：编辑 `postprocess.py` 顶部的常量
- **修改 Modal 部署**：编辑 `modal/app.py`，然后 `modal deploy modal/app.py`
- **重置 API Key**：在 Modal 控制台重新创建 Secret

## 禁止事项

- **禁止提交 `.env` 文件**（Token 泄露风险）
- **禁止修改 `run.py` 的 `param` 块**（影响 CLI 接口稳定性）
- **禁止删除 `.gitignore` 中的 `.env` 规则**
- **禁止硬编码 API Key 到代码中**
