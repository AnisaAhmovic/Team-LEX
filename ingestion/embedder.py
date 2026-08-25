"""
Loads BGE-M3 and provides a small helper for embedding chunk text.

Kept separate from qdrant_indexer.py so the embedding step can be reused
later (e.g. embedding a user's question at query time) without needing
Qdrant-specific code.
"""

from sentence_transformers import SentenceTransformer

from ingestion.embedding_config import (
    EMBEDDING_MODEL_NAME,
    NORMALIZE_EMBEDDINGS,
)

_model = None


def load_model():
    """
    Load BGE-M3 once and cache it in-process.

    The first call downloads the model from Hugging Face Hub to the local
    cache (~/.cache/huggingface). Subsequent calls in the same run reuse
    the cached in-memory model; subsequent runs reuse the local cache on
    disk, so no re-download is needed.
    """
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL_NAME} ...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("Model loaded.")
    return _model


def embed_texts(texts, batch_size=16):
    """
    Embed a list of strings and return a list of dense vectors (lists of
    floats), ready to hand to Qdrant.
    """
    model = load_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=NORMALIZE_EMBEDDINGS,
        show_progress_bar=len(texts) > 1,
    )
    return embeddings.tolist()


def embed_text(text):
    """Embed a single string and return one dense vector."""
    return embed_texts([text])[0]
