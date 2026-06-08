"""
DATA-AI 办公文档工具

提供 Word、PPT、Excel 等办公文档的处理能力。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_ai.core.tool.registry import get_tool_registry

from ...utils.exceptions import ToolException
from ...utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Word 文档工具
# ============================================================================

WORD_READ_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Word 文档路径",
        },
        "extract_tables": {
            "type": "boolean",
            "description": "是否提取表格",
            "default": True,
        },
        "extract_images": {
            "type": "boolean",
            "description": "是否提取图片信息",
            "default": False,
        },
    },
    "required": ["file_path"],
}


async def word_read(
    file_path: str,
    extract_tables: bool = True,
    extract_images: bool = False,
) -> dict[str, Any]:
    """读取 Word 文档 (.docx) 内容，提取文本、段落、表格等结构化信息"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    if path.suffix.lower() not in (".docx", ".doc"):
        raise ToolException(f"不是 Word 文档: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "file_name": path.name,
        "file_size": path.stat().st_size,
        "paragraphs": [],
        "tables": [],
        "images": [],
        "metadata": {},
        "word_count": 0,
        "char_count": 0,
    }

    try:
        try:
            from docx import Document
            from docx.shared import Inches

            doc = Document(str(path))

            core_props = doc.core_properties
            result["metadata"] = {
                "title": core_props.title or "",
                "author": core_props.author or "",
                "subject": core_props.subject or "",
                "keywords": core_props.keywords or "",
                "created": str(core_props.created) if core_props.created else "",
                "modified": str(core_props.modified) if core_props.modified else "",
            }

            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    result["paragraphs"].append(
                        {
                            "text": text,
                            "style": para.style.name if para.style else "Normal",
                        }
                    )
                    result["word_count"] += len(text.split())
                    result["char_count"] += len(text)

            if extract_tables:
                for table_idx, table in enumerate(doc.tables):
                    table_data = []
                    for row in table.rows:
                        row_data = [cell.text.strip() for cell in row.cells]
                        table_data.append(row_data)
                    result["tables"].append(
                        {
                            "index": table_idx,
                            "rows": len(table.rows),
                            "cols": len(table.columns),
                            "data": table_data,
                        }
                    )

            if extract_images:
                for rel in doc.part.rels.values():
                    if "image" in rel.target_ref:
                        result["images"].append(
                            {
                                "type": rel.target_ref.split(".")[-1],
                            }
                        )

        except ImportError:
            raise ToolException("Word 文档处理需要 python-docx: pip install python-docx")

        return result

    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Word 文档读取失败: {str(e)}")


WORD_WRITE_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "输出文件路径",
        },
        "content": {
            "type": "string",
            "description": "文档内容（文本或 JSON 格式）",
        },
        "title": {
            "type": "string",
            "description": "文档标题",
            "default": "",
        },
        "author": {
            "type": "string",
            "description": "文档作者",
            "default": "",
        },
        "format": {
            "type": "string",
            "description": "内容格式: text, json",
            "default": "text",
        },
    },
    "required": ["file_path", "content"],
}


async def word_write(
    file_path: str,
    content: str,
    title: str = "",
    author: str = "",
    format: str = "text",
) -> dict[str, Any]:
    """创建或修改 Word 文档 (.docx)"""
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "file_path": str(output_path.absolute()),
        "success": False,
    }

    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt

        doc = Document()

        if title:
            doc.core_properties.title = title
        if author:
            doc.core_properties.author = author

        if format == "json":
            try:
                content_data = json.loads(content)
            except json.JSONDecodeError:
                content_data = {"paragraphs": [content]}

            if content_data.get("title"):
                doc.add_heading(content_data["title"], level=0)

            for para in content_data.get("paragraphs", []):
                if isinstance(para, str):
                    doc.add_paragraph(para)
                elif isinstance(para, dict):
                    text = para.get("text", "")
                    style = para.get("style", "Normal")
                    p = doc.add_paragraph(text)
                    if style.startswith("Heading"):
                        try:
                            level = int(style.replace("Heading", "").strip())
                            p.style = doc.styles[f"Heading {level}"]
                        except (ValueError, KeyError):
                            pass

            for table_data in content_data.get("tables", []):
                rows = table_data.get("rows", [])
                if rows:
                    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
                    for i, row_data in enumerate(rows):
                        for j, cell_data in enumerate(row_data):
                            table.rows[i].cells[j].text = str(cell_data)

        else:
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    if line.startswith("# "):
                        doc.add_heading(line[2:], level=1)
                    elif line.startswith("## "):
                        doc.add_heading(line[3:], level=2)
                    elif line.startswith("### "):
                        doc.add_heading(line[4:], level=3)
                    else:
                        doc.add_paragraph(line)

        doc.save(str(output_path))
        result["success"] = True
        result["file_size"] = output_path.stat().st_size

        return result

    except ImportError:
        raise ToolException("Word 文档处理需要 python-docx: pip install python-docx")
    except Exception as e:
        raise ToolException(f"Word 文档写入失败: {str(e)}")


