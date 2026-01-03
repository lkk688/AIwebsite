import re
from pathlib import Path
from PIL import Image, ImageOps

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

def is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in ALLOWED_EXT and not p.name.startswith(".")

def natural_key(s: str):
    # Sort IMG_2.jpg before IMG_10.jpg (Natural Sort)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

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
    
    # Use Image.Resampling.LANCZOS if available (Pillow >= 9.1.0), otherwise fallback to Image.LANCZOS
    resample_method = getattr(Image, "Resampling", Image).LANCZOS
    return img.resize((new_w, new_h), resample_method)

def save_webp(img: Image.Image, path: Path, quality: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=quality, method=6)

def save_jpg(img: Image.Image, path: Path, quality: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)

def export_variants_for_one_image(
    im: Image.Image,
    dst_dir: Path,
    idx: int,
    sizes: tuple[int, ...],
    thumb_size: int,
    webp_quality: int,
    jpg_quality: int,
    export_jpg_fallback: bool,
):
    # Regular sizes
    for max_edge in sizes:
        out = resize_to_max_edge(im, max_edge)

        webp_path = dst_dir / f"{idx}_{max_edge}.webp"
        save_webp(out, webp_path, webp_quality)

        if export_jpg_fallback:
            jpg_path = dst_dir / f"{idx}_{max_edge}.jpg"
            save_jpg(out, jpg_path, jpg_quality)

    # Thumbnail (thumb)
    thumb = resize_to_max_edge(im, thumb_size)
    webp_thumb_path = dst_dir / f"{idx}_thumb.webp"
    save_webp(thumb, webp_thumb_path, webp_quality)

    if export_jpg_fallback:
        jpg_thumb_path = dst_dir / f"{idx}_thumb.jpg"
        save_jpg(thumb, jpg_thumb_path, jpg_quality)

def export_webp_and_jpg_variants(
    src_dir: Path,
    dst_root: Path,
    slug: str,
    sizes=(600, 1600),
    thumb_size=300,
    webp_quality=82,
    jpg_quality=85,
    export_jpg_fallback=True,
):
    dst_dir = dst_root / slug
    dst_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(
        [p for p in src_dir.iterdir() if is_image(p)],
        key=lambda p: natural_key(p.name),
    )

    if not images:
        raise SystemExit(f"No images found in: {src_dir}")

    for idx, img_path in enumerate(images, start=1):
        try:
            with Image.open(img_path) as im:
                # Fix EXIF orientation
                im = ImageOps.exif_transpose(im)

                # Convert to RGB (remove alpha, avoid jpg/webp compatibility issues)
                if im.mode in ("RGBA", "P"):
                    im = im.convert("RGB")
                else:
                    im = im.convert("RGB")

                export_variants_for_one_image(
                    im=im,
                    dst_dir=dst_dir,
                    idx=idx,
                    sizes=tuple(int(x) for x in sizes),
                    thumb_size=int(thumb_size),
                    webp_quality=int(webp_quality),
                    jpg_quality=int(jpg_quality),
                    export_jpg_fallback=bool(export_jpg_fallback),
                )

            print(f"[OK] {img_path.name} -> {slug}/{idx}_(sizes|thumb).(webp|jpg)")

        except Exception as e:
            print(f"[WARN] Failed: {img_path} -> {e}")

    print(f"\nDone. Exported to: {dst_dir}")
    print(f"Total source images: {len(images)}")
    print(f"Sizes: {sizes}, Thumb: {thumb_size}")
    print(f"WebP quality: {webp_quality}, JPG quality: {jpg_quality}")
    print(f"JPG fallback: {export_jpg_fallback}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Process one product folder into webp (+jpg fallback) variants.")
    parser.add_argument("--src", default="/Users/kaikailiu/Documents/JWL/2025.12.25/38", help="Source folder of original photos (one product).")
    parser.add_argument("--slug", default="minimalist-sling-waist-bag", help='Output folder name, e.g. "minimalist-sling-waist-bag".')
    parser.add_argument("--dst", default="./public/images/products", help='Destination root, e.g. "./public/images/products".')

    parser.add_argument("--sizes", default="600,1600", help='Comma-separated max-edge sizes, e.g. "600,1600".')
    parser.add_argument("--thumb", type=int, default=300, help="Thumb max-edge size, e.g. 300.")
    parser.add_argument("--webp_quality", type=int, default=95, help="WebP quality (0-100).")
    parser.add_argument("--jpg_quality", type=int, default=95, help="JPG quality (0-100).")

    parser.add_argument(
        "--no_jpg",
        action="store_true",
        help="Disable JPG fallback output (only webp).",
    )

    args = parser.parse_args()

    src_dir = Path(args.src).expanduser().resolve()
    dst_root = Path(args.dst).expanduser().resolve()
    slug = args.slug.strip()

    if not src_dir.exists():
        raise SystemExit(f"Source folder not found: {src_dir}")

    sizes = tuple(int(x.strip()) for x in args.sizes.split(",") if x.strip())

    export_webp_and_jpg_variants(
        src_dir=src_dir,
        dst_root=dst_root,
        slug=slug,
        sizes=sizes,
        thumb_size=args.thumb,
        webp_quality=args.webp_quality,
        jpg_quality=args.jpg_quality,
        export_jpg_fallback=(not args.no_jpg),
    )

if __name__ == "__main__":
    main()