---
name: mineru-pdf
description: 调用 MinerU 解析 PDF 论文为 Markdown，支持三种 API 来源可切换。当用户提到"解析PDF"、"PDF转Markdown"、"MinerU"、"论文解析"、"PDF提取"时触发。
---

# MinerU PDF 解析

调用 MinerU API 将 PDF 论文解析为结构化 Markdown，自动完成后处理。

## 功能

- 支持本地 PDF 文件和远程 URL
- **三种 API 来源可切换**（modal / cloud / agent）
- 自动下载图片本地化、去除重复页眉页脚
- 清理多余空行，输出干净 Markdown

## API 来源

| 来源 | 环境变量 | 说明 | 限制 |
|------|----------|------|------|
| **modal** | `MINERU_API_SOURCE=modal` | Modal 本地部署（默认） | 仅本地文件 |
| **cloud** | `MINERU_API_SOURCE=cloud` | MinerU 云端精准 API | 需 Token，200MB/200页 |
| **agent** | `MINERU_API_SOURCE=agent` | MinerU Agent API | 免登录，10MB/20页 |

切换方式：
```bash
# .env 文件
MINERU_API_SOURCE=modal  # 或 cloud 或 agent

# 命令行参数
python parse_pdf.py paper.pdf --api modal
```

## 前置条件

- `.env` 文件配置（按需）：
  ```env
  MINERU_API_SOURCE=modal          # API 来源
  MINERU_API_TOKEN=xxx             # cloud 模式需要
  MINERU_MODAL_API_KEY=xxx         # modal 模式需要（有默认值）
  ```
- 已安装依赖：`uv sync`

## 使用方式

### 方式 1：命令行

```bash
# 使用 Modal API（默认）
python parse_pdf.py paper.pdf -o ./output

# 指定 API 来源
python parse_pdf.py paper.pdf --api cloud -o ./output

# 启用 OCR（扫描件）
python parse_pdf.py paper.pdf --ocr --api modal
```

参数说明：
- `source`：PDF 文件本地路径或远程 URL（必填）
- `-o, --output`：输出目录，默认 `./output`
- `--ocr`：启用 OCR（扫描件 PDF 需要）
- `--model`：模型选择 `vlm`（默认）或 `pipeline`
- `--timeout`：超时秒数，默认 600
- `--api`：指定 API 来源 `modal` / `cloud` / `agent`

### 方式 2：Python 代码

```python
from parse_pdf import parse_pdf
from pathlib import Path

# 使用 Modal API
result_dir = parse_pdf(
    source="paper.pdf",
    output_dir=Path("./output/paper"),
    api_source="modal",
)

# 使用云端 API
result_dir = parse_pdf(
    source="paper.pdf",
    output_dir=Path("./output/paper"),
    api_source="cloud",
)
```

## 输出结构

### Modal API 输出
```
output/
├── <论文名>.md       # Markdown 文件
```

### Cloud/Agent API 输出
```
output/
├── <论文名>.md       # 处理后的 Markdown
├── images/           # 本地图片
└── raw/              # MinerU 原始输出
```

## 注意事项

- Modal API 仅支持本地文件，不支持 URL
- Cloud API 需要在 https://mineru.net/apiManage 获取 Token
- Agent API 免登录但限制 10MB / 20 页
- Token 无效时自动降级到 Agent API