WORD_EDIT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Word 文档路径",
        },
        "operations": {
            "type": "string",
            "description": "编辑操作（JSON 格式）",
        },
    },
    "required": ["file_path", "operations"],
}


async def word_edit(
    file_path: str,
    operations: str,
) -> dict[str, Any]:
    """对 Word 文档进行编辑操作（替换文本、插入段落等）"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    try:
        ops = json.loads(operations)
    except json.JSONDecodeError:
        raise ToolException("operations 必须是 JSON 格式")

    if not isinstance(ops, list):
        ops = [ops]

    result = {
        "file_path": str(path.absolute()),
        "operations_applied": 0,
        "success": False,
    }

    try:
        from docx import Document

        doc = Document(str(path))

        for op in ops:
            op_type = op.get("type")

            if op_type == "replace":
                old_text = op.get("old", "")
                new_text = op.get("new", "")
                for paragraph in doc.paragraphs:
                    for run in paragraph.runs:
                        if old_text in run.text:
                            run.text = run.text.replace(old_text, new_text)
                            result["operations_applied"] += 1

            elif op_type == "append_paragraph":
                doc.add_paragraph(op.get("text", ""))
                result["operations_applied"] += 1

            elif op_type == "add_heading":
                doc.add_heading(op.get("text", ""), level=op.get("level", 1))
                result["operations_applied"] += 1

            elif op_type == "add_table":
                rows = op.get("rows", [])
                if rows:
                    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
                    for i, row_data in enumerate(rows):
                        for j, cell_data in enumerate(row_data):
                            table.rows[i].cells[j].text = str(cell_data)
                    result["operations_applied"] += 1

        doc.save(str(path))
        result["success"] = True
        result["file_size"] = path.stat().st_size

        return result

    except ImportError:
        raise ToolException("Word 文档处理需要 python-docx: pip install python-docx")
    except Exception as e:
        raise ToolException(f"Word 文档编辑失败: {str(e)}")


WORD_TO_TEXT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Word 文档路径",
        },
    },
    "required": ["file_path"],
}


async def word_to_text(file_path: str) -> dict[str, Any]:
    """将 Word 文档转换为纯文本"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    try:
        from docx import Document

        doc = Document(str(path))
        text_parts = []

        for para in doc.paragraphs:
            text_parts.append(para.text)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text_parts.append(cell.text)

        full_text = "\n".join(text_parts)

        return {
            "file_path": str(path.absolute()),
            "text": full_text,
            "char_count": len(full_text),
            "success": True,
        }

    except ImportError:
        raise ToolException("Word 文档处理需要 python-docx: pip install python-docx")
    except Exception as e:
        raise ToolException(f"Word 转文本失败: {str(e)}")


# ============================================================================
# PPT 演示文稿工具
# ============================================================================

PPT_READ_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "PPT 文件路径",
        },
        "extract_notes": {
            "type": "boolean",
            "description": "是否提取演讲者备注",
            "default": True,
        },
    },
    "required": ["file_path"],
}


