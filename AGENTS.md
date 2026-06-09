# AGENTS.md

本文件为 AI Agent 提供项目上下文和操作指南。

## 项目概述

MinerU API 是一个 Python 工具，用于调用 MinerU 云端 API 解析 PDF 论文为结构化 Markdown，并自动完成图片本地化、去除重复页眉页脚等后处理。

## 技术栈

- Python 3.10+
- 依赖管理：uv
- 外部依赖：requests, python-dotenv

## 核心文件

| 文件 | 职责 | 修改注意事项 |
|------|------|-------------|
| `parse_pdf.py` | MinerU API 调用（精准 API + Agent API 自动降级） | API 端点和参数可能随 MinerU 版本变化 |
| `postprocess.py` | Markdown 后处理（图片、页眉、空行） | 重复行检测参数可调：`REPEATED_LINE_MIN_COUNT`、`REPEATED_LINE_MAX_LEN` |
| `run.py` | 入口脚本，串联解析和后处理 | 纯胶水代码，一般不需修改 |
| `.env` | 存放 `MINERU_API_TOKEN` | **绝对不能提交到 Git** |

## 常用命令

```bash
# 安装依赖
uv sync

# 运行完整流程
python run.py "<PDF路径>" -n "<论文名称>"

# 仅运行后处理（已有 MinerU 输出时）
python postprocess.py "<raw_dir>" -o "<output>" -n "<论文名>"
```

## API 调用流程

```
本地文件 → POST /api/v4/file-urls/batch → 获取上传 URL
         → PUT 文件到 OSS
         → GET /api/v4/extract-results/batch/{batch_id} → 轮询
         → 下载 ZIP → 解压

URL 文件 → POST /api/v4/extract/task → 获取 task_id
         → GET /api/v4/extract/task/{task_id} → 轮询
         → 下载 ZIP → 解压

降级：Token 无效或 API 失败 → Agent API（/api/v1/agent/parse/*）
```

## 后处理逻辑

1. **图片本地化**：匹配 `![alt](https://...)` 下载到 `images/`，替换为相对路径
2. **重复行检测**：去掉 `#` 前缀后，长度 ≤30 字符且出现 ≥3 次的行自动删除
3. **白名单保护**：`摘要/引言/结论/参考文献/致谢` 等章节标题永不删除
4. **图片复制**：从 MinerU 输出的 `images/` 目录复制到统一输出目录

## 已知问题

- Token 长度校验 `len(token) > 50` 是魔术数字，Token 格式变化可能失效
- 图片下载为串行，大量图片时较慢
- `zipfile.extractall` 理论上有 Zip Slip 风险（实际低危，来源为官方 API）

## 修改指南

- 修改后处理参数：编辑 `postprocess.py` 顶部的 `REPEATED_LINE_MIN_COUNT`、`REPEATED_LINE_MAX_LEN`、`HEADER_WHITELIST`
- 添加新的后处理规则：在 `postprocess()` 函数中按顺序添加步骤
- 修改 API 端点：编辑 `parse_pdf.py` 中的 `API_BASE`、`AGENT_API_BASE`

## 禁止事项

- **禁止提交 `.env` 文件**（Token 泄露风险）
- **禁止修改 `run.py` 的 `param` 块**（影响 CLI 接口稳定性）
- **禁止删除 `.gitignore` 中的 `.env` 规则**
