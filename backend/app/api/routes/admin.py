import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel

from app.core.config import settings, BASE_DIR
from app.services.image_processing import process_and_save_image
from app.api import deps
from app.adapters import db

router = APIRouter(dependencies=[Depends(deps.get_current_active_superuser)])

# Paths
PROJECT_ROOT = Path(BASE_DIR).parent
WEBSITE_INFO_PATH = PROJECT_ROOT / "src" / "data" / "websiteinfo.json"
PUBLIC_DIR = PROJECT_ROOT / "public"

def load_website_info() -> Dict[str, Any]:
    if not WEBSITE_INFO_PATH.exists():
        raise HTTPException(status_code=404, detail=f"websiteinfo.json not found at {WEBSITE_INFO_PATH}")
    with open(WEBSITE_INFO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_website_info(data: Dict[str, Any]):
    with open(WEBSITE_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_value_by_path(data: Dict[str, Any], path: str):
    keys = path.split(".")
    curr = data
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        elif isinstance(curr, list) and k.isdigit():
             curr = curr[int(k)]
        else:
            return None
    return curr

def set_value_by_path(data: Dict[str, Any], path: str, value: Any):
    keys = path.split(".")
    curr = data
    for i, k in enumerate(keys[:-1]):
        if isinstance(curr, dict):
            if k not in curr:
                curr[k] = {}
            curr = curr[k]
        elif isinstance(curr, list) and k.isdigit():
            idx = int(k)
            if idx < len(curr):
                curr = curr[idx]
            else:
                # This is tricky for lists, we assume the structure exists
                raise HTTPException(status_code=400, detail=f"Invalid path in list: {k}")
        else:
             raise HTTPException(status_code=400, detail=f"Cannot traverse path: {k}")
    
    last_key = keys[-1]
    if isinstance(curr, dict):
        curr[last_key] = value
    elif isinstance(curr, list) and last_key.isdigit():
        idx = int(last_key)
        if 0 <= idx < len(curr):
            curr[idx] = value
        else:
             raise HTTPException(status_code=400, detail="List index out of range")
    else:
        raise HTTPException(status_code=400, detail="Cannot set value")

@router.get("/website-info")
async def get_website_info():
    try:
        print(f"Loading website info from: {WEBSITE_INFO_PATH}")
        return load_website_info()
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error loading website info: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/health")
async def admin_health():
    return {
        "status": "ok", 
        "project_root": str(PROJECT_ROOT),
        "website_info_path": str(WEBSITE_INFO_PATH),
        "exists": WEBSITE_INFO_PATH.exists()
    }

@router.post("/update-image")
async def update_image(
    file: UploadFile = File(...),
    json_path: str = Form(...),
    current_image_path: str = Form(...) # The current value in json, e.g. "/images/hero/slide1.jpg"
):
    """
    1. Save new image to public folder (processed).
    2. Update websiteinfo.json with new path.
    """
    
    # Determine output directory
    # If current_image_path exists, use its directory.
    # If not (or it's empty), default to /images/uploads
    
    rel_path = current_image_path.strip()
    if rel_path.startswith("/"):
        rel_path = rel_path[1:]
    
    if rel_path:
        target_dir = (PUBLIC_DIR / rel_path).parent
    else:
        target_dir = PUBLIC_DIR / "images" / "uploads"
    
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate new filename (sanitize)
    filename = file.filename
    # Simple sanitization
    filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    filename = filename.replace(" ", "_")
    
    target_path = target_dir / filename
    
    # Process image
    try:
        # process_and_save_image returns the path to the saved webp file
        saved_path = process_and_save_image(file.file, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
    
    # Construct new relative path for JSON
    # saved_path is absolute, we need relative to PUBLIC_DIR
    new_rel_path = "/" + str(saved_path.relative_to(PUBLIC_DIR))
    
    # Update JSON
    data = load_website_info()
    
    # Check if json_path refers to a list or a single string
    # The frontend should pass the exact path to the string value
    try:
        set_value_by_path(data, json_path, new_rel_path)
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Failed to update JSON: {str(e)}")
    
    save_website_info(data)
    
    return {"status": "success", "new_path": new_rel_path}

@router.get("/inquiries")
async def get_inquiries(limit: int = 100, offset: int = 0):
    """
    Fetch all user inquiries from the database.
    """
    try:
        inquiries = db.get_all_inquiries(limit=limit, offset=offset)
        return inquiries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch inquiries: {str(e)}")

@router.post("/process-product-image")
async def process_product_image(
    file: UploadFile = File(...),
    product_slug: str = Form(...),
    image_type: str = Form(...) # 'main' or 'variant'
):
    # This is a placeholder if we want to expose product image processing too
    pass