async def ppt_read(
    file_path: str,
    extract_notes: bool = True,
) -> dict[str, Any]:
    """读取 PowerPoint 演示文稿 (.pptx) 内容，提取幻灯片、文本、形状等"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    if path.suffix.lower() not in (".pptx", ".ppt"):
        raise ToolException(f"不是 PowerPoint 文件: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "file_name": path.name,
        "file_size": path.stat().st_size,
        "slides": [],
        "metadata": {},
        "total_slides": 0,
    }

    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        prs = Presentation(str(path))
        result["total_slides"] = len(prs.slides)

        core_props = prs.core_properties
        result["metadata"] = {
            "title": core_props.title or "",
            "author": core_props.author or "",
            "subject": core_props.subject or "",
            "created": str(core_props.created) if core_props.created else "",
            "modified": str(core_props.modified) if core_props.modified else "",
        }

        for slide_idx, slide in enumerate(prs.slides):
            slide_info = {
                "slide_number": slide_idx + 1,
                "shapes": [],
                "text": [],
                "notes": "",
            }

            for shape in slide.shapes:
                shape_info = {
                    "type": str(shape.shape_type),
                    "name": shape.name,
                }

                if hasattr(shape, "text") and shape.text:
                    slide_info["text"].append(shape.text)
                    shape_info["text"] = shape.text

                if shape.has_table:
                    table_data = []
                    for row in shape.table.rows:
                        row_data = [cell.text for cell in row.cells]
                        table_data.append(row_data)
                    shape_info["table"] = table_data

                slide_info["shapes"].append(shape_info)

            if extract_notes and slide.has_notes_slide:
                notes_slide = slide.notes_slide
                notes_text = notes_slide.notes_text_frame.text
                slide_info["notes"] = notes_text

            result["slides"].append(slide_info)

        return result

    except ImportError:
        raise ToolException("PPT 处理需要 python-pptx: pip install python-pptx")
    except Exception as e:
        raise ToolException(f"PPT 读取失败: {str(e)}")


PPT_WRITE_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "输出文件路径",
        },
        "slides": {
            "type": "string",
            "description": "幻灯片内容（JSON 格式）",
        },
        "title": {
            "type": "string",
            "description": "演示文稿标题",
            "default": "",
        },
        "author": {
            "type": "string",
            "description": "作者",
            "default": "",
        },
    },
    "required": ["file_path", "slides"],
}


async def ppt_write(
    file_path: str,
    slides: str,
    title: str = "",
    author: str = "",
) -> dict[str, Any]:
    """创建 PowerPoint 演示文稿 (.pptx)"""
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "file_path": str(output_path.absolute()),
        "success": False,
    }

    try:
        from pptx import Presentation
        from pptx.enum.text import PP_ALIGN
        from pptx.util import Inches, Pt

        try:
            slides_data = json.loads(slides)
        except json.JSONDecodeError:
            slides_data = [{"title": "Slide", "content": slides}]

        if not isinstance(slides_data, list):
            slides_data = [slides_data]

        prs = Presentation()

        if title:
            prs.core_properties.title = title
        if author:
            prs.core_properties.author = author

        for slide_data in slides_data:
            slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout)

            if slide_data.get("title"):
                title_shape = slide.shapes.title
                if title_shape:
                    title_shape.text = slide_data["title"]

            content = slide_data.get("content", "")
            if content:
                left = Inches(0.5)
                top = Inches(1.5)
                width = Inches(9)
                height = Inches(5)

                txBox = slide.shapes.add_textbox(left, top, width, height)
                tf = txBox.text_frame
                tf.word_wrap = True

                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if i == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    p.text = line
                    p.font.size = Pt(18)

            if slide_data.get("notes"):
                notes_slide = slide.notes_slide
                notes_slide.notes_text_frame.text = slide_data["notes"]

        prs.save(str(output_path))
        result["success"] = True
        result["total_slides"] = len(slides_data)
        result["file_size"] = output_path.stat().st_size

        return result

    except ImportError:
        raise ToolException("PPT 处理需要 python-pptx: pip install python-pptx")
    except Exception as e:
        raise ToolException(f"PPT 创建失败: {str(e)}")


PPT_TO_TEXT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "PPT 文件路径",
        },
        "include_notes": {
            "type": "boolean",
            "description": "是否包含演讲者备注",
            "default": True,
        },
    },
    "required": ["file_path"],
}


async def ppt_to_text(
    file_path: str,
    include_notes: bool = True,
) -> dict[str, Any]:
    """将 PowerPoint 演示文稿转换为纯文本"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    try:
        from pptx import Presentation

        prs = Presentation(str(path))
        text_parts = []

        for slide_idx, slide in enumerate(prs.slides, 1):
            text_parts.append(f"=== Slide {slide_idx} ===")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text_parts.append(shape.text)
            if include_notes and slide.has_notes_slide:
                notes_text = slide.notes_slide.notes_text_frame.text
                if notes_text:
                    text_parts.append(f"[Notes]: {notes_text}")

        full_text = "\n".join(text_parts)

        return {
            "file_path": str(path.absolute()),
            "text": full_text,
            "char_count": len(full_text),
            "total_slides": len(prs.slides),
            "success": True,
        }

    except ImportError:
        raise ToolException("PPT 处理需要 python-pptx: pip install python-pptx")
    except Exception as e:
        raise ToolException(f"PPT 转文本失败: {str(e)}")


# ============================================================================
# Excel 表格工具
# ============================================================================

EXCEL_READ_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Excel 文件路径",
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称（可选，默认读取所有）",
            "default": None,
        },
        "max_rows": {
            "type": "integer",
            "description": "最大读取行数（0 表示无限制）",
            "default": 0,
        },
        "include_formulas": {
            "type": "boolean",
            "description": "是否包含公式",
            "default": True,
        },
    },
    "required": ["file_path"],
}


