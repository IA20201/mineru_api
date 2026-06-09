"""入口脚本：解析 PDF + 后处理。"""

import argparse
from pathlib import Path

from parse_pdf import parse_pdf
from postprocess import postprocess


def run(
    source: str,
    output_dir: Path,
    paper_name: str,
    is_ocr: bool = False,
    model: str = "vlm",
    timeout: int = 600,
) -> Path:
    """完整流程：解析 PDF → 后处理 → 输出。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 调用 MinerU 解析
    print("=" * 60)
    print("📡 步骤 1/2: 调用 MinerU 云端 API 解析 PDF")
    print("=" * 60)
    raw_dir = parse_pdf(
        source=source,
        output_dir=output_dir / "raw",
        is_ocr=is_ocr,
        model=model,
        timeout=timeout,
    )

    # 2. 后处理
    print("\n" + "=" * 60)
    print("🔧 步骤 2/2: 后处理 Markdown")
    print("=" * 60)
    result_path = postprocess(
        raw_dir=raw_dir,
        output_dir=output_dir,
        paper_name=paper_name,
    )

    print("\n" + "=" * 60)
    print(f"🎉 全部完成！输出目录: {output_dir}")
    print(f"   Markdown: {result_path}")
    print(f"   图片目录: {output_dir / 'images'}")
    print("=" * 60)

    return result_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MinerU PDF 解析 + 后处理")
    parser.add_argument("source", help="PDF 文件路径或 URL")
    parser.add_argument("-o", "--output", default="./output", help="输出根目录")
    parser.add_argument("-n", "--name", required=True, help="论文名称")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR")
    parser.add_argument("--model", default="vlm", choices=["pipeline", "vlm"])
    parser.add_argument("--timeout", type=int, default=600, help="超时秒数")
    args = parser.parse_args()

    run(
        source=args.source,
        output_dir=Path(args.output),
        paper_name=args.name,
        is_ocr=args.ocr,
        model=args.model,
        timeout=args.timeout,
    )
