"""
DATA-AI 文档处理工具

提供 PDF、Markdown、HTML 等文档的解析和处理能力。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ...utils.exceptions import ToolException
from ...utils.logging import get_logger
from .registry import BaseTool, ToolParameter

logger = get_logger(__name__)


# ============================================================================
# PDF 工具
# ============================================================================


class PDFReadTool(BaseTool):
    """
    PDF 文档读取工具

    支持读取 PDF 文件内容，提取文本和元数据。
    """

    name = "pdf_read"
    description = "读取 PDF 文件内容，提取文本和元数据"
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="PDF 文件路径",
            required=True,
        ),
        ToolParameter(
            name="pages",
            type="string",
            description="要读取的页码范围，如 '1-5' 或 '1,3,5'，默认读取全部",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="extract_images",
            type="boolean",
            description="是否提取图片信息",
            required=False,
            default=False,
        ),
    ]
    category = "document"

    async def execute(
        self,
        file_path: str,
        pages: str | None = None,
        extract_images: bool = False,
    ) -> dict[str, Any]:
        """执行 PDF 读取"""
        path = Path(file_path)

        if not path.exists():
            raise ToolException(f"文件不存在: {file_path}")

        if not path.suffix.lower() == ".pdf":
            raise ToolException(f"不是 PDF 文件: {file_path}")

        result = {
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "pages": [],
            "metadata": {},
            "total_pages": 0,
        }

        try:
            # 尝试使用 pypdf
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                result["total_pages"] = len(reader.pages)

                # 提取元数据
                if reader.metadata:
                    result["metadata"] = {
                        "title": reader.metadata.get("/Title", ""),
                        "author": reader.metadata.get("/Author", ""),
                        "subject": reader.metadata.get("/Subject", ""),
                        "creator": reader.metadata.get("/Creator", ""),
                        "producer": reader.metadata.get("/Producer", ""),
                        "creation_date": str(reader.metadata.get("/CreationDate", "")),
                    }

                # 解析页码范围
                page_indices = self._parse_page_range(pages, len(reader.pages))

                # 提取文本
                for idx in page_indices:
                    page = reader.pages[idx]
                    text = page.extract_text() or ""

                    page_info = {
                        "page_number": idx + 1,
                        "text": text.strip(),
                        "char_count": len(text.strip()),
                    }

                    # 提取图片信息
                    if extract_images:
                        images = []
                        if hasattr(page, "images"):
                            for img in page.images:
                                images.append(
                                    {
                                        "name": getattr(img, "name", "unknown"),
                                        "size": len(img.data) if hasattr(img, "data") else 0,
                                    }
                                )
                        page_info["images"] = images

                    result["pages"].append(page_info)

            except ImportError:
                # 回退到 PyMuPDF
                try:
                    import fitz  # PyMuPDF

                    doc = fitz.open(str(path))
                    result["total_pages"] = len(doc)

                    # 提取元数据
                    result["metadata"] = {
                        "title": doc.metadata.get("title", ""),
                        "author": doc.metadata.get("author", ""),
                        "subject": doc.metadata.get("subject", ""),
                        "creator": doc.metadata.get("creator", ""),
                        "producer": doc.metadata.get("producer", ""),
                    }

                    page_indices = self._parse_page_range(pages, len(doc))

                    for idx in page_indices:
                        page = doc[idx]
                        text = page.get_text()

                        page_info = {
                            "page_number": idx + 1,
                            "text": text.strip(),
                            "char_count": len(text.strip()),
                        }

                        if extract_images:
                            images = page.get_images()
                            page_info["images"] = [{"count": len(images)}]

                        result["pages"].append(page_info)

                    doc.close()

                except ImportError:
                    raise ToolException(
                        "PDF 处理库未安装。请安装 pypdf 或 PyMuPDF: pip install pypdf 或 pip install pymupdf"
                    )

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"PDF 读取失败: {str(e)}")

    def _parse_page_range(
        self,
        pages: str | None,
        total: int,
    ) -> list[int]:
        """解析页码范围"""
        if not pages:
            return list(range(total))

        indices = []

        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start = int(start) - 1
                end = int(end)
                indices.extend(range(max(0, start), min(end, total)))
            else:
                idx = int(part) - 1
                if 0 <= idx < total:
                    indices.append(idx)

        return sorted(set(indices))


class PDFExtractTool(BaseTool):
    """
    PDF 内容提取工具

    从 PDF 中提取特定内容，如表格、图片等。
    """

    name = "pdf_extract"
    description = "从 PDF 文件中提取表格、图片等特定内容"
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="PDF 文件路径",
            required=True,
        ),
        ToolParameter(
            name="extract_type",
            type="string",
            description="提取类型: tables, images, links, all",
            required=False,
            default="all",
        ),
    ]
    category = "document"

    async def execute(
        self,
        file_path: str,
        extract_type: str = "all",
    ) -> dict[str, Any]:
        """执行内容提取"""
        path = Path(file_path)

        if not path.exists():
            raise ToolException(f"文件不存在: {file_path}")

        result = {
            "file_path": str(path.absolute()),
            "extract_type": extract_type,
            "tables": [],
            "images": [],
            "links": [],
        }

        try:
            # 使用 PyMuPDF 提取
            try:
                import fitz

                doc = fitz.open(str(path))

                for page_num, page in enumerate(doc):
                    # 提取表格
                    if extract_type in ("tables", "all"):
                        tables = page.find_tables()
                        for table in tables:
                            result["tables"].append(
                                {
                                    "page": page_num + 1,
                                    "content": table.extract(),
                                }
                            )

                    # 提取图片
                    if extract_type in ("images", "all"):
                        images = page.get_images()
                        for img in images:
                            result["images"].append(
                                {
                                    "page": page_num + 1,
                                    "xref": img[0],
                                }
                            )

                    # 提取链接
                    if extract_type in ("links", "all"):
                        links = page.get_links()
                        for link in links:
                            if "uri" in link:
                                result["links"].append(
                                    {
                                        "page": page_num + 1,
                                        "uri": link["uri"],
                                    }
                                )

                doc.close()

            except ImportError:
                raise ToolException("PDF 内容提取需要 PyMuPDF: pip install pymupdf")

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"PDF 内容提取失败: {str(e)}")


# ============================================================================
# Markdown 工具
# ============================================================================


class MarkdownReadTool(BaseTool):
    """
    Markdown 文档读取工具

    解析 Markdown 文件，提取结构化内容。
    """

    name = "markdown_read"
    description = "读取并解析 Markdown 文件，提取标题、段落、代码块等结构化内容"
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Markdown 文件路径",
            required=True,
        ),
        ToolParameter(
            name="extract_code_blocks",
            type="boolean",
            description="是否单独提取代码块",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="extract_links",
            type="boolean",
            description="是否提取链接列表",
            required=False,
            default=True,
        ),
    ]
    category = "document"

    async def execute(
        self,
        file_path: str,
        extract_code_blocks: bool = True,
        extract_links: bool = True,
    ) -> dict[str, Any]:
        """执行 Markdown 解析"""
        path = Path(file_path)

        if not path.exists():
            raise ToolException(f"文件不存在: {file_path}")

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            result = {
                "file_path": str(path.absolute()),
                "file_name": path.name,
                "raw_content": content,
                "headings": [],
                "code_blocks": [],
                "links": [],
                "images": [],
                "tables": [],
                "word_count": len(content.split()),
                "char_count": len(content),
            }

            # 提取标题
            heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
            for match in heading_pattern.finditer(content):
                result["headings"].append(
                    {
                        "level": len(match.group(1)),
                        "text": match.group(2).strip(),
                        "position": match.start(),
                    }
                )

            # 提取代码块
            if extract_code_blocks:
                code_block_pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
                for match in code_block_pattern.finditer(content):
                    result["code_blocks"].append(
                        {
                            "language": match.group(1) or "text",
                            "code": match.group(2).strip(),
                            "position": match.start(),
                        }
                    )

            # 提取链接
            if extract_links:
                link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
                for match in link_pattern.finditer(content):
                    url = match.group(2)
                    if url.startswith("http") or url.startswith("/"):
                        result["links"].append(
                            {
                                "text": match.group(1),
                                "url": url,
                            }
                        )
                    elif url.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                        result["images"].append(
                            {
                                "alt": match.group(1),
                                "src": url,
                            }
                        )

            # 提取表格
            table_pattern = re.compile(r"\|.+\|\n\|[-| ]+\|\n((?:\|.+\|\n?)+)", re.MULTILINE)
            for match in table_pattern.finditer(content):
                table_text = match.group(0)
                rows = [row.strip() for row in table_text.split("\n") if row.strip()]
                if len(rows) >= 2:
                    headers = [cell.strip() for cell in rows[0].split("|")[1:-1]]
                    data_rows = []
                    for row in rows[2:]:  # 跳过分隔行
                        cells = [cell.strip() for cell in row.split("|")[1:-1]]
                        if cells:
                            data_rows.append(cells)
                    result["tables"].append(
                        {
                            "headers": headers,
                            "rows": data_rows,
                        }
                    )

            return result

        except Exception as e:
            raise ToolException(f"Markdown 解析失败: {str(e)}")


class MarkdownConvertTool(BaseTool):
    """
    Markdown 转换工具

    将 Markdown 转换为 HTML 或其他格式。
    """

    name = "markdown_convert"
    description = "将 Markdown 转换为 HTML 或其他格式"
    parameters = [
        ToolParameter(
            name="content",
            type="string",
            description="Markdown 内容或文件路径",
            required=True,
        ),
        ToolParameter(
            name="output_format",
            type="string",
            description="输出格式: html, text",
            required=False,
            default="html",
        ),
        ToolParameter(
            name="is_file",
            type="boolean",
            description="content 是否为文件路径",
            required=False,
            default=False,
        ),
    ]
    category = "document"

    async def execute(
        self,
        content: str,
        output_format: str = "html",
        is_file: bool = False,
    ) -> dict[str, Any]:
        """执行转换"""
        try:
            # 读取文件或使用内容
            if is_file:
                path = Path(content)
                if not path.exists():
                    raise ToolException(f"文件不存在: {content}")
                with open(path, encoding="utf-8") as f:
                    md_content = f.read()
            else:
                md_content = content

            result = {
                "output_format": output_format,
                "original_length": len(md_content),
            }

            if output_format == "html":
                # 尝试使用 markdown 库
                try:
                    import markdown

                    html = markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])
                    result["content"] = html
                    result["output_length"] = len(html)
                except ImportError:
                    # 简单转换
                    html = self._simple_md_to_html(md_content)
                    result["content"] = html
                    result["output_length"] = len(html)
                    result["warning"] = "使用简单转换，建议安装 markdown 库: pip install markdown"

            elif output_format == "text":
                # 移除 Markdown 语法
                text = self._strip_markdown(md_content)
                result["content"] = text
                result["output_length"] = len(text)

            else:
                raise ToolException(f"不支持的输出格式: {output_format}")

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Markdown 转换失败: {str(e)}")

    def _simple_md_to_html(self, md: str) -> str:
        """简单的 Markdown 到 HTML 转换"""
        html = md

        # 标题
        for i in range(6, 0, -1):
            html = re.sub(f"^{'#' * i}\\s+(.+)$", f"<h{i}>\\1</h{i}>", html, flags=re.MULTILINE)

        # 粗体和斜体
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

        # 代码块
        html = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

        # 链接
        html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

        # 段落
        paragraphs = html.split("\n\n")
        html = "\n".join(f"<p>{p}</p>" for p in paragraphs if p.strip())

        return html

    def _strip_markdown(self, md: str) -> str:
        """移除 Markdown 语法"""
        text = md

        # 移除标题标记
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # 移除粗体和斜体
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)

        # 移除代码块标记
        text = re.sub(r"```\w*\n?", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # 移除链接，保留文本
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # 移除图片
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)

        return text.strip()


# ============================================================================
# HTML 工具
# ============================================================================


class HTMLReadTool(BaseTool):
    """
    HTML 文档读取工具

    解析 HTML 文件，提取结构化内容。
    """

    name = "html_read"
    description = "读取并解析 HTML 文件，提取文本、链接、图片等结构化内容"
    parameters = [
        ToolParameter(
            name="content",
            type="string",
            description="HTML 内容或文件路径",
            required=True,
        ),
        ToolParameter(
            name="is_file",
            type="boolean",
            description="content 是否为文件路径",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="extract_text",
            type="boolean",
            description="是否提取纯文本",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="extract_links",
            type="boolean",
            description="是否提取链接",
            required=False,
            default=True,
        ),
    ]
    category = "document"

    async def execute(
        self,
        content: str,
        is_file: bool = False,
        extract_text: bool = True,
        extract_links: bool = True,
    ) -> dict[str, Any]:
        """执行 HTML 解析"""
        try:
            # 读取文件或使用内容
            if is_file:
                path = Path(content)
                if not path.exists():
                    raise ToolException(f"文件不存在: {content}")
                with open(path, encoding="utf-8") as f:
                    html_content = f.read()
                file_path = str(path.absolute())
            else:
                html_content = content
                file_path = None

            result = {
                "original_length": len(html_content),
                "text": "",
                "title": "",
                "links": [],
                "images": [],
                "headings": [],
                "meta": {},
            }

            if file_path:
                result["file_path"] = file_path

            # 尝试使用 BeautifulSoup
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")

                # 提取标题
                if soup.title:
                    result["title"] = soup.title.string or ""

                # 提取元数据
                for meta in soup.find_all("meta"):
                    name = meta.get("name") or meta.get("property", "")
                    content_val = meta.get("content", "")
                    if name and content_val:
                        result["meta"][name] = content_val

                # 提取文本
                if extract_text:
                    # 移除脚本和样式
                    for script in soup(["script", "style"]):
                        script.decompose()
                    result["text"] = soup.get_text(separator="\n", strip=True)

                # 提取链接
                if extract_links:
                    for a in soup.find_all("a", href=True):
                        result["links"].append(
                            {
                                "text": a.get_text(strip=True),
                                "href": a["href"],
                            }
                        )

                    for img in soup.find_all("img", src=True):
                        result["images"].append(
                            {
                                "alt": img.get("alt", ""),
                                "src": img["src"],
                            }
                        )

                # 提取标题
                for i in range(1, 7):
                    for heading in soup.find_all(f"h{i}"):
                        result["headings"].append(
                            {
                                "level": i,
                                "text": heading.get_text(strip=True),
                            }
                        )

            except ImportError:
                # 使用正则表达式简单解析
                result["title"] = self._extract_title(html_content)
                if extract_text:
                    result["text"] = self._strip_html(html_content)
                if extract_links:
                    result["links"] = self._extract_links(html_content)
                    result["images"] = self._extract_images(html_content)
                result["warning"] = "建议安装 beautifulsoup4: pip install beautifulsoup4"

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"HTML 解析失败: {str(e)}")

    def _extract_title(self, html: str) -> str:
        """提取标题"""
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _strip_html(self, html: str) -> str:
        """移除 HTML 标签"""
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_links(self, html: str) -> list[dict[str, str]]:
        """提取链接"""
        links = []
        for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            href = match.group(1)
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            links.append({"text": text, "href": href})
        return links

    def _extract_images(self, html: str) -> list[dict[str, str]]:
        """提取图片"""
        images = []
        for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']', html, re.IGNORECASE):
            images.append({"src": match.group(1), "alt": match.group(2)})
        return images


class HTMLToMarkdownTool(BaseTool):
    """
    HTML 转 Markdown 工具
    """

    name = "html_to_markdown"
    description = "将 HTML 转换为 Markdown 格式"
    parameters = [
        ToolParameter(
            name="content",
            type="string",
            description="HTML 内容或文件路径",
            required=True,
        ),
        ToolParameter(
            name="is_file",
            type="boolean",
            description="content 是否为文件路径",
            required=False,
            default=False,
        ),
    ]
    category = "document"

    async def execute(
        self,
        content: str,
        is_file: bool = False,
    ) -> dict[str, Any]:
        """执行转换"""
        try:
            if is_file:
                path = Path(content)
                if not path.exists():
                    raise ToolException(f"文件不存在: {content}")
                with open(path, encoding="utf-8") as f:
                    html_content = f.read()
            else:
                html_content = content

            result = {
                "original_length": len(html_content),
                "markdown": "",
            }

            # 尝试使用 html2text
            try:
                import html2text

                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = False
                h.body_width = 0
                result["markdown"] = h.handle(html_content)
            except ImportError:
                # 简单转换
                result["markdown"] = self._simple_html_to_md(html_content)
                result["warning"] = "建议安装 html2text: pip install html2text"

            result["output_length"] = len(result["markdown"])
            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"HTML 转 Markdown 失败: {str(e)}")

    def _simple_html_to_md(self, html: str) -> str:
        """简单的 HTML 到 Markdown 转换"""
        md = html

        # 标题
        for i in range(1, 7):
            md = re.sub(f"<h{i}[^>]*>(.*?)</h{i}>", f"{'#' * i} \\1\n", md, flags=re.IGNORECASE | re.DOTALL)

        # 粗体和斜体
        md = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", md, flags=re.IGNORECASE | re.DOTALL)
        md = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", md, flags=re.IGNORECASE | re.DOTALL)

        # 链接
        md = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r"[\2](\1)", md, flags=re.IGNORECASE | re.DOTALL)

        # 图片
        md = re.sub(
            r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*/?>',
            r"![\2](\1)",
            md,
            flags=re.IGNORECASE,
        )

        # 代码
        md = re.sub(r"<code>(.*?)</code>", r"`\1`", md, flags=re.IGNORECASE | re.DOTALL)
        md = re.sub(r"<pre>(.*?)</pre>", r"```\n\1\n```", md, flags=re.IGNORECASE | re.DOTALL)

        # 段落和换行
        md = re.sub(r"<br\s*/?>", "\n", md, flags=re.IGNORECASE)
        md = re.sub(r"<p>(.*?)</p>", r"\1\n\n", md, flags=re.IGNORECASE | re.DOTALL)

        # 清理剩余标签
        md = re.sub(r"<[^>]+>", "", md)
        md = re.sub(r"\n{3,}", "\n\n", md)

        return md.strip()


# ============================================================================
# 通用文档工具
# ============================================================================


class DocumentConvertTool(BaseTool):
    """
    文档格式转换工具

    支持多种文档格式之间的转换。
    """

    name = "document_convert"
    description = "在不同文档格式之间转换"
    parameters = [
        ToolParameter(
            name="input_file",
            type="string",
            description="输入文件路径",
            required=True,
        ),
        ToolParameter(
            name="output_format",
            type="string",
            description="输出格式: pdf, html, markdown, txt",
            required=True,
        ),
        ToolParameter(
            name="output_file",
            type="string",
            description="输出文件路径（可选，不指定则返回内容）",
            required=False,
            default=None,
        ),
    ]
    category = "document"

    async def execute(
        self,
        input_file: str,
        output_format: str,
        output_file: str | None = None,
    ) -> dict[str, Any]:
        """执行转换"""
        input_path = Path(input_file)

        if not input_path.exists():
            raise ToolException(f"输入文件不存在: {input_file}")

        result = {
            "input_file": str(input_path.absolute()),
            "input_format": input_path.suffix.lower().lstrip("."),
            "output_format": output_format,
            "success": False,
        }

        try:
            # 根据输入格式读取内容
            input_format = input_path.suffix.lower().lstrip(".")

            if input_format == "md":
                with open(input_path, encoding="utf-8") as f:
                    content = f.read()

                if output_format == "html":
                    tool = MarkdownConvertTool()
                    conv_result = await tool.execute(content, "html", False)
                    result["content"] = conv_result["content"]
                    result["success"] = True

                elif output_format == "txt":
                    tool = MarkdownConvertTool()
                    conv_result = await tool.execute(content, "text", False)
                    result["content"] = conv_result["content"]
                    result["success"] = True

            elif input_format == "html":
                with open(input_path, encoding="utf-8") as f:
                    content = f.read()

                if output_format in ("markdown", "md"):
                    tool = HTMLToMarkdownTool()
                    conv_result = await tool.execute(content, False)
                    result["content"] = conv_result["markdown"]
                    result["success"] = True

                elif output_format == "txt":
                    tool = HTMLReadTool()
                    read_result = await tool.execute(content, False, True, False)
                    result["content"] = read_result["text"]
                    result["success"] = True

            elif input_format == "txt":
                with open(input_path, encoding="utf-8") as f:
                    content = f.read()

                if output_format == "markdown":
                    result["content"] = content
                    result["success"] = True

                elif output_format == "html":
                    result["content"] = f"<pre>{content}</pre>"
                    result["success"] = True

            else:
                raise ToolException(f"不支持的输入格式: {input_format}")

            # 写入输出文件
            if output_file and result["success"]:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result["content"])
                result["output_file"] = str(output_path.absolute())

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"文档转换失败: {str(e)}")


class MarkdownWriteTool(BaseTool):
    """
    Markdown 文档写入工具

    将结构化内容写入 Markdown 文件。
    """

    name = "markdown_write"
    description = "将结构化内容写入 Markdown 文件"
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="输出文件路径",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="文档内容（文本或 JSON 格式）",
            required=True,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="内容格式: text, json",
            required=False,
            default="text",
        ),
    ]
    category = "document"

    async def execute(
        self,
        file_path: str,
        content: str,
        format: str = "text",
    ) -> dict[str, Any]:
        """执行 Markdown 写入"""
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if format == "json":
                # JSON 格式：解析并渲染为 Markdown
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    raise ToolException("JSON 格式错误，无法解析内容")

                md_content = self._render_json_to_markdown(data)
            else:
                # 文本格式：直接写入
                md_content = content

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            logger.info(f"Markdown 文件已写入: {output_path}")

            return {
                "file_path": str(output_path.absolute()),
                "char_count": len(md_content),
                "success": True,
            }

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Markdown 写入失败: {str(e)}")

    def _render_json_to_markdown(self, data: dict[str, Any]) -> str:
        """将 JSON 结构渲染为 Markdown 格式"""
        lines = []

        # 渲染标题
        if data.get("title"):
            lines.append(f"# {data['title']}")
            lines.append("")

        # 渲染标题层级
        for heading in data.get("headings", []):
            level = heading.get("level", 1)
            level = max(1, min(6, level))
            text = heading.get("text", "")
            lines.append(f"{'#' * level} {text}")
            lines.append("")

        # 渲染段落
        for paragraph in data.get("paragraphs", []):
            lines.append(str(paragraph))
            lines.append("")

        # 渲染代码块
        for code_block in data.get("code_blocks", []):
            language = code_block.get("language", "")
            code = code_block.get("code", "")
            lines.append(f"```{language}")
            lines.append(code)
            lines.append("```")
            lines.append("")

        # 渲染表格
        for table in data.get("tables", []):
            headers = table.get("headers", [])
            rows = table.get("rows", [])

            if headers:
                lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                lines.append("| " + " | ".join("---" for _ in headers) + " |")

            for row in rows:
                lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

            lines.append("")

        # 渲染列表
        for list_item in data.get("lists", []):
            items = list_item.get("items", [])
            ordered = list_item.get("ordered", False)

            for idx, item in enumerate(items, 1):
                if ordered:
                    lines.append(f"{idx}. {item}")
                else:
                    lines.append(f"- {item}")

            lines.append("")

        return "\n".join(lines)


# ============================================================================
# PDF 创建工具
# ============================================================================


class PDFCreateTool(BaseTool):
    """
    PDF 文件创建工具

    支持从纯文本、HTML 或 Markdown 内容创建 PDF 文件。
    """

    name = "pdf_create"
    description = "从文本或 HTML 内容创建 PDF 文件"
    parameters = [
        ToolParameter(
            name="content",
            type="string",
            description="要写入 PDF 的内容",
            required=True,
        ),
        ToolParameter(
            name="output_file",
            type="string",
            description="输出的 PDF 文件路径",
            required=True,
        ),
        ToolParameter(
            name="title",
            type="string",
            description="PDF 文档标题",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="内容格式: text, html, markdown",
            required=False,
            default="text",
        ),
    ]
    category = "document"

    async def execute(
        self,
        content: str,
        output_file: str,
        title: str | None = None,
        format: str = "text",
    ) -> dict[str, Any]:
        """执行 PDF 创建"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if format == "text":
                await self._create_from_text(content, output_path, title)
            elif format == "html":
                await self._create_from_html(content, output_path, title)
            elif format == "markdown":
                await self._create_from_markdown(content, output_path, title)
            else:
                raise ToolException(f"不支持的内容格式: {format}")

            file_size = output_path.stat().st_size
            return {
                "file_path": str(output_path.absolute()),
                "file_size": file_size,
                "success": True,
            }

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"PDF 创建失败: {str(e)}")

    async def _create_from_text(self, content: str, output_path: Path, title: str | None = None) -> None:
        """使用 fpdf2 从纯文本创建 PDF"""
        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()

            # 尝试添加支持中文的字体
            try:
                pdf.add_font("NotoSansSC", "", "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf", uni=True)
                pdf.set_font("NotoSansSC", size=12)
            except Exception:
                try:
                    pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
                    pdf.set_font("DejaVu", size=12)
                except Exception:
                    pdf.set_font("Helvetica", size=12)

            if title:
                pdf.set_font_size(16)
                pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(5)
                pdf.set_font_size(12)

            for line in content.split("\n"):
                pdf.multi_cell(0, 6, line)

            pdf.output(str(output_path))
            logger.info(f"使用 fpdf2 创建 PDF 成功: {output_path}")

        except ImportError:
            # 回退到 reportlab
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.units import mm
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.pdfgen import canvas

                c = canvas.Canvas(str(output_path), pagesize=A4)
                width, height = A4

                # 尝试注册中文字体
                try:
                    pdfmetrics.registerFont(
                        TTFont("NotoSansSC", "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf")
                    )
                    font_name = "NotoSansSC"
                except Exception:
                    font_name = "Helvetica"

                y_position = height - 40 * mm

                if title:
                    c.setFont(font_name, 18)
                    c.drawCentredString(width / 2, y_position, title)
                    y_position -= 15 * mm

                c.setFont(font_name, 11)
                for line in content.split("\n"):
                    if y_position < 20 * mm:
                        c.showPage()
                        y_position = height - 20 * mm
                    c.drawString(20 * mm, y_position, line)
                    y_position -= 6 * mm

                c.save()
                logger.info(f"使用 reportlab 创建 PDF 成功: {output_path}")

            except ImportError:
                raise ToolException(
                    "无法创建 PDF：请安装 fpdf2 或 reportlab 库。安装命令: pip install fpdf2 或 pip install reportlab"
                )

    async def _create_from_html(self, content: str, output_path: Path, title: str | None = None) -> None:
        """使用 weasyprint 或 pdfkit 从 HTML 创建 PDF"""
        try:
            from weasyprint import HTML

            if title:
                content = f"<html><head><title>{title}</title></head><body>{content}</body></html>"
            elif not content.strip().lower().startswith("<html"):
                content = f"<html><body>{content}</body></html>"

            HTML(string=content).write_pdf(str(output_path))
            logger.info(f"使用 weasyprint 创建 PDF 成功: {output_path}")

        except ImportError:
            try:
                import pdfkit

                if title:
                    content = f"<html><head><title>{title}</title></head><body>{content}</body></html>"
                elif not content.strip().lower().startswith("<html"):
                    content = f"<html><body>{content}</body></html>"

                with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f:
                    f.write(content)
                    tmp_html = f.name

                try:
                    pdfkit.from_file(tmp_html, str(output_path))
                    logger.info(f"使用 pdfkit 创建 PDF 成功: {output_path}")
                finally:
                    os.unlink(tmp_html)

            except ImportError:
                raise ToolException(
                    "无法从 HTML 创建 PDF：请安装 weasyprint 或 pdfkit 库。"
                    "安装命令: pip install weasyprint 或 pip install pdfkit"
                )

    async def _create_from_markdown(self, content: str, output_path: Path, title: str | None = None) -> None:
        """将 Markdown 转为 HTML 再创建 PDF"""
        try:
            import markdown

            html_content = markdown.markdown(content, extensions=["tables", "fenced_code"])
            await self._create_from_html(html_content, output_path, title)

        except ImportError:
            # 简单的 Markdown 到 HTML 转换作为回退
            simple_html = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            simple_html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", simple_html, flags=re.MULTILINE)
            simple_html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", simple_html, flags=re.MULTILINE)
            simple_html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", simple_html, flags=re.MULTILINE)
            simple_html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", simple_html)
            simple_html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", simple_html)
            simple_html = simple_html.replace("\n", "<br>\n")
            await self._create_from_html(simple_html, output_path, title)


