# MinerU API — PDF 论文解析 + 后处理

调用 [MinerU](https://github.com/opendatalab/MinerU) 云端 API 将 PDF 论文解析为结构化 Markdown，自动完成后处理。

## 功能

- 📄 支持本地 PDF 文件和远程 URL
- 🖼️ 自动下载图片到本地 `images/` 目录
- 🧹 智能去除重复页眉/页脚（通用检测，无需预设期刊名）
- ✨ 清理多余空行，输出干净 Markdown
- 🔄 Token 无效时自动降级到免登录 API

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置 Token（可选）

在项目根目录创建 `.env`：

```env
MINERU_API_TOKEN=你的Token
```

Token 从 [MinerU API 管理页面](https://mineru.net/apiManage) 获取。

> 不配置 Token 也可使用，自动走 Agent 轻量 API（限制 10MB / 20 页）。

### 3. 使用

```bash
# 本地 PDF
python run.py "C:\path\to\paper.pdf" -n "论文名称"

# 远程 URL
python run.py "https://example.com/paper.pdf" -n "论文名称"

# 指定输出目录
python run.py paper.pdf -n "论文名" -o ./my_output

# 扫描件 PDF 启用 OCR
python run.py scanned.pdf -n "论文名" --ocr

# 自定义超时
python run.py large.pdf -n "论文名" --timeout 1200
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `source` | PDF 文件路径或 URL | 必填 |
| `-n, --name` | 论文名称（用于输出文件名） | 必填 |
| `-o, --output` | 输出目录 | `./output` |
| `--ocr` | 启用 OCR（扫描件需要） | 关闭 |
| `--model` | 模型：`vlm` 或 `pipeline` | `vlm` |
| `--timeout` | 超时秒数 | `600` |

## 输出结构

```
output/<论文名>/
├── <论文名>.md       # 处理后的 Markdown
├── images/           # 本地图片
│   ├── xxx.jpg
│   └── xxx.png
└── raw/              # MinerU 原始输出（可删）
```

## 后处理规则

1. **图片本地化**：下载 Markdown 中的远程图片，替换为本地相对路径
2. **重复页眉检测**：自动识别全文中出现 ≥3 次的短行（≤30 字符），删除期刊页眉/页脚
3. **空行清理**：连续 3+ 空行压缩为 2 空行
4. **图片复制**：将 MinerU 输出的本地图片复制到统一的 `images/` 目录

## API 对比

| 维度 | 精准 API（需 Token） | Agent API（免登录） |
|------|---------------------|-------------------|
| 文件大小 | ≤ 200MB | ≤ 10MB |
| 页数限制 | ≤ 200 页 | ≤ 20 页 |
| 输出格式 | ZIP（Markdown + JSON + 图片） | ZIP（Markdown + 图片） |

## 项目结构

```
mineru_api/
├── run.py            # 入口脚本
├── parse_pdf.py      # MinerU API 调用
├── postprocess.py    # Markdown 后处理
├── pyproject.toml    # 项目配置
├── uv.lock           # 依赖锁文件
└── .env              # Token 配置（不提交）
```

## License

MIT
