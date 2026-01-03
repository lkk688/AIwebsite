import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, ImageOps

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

def is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in ALLOWED_EXT and not p.name.startswith(".")

def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "variant"

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

def save_jpg(img: Image.Image, path: Path, quality: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)

def normalize_image(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")
    else:
        im = im.convert("RGB")
    return im

def load_variant_map_from_json_file(json_path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not json_path:
        return {}
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return normalize_variant_map(data)

def normalize_variant_map(data: Any) -> Dict[str, Dict[str, Any]]:
    """
    支持：
    A) { "IMG_3995.jpg": {...}, ... }
    B) { "variants": [ { "file": "...", ...}, ... ] }
    """
    mapping: Dict[str, Dict[str, Any]] = {}
    if isinstance(data, dict) and "variants" in data and isinstance(data["variants"], list):
        for item in data["variants"]:
            if not isinstance(item, dict):
                continue
            fn = str(item.get("file", "")).strip()
            if fn:
                mapping[fn.lower()] = item
        return mapping

    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                mapping[str(k).lower()] = v
        return mapping

    return {}

def export_variants(
    im: Image.Image,
    out_dir: Path,
    base_name: str,
    sizes: tuple[int, ...],
    thumb_size: int,
    webp_quality: int,
    jpg_quality: int,
    export_jpg_fallback: bool,
):
    # thumb
    thumb = resize_to_max_edge(im, thumb_size)
    save_webp(thumb, out_dir / f"{base_name}_thumb.webp", webp_quality)
    if export_jpg_fallback:
        save_jpg(thumb, out_dir / f"{base_name}_thumb.jpg", jpg_quality)

    # sizes
    for max_edge in sizes:
        out = resize_to_max_edge(im, max_edge)
        save_webp(out, out_dir / f"{base_name}_{max_edge}.webp", webp_quality)
        if export_jpg_fallback:
            save_jpg(out, out_dir / f"{base_name}_{max_edge}.jpg", jpg_quality)

def process_main_images(
    src_dir: Path,
    dst_dir: Path,
    sizes: tuple[int, ...],
    thumb_size: int,
    webp_quality: int,
    jpg_quality: int,
    export_jpg_fallback: bool,
    sku_dirnames=("sku", "SKU"),
):
    images = []
    for p in src_dir.iterdir():
        if p.is_dir() and p.name.lower() in [d.lower() for d in sku_dirnames]:
            continue
        if is_image(p):
            images.append(p)

    images = sorted(images, key=lambda p: natural_key(p.name))
    if not images:
        print(f"[WARN] No main images found in {src_dir} (excluding SKU).")
        return 0

    for idx, img_path in enumerate(images, start=1):
        try:
            with Image.open(img_path) as im:
                im = normalize_image(im)
                export_variants(
                    im=im,
                    out_dir=dst_dir,
                    base_name=str(idx),
                    sizes=sizes,
                    thumb_size=thumb_size,
                    webp_quality=webp_quality,
                    jpg_quality=jpg_quality,
                    export_jpg_fallback=export_jpg_fallback,
                )
            print(f"[OK] main: {img_path.name} -> {idx}_*.webp/jpg")
        except Exception as e:
            print(f"[WARN] main failed: {img_path} -> {e}")

    return len(images)

def process_sku_variants(
    src_dir: Path,
    dst_dir: Path,
    sizes: tuple[int, ...],
    thumb_size: int,
    webp_quality: int,
    jpg_quality: int,
    export_jpg_fallback: bool,
    variant_map: Dict[str, Dict[str, Any]],
    sku_dirname="SKU",
):
    sku_dir = None
    for p in src_dir.iterdir():
        if p.is_dir() and p.name.lower() == sku_dirname.lower():
            sku_dir = p
            break

    if not sku_dir:
        print("[INFO] No SKU directory found. Skip variants.")
        return 0

    out_variants_dir = dst_dir / "variants"
    out_variants_dir.mkdir(parents=True, exist_ok=True)

    total = 0

    def get_color_key_from_file(img_path: Path) -> str:
        rec = variant_map.get(img_path.name.lower())
        if rec and rec.get("key"):
            return slugify(str(rec["key"]))
        return slugify(img_path.stem)

    sku_images = [p for p in sku_dir.iterdir() if is_image(p)]
    sku_subdirs = [p for p in sku_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    if sku_images:
        sku_images = sorted(sku_images, key=lambda p: natural_key(p.name))
        for img_path in sku_images:
            color_key = get_color_key_from_file(img_path)
            try:
                with Image.open(img_path) as im:
                    im = normalize_image(im)
                    export_variants(
                        im=im,
                        out_dir=out_variants_dir,
                        base_name=color_key,
                        sizes=sizes,
                        thumb_size=thumb_size,
                        webp_quality=webp_quality,
                        jpg_quality=jpg_quality,
                        export_jpg_fallback=export_jpg_fallback,
                    )
                total += 1
                print(f"[OK] variant: {img_path.name} -> variants/{color_key}_*.webp/jpg")
            except Exception as e:
                print(f"[WARN] variant failed: {img_path} -> {e}")
        return total

    if sku_subdirs:
        for d in sorted(sku_subdirs, key=lambda p: natural_key(p.name)):
            default_key = slugify(d.name)
            imgs = sorted([p for p in d.iterdir() if is_image(p)], key=lambda p: natural_key(p.name))
            if not imgs:
                continue

            for i, img_path in enumerate(imgs, start=1):
                rec = variant_map.get(img_path.name.lower())
                color_key = slugify(str(rec.get("key"))) if rec and rec.get("key") else default_key
                base_name = color_key if len(imgs) == 1 else f"{color_key}-{i}"

                try:
                    with Image.open(img_path) as im:
                        im = normalize_image(im)
                        export_variants(
                            im=im,
                            out_dir=out_variants_dir,
                            base_name=base_name,
                            sizes=sizes,
                            thumb_size=thumb_size,
                            webp_quality=webp_quality,
                            jpg_quality=jpg_quality,
                            export_jpg_fallback=export_jpg_fallback,
                        )
                    total += 1
                    print(f"[OK] variant: {img_path.name} -> variants/{base_name}_*.webp/jpg")
                except Exception as e:
                    print(f"[WARN] variant failed: {img_path} -> {e}")

    print("[INFO] SKU directory exists but no images found.")
    return total

def run_job(job: Dict[str, Any]):
    # Required
    src = Path(job["src"]).expanduser().resolve()
    #slug = str(job["slug"]).strip()
    slug = job["slug"]
    
    dst = Path(job["dst"]).expanduser().resolve()
    out_name = job.get("assetDir") or job.get("outDirName") or job.get("id") or slug
    out_dir = dst / out_name

    if not src.exists():
        raise SystemExit(f"Source folder not found: {src}")

    #out_dir = dst / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Optional with defaults
    sizes = tuple(int(x) for x in job.get("sizes", [600, 1600]))
    thumb = int(job.get("thumb", 300))
    webp_quality = int(job.get("webp_quality", 82))
    jpg_quality = int(job.get("jpg_quality", 85))
    export_jpg_fallback = bool(job.get("export_jpg_fallback", True))
    sku_dirname = str(job.get("sku_dirname", "SKU"))

    # Variants mapping: inline > file
    variant_map: Dict[str, Dict[str, Any]] = {}
    if "variants" in job and job["variants"]:
        variant_map = normalize_variant_map(job["variants"])
    elif "variant_json_path" in job and job["variant_json_path"]:
        variant_map = load_variant_map_from_json_file(Path(job["variant_json_path"]).expanduser().resolve())

    main_count = process_main_images(
        src_dir=src,
        dst_dir=out_dir,
        sizes=sizes,
        thumb_size=thumb,
        webp_quality=webp_quality,
        jpg_quality=jpg_quality,
        export_jpg_fallback=export_jpg_fallback,
        sku_dirnames=(sku_dirname,),
    )

    variant_count = process_sku_variants(
        src_dir=src,
        dst_dir=out_dir,
        sizes=sizes,
        thumb_size=thumb,
        webp_quality=webp_quality,
        jpg_quality=jpg_quality,
        export_jpg_fallback=export_jpg_fallback,
        variant_map=variant_map,
        sku_dirname=sku_dirname,
    )

    print("\n====================")
    print(f"Done: {slug}")
    print(f"Main images processed: {main_count}")
    print(f"Variant images processed: {variant_count}")
    print(f"Output: {out_dir}")
    print("====================\n")

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Process one product folder into main images + SKU variants (webp + jpg fallback + thumb)."
    )

    # New: config mode (whole product json; we will read imageJob if present)
    parser.add_argument(
        "--config",
        default="",
        help="JSON config file. Can be either a pure image job JSON, or a product JSON containing an 'imageJob' field."
    )

    # Old CLI mode (still supported)
    parser.add_argument("--src", default="", help="Source product folder (contains photos and optional SKU folder).")
    parser.add_argument("--slug", default="", help='Output product slug folder, e.g. "kids-school-backpack".')
    parser.add_argument("--dst", default="", help='Destination root, e.g. "./public/images/products".')

    parser.add_argument("--sizes", default="600,1600", help='Comma-separated max-edge sizes, e.g. "600,1600".')
    parser.add_argument("--thumb", type=int, default=300, help="Thumb max-edge size, e.g. 300.")
    parser.add_argument("--webp_quality", type=int, default=82, help="WebP quality (0-100).")
    parser.add_argument("--jpg_quality", type=int, default=85, help="JPG quality (0-100).")
    parser.add_argument("--no_jpg", action="store_true", help="Disable JPG fallback output (only webp).")

    parser.add_argument("--sku_dirname", default="SKU", help='SKU directory name (default: "SKU").')
    parser.add_argument("--variant_json", default="", help="Optional JSON file mapping image filename -> color key/name.")

    args = parser.parse_args()

    # --- Config mode ---
    if args.config:
        cfg_path = Path(args.config).expanduser().resolve()
        if not cfg_path.exists():
            raise SystemExit(f"Config file not found: {cfg_path}")

        data = json.loads(cfg_path.read_text(encoding="utf-8"))

        # ✅ If it's a product JSON, extract the image job from data["imageJob"]
        # Otherwise treat it as a pure image job json.
        job = data.get("imageJob") if isinstance(data, dict) and "imageJob" in data else data

        if not isinstance(job, dict):
            raise SystemExit(f"Invalid config format in {cfg_path}: expected object or object.imageJob")

        run_job(job)
        return

    # --- Fallback: CLI mode ---
    if not (args.src and args.slug and args.dst):
        raise SystemExit("Either provide --config <product.json|job.json> OR provide --src --slug --dst")

    job = {
        "src": args.src,
        "slug": args.slug,
        "dst": args.dst,
        "sizes": [int(x.strip()) for x in args.sizes.split(",") if x.strip()],
        "thumb": args.thumb,
        "webp_quality": args.webp_quality,
        "jpg_quality": args.jpg_quality,
        "export_jpg_fallback": (not args.no_jpg),
        "sku_dirname": args.sku_dirname,
    }

    if args.variant_json:
        job["variant_json_path"] = args.variant_json

    run_job(job)

if __name__ == "__main__":
    main()

#python tools/process_one_productv2.py --config src/data/products/jwl-mini-crossbody-006.json
#% python tools/process_one_productv2.py --src "/Users/kaikailiu/Documents/JWL/2022pics/PIC" --slug "sample_bags"  --dst "./public/images/products"