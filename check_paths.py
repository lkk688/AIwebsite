import sys
import os
from pathlib import Path

# Mock config
BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), "backend")) # Assuming running from root
# But config.py uses __file__

# Let's verify exactly what config.py does
try:
    from backend.app.core.config import settings, BASE_DIR as CONFIG_BASE_DIR
    print(f"Config BASE_DIR: {CONFIG_BASE_DIR}")
    
    PROJECT_ROOT = Path(CONFIG_BASE_DIR).parent
    print(f"Project Root: {PROJECT_ROOT}")
    
    WEBSITE_INFO_PATH = PROJECT_ROOT / "src" / "data" / "websiteinfo.json"
    print(f"Website Info Path: {WEBSITE_INFO_PATH}")
    print(f"Exists: {WEBSITE_INFO_PATH.exists()}")
    
except ImportError:
    # Try adding to path
    sys.path.append(os.getcwd())
    try:
        from backend.app.core.config import settings, BASE_DIR as CONFIG_BASE_DIR
        print(f"Config BASE_DIR: {CONFIG_BASE_DIR}")
        
        PROJECT_ROOT = Path(CONFIG_BASE_DIR).parent
        print(f"Project Root: {PROJECT_ROOT}")
        
        WEBSITE_INFO_PATH = PROJECT_ROOT / "src" / "data" / "websiteinfo.json"
        print(f"Website Info Path: {WEBSITE_INFO_PATH}")
        print(f"Exists: {WEBSITE_INFO_PATH.exists()}")
    except ImportError as e:
        print(f"Import failed: {e}")