async def excel_read(
    file_path: str,
    sheet_name: str | None = None,
    max_rows: int = 0,
    include_formulas: bool = True,
) -> dict[str, Any]:
    """读取 Excel 表格 (.xlsx) 内容，提取工作表、数据、公式等"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    if path.suffix.lower() not in (".xlsx", ".xls", ".csv"):
        raise ToolException(f"不是 Excel 文件: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "file_name": path.name,
        "file_size": path.stat().st_size,
        "sheets": [],
        "metadata": {},
    }

    try:
        try:
            from openpyxl import load_workbook
            from openpyxl.utils import get_column_letter

            wb = load_workbook(str(path), data_only=not include_formulas)

            result["metadata"] = {
                "sheet_names": wb.sheetnames,
                "active_sheet": wb.active.title if wb.active else None,
            }

            if sheet_name:
                if sheet_name not in wb.sheetnames:
                    raise ToolException(f"工作表不存在: {sheet_name}")
                sheets_to_read = [sheet_name]
            else:
                sheets_to_read = wb.sheetnames

            for sheet in sheets_to_read:
                ws = wb[sheet]

                sheet_info = {
                    "name": sheet,
                    "dimensions": ws.dimensions,
                    "max_row": ws.max_row,
                    "max_column": ws.max_column,
                    "data": [],
                    "headers": [],
                }

                rows_read = 0
                for row_idx, row in enumerate(ws.iter_rows(), 1):
                    if max_rows > 0 and rows_read >= max_rows:
                        break

                    row_data = []
                    for cell in row:
                        cell_info = {
                            "column": cell.column_letter,
                            "row": cell.row,
                            "value": cell.value,
                        }

                        if (
                            include_formulas
                            and hasattr(cell, "value")
                            and isinstance(cell.value, str)
                            and cell.value.startswith("=")
                        ):
                            cell_info["formula"] = cell.value

                        row_data.append(cell_info)

                    sheet_info["data"].append(row_data)
                    rows_read += 1

                    if row_idx == 1:
                        sheet_info["headers"] = [cell.value for cell in row]

                result["sheets"].append(sheet_info)

            wb.close()

        except ImportError:
            try:
                import pandas as pd

                if sheet_name:
                    sheets_to_read = [sheet_name]
                else:
                    xl = pd.ExcelFile(str(path))
                    sheets_to_read = xl.sheet_names

                for sheet in sheets_to_read:
                    df = pd.read_excel(str(path), sheet_name=sheet)
                    if max_rows > 0:
                        df = df.head(max_rows)

                    sheet_info = {
                        "name": sheet,
                        "dimensions": f"A1:{chr(64 + len(df.columns))}{len(df) + 1}",
                        "max_row": len(df),
                        "max_column": len(df.columns),
                        "headers": df.columns.tolist(),
                        "data": df.values.tolist()[:max_rows] if max_rows > 0 else df.values.tolist(),
                    }
                    result["sheets"].append(sheet_info)

                result["metadata"]["sheet_names"] = sheets_to_read

            except ImportError:
                raise ToolException("Excel 处理需要 openpyxl 或 pandas: pip install openpyxl 或 pip install pandas")

        return result

    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Excel 读取失败: {str(e)}")


EXCEL_WRITE_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "输出文件路径",
        },
        "data": {
            "type": "string",
            "description": "表格数据（JSON 格式）",
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称",
            "default": "Sheet1",
        },
    },
    "required": ["file_path", "data"],
}


async def excel_write(
    file_path: str,
    data: str,
    sheet_name: str = "Sheet1",
) -> dict[str, Any]:
    """创建或修改 Excel 表格 (.xlsx)"""
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "file_path": str(output_path.absolute()),
        "success": False,
    }

    try:
        try:
            data_obj = json.loads(data)
        except json.JSONDecodeError:
            raise ToolException("数据格式错误，需要 JSON 格式")

        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        if isinstance(data_obj, dict):
            headers = data_obj.get("headers", [])
            rows = data_obj.get("rows", [])

            if headers:
                for col_idx, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col_idx, value=header)
                    cell.font = Font(bold=True)

            for row_idx, row_data in enumerate(rows, 2 if headers else 1):
                for col_idx, value in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)

        elif isinstance(data_obj, list):
            for row_idx, row_data in enumerate(data_obj, 1):
                for col_idx, value in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)

        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except (AttributeError, TypeError):
                    pass
            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

        wb.save(str(output_path))
        result["success"] = True
        result["sheet_name"] = sheet_name
        result["rows"] = ws.max_row
        result["columns"] = ws.max_column
        result["file_size"] = output_path.stat().st_size

        return result

    except ImportError:
        raise ToolException("Excel 处理需要 openpyxl: pip install openpyxl")
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Excel 写入失败: {str(e)}")


EXCEL_EDIT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Excel 文件路径",
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称",
            "default": "Sheet1",
        },
        "cell": {
            "type": "string",
            "description": "目标单元格，如 A1",
        },
        "value": {
            "type": "string",
            "description": "要写入的值",
        },
    },
    "required": ["file_path", "cell", "value"],
}


async def excel_edit(
    file_path: str,
    cell: str,
    value: str,
    sheet_name: str = "Sheet1",
) -> dict[str, Any]:
    """编辑 Excel 文件中的指定单元格"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "cell": cell,
        "sheet_name": sheet_name,
        "success": False,
    }

    try:
        from openpyxl import load_workbook

        wb = load_workbook(str(path))

        if sheet_name not in wb.sheetnames:
            raise ToolException(f"工作表不存在: {sheet_name}")

        ws = wb[sheet_name]
        ws[cell] = value
        wb.save(str(path))
        wb.close()

        result["success"] = True
        result["file_size"] = path.stat().st_size

        return result

    except ImportError:
        raise ToolException("Excel 处理需要 openpyxl: pip install openpyxl")
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Excel 编辑失败: {str(e)}")


