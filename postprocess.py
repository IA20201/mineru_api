"""MinerU Markdown 后处理：图片本地化、去重复页眉、清理格式。"""

import re
import shutil
import urllib.parse
from collections import Counter
from pathlib import Path

import requests

# ── 配置 ─────────────────────────────────────────────────────────────────────
# 重复页眉检测参数
REPEATED_LINE_MIN_COUNT = 3   # 全文出现 ≥ 此次数即视为重复（≥3 避免误删短标题）
REPEATED_LINE_MAX_LEN = 30    # 去掉 # 前缀后，长度 ≤ 此值才视为页眉

# 白名单：这些短行即使重复出现也不删除（论文常见章节标题）
HEADER_WHITELIST: set[str] = {
    "摘要", "Abstract", "ABSTRACT",
    "引言", "Introduction",
    "结论", "Conclusion", "Conclusions",
    "参考文献", "References",
    "致谢", "Acknowledgments",
    "附录", "Appendix",
    "目录", "Table of Contents",
}

# 图片 URL 匹配正则（支持 http/https）
IMAGE_URL_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^\)]+)\)")


# ── 图片本地化 ───────────────────────────────────────────────────────────────
def download_images(md_text: str, images_dir: Path) -> str:
    """下载 Markdown 中所有远程图片到本地，返回替换后的文本。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, str] = {}
    seen_filenames: set[str] = set()

    for match in IMAGE_URL_RE.finditer(md_text):
        alt, url = match.group(1), match.group(2)
        if url in replacements:
            continue

        filename = _extract_filename(url)
        # 处理同名文件：加短 hash 后缀
        if filename in seen_filenames:
            name_hash = str(hash(url))[-8:]
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            filename = f"{stem}_{name_hash}{suffix}"
        seen_filenames.add(filename)

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

        rel_path = f"images/{filename}"
        replacements[url] = rel_path

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


# ── 去重复页眉/页脚（通用检测）──────────────────────────────────────────────
def remove_repeated_headers(md_text: str) -> str:
    """自动检测并删除全文中重复出现的短行（页眉/页脚）。

    规则：
    - 去掉 # 前缀和空白后，长度 ≤ REPEATED_LINE_MAX_LEN 的行
    - 全文出现 ≥ REPEATED_LINE_MIN_COUNT 次
    - 排除空行和纯数字行
    """
    lines = md_text.split("\n")

    # 提取每行的"内容核心"（去掉 # 前缀和首尾空白）
    def core_text(line: str) -> str:
        return re.sub(r"^#{1,6}\s*", "", line.strip())

    # 统计核心文本出现次数（只统计短行，排除白名单）
    short_line_counts: Counter[str] = Counter()
    for line in lines:
        core = core_text(line)
        if core and len(core) <= REPEATED_LINE_MAX_LEN and not core.isdigit() and core not in HEADER_WHITELIST:
            short_line_counts[core] += 1

    # 找出需要删除的核心文本
    to_remove: set[str] = set()
    for core, count in short_line_counts.items():
        if count >= REPEATED_LINE_MIN_COUNT:
            to_remove.add(core)

    if not to_remove:
        return md_text

    # 删除匹配的行
    new_lines = []
    for line in lines:
        core = core_text(line)
        if core in to_remove:
            continue
        new_lines.append(line)

    removed = len(lines) - len(new_lines)
    print(f"  检测到 {len(to_remove)} 种重复短行，共删除 {removed} 行")
    for core in to_remove:
        print(f"    - \"{core}\" ({short_line_counts[core]} 次)")

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


# ── 复制本地图片 ────────────────────────────────────────────────────────────
def _copy_local_images(raw_dir: Path, images_dir: Path):
    """复制 raw 目录中已有的本地图片到输出 images 目录。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    # 只搜索 raw_dir 直接子目录中的 images/，避免误匹配输出目录
    for src_images in raw_dir.rglob("images"):
        if not src_images.is_dir():
            continue
        # 跳过输出目录自身的 images
        try:
            src_images.resolve().relative_to(images_dir.resolve())
            continue
        except ValueError:
            pass

        for img_file in src_images.iterdir():
            if img_file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
                dst = images_dir / img_file.name
                if not dst.exists():
                    shutil.copy2(img_file, dst)
                    copied += 1
                    print(f"  复制图片: {img_file.name}")
    if copied:
        print(f"  共复制 {copied} 张本地图片")


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

    md_text = md_path.read_text(encoding="utf-8")

    # 1. 下载远程图片并本地化
    print("\n🖼️  图片本地化...")
    md_text = download_images(md_text, images_dir)

    # 1b. 复制 raw 目录中的本地图片到输出目录
    _copy_local_images(raw_dir, images_dir)

    # 2. 去重复页眉/页脚（通用检测）
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
