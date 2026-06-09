"""上传本地模型到 Modal Volume。

用法：
    modal run modal/upload_models.py --local-models-dir ./models/OpenDataLab/PDF-Extract-Kit-1___0
"""

import modal
import os

app = modal.App("mineru-upload-models")
volume = modal.Volume.from_name("mineru-models", create_if_missing=True)


@app.function(volumes={"/models": volume}, timeout=3600)
def upload_from_local(local_models_dir: str):
    """在容器内列出 Volume 内容，检查是否完整。"""
    import subprocess

    # 先列出 Volume 当前内容
    target = "/models/hub/models/OpenDataLab/PDF-Extract-Kit-1.0"
    if os.path.exists(target):
        print("Volume 已有模型目录，列出内容：")
        for root, dirs, files in os.walk(target):
            level = root.replace(target, "").count(os.sep)
            if level <= 3:
                indent = " " * 2 * level
                print(f"{indent}{os.path.basename(root)}/")
                for f in files:
                    fpath = os.path.join(root, f)
                    size = os.path.getsize(fpath)
                    print(f"{indent}  {f} ({size / 1024 / 1024:.1f} MB)")
    else:
        print(f"Volume 中没有找到 {target}")

    volume.commit()


@app.local_entrypoint()
def main(local_models_dir: str = ""):
    upload_from_local.remote(local_models_dir)
