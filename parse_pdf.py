"""调用 MinerU 云端 API 解析 PDF，支持 URL 和本地文件两种模式。"""

import os
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://mineru.net/api/v4"
TOKEN = os.getenv("MINERU_API_TOKEN", "")


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }


# ── URL 模式 ─────────────────────────────────────────────────────────────────
def submit_task_from_url(pdf_url: str, is_ocr: bool = False, model: str = "vlm") -> str:
    """通过 URL 提交解析任务，返回 task_id。"""
    payload = {
        "url": pdf_url,
        "is_ocr": is_ocr,
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
        "model_version": model,
    }
    resp = requests.post(
        f"{API_BASE}/extract/task", json=payload, headers=_headers(), timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"提交任务失败: {data}")
    task_id = data["data"]["task_id"]
    print(f"[MinerU] URL 任务已提交: {task_id}")
    return task_id


# ── 本地文件模式 ──────────────────────────────────────────────────────────────
def submit_task_from_file(
    file_path: Path, is_ocr: bool = False, model: str = "vlm"
) -> str:
    """上传本地文件并提交解析任务，返回 task_id。

    流程：
    1. POST /file-urls/batch 获取签名上传 URL 和 task_id
    2. PUT 文件到 OSS
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 第一步：获取签名上传 URL
    payload = {
        "file_name": file_path.name,
        "is_ocr": is_ocr,
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
        "model_version": model,
    }
    resp = requests.post(
        f"{API_BASE}/file-urls/batch",
        json=payload,
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取上传链接失败: {data}")

    task_id = data["data"]["task_id"]
    upload_url = data["data"]["file_url"]
    print(f"[MinerU] 任务已创建: {task_id}")

    # 第二步：PUT 上传文件到 OSS
    print(f"[MinerU] 上传文件: {file_path.name} ({file_path.stat().st_size / 1024 / 1024:.1f} MB)")
    with open(file_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f, timeout=300)
    put_resp.raise_for_status()
    print(f"[MinerU] 文件上传完成")

    return task_id


# ── 轮询任务状态 ─────────────────────────────────────────────────────────────
def poll_task(task_id: str, interval: int = 5, timeout: int = 600) -> dict:
    """轮询任务状态，返回完成后的结果数据。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{API_BASE}/extract/task/{task_id}", headers=_headers(), timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"查询失败: {data}")

        result = data["data"]
        state = result.get("state", "")

        if state == "done":
            print(f"[MinerU] 任务完成: {task_id}")
            return result
        elif state == "failed":
            raise RuntimeError(f"任务失败: {result}")
        else:
            # 显示解析进度
            progress = result.get("extract_progress", {})
            if progress:
                extracted = progress.get("extracted_pages", 0)
                total = progress.get("total_pages", 0)
                print(f"[MinerU] 解析中: {extracted}/{total} 页")
            else:
                print(f"[MinerU] 状态: {state}，等待 {interval}s ...")
            time.sleep(interval)

    raise TimeoutError(f"任务 {task_id} 超时（{timeout}s）")


# ── 下载结果 ─────────────────────────────────────────────────────────────────
def download_result(result_data: dict, output_dir: Path) -> Path:
    """下载 zip 结果并解压，返回解压目录。"""
    zip_url = result_data.get("full_zip_url")
    if not zip_url:
        raise RuntimeError(f"未找到 zip 下载链接: {result_data}")

    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "result.zip"

    print(f"[MinerU] 下载结果...")
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)

    extract_dir = output_dir / "raw"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    zip_path.unlink()  # 删除 zip
    print(f"[MinerU] 已解压到: {extract_dir}")
    return extract_dir


# ── 主入口 ───────────────────────────────────────────────────────────────────
def parse_pdf(
    source: str,
    output_dir: Path,
    is_ocr: bool = False,
    model: str = "vlm",
) -> Path:
    """完整流程：提交 → 轮询 → 下载 → 解压。返回解压目录。

    Args:
        source: PDF 文件路径（本地）或 URL
        output_dir: 输出目录
        is_ocr: 是否启用 OCR
        model: 模型版本 (pipeline/vlm)
    """
    if not TOKEN:
        raise RuntimeError("请在 .env 中设置 MINERU_API_TOKEN")

    # 判断是本地文件还是 URL
    if source.startswith("http://") or source.startswith("https://"):
        task_id = submit_task_from_url(source, is_ocr=is_ocr, model=model)
    else:
        task_id = submit_task_from_file(Path(source), is_ocr=is_ocr, model=model)

    result = poll_task(task_id)
    return download_result(result, output_dir)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinerU 云端 PDF 解析")
    parser.add_argument("source", help="PDF 文件路径或 URL")
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR")
    parser.add_argument("--model", default="vlm", choices=["pipeline", "vlm"])
    args = parser.parse_args()

    extract_dir = parse_pdf(
        source=args.source,
        output_dir=Path(args.output),
        is_ocr=args.ocr,
        model=args.model,
    )
    print(f"\n✅ 解析完成，原始文件在: {extract_dir}")
