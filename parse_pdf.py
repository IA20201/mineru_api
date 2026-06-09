"""调用 MinerU API 解析 PDF，支持三种 API 来源可切换。

API 来源优先级（可通过 MINERU_API_SOURCE 环境变量切换）：
1. modal  — Modal 本地部署（最稳定，需部署）
2. cloud  — MinerU 云端精准 API（需 Token）
3. agent  — MinerU Agent API（免登录，限制 10MB/20页）

环境变量配置（.env 文件）：
    MINERU_API_SOURCE=modal|cloud|agent  # 切换 API 来源，默认 modal
    MINERU_API_TOKEN=xxx                 # 云端 API Token（cloud 模式必需）
    MINERU_MODAL_API_KEY=xxx             # Modal API Key（modal 模式必需）
"""

import os
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ── API 配置 ─────────────────────────────────────────────────────────────────
MODAL_API_URL = "https://jhdhhu58--mineru-api-fastapi-app.modal.run"
CLOUD_API_BASE = "https://mineru.net/api/v4"
AGENT_API_BASE = "https://mineru.net/api/v1/agent"


def _get_api_source() -> str:
    """获取 API 来源：modal / cloud / agent"""
    return os.getenv("MINERU_API_SOURCE", "cloud").lower()


def _get_cloud_token() -> str:
    return os.getenv("MINERU_API_TOKEN", "")


def _get_modal_key() -> str:
    key = os.getenv("MINERU_MODAL_API_KEY", "")
    if not key:
        raise RuntimeError("Modal API 需要配置 MINERU_MODAL_API_KEY")
    return key


# ── Modal API（本地部署）────────────────────────────────────────────────────
def _parse_via_modal(file_path: Path, is_ocr: bool, model: str) -> dict:
    """通过 Modal API 解析 PDF，返回结果字典。"""
    api_key = _get_modal_key()
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{MODAL_API_URL}/parse",
            headers={"X-API-Key": api_key},
            files={"file": (file_path.name, f, "application/pdf")},
            data={
                "backend": model,
                "is_ocr": str(is_ocr).lower(),
                "enable_table": "true",
                "enable_formula": "true",
                "language": "ch",
            },
            timeout=600,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Modal API 失败: {data.get('error', '未知错误')}")
    return data


# ── 云端 API（精准解析）────────────────────────────────────────────────────
def _auth_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_cloud_token()}",
    }


def _submit_url_cloud(pdf_url: str, is_ocr: bool, model: str) -> str:
    payload = {
        "url": pdf_url,
        "is_ocr": is_ocr,
        "enable_formula": True,
        "enable_table": True,
        "language": "ch",
        "model_version": model,
    }
    resp = requests.post(
        f"{CLOUD_API_BASE}/extract/task", json=payload, headers=_auth_headers(), timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"提交任务失败: {data}")
    task_id = data["data"]["task_id"]
    print(f"[云端API] URL 任务已提交: {task_id}")
    return task_id


def _submit_file_cloud(file_path: Path, is_ocr: bool, model: str) -> str:
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
        f"{CLOUD_API_BASE}/file-urls/batch", json=payload, headers=_auth_headers(), timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取上传链接失败: {data}")

    batch_id = data["data"]["batch_id"]
    upload_url = data["data"]["file_urls"][0]
    print(f"[云端API] 批次已创建: {batch_id}")

    _upload_file(file_path, upload_url)
    return batch_id


# ── Agent API（免登录）─────────────────────────────────────────────────────
def _submit_file_agent(file_path: Path, is_ocr: bool, model: str) -> str:
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
    size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"[MinerU] 上传文件: {file_path.name} ({size_mb:.1f} MB)")
    with open(file_path, "rb") as f:
        put_resp = requests.put(upload_url, data=f, timeout=300)
    put_resp.raise_for_status()
    print(f"[MinerU] 上传完成")


# ── 轮询 ─────────────────────────────────────────────────────────────────────
def _poll_cloud_task(task_id: str, interval: int, timeout: int) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{CLOUD_API_BASE}/extract/task/{task_id}",
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
        time.sleep(interval)
    raise TimeoutError(f"任务 {task_id} 超时（{timeout}s）")


def _poll_cloud_batch(batch_id: str, interval: int, timeout: int) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{CLOUD_API_BASE}/extract-results/batch/{batch_id}",
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
        time.sleep(interval)
    raise TimeoutError(f"批次 {batch_id} 超时（{timeout}s）")


