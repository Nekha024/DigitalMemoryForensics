import os
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

GLM_BASE_URL = os.getenv("GLM_BASE_URL", "").rstrip("/")
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-5.1")

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "glm").lower()


def build_rag_prompt(question, chunks):
    context_parts = []

    for i, chunk in enumerate(chunks, start=1):
        content = chunk.get("content", "")
        title = chunk.get("title", "Unknown File")
        chunk_index = chunk.get("chunk_index", "N/A")

        context_parts.append(
            f"[Source {i}] File: {title} | Chunk: {chunk_index}\n{content}"
        )

    context_text = "\n\n".join(context_parts)

    prompt = f"""
You are a digital forensics assistant.

Answer the user's question using ONLY the evidence context below.
Do not make up facts.
If the answer is not in the evidence, say: "The answer is not available in the uploaded evidence."

Evidence Context:
{context_text}

User Question:
{question}

Instructions:
- Give a clear answer based only on the evidence.
- Mention important facts only if present in the evidence.
- Keep the answer concise but useful.
- At the end, add a short "Sources Used" section listing the source numbers you relied on.
""".strip()

    return prompt


def generate_with_ollama(prompt, model=None):
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()

    data = response.json()
    return data.get("response", "").strip()


def generate_with_glm(prompt, model=None):
    if not GLM_BASE_URL or not GLM_API_KEY:
        raise ValueError("GLM_BASE_URL or GLM_API_KEY is not set in environment variables.")

    model = model or GLM_MODEL

    url = f"{GLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a digital forensics assistant. Answer only from the provided evidence context."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()

    choices = data.get("choices", [])
    if not choices:
        return "No response generated from GLM."

    return choices[0].get("message", {}).get("content", "").strip()


def generate_rag_answer(question, retrieved_chunks, provider=None):
    provider = (provider or DEFAULT_LLM_PROVIDER).lower()

    if not retrieved_chunks:
        return {
            "answer": "No relevant evidence chunks were found for this question.",
            "sources": []
        }

    prompt = build_rag_prompt(question, retrieved_chunks)

    if provider == "ollama":
        answer = generate_with_ollama(prompt)
    elif provider == "glm":
        answer = generate_with_glm(prompt)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    sources = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        sources.append({
            "source_no": i,
            "title": chunk.get("title"),
            "chunk_index": chunk.get("chunk_index"),
            "content": chunk.get("content"),
            "score": chunk.get("score"),
            "evidence_id": chunk.get("evidence_id"),
        })

    return {
        "answer": answer,
        "sources": sources
    }