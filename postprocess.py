"""MinerU Markdown 后处理：图片本地化、去重复页眉、清理格式。"""

import re
import urllib.parse
from pathlib import Path

import requests

# ── 配置 ─────────────────────────────────────────────────────────────────────
# 需要删除的重复页眉/页脚模式（每行独立匹配，全文出现 ≥2 次即删除）
REPEATED_HEADER_PATTERNS = [
    r"^#\s*工商管理\s*$",
    r"^#\s*管理世界\s*$",
    r"^#\s*南开管理评论\s*$",
    r"^#\s*科研管理\s*$",
    r"^#\s*科学学研究\s*$",
]

# 图片 URL 匹配正则
IMAGE_URL_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^\)]+)\)")


# ── 图片本地化 ───────────────────────────────────────────────────────────────
def download_images(md_text: str, images_dir: Path) -> str:
    """下载 Markdown 中所有远程图片到本地，返回替换后的文本。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, str] = {}

    for match in IMAGE_URL_RE.finditer(md_text):
        alt, url = match.group(1), match.group(2)
        if url in replacements:
            continue

        # 从 URL 提取文件名
        filename = _extract_filename(url)
        local_path = images_dir / filename

        if not local_path.exists():
            print(f"  下载图片: {filename}")
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
            except Exception as e:
                print(f"  ⚠️ 下载失败 {url}: {e}")
                continue
        else:
            print(f"  跳过已存在: {filename}")

        # 替换为相对路径
        rel_path = f"images/{filename}"
        replacements[url] = rel_path

    # 执行替换
    for url, rel in replacements.items():
        md_text = md_text.replace(url, rel)

    print(f"  共处理 {len(replacements)} 张图片")
    return md_text


def _extract_filename(url: str) -> str:
    """从 URL 提取文件名，保留原始扩展名。"""
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name
    if not filename or "." not in filename:
        filename = url.split("/")[-1][:64]
    return filename


# ── 去重复页眉/页脚 ─────────────────────────────────────────────────────────
def remove_repeated_headers(md_text: str) -> str:
    """删除全文中出现 ≥2 次的期刊页眉行。"""
    lines = md_text.split("\n")

    # 统计每个模式出现的次数
    pattern_counts: dict[str, int] = {}
    for pattern in REPEATED_HEADER_PATTERNS:
        count = sum(1 for line in lines if re.match(pattern, line.strip()))
        if count >= 2:
            pattern_counts[pattern] = count

    if not pattern_counts:
        return md_text

    # 删除匹配的行
    new_lines = []
    for line in lines:
        should_remove = False
        for pattern in pattern_counts:
            if re.match(pattern, line.strip()):
                should_remove = True
                break
        if not should_remove:
            new_lines.append(line)

    removed = len(lines) - len(new_lines)
    for pat, cnt in pattern_counts.items():
        print(f"  删除重复页眉 '{pat}': {cnt} 次")
    print(f"  共删除 {removed} 行")

    return "\n".join(new_lines)


# ── 清理空行 ────────────────────────────────────────────────────────────────
def clean_blank_lines(md_text: str, max_consecutive: int = 2) -> str:
    """将连续超过 max_consecutive 个空行压缩为 max_consecutive 个。"""
    pattern = r"\n{" + str(max_consecutive + 1) + r",}"
    replacement = "\n" * max_consecutive
    cleaned = re.sub(pattern, replacement, md_text)
    diff = len(md_text) - len(cleaned)
    if diff > 0:
        print(f"  清理多余空行: 节省 {diff} 字符")
    return cleaned


# ── 主处理流程 ──────────────────────────────────────────────────────────────
def postprocess(raw_dir: Path, output_dir: Path, paper_name: str) -> Path:
    """
    对 MinerU 解析结果进行后处理。

    Args:
        raw_dir: MinerU 解压后的原始目录（含 markdown 和图片）
        output_dir: 最终输出目录
        paper_name: 论文名称（用于输出文件名）

    Returns:
        处理后的 markdown 文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"

    # 查找原始 markdown 文件
    md_files = list(raw_dir.rglob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"未找到 markdown 文件: {raw_dir}")

    md_path = md_files[0]
    print(f"\n📄 处理文件: {md_path.name}")

    # 读取原始内容
    md_text = md_path.read_text(encoding="utf-8")

    # 1. 下载图片并本地化（处理远程 URL）
    print("\n🖼️  图片本地化...")
    md_text = download_images(md_text, images_dir)

    # 1b. 复制 raw 目录中的本地图片到输出目录
    _copy_local_images(raw_dir, images_dir)

    # 2. 去重复页眉/页脚
    print("\n🧹 去除重复页眉...")
    md_text = remove_repeated_headers(md_text)

    # 3. 清理多余空行
    print("\n✨ 清理格式...")
    md_text = clean_blank_lines(md_text)

    # 写入输出
    output_path = output_dir / f"{paper_name}.md"
    output_path.write_text(md_text, encoding="utf-8")
    print(f"\n✅ 输出: {output_path}")

    return output_path


def _copy_local_images(raw_dir: Path, images_dir: Path):
    """复制 raw 目录中已有的本地图片到输出 images 目录。"""
    import shutil
    images_dir.mkdir(parents=True, exist_ok=True)
    # 查找 raw 下所有 images 子目录
    for src_images in raw_dir.rglob("images"):
        if not src_images.is_dir():
            continue
        for img_file in src_images.iterdir():
            if img_file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
                dst = images_dir / img_file.name
                if not dst.exists():
                    shutil.copy2(img_file, dst)
                    print(f"  复制图片: {img_file.name}")


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinerU Markdown 后处理")
    parser.add_argument("raw_dir", help="MinerU 解压后的原始目录")
    parser.add_argument("-o", "--output", required=True, help="输出目录")
    parser.add_argument("-n", "--name", required=True, help="论文名称")
    args = parser.parse_args()

    postprocess(
        raw_dir=Path(args.raw_dir),
        output_dir=Path(args.output),
        paper_name=args.name,
    )
