import os
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


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
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
    collection = get_collection()
    model = get_embedding_model()

    # Delete old chunks for this evidence from ChromaDB
    old_chunks = EvidenceChunk.objects.filter(evidence_file=evidence)
    old_ids = list(old_chunks.values_list("qdrant_point_id", flat=True))

    if old_ids:
        try:
            collection.delete(ids=old_ids)
        except Exception:
            pass

    old_chunks.delete()

    # Chunk the extracted text
    chunks = chunk_text(evidence.extracted_text)

    if not chunks:
        return 0

    # Generate embeddings
    embeddings = model.encode(chunks).tolist()

    ids = []
    documents = []
    metadatas = []
    embed_list = []

    for idx, chunk in enumerate(chunks):
        import uuid
        point_id = str(uuid.uuid4())

        EvidenceChunk.objects.create(
            evidence_file=evidence,
            chunk_index=idx,
            content=chunk,
            qdrant_point_id=point_id,  # reusing the same field for chroma id
        )

        ids.append(point_id)
        documents.append(chunk)
        embed_list.append(embeddings[idx])
        metadatas.append({
            "evidence_id": evidence.id,
            "case_id": evidence.case.id,
            "title": evidence.title,
            "chunk_index": idx,
            "file_type": evidence.file_type,
        })

    collection.add(
        ids=ids,
        embeddings=embed_list,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


def search_similar_chunks(query, case_id=None, limit=5):
    collection = get_collection()
    model = get_embedding_model()

    # Return early if nothing is indexed yet
    total = collection.count()
    if total == 0:
        return []

    query_vector = model.encode(query).tolist()

    # If filtering by case_id, use ChromaDB's where filter
    # case_id stored as int in metadata, so ensure type matches
    where = {"case_id": int(case_id)} if case_id is not None else None

    # n_results cannot exceed collection size
    n = min(limit, total)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    filtered_results = []

    docs_list = results.get("documents", [[]])[0]
    metas_list = results.get("metadatas", [[]])[0]
    distances_list = results.get("distances", [[]])[0]

    for i, doc in enumerate(docs_list):
        meta = metas_list[i] if i < len(metas_list) else {}
        distance = distances_list[i] if i < len(distances_list) else 1.0
        score = round(1 - distance, 4)  # cosine similarity from distance

        filtered_results.append({
            "score": score,
            "title": meta.get("title"),
            "content": doc,
            "chunk_index": meta.get("chunk_index"),
            "evidence_id": meta.get("evidence_id"),
            "file_type": meta.get("file_type"),
        })

    return filtered_results