import abc
import numpy as np
import logging
import time
from typing import Tuple, Optional

logger = logging.getLogger("jwl.vector_index")

class VectorIndex(abc.ABC):
    @abc.abstractmethod
    def build(self, vectors: np.ndarray) -> None:
        """
        Build the index with the given vectors.
        vectors: shape (N, D)
        """
        pass

    @abc.abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for the nearest neighbors.
        query_vector: shape (D,)
        Returns: (scores, indices)
        """
        pass

class NumpyIndex(VectorIndex):
    def __init__(self):
        self._vectors: Optional[np.ndarray] = None
        self._norms: Optional[np.ndarray] = None

    def build(self, vectors: np.ndarray) -> None:
        self._vectors = vectors.astype(np.float32)
        # Precompute norms for cosine similarity
        self._norms = np.linalg.norm(self._vectors, axis=1)
        # Avoid division by zero
        self._norms[self._norms == 0] = 1e-12

    def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        t0 = time.time()
        if self._vectors is None or len(self._vectors) == 0:
            return np.array([]), np.array([])
        
        q = query_vector.astype(np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            q_norm = 1e-12
            
        # Cosine similarity: (A . B) / (|A| * |B|)
        dot_products = self._vectors @ q
        scores = dot_products / (self._norms * q_norm)
        
        # Top K
        k = min(top_k, len(scores))
        if k == 0:
            return np.array([]), np.array([])

        # np.argsort returns indices that sort the array (ascending). 
        # We want descending order of scores.
        # Use argpartition for efficiency if N is large, but argsort is fine for <10k items
        sorted_indices = np.argsort(-scores)
        top_k_indices = sorted_indices[:k]
        top_k_scores = scores[top_k_indices]
        
        logger.debug("NumpyIndex search: k=%d pool=%d took=%.4fs", k, len(scores), time.time() - t0)
        return top_k_scores, top_k_indices

class FaissIndex(VectorIndex):
    def __init__(self):
        self.index = None
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            logger.error("Faiss not installed. Please install faiss-cpu or faiss-gpu.")
            raise ImportError("Faiss not installed")

    def build(self, vectors: np.ndarray) -> None:
        # Faiss expects float32
        # Copy to avoid modifying original if normalize_L2 is in-place
        vectors_cp = vectors.astype(np.float32).copy()
        d = vectors_cp.shape[1]
        
        # We use IndexFlatIP (Inner Product) for cosine similarity
        # But we must normalize vectors first
        self.index = self.faiss.IndexFlatIP(d)
        
        # Normalize vectors for cosine similarity
        # pylint: disable=no-value-for-parameter
        self.faiss.normalize_L2(vectors_cp)
        self.index.add(vectors_cp)

    def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        t0 = time.time()
        if self.index is None:
            return np.array([]), np.array([])
            
        q = query_vector.astype(np.float32).reshape(1, -1)
        # Normalize query
        # pylint: disable=no-value-for-parameter
        self.faiss.normalize_L2(q)
        
        # pylint: disable=no-value-for-parameter
        scores, indices = self.index.search(q, top_k)
        
        # Faiss returns (1, k) arrays
        # Filter out -1 indices if any (though IndexFlatIP shouldn't return -1 unless k > N)
        valid_mask = indices[0] != -1
        
        logger.debug("FaissIndex search: k=%d pool=%d took=%.4fs", top_k, self.index.ntotal, time.time() - t0)
        return scores[0][valid_mask], indices[0][valid_mask]

def get_vector_index(index_type: str) -> VectorIndex:
    if index_type == "faiss":
        return FaissIndex()
    return NumpyIndex()
