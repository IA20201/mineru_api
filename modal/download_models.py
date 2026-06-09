"""全面下载 MinerU 所有模型到 Modal Volume。

用法：
    modal run modal/download_models.py
"""

import modal

app = modal.App("mineru-download-models")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install("mineru[all]")
    .env({"MINERU_MODEL_SOURCE": "modelscope"})
)

volume = modal.Volume.from_name("mineru-models", create_if_missing=True)
MODEL_DIR = "/root/.cache/modelscope"


@app.function(
    image=image,
    gpu="L4",
    timeout=3600,
    volumes={MODEL_DIR: volume},
)
def download_models():
    """下载所有 MinerU 模型到 Volume。"""
    import os
    import tempfile

    os.environ["MINERU_MODEL_SOURCE"] = "modelscope"

    # 用 modelscope SDK 下载所有模型
    from modelscope import snapshot_download

    print("下载 PDF-Extract-Kit 模型...")
    model_dir = snapshot_download("OpenDataLab/PDF-Extract-Kit-1.0", cache_dir=MODEL_DIR)
    print(f"模型已下载到: {model_dir}")

    # 额外下载 paddleocr_torch 模型（pipeline 后端需要）
    print("\n下载 paddleocr_torch 模型...")
    try:
        snapshot_download("OpenDataLab/PDF-Extract-Kit-1.0", cache_dir=MODEL_DIR,
                         include=["*paddleocr*", "*PaddleOCR*", "*ppocr*"])
    except Exception as e:
        print(f"paddleocr 下载警告: {e}")

    # 列出下载结果
    print("\n模型目录内容:")
    base = os.path.join(MODEL_DIR, "hub", "models", "OpenDataLab")
    if os.path.exists(base):
        for item in os.listdir(base):
            print(f"  {item}")

    volume.commit()
    print("\n✅ 所有模型已保存到 Volume 'mineru-models'")


@app.local_entrypoint()
def main():
    download_models.remote()
