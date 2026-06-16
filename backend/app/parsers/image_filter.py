"""图片智能筛选器 - 判断图片是否值得用 LLM 分析"""

import logging
from typing import Dict, Any, List
from pathlib import Path
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ImageFilter:
    """智能筛选图片，只分析有意义的图片"""

    def __init__(self):
        pass

    def should_analyze(self, image_path: str) -> Dict[str, Any]:
        """
        判断图片是否值得用 LLM 分析

        Args:
            image_path: 图片路径

        Returns:
            {
                "should_analyze": bool,  # 是否需要分析
                "reason": str,  # 原因
                "confidence": float,  # 置信度
                "image_type": str  # 图片类型
            }
        """
        try:
            # 1. 读取图片
            img = Image.open(image_path)
            img_array = np.array(img)

            # 2. 基础特征分析
            features = self._extract_features(img_array)

            # 3. 判断图片类型
            image_type = self._classify_image(features)

            # 4. 决定是否分析
            should_analyze = image_type in ["chart", "table", "architecture", "diagram"]

            return {
                "should_analyze": should_analyze,
                "reason": f"识别为 {image_type} 类型图片",
                "confidence": features.get("confidence", 0.5),
                "image_type": image_type,
                "features": features
            }

        except Exception as e:
            logger.warning(f"图片筛选失败 {image_path}: {e}")
            return {
                "should_analyze": True,  # 出错时保守处理，还是分析
                "reason": f"筛选失败，默认分析: {str(e)}",
                "confidence": 0.0,
                "image_type": "unknown",
                "features": {}
            }

    def _extract_features(self, img_array: np.ndarray) -> Dict[str, Any]:
        """提取图片特征"""
        features = {}

        # 1. 颜色分布（黑白文本 vs 彩色图表）
        if len(img_array.shape) == 3:
            # 彩色图片
            rgb_mean = np.mean(img_array, axis=(0, 1))
            color_variance = np.var(img_array, axis=(0, 1)).mean()
            features["is_colorful"] = color_variance > 1000
            features["color_variance"] = color_variance
        else:
            # 灰度图片
            features["is_colorful"] = False
            features["color_variance"] = 0

        # 2. 边缘密度（图表通常有较多线条）
        from cv2 import Canny, cvtColor, COLOR_BGR2GRAY
        if len(img_array.shape) == 3:
            gray = cvtColor(img_array, COLOR_BGR2GRAY)
        else:
            gray = img_array

        edges = Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        features["edge_density"] = edge_density

        # 3. 文本密度（表格通常有较多文本）
        # 简单判断：边缘密度适中且颜色变化小
        features["text_density"] = edge_density * (1 if not features.get("is_colorful", False) else 0.5)

        # 4. 置信度
        confidence = 0.5
        if features.get("edge_density", 0) > 0.05:
            confidence += 0.2
        if features.get("is_colorful", False):
            confidence += 0.2
        if features.get("text_density", 0) > 0.1:
            confidence += 0.1

        features["confidence"] = min(confidence, 1.0)

        return features

    def _classify_image(self, features: Dict[str, Any]) -> str:
        """根据特征分类图片"""
        edge_density = features.get("edge_density", 0)
        is_colorful = features.get("is_colorful", False)
        text_density = features.get("text_density", 0)

        # 分类规则
        if edge_density > 0.15 and is_colorful:
            return "chart"  # 图表：线条多且彩色
        elif edge_density > 0.1 and text_density > 0.1:
            return "table"  # 表格：线条和文本都多
        elif edge_density > 0.08:
            return "architecture"  # 架构图：线条较多
        elif edge_density > 0.05:
            return "diagram"  # 示意图
        else:
            return "text"  # 纯文本页面


# 全局筛选器实例
_image_filter: ImageFilter = None


def get_image_filter() -> ImageFilter:
    """获取图片筛选器实例"""
    global _image_filter
    if _image_filter is None:
        _image_filter = ImageFilter()
    return _image_filter