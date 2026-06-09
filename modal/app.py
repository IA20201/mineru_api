"""MinerU Modal 部署 — 本地 PDF 解析服务。

部署方式：
    modal deploy modal/app.py

API 认证：
    - 需要设置 Modal Secret: mineru-api-key
    - 请求时添加 Header: X-API-Key: <your-key>
"""

import modal

app = modal.App("mineru-api")

# Volume 存储模型
volume = modal.Volume.from_name("mineru-models", create_if_missing=True)
MODEL_DIR = "/root/.cache/modelscope"

# API Key Secret
api_key_secret = modal.Secret.from_name("mineru-api-key")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install("mineru[all]", "fastapi[standard]")
    .env({
        "MINERU_MODEL_SOURCE": "local",
        "MINERU_TOOLS_CONFIG_JSON": f"{MODEL_DIR}/mineru.json",
    })
)


@app.function(
    image=image,
    gpu="L4",
    timeout=600,
    scaledown_window=300,
    volumes={MODEL_DIR: volume},
    memory=16384,
    secrets=[api_key_secret],
)
@modal.concurrent(max_inputs=5)
@modal.asgi_app()
def fastapi_app():
    import os
    import logging
    import tempfile
    from pathlib import Path
    from typing import Literal
    from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Depends
    from fastapi.responses import JSONResponse

    # 配置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # 从环境变量读取 API Key
    API_KEY = os.environ.get("MINERU_API_KEY", "")

    # 文件大小限制 100MB
    MAX_FILE_SIZE = 100 * 1024 * 1024

    web_app = FastAPI(title="MinerU API")

    async def verify_api_key(x_api_key: str = Header(None)):
        """验证 API Key（FastAPI 依赖注入）"""
        if API_KEY and x_api_key != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API Key")

    @web_app.get("/health")
    async def health():
        """健康检查（无需认证）"""
        return {"status": "ok"}

    @web_app.get("/")
    async def root():
        """服务信息（无需认证）"""
        return {
            "message": "MinerU 本体 — 本地解析",
            "usage": "POST /parse",
            "auth": "Header: X-API-Key",
        }

    @web_app.post("/parse")
    async def parse_pdf(
        file: UploadFile = File(...),
        backend: Literal["pipeline", "vlm"] = Form("pipeline"),
        is_ocr: bool = Form(False),
        enable_table: bool = Form(True),
        enable_formula: bool = Form(True),
        language: Literal["ch", "en"] = Form("ch"),
        _: None = Depends(verify_api_key),
    ):
        """PDF 解析（需要 API Key）"""
        from mineru.cli.common import do_parse

        # 验证文件类型
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "仅支持 PDF 文件"},
            )

        # 读取文件内容
        content = await file.read()

        # 验证文件大小
        if len(content) > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=413,
                content={"success": False, "error": f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"},
            )

        # 安全文件名（防止路径遍历）
        safe_name = Path(file.filename).name

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_path = tmp_path / safe_name
            pdf_path.write_bytes(content)

            output_path = tmp_path / "output"
            output_path.mkdir()
            file_name = pdf_path.stem
            parse_method = "ocr" if is_ocr else "auto"

            try:
                do_parse(
                    output_dir=str(output_path),
                    pdf_file_names=[file_name],
                    pdf_bytes_list=[content],
                    p_lang_list=[language],
                    backend=backend,
                    parse_method=parse_method,
                    p_formula_enable=enable_formula,
                    p_table_enable=enable_table,
                    f_dump_md=True,
                    f_dump_middle_json=False,
                    f_dump_model_output=False,
                    f_dump_orig_pdf=False,
                    f_dump_content_list=False,
                    f_draw_layout_bbox=False,
                    f_draw_span_bbox=False,
                )

                md_files = list(output_path.rglob("*.md"))
                if not md_files:
                    return JSONResponse(
                        status_code=500,
                        content={"success": False, "error": "未生成 markdown"},
                    )

                md_content = md_files[0].read_text(encoding="utf-8")
                return JSONResponse(content={
                    "success": True,
                    "filename": file.filename,
                    "backend": backend,
                    "markdown": md_content,
                })

            except Exception as e:
                # 记录详细错误到日志，不返回给客户端
                logger.exception("PDF 解析失败")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": "内部服务器错误"},
                )

    return web_app