# ============================================================================
# PDF 合并工具
# ============================================================================


class PDFMergeTool(BaseTool):
    """
    PDF 文件合并工具

    将多个 PDF 文件合并为一个文件。
    """

    name = "pdf_merge"
    description = "合并多个 PDF 文件为一个"
    parameters = [
        ToolParameter(
            name="input_files",
            type="string",
            description="要合并的 PDF 文件路径列表（JSON 数组格式）",
            required=True,
        ),
        ToolParameter(
            name="output_file",
            type="string",
            description="输出的合并 PDF 文件路径",
            required=True,
        ),
    ]
    category = "document"

    async def execute(
        self,
        input_files: str,
        output_file: str,
    ) -> dict[str, Any]:
        """执行 PDF 合并"""
        # 解析输入文件列表
        try:
            files = json.loads(input_files)
            if not isinstance(files, list):
                raise ValueError("input_files 必须是 JSON 数组格式")
        except json.JSONDecodeError as e:
            raise ToolException(f"input_files 格式错误，需要 JSON 数组: {str(e)}")

        if not files:
            raise ToolException("输入文件列表不能为空")

        # 验证所有输入文件
        for f in files:
            path = Path(f)
            if not path.exists():
                raise ToolException(f"文件不存在: {f}")
            if path.suffix.lower() != ".pdf":
                raise ToolException(f"不是 PDF 文件: {f}")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            merged_count = await self._merge_with_pypdf(files, output_path)
        except ImportError:
            try:
                merged_count = await self._merge_with_pymupdf(files, output_path)
            except ImportError:
                raise ToolException(
                    "无法合并 PDF：请安装 pypdf 或 PyMuPDF 库。安装命令: pip install pypdf 或 pip install PyMuPDF"
                )

        file_size = output_path.stat().st_size
        return {
            "output_file": str(output_path.absolute()),
            "merged_count": merged_count,
            "file_size": file_size,
            "success": True,
        }

    async def _merge_with_pypdf(self, files: list[str], output_path: Path) -> int:
        """使用 pypdf 合并 PDF"""
        from pypdf import PdfMerger

        merger = PdfMerger()
        for f in files:
            merger.append(str(f))

        merger.write(str(output_path))
        merger.close()
        logger.info(f"使用 pypdf 合并 {len(files)} 个 PDF 成功: {output_path}")
        return len(files)

    async def _merge_with_pymupdf(self, files: list[str], output_path: Path) -> int:
        """使用 PyMuPDF (fitz) 合并 PDF"""
        import fitz

        merged_doc = fitz.open()
        for f in files:
            with fitz.open(str(f)) as doc:
                merged_doc.insert_pdf(doc)

        merged_doc.save(str(output_path))
        merged_doc.close()
        logger.info(f"使用 PyMuPDF 合并 {len(files)} 个 PDF 成功: {output_path}")
        return len(files)


# ============================================================================
# 注册函数
# ============================================================================


def register_document_tools() -> None:
    """注册所有文档工具"""
    from .registry import get_tool_registry

    registry = get_tool_registry()

    # PDF 工具
    registry.register(PDFReadTool())
    registry.register(PDFExtractTool())
    registry.register(PDFCreateTool())
    registry.register(PDFMergeTool())

    # Markdown 工具
    registry.register(MarkdownReadTool())
    registry.register(MarkdownConvertTool())
    registry.register(MarkdownWriteTool())

    # HTML 工具
    registry.register(HTMLReadTool())
    registry.register(HTMLToMarkdownTool())

    # 通用工具
    registry.register(DocumentConvertTool())

    logger.info("文档处理工具已注册")
