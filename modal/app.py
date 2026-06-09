"""MinerU Modal 部署 — 本地 PDF 解析服务。

部署方式：
    modal deploy modal/app.py
"""

import modal

app = modal.App("mineru-api")

# Volume 存储模型
volume = modal.Volume.from_name("mineru-models", create_if_missing=True)
MODEL_DIR = "/root/.cache/modelscope"

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
)
@modal.concurrent(max_inputs=5)
@modal.asgi_app()
def fastapi_app():
    import tempfile
    import traceback
    from pathlib import Path
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import JSONResponse

    web_app = FastAPI(title="MinerU API")

    @web_app.get("/health")
    async def health():
        return {"status": "ok"}

    @web_app.get("/")
    async def root():
        return {"message": "MinerU 本体 — 本地解析", "usage": "POST /parse"}

    @web_app.post("/parse")
    async def parse_pdf(
        file: UploadFile = File(...),
        backend: str = Form("pipeline"),
        is_ocr: bool = Form(False),
        enable_table: bool = Form(True),
        enable_formula: bool = Form(True),
        language: str = Form("ch"),
    ):
        from mineru.cli.common import do_parse

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_path = tmp_path / file.filename
            content = await file.read()
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
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e), "traceback": traceback.format_exc()[-2000:]},
                )

    return web_app