def _poll_agent_task(task_id: str, interval: int, timeout: int) -> dict:
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
        time.sleep(interval)
    raise TimeoutError(f"任务 {task_id} 超时（{timeout}s）")


def _print_progress(result: dict, interval: int):
    progress = result.get("extract_progress", {})
    if progress:
        extracted = progress.get("extracted_pages", 0)
        total = progress.get("total_pages", 0)
        print(f"[MinerU] 解析中: {extracted}/{total} 页")
    else:
        print(f"[MinerU] 等待中，{interval}s ...")


def download_result(result_data: dict, output_dir: Path) -> Path:
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

    # ZIP 安全校验（防止 Zip Slip 攻击）
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            member_path = (extract_dir / member).resolve()
            if not str(member_path).startswith(str(extract_dir.resolve())):
                raise RuntimeError(f"ZIP 条目路径不安全: {member}")
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
    api_source: str = None,  # 可覆盖环境变量
) -> Path:
    """完整流程：解析 PDF 并返回结果目录。

    Args:
        api_source: 强制指定 API 来源 (modal/cloud/agent)，None 则用环境变量
    """
    is_url = source.startswith("http://") or source.startswith("https://")
    file_path = None if is_url else Path(source)

    if file_path and not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    source_type = api_source or _get_api_source()
    print(f"[MinerU] 使用 API: {source_type}")

    # ── Modal API ─────────────────────────────────────────────────────────
    if source_type == "modal":
        if is_url:
            raise ValueError("Modal API 暂不支持 URL，请使用本地文件")
        result_data = _parse_via_modal(file_path, is_ocr, model)
        # Modal API 直接返回 markdown，不需要下载 zip
        md_path = output_dir / f"{file_path.stem}.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(result_data["markdown"], encoding="utf-8")
        print(f"[Modal] 解析完成，Markdown 已保存到: {md_path}")
        return output_dir

    # ── 云端 / Agent API ──────────────────────────────────────────────────
    size_mb = file_path.stat().st_size / 1024 / 1024 if file_path else 0
    task_or_batch_id = None
    is_batch = False
    submitted_via_cloud = False

    if source_type == "cloud":
        token = _get_cloud_token()
        if not token or len(token) < 50:
            raise RuntimeError("云端 API 需要配置 MINERU_API_TOKEN")
        try:
            if is_url:
                task_or_batch_id = _submit_url_cloud(source, is_ocr, model)
            else:
                task_or_batch_id = _submit_file_cloud(file_path, is_ocr, model)
                is_batch = True
            submitted_via_cloud = True
        except Exception as e:
            print(f"[MinerU] 云端 API 失败 ({e})，降级到 Agent API...")

    if task_or_batch_id is None:
        if file_path and size_mb > 10:
            raise RuntimeError(
                f"文件 {size_mb:.1f}MB 超过 Agent API 限制(10MB)，请使用 modal 或 cloud API"
            )
        if is_url:
            task_or_batch_id = _submit_url_agent(source, is_ocr, model)
        else:
            task_or_batch_id = _submit_file_agent(file_path, is_ocr, model)

    # 轮询结果
    if submitted_via_cloud and is_batch:
        result = _poll_cloud_batch(task_or_batch_id, poll_interval, timeout)
    elif submitted_via_cloud:
        result = _poll_cloud_task(task_or_batch_id, poll_interval, timeout)
    else:
        result = _poll_agent_task(task_or_batch_id, poll_interval, timeout)

    return download_result(result, output_dir)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinerU PDF 解析（支持三种 API）")
    parser.add_argument("source", help="PDF 文件路径或 URL")
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR")
    parser.add_argument("--model", default="vlm", choices=["pipeline", "vlm"])
    parser.add_argument("--timeout", type=int, default=600, help="超时秒数")
    parser.add_argument("--api", choices=["modal", "cloud", "agent"], help="指定 API 来源")
    args = parser.parse_args()

    result_dir = parse_pdf(
        source=args.source,
        output_dir=Path(args.output),
        is_ocr=args.ocr,
        model=args.model,
        timeout=args.timeout,
        api_source=args.api,
    )
    print(f"\n✅ 解析完成，结果在: {result_dir}")
