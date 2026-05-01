import os
import uuid
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from .models import EvidenceChunk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "media", "chroma_data")
COLLECTION_NAME = "evidence_chunks"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def get_chroma_client():
    os.makedirs(CHROMA_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_PATH)


@lru_cache(maxsize=1)
def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


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
    collection = get_collection()
    model = get_embedding_model()

    old_chunks = EvidenceChunk.objects.filter(evidence_file=evidence)
    old_ids = list(old_chunks.values_list("qdrant_point_id", flat=True))

    if old_ids:
        try:
            collection.delete(ids=old_ids)
        except Exception:
            pass

    old_chunks.delete()

    chunks = chunk_text(evidence.extracted_text)

    if not chunks:
        return 0

    embeddings = model.encode(chunks).tolist()

    ids = []
    documents = []
    metadatas = []

    for idx, chunk in enumerate(chunks):
        point_id = str(uuid.uuid4())

        EvidenceChunk.objects.create(
            evidence_file=evidence,
            chunk_index=idx,
            content=chunk,
            qdrant_point_id=point_id,
        )

        ids.append(point_id)
        documents.append(chunk)
        metadatas.append({
            "evidence_id": evidence.id,
            "case_id": evidence.case.id,
            "title": evidence.title,
            "chunk_index": idx,
            "file_type": evidence.file_type,
        })

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(chunks)


def search_similar_chunks(query, case_id=None, limit=5):
    collection = get_collection()
    model = get_embedding_model()

    query_embedding = model.encode([query]).tolist()

    where = None
    if case_id is not None:
        where = {"case_id": {"$eq": int(case_id)}}

    response = collection.query(
        query_embeddings=query_embedding,
        n_results=limit,
        where=where,
    )

    results = []

    ids = response.get("ids", [[]])[0]
    documents = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]
    distances = response.get("distances", [[]])[0]

    for i in range(len(ids)):
        meta = metadatas[i] or {}
        results.append({
            "score": 1 - distances[i] if i < len(distances) else None,
            "title": meta.get("title"),
            "content": documents[i],
            "chunk_index": meta.get("chunk_index"),
            "evidence_id": meta.get("evidence_id"),
            "file_type": meta.get("file_type"),
        })

    return results