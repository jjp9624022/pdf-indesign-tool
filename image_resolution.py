"""
Multi-resolution image processing for OCR optimization

Strategy:
1. Low-resolution image for text region detection (fast, memory-efficient)
2. High-resolution regions for accurate text extraction (high quality)
"""

from PIL import Image
from typing import Tuple, List, Dict, Any, Optional
import io


class ResolutionLevel:
    """Represents a resolution level for processing"""

    def __init__(self, name: str, max_dimension: int, quality: int = 85):
        self.name = name
        self.max_dimension = max_dimension
        self.quality = quality

    def __repr__(self):
        return f"ResolutionLevel({self.name}, {self.max_dimension}px)"


# Predefined resolution levels
LOW_RES = ResolutionLevel("low", 512, 75)  # For detection
MEDIUM_RES = ResolutionLevel("medium", 1024, 85)  # For preview
HIGH_RES = ResolutionLevel("high", 2048, 90)  # For detailed analysis
FULL_RES = ResolutionLevel("full", 4096, 95)  # Original quality


def create_resolution_pyramid(
    image: Image.Image, levels: List[ResolutionLevel] = None
) -> Dict[str, Image.Image]:
    """
    Create a pyramid of images at different resolutions

    Args:
        image: Original PIL Image
        levels: List of resolution levels (default: low, medium, high)

    Returns:
        Dictionary mapping resolution names to images
    """
    if levels is None:
        levels = [LOW_RES, MEDIUM_RES, HIGH_RES]

    pyramid = {}
    original_size = image.size

    for level in levels:
        # Calculate new size maintaining aspect ratio
        max_dim = max(original_size)
        if max_dim > level.max_dimension:
            scale = level.max_dimension / max_dim
            new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
        else:
            new_size = original_size

        # Resize image
        if new_size != original_size:
            resized = image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            resized = image.copy()

        pyramid[level.name] = resized
        print(f"  {level.name}: {original_size} -> {new_size}")

    return pyramid


def extract_region_at_full_resolution(
    full_image: Image.Image, bbox: Tuple[int, int, int, int], context_scale: float = 1.2
) -> Image.Image:
    """
    Extract a region from full-resolution image with optional context padding

    Args:
        full_image: Original high-resolution image
        bbox: (x, y, width, height) from detection
        context_scale: Factor to expand region for context (default: 1.2)

    Returns:
        Cropped high-resolution region
    """
    x, y, w, h = bbox

    # Add context padding
    center_x = x + w // 2
    center_y = y + h // 2
    new_w = int(w * context_scale)
    new_h = int(h * context_scale)

    # Calculate new bounds
    x1 = max(0, center_x - new_w // 2)
    y1 = max(0, center_y - new_h // 2)
    x2 = min(full_image.width, center_x + new_w // 2)
    y2 = min(full_image.height, center_y + new_h // 2)

    # Crop from full resolution
    region = full_image.crop((x1, y1, x2, y2))

    return region


def smart_resize_for_ocr(
    image: Image.Image, target_short_side: int = 512, max_long_side: int = 1024
) -> Image.Image:
    """
    Smart resize optimized for OCR:
    - Ensure short side is at least target_short_side for good character recognition
    - Cap long side to max_long_side to avoid memory issues
    - Maintain aspect ratio

    Args:
        image: Input PIL Image
        target_short_side: Minimum short side dimension
        max_long_side: Maximum long side dimension

    Returns:
        Resized PIL Image
    """
    w, h = image.size
    short_side = min(w, h)
    long_side = max(w, h)

    # Calculate scale factors
    scale_up = target_short_side / short_side if short_side < target_short_side else 1.0
    scale_down = (
        max_long_side / long_side if long_side * scale_up > max_long_side else 1.0
    )

    # Apply combined scale
    final_scale = scale_up * scale_down

    if final_scale != 1.0:
        new_size = (int(w * final_scale), int(h * final_scale))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    return image.copy()


# Convenience function for the full pipeline
def process_with_resolution_pyramid(
    image: Image.Image,
    detection_level: ResolutionLevel = LOW_RES,
    extraction_level: ResolutionLevel = FULL_RES,
) -> Dict[str, Any]:
    """
    Process image through resolution pyramid pipeline

    Returns:
        Dict with:
        - detection_image: Low-res for text detection
        - extraction_image: High-res for text extraction
        - scale_factor: Ratio between resolutions (for coordinate mapping)
    """
    pyramid = create_resolution_pyramid(
        image, levels=[detection_level, extraction_level]
    )

    detection_img = pyramid[detection_level.name]
    extraction_img = pyramid[extraction_level.name]

    # Calculate scale factor for coordinate mapping
    scale_factor = extraction_img.width / detection_img.width

    return {
        "detection_image": detection_img,
        "extraction_image": extraction_img,
        "scale_factor": scale_factor,
        "original_image": image,
    }
