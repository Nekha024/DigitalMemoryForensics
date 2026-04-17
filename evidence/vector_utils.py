import os
import uuid
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from .models import EvidenceChunk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDRANT_PATH = os.path.join(BASE_DIR, "media", "qdrant_data")
COLLECTION_NAME = "evidence_chunks"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def get_qdrant_client():
    os.makedirs(QDRANT_PATH, exist_ok=True)
    return QdrantClient(path=QDRANT_PATH)


def ensure_collection():
    client = get_qdrant_client()
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME not in names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def chunk_text(text, chunk_size=500, overlap=100):
    chunks = []
    text = (text or "").strip()

    if not text:
        return chunks

    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def index_evidence_file(evidence):
    ensure_collection()
    client = get_qdrant_client()
    model = get_embedding_model()

    old_chunks = EvidenceChunk.objects.filter(evidence_file=evidence)
    old_ids = list(old_chunks.values_list("qdrant_point_id", flat=True))

    if old_ids:
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=old_ids,
            )
        except Exception:
            pass

    old_chunks.delete()

    chunks = chunk_text(evidence.extracted_text)

    if not chunks:
        return 0

    embeddings = model.encode(chunks)

    points = []

    for idx, chunk in enumerate(chunks):
        point_id = str(uuid.uuid4())

        EvidenceChunk.objects.create(
            evidence_file=evidence,
            chunk_index=idx,
            content=chunk,
            qdrant_point_id=point_id,
        )

        points.append(
            PointStruct(
                id=point_id,
                vector=embeddings[idx].tolist(),
                payload={
                    "evidence_id": evidence.id,
                    "case_id": evidence.case.id,
                    "title": evidence.title,
                    "chunk_index": idx,
                    "content": chunk,
                    "file_type": evidence.file_type,
                },
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    return len(chunks)


def search_similar_chunks(query, case_id=None, limit=5):
    ensure_collection()
    client = get_qdrant_client()
    model = get_embedding_model()

    query_vector = model.encode(query).tolist()

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit,
    )

    filtered_results = []

    for item in results:
        payload = item.payload or {}

        if case_id is None or payload.get("case_id") == case_id:
            filtered_results.append({
                "score": item.score,
                "title": payload.get("title"),
                "content": payload.get("content"),
                "chunk_index": payload.get("chunk_index"),
                "evidence_id": payload.get("evidence_id"),
                "file_type": payload.get("file_type"),
            })

    return filtered_results