EXCEL_TO_TEXT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Excel 文件路径",
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称（可选，默认第一个）",
            "default": None,
        },
    },
    "required": ["file_path"],
}


async def excel_to_text(
    file_path: str,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """将 Excel 表格转换为文本（TSV 格式）"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    try:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), data_only=True)

        target_sheet = sheet_name or wb.sheetnames[0]
        if target_sheet not in wb.sheetnames:
            raise ToolException(f"工作表不存在: {target_sheet}")

        ws = wb[target_sheet]
        text_parts = []

        for row in ws.iter_rows(values_only=True):
            text_parts.append("\t".join(str(c) if c is not None else "" for c in row))

        full_text = "\n".join(text_parts)
        wb.close()

        return {
            "file_path": str(path.absolute()),
            "sheet_name": target_sheet,
            "text": full_text,
            "char_count": len(full_text),
            "rows": ws.max_row,
            "success": True,
        }

    except ImportError:
        raise ToolException("Excel 处理需要 openpyxl: pip install openpyxl")
    except Exception as e:
        raise ToolException(f"Excel 转文本失败: {str(e)}")


EXCEL_ANALYZE_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Excel 文件路径",
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称（可选）",
            "default": None,
        },
        "analysis_type": {
            "type": "string",
            "description": "分析类型: summary, stats, correlation",
            "default": "summary",
        },
    },
    "required": ["file_path"],
}


async def excel_analyze(
    file_path: str,
    sheet_name: str | None = None,
    analysis_type: str = "summary",
) -> dict[str, Any]:
    """对 Excel 表格数据进行统计分析"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "analysis_type": analysis_type,
        "results": {},
    }

    try:
        import pandas as pd

        df = pd.read_excel(str(path), sheet_name=sheet_name or 0)

        if analysis_type == "summary":
            import math

            def _sanitize(v: Any) -> Any:
                """把 NaN/Inf 转 None，让 JSON 序列化通过"""
                if isinstance(v, float):
                    if math.isnan(v) or math.isinf(v):
                        return None
                if isinstance(v, dict):
                    return {k: _sanitize(x) for k, x in v.items()}
                if isinstance(v, list):
                    return [_sanitize(x) for x in v]
                return v

            result["results"] = {
                "shape": list(df.shape),
                "columns": [str(c) for c in df.columns.tolist()],
                "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
                "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
                "describe": _sanitize(df.describe().to_dict()),
            }

        elif analysis_type == "stats":
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            stats = {}
            for col in numeric_cols:
                stats[col] = {
                    "mean": float(df[col].mean()) if not df[col].empty else None,
                    "median": float(df[col].median()) if not df[col].empty else None,
                    "std": float(df[col].std()) if not df[col].empty else None,
                    "min": float(df[col].min()) if not df[col].empty else None,
                    "max": float(df[col].max()) if not df[col].empty else None,
                }
            result["results"] = stats

        elif analysis_type == "correlation":
            numeric_df = df.select_dtypes(include=["number"])
            if not numeric_df.empty:
                result["results"] = numeric_df.corr().to_dict()
            else:
                result["results"] = {"error": "没有数值列"}

        else:
            raise ToolException(f"不支持的分析类型: {analysis_type}")

        return result

    except ImportError:
        raise ToolException("Excel 分析需要 pandas: pip install pandas openpyxl")
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"数据分析失败: {str(e)}")


WORD_TEMPLATE_PARAMS = {
    "type": "object",
    "properties": {
        "template_path": {
            "type": "string",
            "description": "模板文件路径",
        },
        "output_path": {
            "type": "string",
            "description": "输出文件路径",
        },
        "data": {
            "type": "string",
            "description": "JSON 格式的键值对数据，用于替换模板中的 {{key}} 占位符",
        },
    },
    "required": ["template_path", "output_path", "data"],
}


