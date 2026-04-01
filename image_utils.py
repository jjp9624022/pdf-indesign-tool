"""
Image utilities for optimizing images before sending to Ollama
"""

from PIL import Image
import io
from typing import Tuple, Optional


def compress_image(
    image: Image.Image,
    max_size: Tuple[int, int] = (1024, 1024),
    quality: int = 85,
    format: str = "JPEG",
) -> Image.Image:
    """
    Compress and resize image to reduce size for Ollama processing

    Args:
        image: PIL Image
        max_size: Maximum (width, height) for resizing
        quality: JPEG quality (1-100)
        format: Output format (JPEG, PNG)

    Returns:
        Compressed PIL Image
    """
    # Resize if too large
    if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
        image = image.copy()
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Convert to RGB if necessary (for JPEG)
    if format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        if image.mode in ("RGBA", "LA"):
            background.paste(
                image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None
            )
            image = background

    return image


def image_to_bytes(
    image: Image.Image, format: str = "JPEG", quality: int = 85
) -> bytes:
    """
    Convert PIL Image to bytes

    Args:
        image: PIL Image
        format: Output format
        quality: JPEG quality

    Returns:
        Image bytes
    """
    img_bytes = io.BytesIO()
    if format == "JPEG":
        image.save(img_bytes, format=format, quality=quality, optimize=True)
    else:
        image.save(img_bytes, format=format, optimize=True)
    return img_bytes.getvalue()


def prepare_image_for_ollama(
    image: Image.Image, max_size: Tuple[int, int] = (1024, 1024), quality: int = 85
) -> bytes:
    """
    Full pipeline: compress and convert image to bytes for Ollama

    Args:
        image: PIL Image
        max_size: Maximum dimensions
        quality: JPEG quality

    Returns:
        Compressed image bytes
    """
    compressed = compress_image(
        image, max_size=max_size, quality=quality, format="JPEG"
    )
    return image_to_bytes(compressed, format="JPEG", quality=quality)
