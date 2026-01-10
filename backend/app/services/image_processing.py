import re
from pathlib import Path
from PIL import Image, ImageOps

def resize_to_max_edge(img: Image.Image, max_edge: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_edge:
        return img
    if w >= h:
        new_w = max_edge
        new_h = int(h * (max_edge / w))
    else:
        new_h = max_edge
        new_w = int(w * (max_edge / h))
    
    if hasattr(Image, "Resampling"):
        resample_method = Image.Resampling.LANCZOS
    else:
        resample_method = Image.LANCZOS  # pylint: disable=no-member
    return img.resize((new_w, new_h), resample_method)

def save_webp(img: Image.Image, path: Path, quality: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=quality, method=6)

def normalize_image(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")
    else:
        im = im.convert("RGB")
    return im

def process_and_save_image(image_file, output_path: Path):
    """
    Process uploaded image: normalize, resize (optional), convert to WebP, and save.
    """
    try:
        with Image.open(image_file) as im:
            im = normalize_image(im)
            # Resize if needed? Let's assume we want to keep it reasonable, say max 1600
            im = resize_to_max_edge(im, 1600)
            
            # Change extension to .webp
            new_path = output_path.with_suffix(".webp")
            save_webp(im, new_path, quality=85)
            return new_path
    except Exception as e:
        raise RuntimeError(f"Failed to process image: {e}")