async def word_template(
    template_path: str,
    output_path: str,
    data: str,
) -> dict[str, Any]:
    """基于 Word 模板文件生成文档，替换模板中的占位符"""
    tpl_path = Path(template_path)
    out_path = Path(output_path)

    if not tpl_path.exists():
        raise ToolException(f"模板文件不存在: {template_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        try:
            replacements = json.loads(data)
        except json.JSONDecodeError:
            raise ToolException("数据格式错误，需要 JSON 格式的键值对")

        if not isinstance(replacements, dict):
            raise ToolException("数据格式错误，需要 JSON 对象（键值对）")

        from docx import Document

        doc = Document(str(tpl_path))
        total_replacements = 0

        for paragraph in doc.paragraphs:
            for run in paragraph.runs:
                for key, value in replacements.items():
                    placeholder = "{{" + str(key) + "}}"
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, str(value))
                        total_replacements += 1

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            for key, value in replacements.items():
                                placeholder = "{{" + str(key) + "}}"
                                if placeholder in run.text:
                                    run.text = run.text.replace(placeholder, str(value))
                                    total_replacements += 1

        doc.save(str(out_path))

        logger.info(f"Word 模板文档已生成: {out_path}，共替换 {total_replacements} 处")

        return {
            "output_path": str(out_path.absolute()),
            "replacements": total_replacements,
            "success": True,
        }

    except ImportError:
        raise ToolException("Word 文档处理需要 python-docx: pip install python-docx")
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Word 模板处理失败: {str(e)}")


EXCEL_CHART_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Excel 文件路径",
        },
        "chart_type": {
            "type": "string",
            "description": "图表类型: bar, line, pie, scatter",
        },
        "data_range": {
            "type": "string",
            "description": "数据范围，如 'A1:B10'",
            "default": None,
        },
        "title": {
            "type": "string",
            "description": "图表标题",
            "default": None,
        },
        "sheet_name": {
            "type": "string",
            "description": "工作表名称（默认使用活动工作表）",
            "default": None,
        },
        "x_axis_title": {
            "type": "string",
            "description": "X 轴标题",
            "default": None,
        },
        "y_axis_title": {
            "type": "string",
            "description": "Y 轴标题",
            "default": None,
        },
        "output_file": {
            "type": "string",
            "description": "输出文件路径（不指定则修改原文件）",
            "default": None,
        },
    },
    "required": ["file_path", "chart_type"],
}


