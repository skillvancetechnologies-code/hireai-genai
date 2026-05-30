import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.schemas import Candidate
from app.services.candidate_service import candidates_from_dataframe
from app.services.dataset_loader import get_candidate_search_data, get_candidates_data


FAISS_DIR = Path(__file__).resolve().parents[3] / "data" / "faiss"
INDEX_PATH = FAISS_DIR / "candidates.index"
IDS_PATH = FAISS_DIR / "ids.pkl"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ENCODE_CHUNK_SIZE = 1000


class SemanticSearchError(RuntimeError):
    """Raised when semantic retrieval cannot be completed safely."""


def build_faiss_index(limit: int | None = None) -> dict[str, int | str]:
    """Build and save a FAISS index over candidate skills, projects, education."""
    faiss = _import_faiss()
    model = _get_embedding_model()
    candidates = get_candidates_data().copy()
    total_candidates = len(candidates)

    if limit is not None:
        candidates = candidates.head(limit)

    if candidates.empty:
        raise SemanticSearchError("No candidate data is available for indexing.")

    texts = candidates.apply(_candidate_embedding_text, axis=1).tolist()
    vectors = _encode_texts(model, texts)
    if vectors.ndim != 2 or vectors.shape[0] != len(candidates):
        raise SemanticSearchError("Generated malformed candidate embeddings.")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    with IDS_PATH.open("wb") as file:
        pickle.dump(candidates["candidate_id"].astype(int).tolist(), file)

    _load_faiss_assets.cache_clear()
    return {
        "indexed_candidates": len(candidates),
        "total_available_candidates": total_candidates,
        "embedding_dimension": vectors.shape[1],
        "index_path": str(INDEX_PATH),
        "ids_path": str(IDS_PATH),
    }


def semantic_search(query: str, top_k: int) -> list[Candidate]:
    """Search candidates by semantic similarity and return full candidate rows."""
    if not query or not query.strip():
        raise SemanticSearchError("Semantic query cannot be empty.")

    index, candidate_ids = _load_faiss_assets()
    if index.ntotal == 0 or not candidate_ids:
        raise SemanticSearchError("Semantic index is empty. Please rebuild it.")

    model = _get_embedding_model()
    query_embedding = model.encode([query], normalize_embeddings=True)
    query_vector = np.asarray(query_embedding, dtype="float32")
    if query_vector.ndim != 2:
        raise SemanticSearchError("Generated malformed query embedding.")

    search_k = min(max(top_k, 1), len(candidate_ids))
    _, positions = index.search(query_vector, search_k)
    ranked_ids = [
        candidate_ids[position]
        for position in positions[0].tolist()
        if position >= 0 and position < len(candidate_ids)
    ]

    if not ranked_ids:
        raise SemanticSearchError("No semantic matches were found.")

    rows = _best_rows_for_candidate_ids(ranked_ids)
    return candidates_from_dataframe(rows)


@lru_cache(maxsize=1)
def _load_faiss_assets():
    """Load FAISS index and ID mapping from disk, rebuilding if missing."""
    faiss = _import_faiss()

    if not INDEX_PATH.exists() or not IDS_PATH.exists():
        build_faiss_index()

    try:
        index = faiss.read_index(str(INDEX_PATH))
        with IDS_PATH.open("rb") as file:
            candidate_ids = pickle.load(file)
    except Exception as exc:
        raise SemanticSearchError(
            "Could not load semantic index. Please rebuild it."
        ) from exc

    return index, candidate_ids


@lru_cache(maxsize=1)
def _get_embedding_model():
    """Load the sentence-transformers model once per process."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SemanticSearchError(
            "sentence-transformers is not installed. Install requirements first."
        ) from exc

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def _import_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise SemanticSearchError(
            "faiss-cpu is not installed. Install requirements first."
        ) from exc

    return faiss


def _candidate_embedding_text(row: pd.Series) -> str:
    """Format candidate fields in the text shape required by documentation."""
    return (
        f"{row['name']}. "
        f"Skills: {_format_pipe_values(row['skills'])}. "
        f"Education: {row['education']}. "
        f"Projects: {_format_pipe_values(row['projects'])}."
    )


def _format_pipe_values(value: object) -> str:
    return ", ".join(part.strip() for part in str(value).split("|") if part.strip())


def _encode_texts(model, texts: list[str]) -> np.ndarray:
    """Encode in chunks so local machines do not stall on the full dataset."""
    chunks: list[np.ndarray] = []
    total = len(texts)
    for start in range(0, total, ENCODE_CHUNK_SIZE):
        end = min(start + ENCODE_CHUNK_SIZE, total)
        print(f"Embedding candidates {start + 1}-{end} of {total}", flush=True)
        embeddings = model.encode(
            texts[start:end],
            batch_size=64,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        chunks.append(np.asarray(embeddings, dtype="float32"))

    return np.vstack(chunks)


def _best_rows_for_candidate_ids(candidate_ids: list[int]) -> pd.DataFrame:
    """Fetch one full, highest-score joined row per semantic candidate ID."""
    order = pd.DataFrame(
        {"candidate_id": candidate_ids, "semantic_rank": range(len(candidate_ids))}
    )
    best_rows = (
        get_candidate_search_data()
        .sort_values("score", ascending=False)
        .drop_duplicates(subset=["candidate_id"])
    )
    return (
        order.merge(best_rows, on="candidate_id", how="inner")
        .sort_values("semantic_rank")
        .drop(columns=["semantic_rank"])
    )
