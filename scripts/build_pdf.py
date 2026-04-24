#!/usr/bin/env python3
"""
将 docs/ 和 interview/ 目录下的 Markdown 文件转换为 PDF。

依赖（默认引擎 playwright，无需 GTK）:
    pip install markdown latex2mathml playwright
    playwright install chromium

可选：使用 WeasyPrint 引擎（Windows 上需额外安装 GTK3 Runtime）:
    pip install "weasyprint>=60"
    # 下载 GTK3 Runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

使用方法:
    python scripts/build_pdf.py                        # playwright（默认）
    python scripts/build_pdf.py --combined             # 同时生成合并版完整 PDF
    python scripts/build_pdf.py --engine weasyprint    # 使用 WeasyPrint

输出:
    dist/pdf/ 目录下生成所有 PDF 文件
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
INTERVIEW_DIR = ROOT / "interview"
OUTPUT_DIR = ROOT / "dist" / "pdf"

CSS = """
@page { size: A4; margin: 2cm; }
body {
    font-family: "Microsoft YaHei", "Noto Sans SC", "PingFang SC", sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    color: #1e293b;
}
h1 { font-size: 20pt; color: #4f46e5; border-bottom: 2px solid #4f46e5; padding-bottom: 6pt; margin-top: 24pt; }
h2 { font-size: 16pt; color: #334155; border-left: 4px solid #4f46e5; padding-left: 8pt; margin-top: 20pt; }
h3 { font-size: 13pt; margin-top: 16pt; }
code { background: #f1f5f9; padding: 1pt 4pt; border-radius: 3pt; font-size: 9.5pt; font-family: Consolas, monospace; }
pre { background: #1e293b; color: #e2e8f0; padding: 12pt; border-radius: 6pt; font-size: 9pt; line-height: 1.4; overflow-wrap: break-word; white-space: pre-wrap; }
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
table { width: 100%; border-collapse: collapse; font-size: 10pt; margin: 8pt 0; }
th, td { border: 1px solid #e2e8f0; padding: 5pt 8pt; text-align: left; }
th { background: #eef2ff; }
blockquote { border-left: 3px solid #4f46e5; background: #eef2ff; padding: 8pt 12pt; margin: 8pt 0; }
img { max-width: 100%; height: auto; }
strong { color: #4f46e5; }
/* details/summary（课后题答案） */
details { border-left: 3px solid #10b981; background: #f0fdf4; padding: 8pt 12pt; margin: 8pt 0; border-radius: 0 6pt 6pt 0; }
details summary { font-weight: 600; color: #059669; margin-bottom: 6pt; }
/* MathML */
math { font-size: 1em; }
math[display="block"] { display: block; text-align: center; margin: 1em 0; overflow-x: auto; }
"""


# ---------------------------------------------------------------------------
# 数学公式预处理：LaTeX → MathML
# ---------------------------------------------------------------------------

def _latex_to_mathml(latex: str, display: bool = False) -> str:
    """将 LaTeX 转换为 MathML。未安装 latex2mathml 时退化为高亮 <code>。"""
    try:
        import latex2mathml.converter
        return latex2mathml.converter.convert(
            latex.strip(),
            display="block" if display else "inline",
        )
    except ImportError:
        delim = "$$" if display else "$"
        return (
            f'<code style="color:#b45309;background:#fef3c7;'
            f'padding:1pt 4pt;border-radius:3pt">'
            f"{delim}{latex.strip()}{delim}</code>"
        )
    except Exception:
        delim = "$$" if display else "$"
        return f'<code style="color:#94a3b8">{delim}{latex.strip()}{delim}</code>'


def _preprocess_math(md_text: str) -> tuple[str, list[tuple[str, bool]]]:
    """将 LaTeX 数学公式替换为 HTML 注释占位符，跳过代码块。"""
    math_list: list[tuple[str, bool]] = []
    stash: dict[str, str] = {}
    counter = [0]

    def _stash(m: re.Match) -> str:
        key = f"XSTASHX{counter[0]:06d}X"
        stash[key] = m.group(0)
        counter[0] += 1
        return key

    text = re.sub(r"```[\s\S]*?```", _stash, md_text)
    text = re.sub(r"~~~[\s\S]*?~~~", _stash, text)
    text = re.sub(r"`[^`\n]+`", _stash, text)

    def _store(latex: str, display: bool) -> str:
        idx = len(math_list)
        math_list.append((latex, display))
        return f"<!--MATHPH_{idx}-->"

    # 块级先处理，避免 $$ 被行内 $ 误匹配
    text = re.sub(r"\$\$([\s\S]+?)\$\$", lambda m: _store(m.group(1), True), text)
    text = re.sub(r"\\\[([\s\S]+?)\\\]", lambda m: _store(m.group(1), True), text)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: _store(m.group(1), False), text)
    text = re.sub(
        r"(?<!\$)\$(?!\$)([^\n$]{1,300}?)(?<!\$)\$(?!\$)",
        lambda m: _store(m.group(1), False),
        text,
    )

    for key, val in stash.items():
        text = text.replace(key, val)

    return text, math_list


def _restore_math(html: str, math_list: list[tuple[str, bool]]) -> str:
    def _replace(m: re.Match) -> str:
        latex, display = math_list[int(m.group(1))]
        return _latex_to_mathml(latex, display)
    return re.sub(r"<!--MATHPH_(\d+)-->", _replace, html)


def _md_to_html(md_text: str) -> str:
    """Markdown → HTML（含数学公式预处理）。"""
    import markdown
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension

    processed_md, math_list = _preprocess_math(md_text)
    html_body = markdown.markdown(
        processed_md,
        extensions=[FencedCodeExtension(), TableExtension()],
    )
    return _restore_math(html_body, math_list)


def _make_full_html(html_body: str) -> str:
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">'
        f'<head><meta charset="utf-8"><style>{CSS}</style></head>'
        f"<body>{html_body}</body></html>"
    )


# ---------------------------------------------------------------------------
# 构建函数
# ---------------------------------------------------------------------------

def build_with_playwright(source_dirs=None, out_suffix=""):
    """使用 Playwright + Chromium 生成 PDF（推荐，无需 GTK）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请安装依赖:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    if source_dirs is None:
        source_dirs = [DOCS_DIR, INTERVIEW_DIR]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    count = errors = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for source_dir in source_dirs:
            if not source_dir.exists():
                continue
            for md_path in sorted(source_dir.glob("*.md")):
                try:
                    md_text = md_path.read_text(encoding="utf-8")
                    full_html = _make_full_html(_md_to_html(md_text))

                    page = browser.new_page()
                    page.set_content(full_html, wait_until="load")
                    # 强制展开所有 <details>，确保答案在 PDF 中可见
                    page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                    pdf_path = OUTPUT_DIR / (md_path.stem + out_suffix + ".pdf")
                    page.pdf(
                        path=str(pdf_path),
                        format="A4",
                        margin={"top": "2cm", "bottom": "2cm",
                                "left": "2cm", "right": "2cm"},
                        print_background=True,
                    )
                    page.close()
                    count += 1
                    print(f"  [ok] {pdf_path.name}")
                except Exception as e:
                    errors += 1
                    print(f"  [fail] {md_path.name}: {e}")

        browser.close()

    print(f"\n完成：已生成 {count} 个 PDF 文件到 {OUTPUT_DIR}")
    if errors:
        print(f"  {errors} 个文件生成失败")


def build_with_weasyprint():
    """使用 WeasyPrint 生成 PDF（需要 GTK3，Windows 上配置较复杂）。"""
    # Windows: 尝试常见的 GTK3 安装路径
    if sys.platform == "win32":
        gtk_candidates = [
            r"C:\Program Files\GTK3-Runtime Win64\bin",
            r"C:\GTK3-Runtime Win64\bin",
            r"C:\msys64\mingw64\bin",
            r"E:\GTK3-Runtime Win64\bin",
        ]
        gtk_found = False
        for path in gtk_candidates:
            if os.path.isdir(path):
                os.add_dll_directory(path)
                gtk_found = True
                break
        if not gtk_found:
            print("未找到 GTK3 Runtime，WeasyPrint 在 Windows 上需要 GTK3。")
            print("请从以下地址下载并安装后重试：")
            print("  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer")
            print()
            print("或改用 playwright 引擎（无需 GTK）：")
            print("  pip install playwright && playwright install chromium")
            print("  python scripts/build_pdf.py --engine playwright")
            sys.exit(1)

    try:
        from weasyprint import HTML as WHTML
    except (ImportError, OSError) as e:
        print(f"WeasyPrint 加载失败: {e}")
        print("建议改用 playwright 引擎（无需 GTK）：")
        print("  pip install playwright && playwright install chromium")
        print("  python scripts/build_pdf.py")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for source_dir in [DOCS_DIR, INTERVIEW_DIR]:
        if not source_dir.exists():
            continue
        for md_path in sorted(source_dir.glob("*.md")):
            md_text = md_path.read_text(encoding="utf-8")
            full_html = _make_full_html(_md_to_html(md_text))
            pdf_path = OUTPUT_DIR / (md_path.stem + ".pdf")
            WHTML(string=full_html, base_url=str(ROOT)).write_pdf(str(pdf_path))
            count += 1
            print(f"  [ok] {pdf_path.name}")

    print(f"\n完成：已生成 {count} 个 PDF 文件到 {OUTPUT_DIR}")


def build_combined_pdf(engine: str = "playwright"):
    """生成合并版完整 PDF（所有课程 + 面试题）。"""
    try:
        from playwright.sync_api import sync_playwright
        _use_playwright = engine != "weasyprint"
    except ImportError:
        _use_playwright = False

    all_html_parts = []
    for source_dir in [DOCS_DIR, INTERVIEW_DIR]:
        if not source_dir.exists():
            continue
        for md_path in sorted(source_dir.glob("*.md")):
            html = _md_to_html(md_path.read_text(encoding="utf-8"))
            all_html_parts.append(f'<div style="page-break-before:always">{html}</div>')

    cover = (
        '<div style="text-align:center;padding:200pt 0">'
        '<h1 style="font-size:32pt;border:none">MiniMind 面试学习指南</h1>'
        '<p style="font-size:14pt;color:#64748b;margin-top:20pt">从零开始学习 64M 参数大语言模型</p>'
        '<p style="font-size:12pt;color:#94a3b8;margin-top:40pt">面试导向 · 小白友好 · 全链路覆盖</p>'
        "</div>"
    )
    combined_html = _make_full_html(cover + "".join(all_html_parts))
    pdf_path = OUTPUT_DIR / "MiniMind面试学习指南-完整版.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if _use_playwright:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(combined_html, wait_until="load")
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "2cm", "bottom": "2cm",
                        "left": "2cm", "right": "2cm"},
                print_background=True,
            )
            browser.close()
    else:
        from weasyprint import HTML as WHTML
        WHTML(string=combined_html, base_url=str(ROOT)).write_pdf(str(pdf_path))

    print(f"完整版 PDF: {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Markdown to PDF converter")
    parser.add_argument(
        "--engine",
        choices=["playwright", "weasyprint"],
        default="playwright",
        help="PDF 生成引擎 (默认: playwright，无需 GTK)",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="同时生成合并版完整 PDF",
    )
    args = parser.parse_args()

    if args.engine == "playwright":
        build_with_playwright()
    else:
        build_with_weasyprint()

    if args.combined:
        build_combined_pdf(engine=args.engine)