async def excel_chart(
    file_path: str,
    chart_type: str,
    data_range: str | None = None,
    title: str | None = None,
    sheet_name: str | None = None,
    x_axis_title: str | None = None,
    y_axis_title: str | None = None,
    output_file: str | None = None,
) -> dict[str, Any]:
    """在 Excel 文件中创建图表（柱状图、折线图、饼图、散点图）"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    save_path = Path(output_file) if output_file else path

    try:
        from openpyxl import load_workbook
        from openpyxl.chart import (
            BarChart,
            LineChart,
            PieChart,
            Reference,
            ScatterChart,
        )

        wb = load_workbook(str(path))

        if sheet_name:
            if sheet_name not in wb.sheetnames:
                raise ToolException(f"工作表不存在: {sheet_name}")
            ws = wb[sheet_name]
        else:
            ws = wb.active

        actual_sheet_name = ws.title

        if data_range:
            from openpyxl.utils import range_boundaries

            min_col, min_row, max_col, max_row = range_boundaries(data_range)
        else:
            min_col = 1
            min_row = 1
            max_col = ws.max_column
            max_row = ws.max_row

        if max_row < 2 or max_col < 1:
            raise ToolException("数据范围无效，至少需要标题行和一行数据")

        chart = None

        if chart_type == "bar":
            chart = BarChart()
            data_ref = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
            cats_ref = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)

        elif chart_type == "line":
            chart = LineChart()
            data_ref = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
            cats_ref = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)

        elif chart_type == "pie":
            chart = PieChart()
            data_ref = Reference(ws, min_col=min_col + 1, min_row=min_row, max_col=max_col, max_row=max_row)
            cats_ref = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats_ref)

        elif chart_type == "scatter":
            chart = ScatterChart()
            x_values = Reference(ws, min_col=min_col, min_row=min_row + 1, max_row=max_row)
            y_values = Reference(ws, min_col=min_col + 1, min_row=min_row, max_col=max_col, max_row=max_row)
            chart.add_data(y_values, titles_from_data=True)
            chart.set_categories(x_values)

        else:
            raise ToolException(f"不支持的图表类型: {chart_type}，支持: bar, line, pie, scatter")

        if title:
            chart.title = title

        if chart_type != "pie":
            if x_axis_title:
                chart.x_axis.title = x_axis_title
            if y_axis_title:
                chart.y_axis.title = y_axis_title

        chart_anchor = f"A{max_row + 2}"
        ws.add_chart(chart, chart_anchor)

        wb.save(str(save_path))

        logger.info(f"Excel 图表已创建: {save_path}，类型: {chart_type}")

        return {
            "chart_type": chart_type,
            "sheet_name": actual_sheet_name,
            "file_path": str(save_path.absolute()),
            "success": True,
        }

    except ImportError:
        raise ToolException("Excel 图表处理需要 openpyxl: pip install openpyxl")
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(f"Excel 图表创建失败: {str(e)}")


# ============================================================================
# PDF 工具
# ============================================================================

PDF_READ_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "PDF 文件路径",
        },
        "max_pages": {
            "type": "integer",
            "description": "最大读取页数（0 表示无限制）",
            "default": 0,
        },
    },
    "required": ["file_path"],
}


async def pdf_read(
    file_path: str,
    max_pages: int = 0,
) -> dict[str, Any]:
    """读取 PDF 文件内容，提取文本"""
    path = Path(file_path)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ToolException(f"不是 PDF 文件: {file_path}")

    result = {
        "file_path": str(path.absolute()),
        "file_name": path.name,
        "file_size": path.stat().st_size,
        "pages": [],
        "total_pages": 0,
        "metadata": {},
    }

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        result["total_pages"] = len(reader.pages)

        if reader.metadata:
            result["metadata"] = {
                "title": reader.metadata.title or "",
                "author": reader.metadata.author or "",
                "subject": reader.metadata.subject or "",
                "creator": reader.metadata.creator or "",
            }

        page_limit = max_pages if max_pages > 0 else len(reader.pages)
        for i, page in enumerate(reader.pages[:page_limit]):
            text = page.extract_text() or ""
            result["pages"].append(
                {
                    "page_number": i + 1,
                    "text": text,
                    "char_count": len(text),
                }
            )

        return result

    except ImportError:
        raise ToolException("PDF 处理需要 PyPDF2: pip install PyPDF2")
    except Exception as e:
        raise ToolException(f"PDF 读取失败: {str(e)}")


PDF_MERGE_PARAMS = {
    "type": "object",
    "properties": {
        "input_files": {
            "type": "array",
            "description": "要合并的 PDF 文件路径列表（JSON 数组字符串）",
        },
        "output_file": {
            "type": "string",
            "description": "输出文件路径",
        },
    },
    "required": ["input_files", "output_file"],
}


async def pdf_merge(
    input_files: str,
    output_file: str,
) -> dict[str, Any]:
    """合并多个 PDF 文件"""
    try:
        file_list = json.loads(input_files)
    except json.JSONDecodeError:
        if isinstance(input_files, list):
            file_list = input_files
        else:
            raise ToolException("input_files 必须是 JSON 数组或字符串")

    if not isinstance(file_list, list) or len(file_list) < 2:
        raise ToolException("至少需要 2 个 PDF 文件进行合并")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "output_file": str(output_path.absolute()),
        "input_files": file_list,
        "success": False,
    }

    try:
        from PyPDF2 import PdfWriter

        writer = PdfWriter()

        for file_path in file_list:
            p = Path(file_path)
            if not p.exists():
                raise ToolException(f"文件不存在: {file_path}")
            from PyPDF2 import PdfReader

            reader = PdfReader(str(p))
            for page in reader.pages:
                writer.add_page(page)

        with open(str(output_path), "wb") as f:
            writer.write(f)

        result["success"] = True
        result["file_size"] = output_path.stat().st_size
        result["total_pages"] = len(writer.pages)

        return result

    except ImportError:
        raise ToolException("PDF 处理需要 PyPDF2: pip install PyPDF2")
    except Exception as e:
        raise ToolException(f"PDF 合并失败: {str(e)}")


PDF_SPLIT_PARAMS = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "PDF 文件路径",
        },
        "output_dir": {
            "type": "string",
            "description": "输出目录",
        },
        "page_ranges": {
            "type": "string",
            "description": "页码范围（JSON 数组，如 [[1,3],[4,6]]）",
            "default": None,
        },
    },
    "required": ["file_path", "output_dir"],
}


async def pdf_split(
    file_path: str,
    output_dir: str,
    page_ranges: str | None = None,
) -> dict[str, Any]:
    """拆分 PDF 文件为多个文件"""
    path = Path(file_path)
    out_dir = Path(output_dir)

    if not path.exists():
        raise ToolException(f"文件不存在: {file_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "file_path": str(path.absolute()),
        "output_dir": str(out_dir.absolute()),
        "files": [],
        "success": False,
    }

    try:
        from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(str(path))
        total_pages = len(reader.pages)

        if page_ranges:
            try:
                ranges = json.loads(page_ranges)
            except json.JSONDecodeError:
                raise ToolException("page_ranges 必须是 JSON 数组")
        else:
            ranges = [[i + 1, i + 1] for i in range(total_pages)]

        for idx, page_range in enumerate(ranges):
            start, end = page_range
            writer = PdfWriter()

            for page_num in range(start - 1, min(end, total_pages)):
                writer.add_page(reader.pages[page_num])

            output_file = out_dir / f"{path.stem}_part{idx + 1}.pdf"
            with open(str(output_file), "wb") as f:
                writer.write(f)

            result["files"].append(
                {
                    "file": str(output_file.absolute()),
                    "pages": end - start + 1,
                }
            )

        result["success"] = True

        return result

    except ImportError:
        raise ToolException("PDF 处理需要 PyPDF2: pip install PyPDF2")
    except Exception as e:
        raise ToolException(f"PDF 拆分失败: {str(e)}")


# ============================================================================
# 注册函数
# ============================================================================


def register_office_tools() -> None:
    """注册所有办公文档工具"""
    registry = get_tool_registry()

    registry.register_function(
        name="word_read",
        func=word_read,
        description="读取 Word 文档 (.docx) 内容，提取文本、段落、表格等结构化信息",
        parameters=WORD_READ_PARAMS,
    )

    registry.register_function(
        name="word_write",
        func=word_write,
        description="创建或修改 Word 文档 (.docx)",
        parameters=WORD_WRITE_PARAMS,
    )

    registry.register_function(
        name="word_edit",
        func=word_edit,
        description="对 Word 文档进行编辑操作（替换文本、插入段落等）",
        parameters=WORD_EDIT_PARAMS,
    )

    registry.register_function(
        name="word_to_text",
        func=word_to_text,
        description="将 Word 文档转换为纯文本",
        parameters=WORD_TO_TEXT_PARAMS,
    )

    registry.register_function(
        name="word_template",
        func=word_template,
        description="基于 Word 模板文件生成文档，替换模板中的占位符",
        parameters=WORD_TEMPLATE_PARAMS,
    )

    registry.register_function(
        name="ppt_read",
        func=ppt_read,
        description="读取 PowerPoint 演示文稿 (.pptx) 内容，提取幻灯片、文本、形状等",
        parameters=PPT_READ_PARAMS,
    )

    registry.register_function(
        name="ppt_write",
        func=ppt_write,
        description="创建 PowerPoint 演示文稿 (.pptx)",
        parameters=PPT_WRITE_PARAMS,
    )

    registry.register_function(
        name="ppt_to_text",
        func=ppt_to_text,
        description="将 PowerPoint 演示文稿转换为纯文本",
        parameters=PPT_TO_TEXT_PARAMS,
    )

    registry.register_function(
        name="excel_read",
        func=excel_read,
        description="读取 Excel 表格 (.xlsx) 内容，提取工作表、数据、公式等",
        parameters=EXCEL_READ_PARAMS,
    )

    registry.register_function(
        name="excel_write",
        func=excel_write,
        description="创建或修改 Excel 表格 (.xlsx)",
        parameters=EXCEL_WRITE_PARAMS,
    )

    registry.register_function(
        name="excel_edit",
        func=excel_edit,
        description="编辑 Excel 文件中的指定单元格",
        parameters=EXCEL_EDIT_PARAMS,
    )

    registry.register_function(
        name="excel_to_text",
        func=excel_to_text,
        description="将 Excel 表格转换为文本（TSV 格式）",
        parameters=EXCEL_TO_TEXT_PARAMS,
    )

    registry.register_function(
        name="excel_analyze",
        func=excel_analyze,
        description="对 Excel 表格数据进行统计分析",
        parameters=EXCEL_ANALYZE_PARAMS,
    )

    registry.register_function(
        name="excel_chart",
        func=excel_chart,
        description="在 Excel 文件中创建图表（柱状图、折线图、饼图、散点图）",
        parameters=EXCEL_CHART_PARAMS,
    )

    registry.register_function(
        name="pdf_read",
        func=pdf_read,
        description="读取 PDF 文件内容，提取文本",
        parameters=PDF_READ_PARAMS,
    )

    registry.register_function(
        name="pdf_merge",
        func=pdf_merge,
        description="合并多个 PDF 文件",
        parameters=PDF_MERGE_PARAMS,
    )

    registry.register_function(
        name="pdf_split",
        func=pdf_split,
        description="拆分 PDF 文件为多个文件",
        parameters=PDF_SPLIT_PARAMS,
    )

    logger.info("办公文档工具已注册")
