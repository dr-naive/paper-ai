"""多媒体信息提取器 - 从论文中提取图片、表格、公式"""
import asyncio
import re
import json
import logging
import io
from typing import List, Dict, Any, Optional
from pathlib import Path

from .table_analyzer import TableSemanticAnalyzer
from .image_analyzer import ImageAnalyzer

logger = logging.getLogger(__name__)


class MultimediaExtractor:
    """
    从论文文本和PDF页面中提取表格、图片、公式等多媒体信息

    表格格式示例：
    {
        "table_number": 1,
        "caption": "表1: 实验结果对比",
        "content": [["指标", "方法A", "方法B"], ["准确率", "92%", "88%"]],
        "position": "第3章第2节",
        "page": 15
    }

    图片格式示例：
    {
        "figure_number": 1,
        "caption": "图1: 模型架构图",
        "description": "展示了Transformer编码器和解码器的结构",
        "position": "第3章第1节",
        "page": 12,
        "type": "架构图",
        "image_path": "/path/to/image.jpg"  # 如果保存了图片
    }
    """

    def __init__(self, pdf_path: str = None):
        self.pdf_path = pdf_path
        # 表格匹配模式（从文本中）
        self.table_patterns = [
            re.compile(r'表\s*(\d+)[：:]\s*(.*?)(?=\n表\s*\d+|\n图\s*\d+|\n[一二三四五六七八九十]+\.|$)', re.DOTALL),
            re.compile(r'Table\s*(\d+)[：:]\s*(.*?)(?=\nTable\s*\d+|\nFigure\s*\d+|\n\d+\.|$)', re.DOTALL),
        ]

        # 图片匹配模式（从文本中）
        self.figure_patterns = [
            re.compile(r'图\s*(\d+)[：:]\s*(.*?)(?=\n表\s*\d+|\n图\s*\d+|\n[一二三四五六七八九十]+\.|$)', re.DOTALL),
            re.compile(r'Figure\s*(\d+)[：:]\s*(.*?)(?=\nTable\s*\d+|\nFigure\s*\d+|\n\d+\.|$)', re.DOTALL),
        ]

        # 公式匹配模式
        self.formula_patterns = [
            re.compile(r'(\$[^$]+\$)', re.MULTILINE),
            re.compile(r'\\\[(.*?)\\\]', re.DOTALL),
        ]

    async def extract_tables_from_pdf(self, pdf_path: str = None) -> List[Dict[str, Any]]:
        """
        从 PDF 中提取表格数据（混合模式：pdfplumber + VLM）

        返回格式：
        [{
            "page": 1,
            "table_number": 1,
            "bbox": [x1, y1, x2, y2],  # 表格边界框
            "content": [["A", "B"], ["1", "2"]],
            "markdown": "| A | B |\\n|---|---|\\n| 1 | 2 |",
            "csv": "A,B\\n1,2",
            "caption": "表1: 结果对比"  # 如果能识别到
        }]
        """
        tables = []
        path = pdf_path or self.pdf_path

        if not path:
            logger.warning("未提供 PDF 路径，无法提取表格")
            return tables

        if self._is_raster_document_without_vector_tables(path):
            logger.info("📊 检测到无矢量线条的整页栅格 PDF，跳过无效的 pdfplumber 表格扫描")
            return tables

        try:
            import pdfplumber
            import os
            logger.info(f"📊 开始使用 pdfplumber 提取表格，路径: {path}")
            with pdfplumber.open(path) as pdf:
                logger.info(f"📊 PDF 总页数: {len(pdf.pages)}")
                for page_num, page in enumerate(pdf.pages, start=1):
                    found_tables = page.find_tables()
                    page_tables = found_tables.tables
                    logger.info(f"📊 第 {page_num} 页提取到 {len(page_tables)} 个表格")

                    if page_tables:
                        for idx, found_table in enumerate(page_tables):
                            table_data = found_table.extract()
                            if table_data and len(table_data) > 0:
                                markdown = self._table_to_markdown(table_data)
                                csv = self._table_to_csv(table_data)
                                bbox = [float(value) for value in found_table.bbox]
                                cell_bboxes = [
                                    [
                                        [float(value) for value in cell] if cell else None
                                        for cell in row.cells
                                    ]
                                    for row in found_table.rows
                                ]
                                caption = self._extract_table_caption(page, bbox)

                                tables.append({
                                    "page": page_num,
                                    "table_number": idx + 1,
                                    "content": table_data,
                                    "markdown": markdown,
                                    "csv": csv,
                                    "bbox": bbox,
                                    "cell_bboxes": cell_bboxes,
                                    "caption": caption,
                                    "extraction_method": "pdfplumber"
                                })

        except ImportError as e:
            logger.error(f"需要安装依赖: {e}")
        except Exception as e:
            logger.error(f"PDF 表格提取失败: {e}")

        return tables

    @staticmethod
    def _extract_table_caption(page, bbox: List[float]) -> str:
        """Read the closest caption immediately above a detected table."""
        try:
            top = max(0.0, float(bbox[1]) - 72.0)
            text = page.crop((0.0, top, float(page.width), float(bbox[1]))).extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            pattern = re.compile(r"^(?:表\s*\d+|table\s*\d+)", re.I)
            matches = [line for line in lines if pattern.match(line)]
            return matches[-1] if matches else ""
        except Exception:
            return ""

    @staticmethod
    def _is_raster_document_without_vector_tables(pdf_path: str) -> bool:
        """Return true when every page is a dominant raster image without vector lines."""
        try:
            import fitz

            doc = fitz.open(pdf_path)
            if not doc.page_count:
                doc.close()
                return False

            for page in doc:
                page_area = page.rect.width * page.rect.height
                has_dominant_image = False
                for image_info in page.get_images(full=True):
                    for rect in page.get_image_rects(image_info[0]):
                        coverage = rect.width * rect.height / page_area if page_area else 0
                        if coverage >= 0.8:
                            has_dominant_image = True
                            break
                    if has_dominant_image:
                        break

                if not has_dominant_image or page.get_drawings():
                    doc.close()
                    return False

            doc.close()
            return True
        except Exception as exc:
            logger.debug("整页栅格 PDF 检测失败，保留 pdfplumber 路径: %s", exc)
            return False

    def _table_to_markdown(self, table_data: List[List[str]]) -> str:
        """将表格数据转换为 Markdown 格式"""
        if not table_data:
            return ""

        lines = []
        for row_idx, row in enumerate(table_data):
            # 清理单元格内容
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            line = "| " + " | ".join(cleaned_row) + " |"
            lines.append(line)

            # 添加分隔线（在表头后）
            if row_idx == 0 and len(table_data) > 1:
                separator = "| " + " | ".join(["---"] * len(cleaned_row)) + " |"
                lines.append(separator)

        return "\n".join(lines)

    def _table_to_csv(self, table_data: List[List[str]]) -> str:
        """将表格数据转换为 CSV 格式"""
        if not table_data:
            return ""

        lines = []
        for row in table_data:
            # 清理单元格内容并处理逗号
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    cell_str = str(cell).strip()
                    # 如果包含逗号或引号，需要用引号包裹
                    if "," in cell_str or '"' in cell_str:
                        cell_str = '"' + cell_str.replace('"', '""') + '"'
                    cleaned_row.append(cell_str)
            lines.append(",".join(cleaned_row))

        return "\n".join(lines)

    async def extract_suspected_table_images_from_pdf(
        self, 
        pdf_path: str = None, 
        output_dir: str = None,
        min_width: int = 300, 
        min_height: int = 150
    ) -> List[Dict[str, Any]]:
        """
        从 PDF 中提取疑似表格的图片区域（使用 PyMuPDF）
        
        通过尺寸和长宽比过滤掉 Logo、页眉、小图标，只保留"疑似表格"的大尺寸图片
        
        返回格式：
        [{
            "page": 1,
            "image_index": 1,
            "image_path": "/path/to/img_1_p1.jpg",
            "width": 800,
            "height": 400,
            "aspect_ratio": 2.0
        }]
        """
        table_images = []
        path = pdf_path or self.pdf_path

        if not path:
            logger.warning("未提供 PDF 路径，无法提取疑似表格图片")
            return table_images

        try:
            import fitz
            from PIL import Image
            import os

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            else:
                output_dir = f"/tmp/paper_table_images_{Path(path).stem}"
                os.makedirs(output_dir, exist_ok=True)

            doc = fitz.open(path)
            total_pages = len(doc)
            found_large_images = False

            for page_num, page in enumerate(doc, start=1):
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list, start=1):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]

                        img = Image.open(io.BytesIO(image_bytes))
                        width, height = img.size

                        page_width = page.rect.width
                        page_height = page.rect.height

                        if width < min_width or height < min_height:
                            logger.debug(f"跳过过小图片: {width}x{height}")
                            continue

                        is_full_page = width > page_width * 0.95 and height > page_height * 0.95
                        area_ratio = (width * height) / (page_width * page_height) if page_width * page_height > 0 else 0

                        if is_full_page:
                            found_large_images = True
                            logger.debug(f"检测到整页图片: {width}x{height}")
                            continue

                        if area_ratio > 0.8:
                            logger.debug(f"跳过占比过大的图片: {area_ratio:.2f}")
                            continue

                        aspect_ratio = width / height if height > 0 else 0
                        if aspect_ratio > 5 or aspect_ratio < 0.2:
                            logger.debug(f"跳过长宽比异常图片: {aspect_ratio:.2f}")
                            continue

                        image_filename = f"table_img_{img_index}_p{page_num}.jpg"
                        image_path = os.path.join(output_dir, image_filename)
                        img.save(image_path, "JPEG", quality=95)

                        table_images.append({
                            "page": page_num,
                            "image_index": img_index,
                            "image_path": image_path,
                            "width": width,
                            "height": height,
                            "aspect_ratio": aspect_ratio,
                            "area_ratio": area_ratio,
                            "format": base_image.get("ext", "jpg"),
                            "extraction_method": "pymupdf_table_detection"
                        })

                        logger.info(f"📊 第 {page_num} 页疑似表格图片: {width}x{height}, 面积占比: {area_ratio:.2f}")

                    except Exception as e:
                        logger.warning(f"提取第 {page_num} 页第 {img_index} 张图片失败: {e}")
                        continue

            if found_large_images and len(table_images) == 0:
                logger.info("📊 检测到整页图片模式，尝试截取页面区域")
                table_images = await self._extract_table_regions_from_full_pages(doc, output_dir)

            doc.close()

        except ImportError:
            logger.error("需要安装 PyMuPDF: pip install pymupdf")
        except Exception as e:
            logger.error(f"PDF 疑似表格图片提取失败: {e}")

        return table_images

    async def _extract_table_regions_from_full_pages(
        self, 
        doc: object, 
        output_dir: str
    ) -> List[Dict[str, Any]]:
        """
        从整页图片模式的 PDF 中截取疑似表格区域
        
        策略：基于文本坐标的反向精准裁剪（利用PDF中的文本层定位表格位置）
        1. 遍历页面文本块，寻找表格特征关键词（如"表1"、"ACC"、"F1"、"IoU"等）
        2. 收集这些关键词所在文本块的坐标，计算最小外接矩形
        3. 向外扩展padding，截取局部区域图片
        4. 只将这张小图发送给VLM分析
        """
        table_images = []
        import fitz
        from PIL import Image
        import os
        import re

        table_keywords = [
            "表", "Table", "Tab.",
            "方法", "Method", "Methods",
            "ACC", "acc", "accuracy", "准确率",
            "F1", "f1", "F1-score",
            "IoU", "iou", "交并比",
            "Precision", "precision", "精确率",
            "Recall", "recall", "召回率",
            "AUC", "auc",
            "CSS", "css",
            "DSO", "dso",
            "Korus", "korus",
            "Columbia", "columbia",
            "Coverage", "coverage",
            "PhotoShop", "photoshop",
            "NIST", "nist",
            "IMD2020", "imd2020",
            "DeepFake", "deepfake",
            "AIGC", "aigc",
            "CASIA", "casia",
            "DFFD", "dffd",
            "Seq-DeepFake",
            "ControlNet", "controlnet",
            "SDXL", "sdxl",
            "Inpainting", "inpainting"
        ]

        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)

        for page_num, page in enumerate(doc, start=1):
            try:
                blocks = page.get_text("blocks")
                if not blocks:
                    continue

                target_blocks = []
                for block in blocks:
                    if len(block) >= 6:
                        x0, y0, x1, y1, text, block_no = block[:6]
                        if any(keyword in text for keyword in table_keywords):
                            target_blocks.append((x0, y0, x1, y1, text))

                if not target_blocks:
                    continue

                table_titles = []
                for block in blocks:
                    if len(block) >= 6:
                        x0, y0, x1, y1, text, block_no = block[:6]
                        text_stripped = text.strip()
                        if len(text_stripped) < 200 and (re.match(r'^表\d+[:：]', text_stripped) or re.match(r'^Table\s+\d+', text_stripped) or re.match(r'^表\d+[^0-9]', text_stripped)):
                            table_titles.append((x0, y0, x1, y1, text))

                if table_titles:
                    table_groups = []
                    
                    # 按Y坐标排序所有文本块
                    blocks_sorted = sorted(blocks, key=lambda x: x[1] if len(x) >= 6 else 0)
                    
                    for i, title_block in enumerate(table_titles):
                        tx0, ty0, tx1, ty1, ttext = title_block
                        
                        # 如果有下一个表格标题，使用它的 Y 坐标作为边界
                        if i < len(table_titles) - 1:
                            next_title_y0 = table_titles[i + 1][1]
                            region_y_end = next_title_y0 - 10
                        else:
                            # 查找表格标题下方最近的非表格标题文本块
                            region_y_end = ty0 + 200  # 默认扩展200像素
                            
                            for block in blocks_sorted:
                                if len(block) >= 6:
                                    bx0, by0, bx1, by1, btext, bno = block[:6]
                                    # 找到标题下方最近的文本块（且不是表格标题）
                                    if by0 > ty1 + 20:  # 标题下方至少20像素
                                        btext_stripped = btext.strip()
                                        is_table_title = len(btext_stripped) < 200 and (
                                            re.match(r'^表\d+[:：]', btext_stripped) or 
                                            re.match(r'^Table\s+\d+', btext_stripped) or 
                                            re.match(r'^表\d+[^0-9]', btext_stripped)
                                        )
                                        if not is_table_title:
                                            region_y_end = by0 - 10  # 使用这个文本块的 Y 坐标作为边界
                                            break
                            
                            region_y_end = min(region_y_end, page.rect.height - 50)

                        region_height = region_y_end - ty0
                        if region_height < 100:
                            region_height = 150
                            region_y_end = min(ty0 + region_height, page.rect.height - 50)

                        table_groups.append([(tx0, ty0, page.rect.width - 50, region_y_end, ttext)])
                else:
                    # 泛化关键词（Method、ACC、数据集名等）在正文中很常见，不能据此
                    # 把整页送给视觉模型。无明确标题的结构化表格已由 pdfplumber 处理；
                    # 纯扫描件应进入独立 OCR/版面检测回退。
                    continue

                for group_idx, group in enumerate(table_groups):
                    min_x0 = min(b[0] for b in group)
                    min_y0 = min(b[1] for b in group)
                    max_x1 = max(b[2] for b in group)
                    max_y1 = max(b[3] for b in group)

                    padding = 25
                    clip_rect = fitz.Rect(
                        max(0, min_x0 - padding),
                        max(0, min_y0 - padding),
                        min(page.rect.width, max_x1 + padding),
                        min(page.rect.height, max_y1 + padding)
                    )

                    clip_width = clip_rect.width
                    clip_height = clip_rect.height

                    if clip_width < 50 or clip_height < 50:
                        continue

                    if clip_width > page.rect.width * 0.95 and clip_height > page.rect.height * 0.95:
                        continue

                    clip_aspect_ratio = clip_width / clip_height if clip_height > 0 else 0
                    if clip_aspect_ratio > 5.0 or clip_aspect_ratio < 0.2:
                        continue

                    pix = page.get_pixmap(clip=clip_rect, matrix=mat)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    region_width, region_height = img.size
                    if region_width < 200 or region_height < 100:
                        continue

                    image_filename = f"table_region_{page_num}_{group_idx + 1}.jpg"
                    image_path = os.path.join(output_dir, image_filename)
                    img.save(image_path, "JPEG", quality=95)

                    table_images.append({
                        "page": page_num,
                        "image_index": len(table_images) + 1,
                        "image_path": image_path,
                        "width": region_width,
                        "height": region_height,
                        "aspect_ratio": region_width / region_height if region_height > 0 else 0,
                        "format": "jpg",
                        "extraction_method": "text_bbox_cropping",
                        "bbox": [clip_rect.x0, clip_rect.y0, clip_rect.x1, clip_rect.y1],
                        "group_index": group_idx + 1,
                        "total_groups": len(table_groups)
                    })

                    logger.info(f"📊 第 {page_num} 页第{group_idx+1}组表格: {region_width}x{region_height}, bbox: ({clip_rect.x0:.1f}, {clip_rect.y0:.1f})-({clip_rect.x1:.1f}, {clip_rect.y1:.1f})")

            except Exception as e:
                logger.warning(f"截取第 {page_num} 页区域失败: {e}")
                continue

        return table_images

    async def analyze_table_images(self, table_images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用多模态 LLM 分析疑似表格图片
        
        Args:
            table_images: 疑似表格图片列表
            
        Returns:
            分析后的表格数据列表
        """
        from .image_analyzer import get_image_analyzer
        
        analyzer = get_image_analyzer()
        semaphore = asyncio.Semaphore(3)

        async def analyze_one(item: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
            image_path = item.get("image_path")
            if not image_path:
                return item, {"success": False, "is_table": False, "error": "缺少图片路径"}
            async with semaphore:
                return item, await analyzer.analyze_table_image(image_path)

        analyzed = await asyncio.gather(*(analyze_one(item) for item in table_images))

        # 并发调用中的瞬时错误串行重试一次，避免限流或格式错误直接造成表格丢失。
        for index, (item, analysis_result) in enumerate(analyzed):
            if not analysis_result.get("success") and item.get("image_path"):
                logger.warning("表格候选 %s 首次分析失败，串行重试", index + 1)
                await asyncio.sleep(0.5)
                analyzed[index] = (
                    item,
                    await analyzer.analyze_table_image(item["image_path"]),
                )

        results = []
        for index, (item, analysis_result) in enumerate(analyzed):
            image_path = item.get("image_path")
            page_num = item.get("page")

            if analysis_result.get("is_table"):
                results.append({
                    "page": page_num,
                    "image_index": item.get("image_index"),
                    "table_title": analysis_result.get("table_title", f"表{index + 1}"),
                    "markdown_content": analysis_result.get("markdown_content", ""),
                    "csv_content": analysis_result.get("csv_content", ""),
                    "key_data_points": analysis_result.get("key_data_points", []),
                    "core_conclusion": analysis_result.get("core_conclusion", ""),
                    "qa_context": analysis_result.get("qa_context", ""),
                    "image_path": image_path,
                    "extraction_method": "vlm_table_extraction"
                })
                logger.info(f"✅ 第 {page_num} 页图片确认为表格: {analysis_result.get('table_title', '未命名表格')}")
            else:
                logger.info(f"❌ 第 {page_num} 页图片不是表格")

        return results

    async def extract_images_from_pdf(self, pdf_path: str = None, output_dir: str = None) -> List[Dict[str, Any]]:
        """
        从 PDF 中提取图片（使用 PyMuPDF）

        返回格式：
        [{
            "page": 1,
            "image_index": 1,
            "image_path": "/path/to/img_1_p1.jpg",
            "width": 800,
            "height": 600,
            "caption": "图1: 架构图"  # 如果能识别到
        }]
        """
        images = []
        path = pdf_path or self.pdf_path

        if not path:
            logger.warning("未提供 PDF 路径，无法提取图片")
            return images

        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import os

            # 创建输出目录
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            else:
                output_dir = f"/tmp/paper_images_{Path(path).stem}"
                os.makedirs(output_dir, exist_ok=True)

            # 打开 PDF
            doc = fitz.open(path)

            for page_num, page in enumerate(doc, start=1):
                # 获取页面中的所有图像
                image_list = page.get_images(full=True)
                full_page_processed = False

                for img_index, img_info in enumerate(image_list, start=1):
                    try:
                        # 提取图像
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]

                        page_area = page.rect.width * page.rect.height
                        image_rects = page.get_image_rects(xref)
                        max_page_coverage = max(
                            (
                                max(0, rect.width) * max(0, rect.height) / page_area
                                for rect in image_rects
                            ),
                            default=0,
                        ) if page_area else 0
                        if max_page_coverage >= 0.8:
                            if full_page_processed:
                                continue
                            full_page_processed = True

                            figure_regions = self._extract_figure_regions_from_page(
                                page=page,
                                page_num=page_num,
                                output_dir=output_dir,
                                start_index=len(images) + 1,
                            )
                            if figure_regions:
                                images.extend(figure_regions)
                                logger.info(
                                    "整页背景第 %s 页裁出 %s 个图区域",
                                    page_num,
                                    len(figure_regions),
                                )
                                continue

                            # 纯扫描页没有可定位文字层时保留整页视觉回退，避免召回归零。
                            if not page.get_text().strip():
                                img = Image.open(io.BytesIO(image_bytes))
                                width, height = img.size
                                image_path = os.path.join(output_dir, f"full_page_p{page_num}.jpg")
                                img.convert("RGB").save(image_path, "JPEG", quality=85)
                                images.append({
                                    "page": page_num,
                                    "image_index": len(images) + 1,
                                    "image_path": image_path,
                                    "width": width,
                                    "height": height,
                                    "aspect_ratio": width / height if height else 0,
                                    "caption": None,
                                    "extraction_method": "full_page_scan_fallback",
                                })
                                logger.info("纯扫描页 %s 保留整页视觉回退", page_num)
                                continue

                            logger.info(
                                "整页背景第 %s 页无图标题，跳过普通图片分析",
                                page_num,
                            )
                            continue

                        # 转换为 PIL Image
                        img = Image.open(io.BytesIO(image_bytes))

                        # 尺寸过滤
                        width, height = img.size
                        if width < 100 or height < 100:
                            logger.info(f"跳过过小图片: {width}x{height}")
                            continue

                        # 长宽比过滤（极端比例可能是装饰或水印）
                        aspect_ratio = width / height if height > 0 else 0
                        if aspect_ratio > 10 or aspect_ratio < 0.1:
                            logger.info(f"跳过长宽比异常图片: {aspect_ratio:.2f}")
                            continue

                        # 保存图片
                        image_filename = f"img_{img_index}_p{page_num}.jpg"
                        image_path = os.path.join(output_dir, image_filename)
                        img.save(image_path, "JPEG", quality=95)

                        images.append({
                            "page": page_num,
                            "image_index": img_index,
                            "image_path": image_path,
                            "width": width,
                            "height": height,
                            "aspect_ratio": aspect_ratio,
                            "caption": None,  # 需要后续 OCR 或多模态识别
                            "extraction_method": "pymupdf"
                        })

                        logger.info(f"第 {page_num} 页第 {img_index} 张图片提取成功: {width}x{height}")

                    except Exception as e:
                        logger.warning(f"提取第 {page_num} 页第 {img_index} 张图片失败: {e}")
                        continue

            doc.close()

        except ImportError:
            logger.error("需要安装 PyMuPDF: pip install pymupdf")
        except Exception as e:
            logger.error(f"PDF 图片提取失败: {e}")

        return images

    def _extract_figure_regions_from_page(
        self,
        page: object,
        page_num: int,
        output_dir: str,
        start_index: int,
    ) -> List[Dict[str, Any]]:
        """Crop figure candidates above explicit figure captions on rasterized pages."""
        import fitz
        import os

        blocks = [block for block in page.get_text("blocks") if len(block) >= 5]
        caption_pattern = re.compile(
            r"^(?:图\s*\d+\s*[：:]|fig(?:ure)?\.?\s*\d+\s*[.:])",
            re.IGNORECASE,
        )
        captions = [block for block in blocks if caption_pattern.match(block[4].strip())]
        if not captions:
            return []

        page_width = page.rect.width
        page_height = page.rect.height
        margin_x = max(24.0, page_width * 0.08)
        regions = []
        full_page_fallback_added = False

        for offset, caption in enumerate(sorted(captions, key=lambda block: block[1])):
            cx0, cy0, cx1, cy1, caption_text = caption[:5]

            if cx0 >= page_width * 0.48:
                region_x0, region_x1 = page_width * 0.49, page_width - margin_x
            elif cx1 <= page_width * 0.52:
                region_x0, region_x1 = margin_x, page_width * 0.51
            else:
                region_x0, region_x1 = margin_x, page_width - margin_x

            previous_bottom = page_height * 0.05
            preceding_content_blocks = []
            preceding_caption_is_table = False
            for block in blocks:
                bx0, by0, bx1, by1 = block[:4]
                if by1 >= cy0 - 4:
                    continue
                overlap = max(0.0, min(region_x1, bx1) - max(region_x0, bx0))
                if overlap >= min(region_x1 - region_x0, bx1 - bx0) * 0.2:
                    previous_bottom = max(previous_bottom, by1)
                    text = block[4].strip()
                    if by0 > page_height * 0.06:
                        preceding_content_blocks.append(block)
                    if re.match(r"^(?:表\s*\d+|table\s*\d+)", text, re.IGNORECASE):
                        preceding_caption_is_table = True

            clip = fitz.Rect(
                max(0, region_x0 - 8),
                max(0, previous_bottom + 5),
                min(page_width, region_x1 + 8),
                min(page_height, cy1 + 6),
            )
            boundary_is_ambiguous = (
                len(preceding_content_blocks) >= 3
                or preceding_caption_is_table
                or clip.height < page_height * 0.18
            )
            if boundary_is_ambiguous:
                if full_page_fallback_added:
                    continue
                full_page_fallback_added = True
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                image_index = start_index + len(regions)
                image_path = os.path.join(
                    output_dir,
                    f"figure_page_{image_index}_p{page_num}.jpg",
                )
                pix.save(image_path)
                regions.append({
                    "page": page_num,
                    "image_index": image_index,
                    "image_path": image_path,
                    "width": pix.width,
                    "height": pix.height,
                    "aspect_ratio": pix.width / pix.height if pix.height else 0,
                    "caption": re.sub(r"\s+", " ", caption_text).strip(),
                    "bbox": [0, 0, page_width, page_height],
                    "extraction_method": "caption_page_fallback",
                })
                continue

            if clip.width < 120 or clip.height < 60:
                continue

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            image_index = start_index + offset
            image_path = os.path.join(
                output_dir,
                f"figure_region_{image_index}_p{page_num}.jpg",
            )
            pix.save(image_path)
            regions.append({
                "page": page_num,
                "image_index": image_index,
                "image_path": image_path,
                "width": pix.width,
                "height": pix.height,
                "aspect_ratio": pix.width / pix.height if pix.height else 0,
                "caption": re.sub(r"\s+", " ", caption_text).strip(),
                "bbox": [clip.x0, clip.y0, clip.x1, clip.y1],
                "extraction_method": "caption_region_cropping",
            })

        return regions

    def extract_text_from_image(self, image_path: str) -> str:
        """
        使用 OCR 从图片中提取文字（需要安装 pytesseract）
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            提取的文字内容
        """
        try:
            from PIL import Image
            import pytesseract
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip()
        
        except ImportError as e:
            logger.error(f"缺少 OCR 依赖库: {e}")
            logger.info("安装依赖: pip install pytesseract pillow")
            return ""
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return ""

    def extract_tables_from_text(self, text: str, section_title: str = "", page: int = None) -> List[Dict[str, Any]]:
        """从文本中提取表格信息（基于标题和原始内容）"""
        tables = []

        for pattern in self.table_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                table_num = match.group(1)
                content = match.group(2).strip()

                # 分离标题和内容：标题通常在第一行，内容在后面
                lines = content.split('\n')
                caption_text = lines[0].strip() if lines else ""
                table_content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""

                tables.append({
                    "table_number": int(table_num),
                    "caption": f"表{table_num}: {caption_text}" if caption_text else f"表{table_num}",
                    "content": self._parse_table_content(table_content),
                    "raw_content": content,
                    "section": section_title,
                    "page": page,
                    "position": section_title,
                    "extraction_method": "text_pattern"
                })

        return tables

    def extract_figures_from_text(self, text: str, section_title: str = "", page: int = None) -> List[Dict[str, Any]]:
        """从文本中提取图片信息（基于标题和描述）"""
        figures = []

        for pattern in self.figure_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                fig_num = match.group(1)
                content = match.group(2).strip()

                figures.append({
                    "figure_number": int(fig_num),
                    "caption": f"图{fig_num}: {content[:100]}...",
                    "description": content,
                    "section": section_title,
                    "page": page,
                    "position": section_title,
                    "type": self._infer_figure_type(content),
                    "extraction_method": "text_pattern"
                })

        return figures

    def extract_formulas(self, text: str, section_title: str = "") -> List[Dict[str, Any]]:
        """提取公式"""
        formulas = []

        for pattern in self.formula_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                formula = match.group(1).strip()

                formulas.append({
                    "formula": formula,
                    "section": section_title,
                    "position": section_title,
                    "type": "inline" if formula.startswith("$") else "block"
                })

        return formulas

    def _parse_table_content(self, raw_content: str) -> List[List[str]]:
        """解析表格内容为二维列表"""
        rows = raw_content.split('\n')
        table_data = []

        for row in rows:
            if '|' in row:
                cells = [c.strip() for c in row.split('|') if c.strip()]
            elif '\t' in row:
                cells = [c.strip() for c in row.split('\t') if c.strip()]
            else:
                cells = re.split(r'\s{2,}', row.strip())

            if cells:
                table_data.append(cells)

        return table_data

    def _infer_figure_type(self, description: str) -> str:
        """根据描述推断图片类型"""
        description = description.lower()

        type_keywords = {
            '架构图': ['架构', '结构', '流程图', 'framework', 'architecture'],
            '实验图表': ['实验', '结果', '对比', 'accuracy', 'result', 'chart', '曲线', '柱状'],
            '网络图': ['网络', '模型', 'neural', 'network'],
            '示例图': ['示例', '样例', 'example'],
            '数据可视化': ['数据', '可视化', 'distribution', '散点', 'scatter']
        }

        for fig_type, keywords in type_keywords.items():
            if any(keyword in description for keyword in keywords):
                return fig_type
        return '其他'

    async def extract_all_multimedia(self, pdf_path: str = None, text: str = "", section_title: str = "") -> Dict[str, Any]:
        """
        综合提取所有多媒体信息（文本 + PDF）

        Args:
            pdf_path: PDF 文件路径
            text: 原始文本（用于提取标题和描述）
            section_title: 章节标题

        Returns:
            {
                "tables": [...],  # 表格数据（来自 PDF + VLM）
                "figures": [...],  # 图片信息（来自文本描述 + PDF）
                "formulas": [...], # 公式（来自文本）
                "raw_multimedia": {...}  # 原始多媒体信息
            }
        """
        result = {
            "tables": [],
            "figures": [],
            "formulas": [],
            "raw_multimedia": {
                "tables_from_text": [],
                "figures_from_text": [],
                "tables_from_pdf": [],
                "tables_from_images": [],
                "images_from_pdf": []
            }
        }

        # 1. 从文本提取标题/描述
        if text:
            result["raw_multimedia"]["tables_from_text"] = self.extract_tables_from_text(text, section_title)
            result["raw_multimedia"]["figures_from_text"] = self.extract_figures_from_text(text, section_title)
            result["formulas"] = self.extract_formulas(text, section_title)

        # 2. 从 PDF 提取表格数据（pdfplumber）
        if pdf_path:
            result["raw_multimedia"]["tables_from_pdf"] = await self.extract_tables_from_pdf(pdf_path)
            # 注意：图片提取已移至 papers.py 的论文级别统一处理

        # 3. 如果 pdfplumber 没有提取到表格，尝试从图片中提取（VLM）
        if pdf_path and len(result["raw_multimedia"]["tables_from_pdf"]) == 0:
            logger.info("📊 pdfplumber 未提取到表格，尝试从图片中提取（VLM）")
            table_images = await self.extract_suspected_table_images_from_pdf(pdf_path)
            if table_images:
                logger.info(f"📊 找到 {len(table_images)} 个疑似表格图片")
                result["raw_multimedia"]["tables_from_images"] = await self.analyze_table_images(table_images)
            else:
                logger.info("📊 未找到疑似表格图片")

        # 4. 合并结果（优先使用 PDF 数据，其次 VLM 数据，最后文本数据）
        result["tables"] = self._merge_table_data_enhanced(
            result["raw_multimedia"]["tables_from_pdf"],
            result["raw_multimedia"]["tables_from_images"],
            result["raw_multimedia"]["tables_from_text"]
        )
        result["figures"] = result["raw_multimedia"]["figures_from_text"]

        # 5. 对表格进行语义分析
        analyzer = TableSemanticAnalyzer()
        for table in result["tables"]:
            table_data = table.get("content", [])
            caption = table.get("caption", "")
            analysis = await analyzer.analyze_table(table_data, caption, section_title)
            table["semantic_analysis"] = analysis
            if not table.get("qa_context"):
                table["qa_context"] = analyzer.get_qa_context(analysis)

        # 注意：图片分析已移至 papers.py 的论文级别统一处理
        # 避免每个章节重复提取和分析图片

        return result

    def _merge_table_data(self, pdf_tables: List, text_tables: List) -> List[Dict]:
        """合并 PDF 和文本中的表格数据（旧版，兼容）"""
        return self._merge_table_data_enhanced(pdf_tables, [], text_tables)

    def _merge_table_data_enhanced(self, pdf_tables: List, vlm_tables: List, text_tables: List) -> List[Dict]:
        """合并 PDF、VLM 和文本中的表格数据"""
        merged = []
        existing_captions = set()

        # 1. 先添加 PDF 表格（最准确）
        for table in pdf_tables:
            caption = table.get("caption", "")
            if caption not in existing_captions:
                existing_captions.add(caption)
                merged.append({
                    "table_number": table.get("table_number", len(merged) + 1),
                    "page": table.get("page"),
                    "content": table.get("content", []),
                    "markdown": table.get("markdown", ""),
                    "csv": table.get("csv", ""),
                    "caption": caption,
                    "source": "pdfplumber",
                    "extraction_method": "pdf"
                })

        # 2. 添加 VLM 提取的表格（其次准确）
        for table in vlm_tables:
            caption = table.get("table_title", "")
            if caption and caption not in existing_captions:
                existing_captions.add(caption)
                content = self._parse_markdown_table(table.get("markdown_content", ""))
                merged.append({
                    "table_number": len(merged) + 1,
                    "page": table.get("page"),
                    "content": content,
                    "markdown": table.get("markdown_content", ""),
                    "csv": table.get("csv_content", ""),
                    "caption": caption,
                    "source": "vlm_image",
                    "extraction_method": "vlm",
                    "key_data_points": table.get("key_data_points", []),
                    "core_conclusion": table.get("core_conclusion", ""),
                    "qa_context": table.get("qa_context", ""),
                    "image_path": table.get("image_path", "")
                })

        # 3. 添加文本中识别到但未提取到的表格（最后）
        for table in text_tables:
            caption = table.get("caption", "")
            if caption and caption not in existing_captions:
                existing_captions.add(caption)
                merged.append({
                    "table_number": table.get("table_number", len(merged) + 1),
                    "page": table.get("page"),
                    "content": table.get("content", []),
                    "caption": caption,
                    "source": "text_pattern",
                    "extraction_method": "text"
                })

        return merged

    def _parse_markdown_table(self, markdown: str) -> List[List[str]]:
        """解析 Markdown 表格为二维列表"""
        if not markdown:
            return []

        lines = markdown.strip().split('\n')
        table_data = []

        for line in lines:
            if line.startswith('**表'):
                continue
            if line.startswith('|'):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells and not all(c == '---' for c in cells):
                    table_data.append(cells)

        return table_data


# 依赖库安装提示
REQUIRED_PACKAGES = {
    "pdfplumber": "pip install pdfplumber  # PDF表格提取",
    "pdf2image": "pip install pdf2image    # PDF转图片",
    "Pillow": "pip install pillow           # 图片处理",
    "pytesseract": "pip install pytesseract  # OCR文字识别（可选）"
}


if __name__ == "__main__":
    print("多媒体提取器使用示例：")
    print("=" * 60)

    # 示例1：从文本提取
    extractor = MultimediaExtractor()
    test_text = """
    表1: 实验结果对比

    方法 | 准确率 | 召回率
    ----|--------|--------
    A | 92.5% | 89.3%

    图1: 模型架构图

    展示Transformer结构。
    """

    tables = extractor.extract_tables_from_text(test_text, "实验")
    figures = extractor.extract_figures_from_text(test_text, "实验")

    print("从文本提取的表格:", json.dumps(tables, ensure_ascii=False, indent=2))
    print("\n从文本提取的图片:", json.dumps(figures, ensure_ascii=False, indent=2))

    # 示例2：需要的依赖库
    print("\n需要的依赖库：")
    for pkg, install_cmd in REQUIRED_PACKAGES.items():
        print(f"  - {install_cmd}")
