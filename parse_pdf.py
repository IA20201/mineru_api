"""调用 MinerU 云端 API 解析 PDF，支持 URL 和本地文件两种模式。

API 优先级：
1. 精准解析 API（需 Token）— 支持 200MB/200页
2. Agent 轻量 API（免登录）— 支持 10MB/20页，自动降级
"""

import os
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_BASE = "https://mineru.net/api/v4"
AGENT_API_BASE = "https://mineru.net/api/v1/agent"


def _get_token() -> str:
    return os.getenv("MINERU_API_TOKEN", "")


def _auth_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_token()}",
    }


# ── 精准解析 API（需 Token）──────────────────────────────────────────────────
def _submit_url_auth(pdf_url: str, is_ocr: bool, model: str) -> str:
    """通过 URL + 精准 API 提交任务，返回 task_id。"""
    payload = {
        "url": pdf_url,
        "is_ocr": is_ocr,
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
        "model_version": model,
    }
    resp = requests.post(
        f"{API_BASE}/extract/task", json=payload, headers=_auth_headers(), timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"提交任务失败: {data}")
    task_id = data["data"]["task_id"]
    print(f"[精准API] URL 任务已提交: {task_id}")
    return task_id


def _submit_file_auth(file_path: Path, is_ocr: bool, model: str) -> str:
    """上传本地文件 + 精准 API，返回 batch_id。"""
    payload = {
        "files": [{
            "name": file_path.name,
            "is_ocr": is_ocr,
            "enable_formula": True,
            "enable_table": True,
            "language": "ch",
        }]
    }
    resp = requests.post(
        f"{API_BASE}/file-urls/batch", json=payload, headers=_auth_headers(), timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取上传链接失败: {data}")

    batch_id = data["data"]["batch_id"]
    upload_url = data["data"]["file_urls"][0]
    print(f"[精准API] 批次已创建: {batch_id}")

    _upload_file(file_path, upload_url)
    return batch_id


# ── Agent 轻量 API（免登录）─────────────────────────────────────────────────
def _submit_file_agent(file_path: Path, is_ocr: bool, model: str) -> str:
    """上传本地文件 + Agent API（免 Token），返回 task_id。"""
    payload = {
        "file_name": file_path.name,
        "language": "ch",
        "enable_table": True,
        "is_ocr": is_ocr,
        "enable_formula": True,
    }
    resp = requests.post(
        f"{AGENT_API_BASE}/parse/file", json=payload, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Agent API 失败: {data}")

    task_id = data["data"]["task_id"]
    upload_url = data["data"]["file_url"]
    print(f"[AgentAPI] 任务已创建: {task_id}")

    _upload_file(file_path, upload_url)
    return task_id


def _submit_url_agent(pdf_url: str, is_ocr: bool, model: str) -> str:
    """通过 URL + Agent API 提交任务，返回 task_id。"""
    payload = {
        "url": pdf_url,
        "language": "ch",
        "enable_table": True,
        "is_ocr": is_ocr,
        "enable_formula": True,
    }
    resp = requests.post(
        f"{AGENT_API_BASE}/parse/url", json=payload, timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Agent API 失败: {data}")

    task_id = data["data"]["task_id"]
    print(f"[AgentAPI] URL 任务已提交: {task_id}")
    return task_id


# ── 通用工具 ─────────────────────────────────────────────────────────────────
def _upload_file(file_path: Path, upload_url: str):
    """PUT 上传文件到 OSS。"""
    size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"[MinerU] 上传文件: {file_path.name} ({size_mb:.1f} MB)")
    with open(file_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f, timeout=300)
    put_resp.raise_for_status()
    print(f"[MinerU] 上传完成")


# ── 轮询：精准 API ─────────────────────────────────────────────────────────
def _poll_auth_task(task_id: str, interval: int, timeout: int) -> dict:
    """轮询精准 API 的单文件任务。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{API_BASE}/extract/task/{task_id}",
            headers=_auth_headers(), timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            result = data["data"]
            state = result.get("state", "")
            if state == "done":
                print(f"[MinerU] 任务完成: {task_id}")
                return result
            elif state == "failed":
                raise RuntimeError(f"任务失败: {result}")
            _print_progress(result, interval)
        else:
            print(f"[MinerU] 查询中，等待 {interval}s ...")
        time.sleep(interval)
    raise TimeoutError(f"任务 {task_id} 超时（{timeout}s）")


def _poll_auth_batch(batch_id: str, interval: int, timeout: int) -> dict:
    """轮询精准 API 的批量任务，返回第一个文件的结果。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{API_BASE}/extract-results/batch/{batch_id}",
            headers=_auth_headers(), timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            results = data["data"].get("extract_result", [])
            if results:
                first = results[0]
                state = first.get("state", "")
                if state == "done":
                    print(f"[MinerU] 批次完成: {batch_id}")
                    return first
                elif state == "failed":
                    raise RuntimeError(f"任务失败: {first}")
                _print_progress(first, interval)
            else:
                print(f"[MinerU] 等待结果，{interval}s ...")
        else:
            print(f"[MinerU] 查询中，{interval}s ...")
        time.sleep(interval)
    raise TimeoutError(f"批次 {batch_id} 超时（{timeout}s）")


# ── 轮询：Agent API ─────────────────────────────────────────────────────────
def _poll_agent_task(task_id: str, interval: int, timeout: int) -> dict:
    """轮询 Agent API 任务。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{AGENT_API_BASE}/extract/task/{task_id}",
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                result = data["data"]
                state = result.get("state", "")
                if state == "done":
                    print(f"[MinerU] 任务完成: {task_id}")
                    return result
                elif state == "failed":
                    raise RuntimeError(f"任务失败: {result}")
                _print_progress(result, interval)
            else:
                print(f"[MinerU] 查询中，{interval}s ...")
        else:
            print(f"[MinerU] 查询中（{resp.status_code}），{interval}s ...")
        time.sleep(interval)
    raise TimeoutError(f"任务 {task_id} 超时（{timeout}s）")


def _print_progress(result: dict, interval: int):
    """打印解析进度。"""
    progress = result.get("extract_progress", {})
    state = result.get("state", "running")
    if progress:
        extracted = progress.get("extracted_pages", 0)
        total = progress.get("total_pages", 0)
        print(f"[MinerU] 解析中: {extracted}/{total} 页")
    else:
        print(f"[MinerU] 状态: {state}，等待 {interval}s ...")


def download_result(result_data: dict, output_dir: Path) -> Path:
    """下载 zip 结果并解压，返回解压目录。流式写入避免大文件 OOM。"""
    zip_url = result_data.get("full_zip_url")
    if not zip_url:
        raise RuntimeError(f"未找到 zip 下载链接: {result_data}")

    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "result.zip"

    print(f"[MinerU] 下载结果...")
    with requests.get(zip_url, timeout=120, stream=True) as resp:
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    extract_dir = output_dir / "raw"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    zip_path.unlink()
    print(f"[MinerU] 已解压到: {extract_dir}")
    return extract_dir


# ── 主入口 ───────────────────────────────────────────────────────────────────
def parse_pdf(
    source: str,
    output_dir: Path,
    is_ocr: bool = False,
    model: str = "vlm",
    poll_interval: int = 5,
    timeout: int = 600,
) -> Path:
    """完整流程：提交 → 轮询 → 下载 → 解压。返回解压目录。

    优先使用精准 API（需 Token），Token 无效时自动降级到 Agent API。
    """
    is_url = source.startswith("http://") or source.startswith("https://")
    file_path = None if is_url else Path(source)

    # 校验本地文件存在性
    if file_path and not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 检查文件大小（Agent API 限制 10MB）
    size_mb = file_path.stat().st_size / 1024 / 1024 if file_path else 0

    token = _get_token()
    use_auth = bool(token and len(token) > 50)
    task_or_batch_id = None
    is_batch = False
    submitted_via_auth = False  # 记录实际提交方式

    if use_auth:
        try:
            if is_url:
                task_or_batch_id = _submit_url_auth(source, is_ocr, model)
                submitted_via_auth = True
            else:
                task_or_batch_id = _submit_file_auth(file_path, is_ocr, model)
                is_batch = True
                submitted_via_auth = True
        except Exception as e:
            print(f"[MinerU] 精准 API 失败 ({e})，降级到 Agent API...")

    if task_or_batch_id is None:
        if file_path and size_mb > 10:
            raise RuntimeError(
                f"文件 {size_mb:.1f}MB 超过 Agent API 限制(10MB)，请配置有效的 MINERU_API_TOKEN"
            )
        if is_url:
            task_or_batch_id = _submit_url_agent(source, is_ocr, model)
        else:
            task_or_batch_id = _submit_file_agent(file_path, is_ocr, model)

    # 轮询结果：根据实际提交方式选择轮询函数
    if submitted_via_auth and is_batch:
        result = _poll_auth_batch(task_or_batch_id, poll_interval, timeout)
    elif submitted_via_auth:
        result = _poll_auth_task(task_or_batch_id, poll_interval, timeout)
    else:
        result = _poll_agent_task(task_or_batch_id, poll_interval, timeout)

    return download_result(result, output_dir)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinerU 云端 PDF 解析")
    parser.add_argument("source", help="PDF 文件路径或 URL")
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR")
    parser.add_argument("--model", default="vlm", choices=["pipeline", "vlm"])
    parser.add_argument("--timeout", type=int, default=600, help="超时秒数")
    args = parser.parse_args()

    extract_dir = parse_pdf(
        source=args.source,
        output_dir=Path(args.output),
        is_ocr=args.ocr,
        model=args.model,
        timeout=args.timeout,
    )
    print(f"\n✅ 解析完成，原始文件在: {extract_dir}")
