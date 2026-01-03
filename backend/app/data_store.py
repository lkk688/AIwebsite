import os
import json
import glob
from typing import Any, Dict, List


def _load_json(filepath: str) -> Any:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class DataStore:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        self._cache: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        data: Dict[str, Any] = {}
        data["website_info"] = _load_json(os.path.join(self.data_dir, "websiteinfo.json"))
        data["product_info"] = _load_json(os.path.join(self.data_dir, "productinfo.json"))
        data["certifications"] = _load_json(os.path.join(self.data_dir, "certifications.json"))

        products: List[Dict[str, Any]] = []
        for pf in glob.glob(os.path.join(self.data_dir, "products", "*.json")):
            p = _load_json(pf)
            if isinstance(p, dict) and p.get("id"):
                products.append(p)
        data["products"] = products
        self._cache = data

    @property
    def website_info(self) -> Dict[str, Any]:
        return self._cache.get("website_info", {})

    @property
    def certifications(self) -> Dict[str, Any]:
        return self._cache.get("certifications", {})

    @property
    def products(self) -> List[Dict[str, Any]]:
        return self._cache.get("products", [])