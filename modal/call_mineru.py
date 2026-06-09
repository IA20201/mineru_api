"""调用 MinerU API 解析 PDF。

用法：
    python call_mineru.py <pdf_path> [--output result.json]
"""

import argparse
import json
import requests
from pathlib import Path

API_URL = "https://jhdhhu58--mineru-api-fastapi-app.modal.run"
API_KEY = "ld0OgOZOsgZUVqGtBDfETucAV2DSHt7HFC0A8XmeRLc"


def parse_pdf(pdf_path: str, backend: str = "pipeline", language: str = "ch") -> dict:
    """调用 MinerU API 解析 PDF。"""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"文件不存在: {pdf_path}")

    with open(pdf_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/parse",
            headers={"X-API-Key": API_KEY},
            files={"file": (pdf_path.name, f, "application/pdf")},
            data={"backend": backend, "language": language},
            timeout=600,
        )

    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="MinerU PDF 解析")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--backend", "-b", default="pipeline", help="解析后端 (pipeline/vlm)")
    parser.add_argument("--language", "-l", default="ch", help="语言 (ch/en)")
    args = parser.parse_args()

    print(f"解析: {args.pdf_path}")
    result = parse_pdf(args.pdf_path, args.backend, args.language)

    if result["success"]:
        print(f"✅ 成功! Markdown 长度: {len(result['markdown'])} 字符")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"📄 已保存到: {args.output}")
        else:
            print("\n--- Markdown 预览 (前 500 字符) ---")
            print(result["markdown"][:500])
    else:
        print(f"❌ 失败: {result['error']}")


if __name__ == "__main__":
    main()
