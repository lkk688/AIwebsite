from typing import Optional, Dict, Any, List

class ProductResolver:
    def __init__(self, products: List[Dict[str, Any]]):
        self.products = products
        self._id_map = {str(p.get("id")): p for p in products if p.get("id")}
        self._slug_map = {str(p.get("slug")): p for p in products if p.get("slug")}

    def resolve(self, product_id: Optional[str] = None, product_slug: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Resolves product_id and product_slug to a consistent pair.
        Returns {'id': ..., 'slug': ...} or None if not found/invalid.
        
        Rules:
        - If both None -> None
        - If only product_id provided -> look up slug
        - If only product_slug provided -> look up id
        - If both provided -> verify consistency. If mismatch, prefer product_id.
        """
        if not product_id and not product_slug:
            return None

        p_by_id = None
        p_by_slug = None

        if product_id:
            p_by_id = self._id_map.get(str(product_id))
        
        if product_slug:
            p_by_slug = self._slug_map.get(str(product_slug))

        # Case 1: Both provided
        if product_id and product_slug:
            if p_by_id and p_by_slug:
                if str(p_by_id.get('id')) == str(p_by_slug.get('id')):
                    # Consistent
                    return {'id': str(p_by_id['id']), 'slug': str(p_by_id['slug'])}
                else:
                    # Mismatch: prefer product_id
                    return {'id': str(p_by_id['id']), 'slug': str(p_by_id['slug'])}
            elif p_by_id:
                # Slug invalid, but ID valid -> use ID's data
                return {'id': str(p_by_id['id']), 'slug': str(p_by_id['slug'])}
            elif p_by_slug:
                 # ID invalid, but Slug valid -> mismatch logic says "prefer product_id".
                 # If ID is provided but not found, we treat it as invalid product reference.
                 return None
            else:
                # Both invalid
                return None

        # Case 2: Only ID provided
        if product_id:
            if p_by_id:
                return {'id': str(p_by_id['id']), 'slug': str(p_by_id['slug'])}
            else:
                return None

        # Case 3: Only Slug provided
        if product_slug:
            if p_by_slug:
                return {'id': str(p_by_slug['id']), 'slug': str(p_by_slug['slug'])}
            else:
                return None
                
        return None

# Global helper to be initialized or lazy loaded
_resolver: Optional[ProductResolver] = None

def get_resolver(products: Optional[List[Dict[str, Any]]] = None) -> ProductResolver:
    global _resolver
    if products is not None:
        _resolver = ProductResolver(products)
    
    if _resolver is None:
        # Fallback: try to load from app.core.services (lazy import)
        try:
            from app.core.services import store
            _resolver = ProductResolver(store.products)
        except ImportError:
            # Should not happen in running app, but might in tests if not mocked
            _resolver = ProductResolver([])
            
    return _resolver
