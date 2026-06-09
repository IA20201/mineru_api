---
name: mineru-pdf
description: 调用 MinerU 云端 API 解析 PDF 论文为 Markdown，自动下载图片本地化、去除重复页眉页脚。当用户提到"解析PDF"、"PDF转Markdown"、"MinerU"、"论文解析"、"PDF提取"时触发。
---

# MinerU PDF 解析

调用 MinerU 云端 API 将 PDF 论文解析为结构化 Markdown，自动完成后处理。

## 功能

- 支持本地 PDF 文件和远程 URL
- 自动下载图片到本地 `images/` 目录
- 去除重复页眉/页脚（如期刊名、页码等）
- 清理多余空行，输出干净 Markdown

## 前置条件

- `.env` 文件中配置 `MINERU_API_TOKEN`（从 https://mineru.net/apiManage 获取）
- 已安装依赖：`uv sync`（项目根目录执行）

## 使用方式

### 方式 1：直接调用脚本

```bash
# 在项目目录 D:/MyProjects/mineru_api 下执行
python run.py "<PDF路径或URL>" -n "<论文名称>" [-o "<输出目录>"] [--timeout 600]
```

参数说明：
- `source`：PDF 文件本地路径或远程 URL（必填）
- `-n, --name`：论文名称，用于输出文件名（必填）
- `-o, --output`：输出目录，默认 `./output`
- `--ocr`：启用 OCR（扫描件 PDF 需要）
- `--model`：模型选择 `vlm`（默认）或 `pipeline`
- `--timeout`：超时秒数，默认 600

### 方式 2：分步调用

```python
# 仅解析（获取原始 Markdown + 图片）
from parse_pdf import parse_pdf
from pathlib import Path
raw_dir = parse_pdf(source="paper.pdf", output_dir=Path("./output/paper/raw"))

# 仅后处理（已有 MinerU 输出时）
from postprocess import postprocess
postprocess(raw_dir=Path("./raw"), output_dir=Path("./output"), paper_name="论文名")
```

## 输出结构

```
output/<论文名>/
├── <论文名>.md       # 处理后的 Markdown
├── images/           # 本地图片
│   ├── xxx.jpg
│   └── ...
└── raw/              # MinerU 原始输出（可删）
```

## 注意事项

- Agent API（免 Token）限制 10MB / 20 页，超出需配置 Token
- 精准 API（需 Token）支持 200MB / 200 页
- Token 无效时自动降级到 Agent API
- 图片下载为串行，大量图片时耗时较长
