import os
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

GLM_BASE_URL = os.getenv("GLM_BASE_URL", "").rstrip("/")
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_API_KEY_FALLBACK = os.getenv("GLM_API_KEY_FALLBACK", "")
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


def _ollama_list_models():
    """Return list of locally available Ollama model names, or [] on failure."""
    import json as _json
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.ok:
            return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def generate_with_ollama(prompt, model=None):
    import json as _json
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,          # streaming = tokens arrive fast, no read-timeout
        "options": {
            "num_predict": 512,
            "temperature": 0.2,
        }
    }

    # connect timeout 30s, read timeout 600s (stream keeps the socket alive)
    try:
        response = requests.post(url, json=payload, timeout=(30, 600), stream=True)
    except requests.exceptions.ConnectionError:
        raise Exception(
            "Cannot connect to Ollama at localhost:11434. "
            "Make sure Ollama is running: open a terminal and run  ollama serve"
        )

    # Ollama returns 500 when the model isn't pulled yet.
    # Read the error body and give a clear actionable message.
    if response.status_code == 500:
        try:
            err_body = response.json()
            ollama_msg = err_body.get("error", "")
        except Exception:
            ollama_msg = response.text[:300]

        available = _ollama_list_models()
        avail_str = ", ".join(available) if available else "none found"

        raise Exception(
            f"Ollama model '{model}' failed with: {ollama_msg or 'Internal Server Error'}. "
            f"Available models on this machine: [{avail_str}]. "
            f"To download the model run:  ollama pull {model}"
        )

    response.raise_for_status()

    full_text = []
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        try:
            chunk = _json.loads(raw_line)
        except ValueError:
            continue

        # Ollama also streams error objects mid-stream (e.g. context overflow)
        if chunk.get("error"):
            raise Exception(f"Ollama stream error: {chunk['error']}")

        token = chunk.get("response", "")
        full_text.append(token)
        if chunk.get("done", False):
            break

    result = "".join(full_text).strip()
    if not result:
        raise Exception(
            f"Ollama returned an empty response for model '{model}'. "
            "The model may still be loading — wait a moment and try again."
        )
    return result


def generate_with_glm(prompt, model=None):
    has_primary = GLM_API_KEY and GLM_API_KEY.strip() != "" and "your_glm" not in GLM_API_KEY
    has_fallback = GLM_API_KEY_FALLBACK and GLM_API_KEY_FALLBACK.strip() != "" and "your_glm" not in GLM_API_KEY_FALLBACK

    if not (has_primary or has_fallback):
        import re
        
        question_match = re.search(r"User Question:\s*(.*)", prompt)
        question = question_match.group(1).strip() if question_match else "N/A"
        
        context_match = re.search(r"Evidence Context:\s*(.*?)\s*User Question:", prompt, re.DOTALL)
        context = context_match.group(1).strip() if context_match else ""
        
        answer = (
            "🤖 **[DEMO MODE - Mock Forensics AI]**\n\n"
            "It looks like `GLM_API_KEY` is not set in your `.env` file, so the RAG engine is running in Demo Mode.\n\n"
            f"**Question Analyzed:** *\"{question}\"*\n\n"
        )
        
        found = False
        if context:
            sentences = re.split(r'(?<=[.!?])\s+', context)
            keywords = [w.lower() for w in question.split() if len(w) > 4]
            
            relevant_sentences = []
            for s in sentences:
                if any(k in s.lower() for k in keywords):
                    relevant_sentences.append(s.strip())
            
            if relevant_sentences:
                answer += "**Evidence Context Summary:**\n" + "\n".join([f"- {s}" for s in relevant_sentences[:4]])
                found = True
                
        if not found:
            if context:
                answer += f"**Evidence Context Overview (First 300 chars):**\n> {context[:300]}..."
            else:
                answer += "⚠️ No evidence context is currently uploaded or indexed for this case. Please upload a file and index it first."
                
        answer += "\n\n*(Note: To use live cloud intelligence, configure your `GLM_API_KEY` inside the `.env` file.)*"
        return answer

    model = model or GLM_MODEL
    url = f"{GLM_BASE_URL.rstrip('/')}/chat/completions"

    keys_to_try = []
    if has_primary:
        keys_to_try.append(GLM_API_KEY)
    if has_fallback:
        keys_to_try.append(GLM_API_KEY_FALLBACK)

    last_exception = None
    for api_key in keys_to_try:
        headers = {
            "Authorization": f"Bearer {api_key}",
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

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                
                if response.status_code == 429:
                    wait = 5 * (attempt + 1)
                    import time
                    time.sleep(wait)
                    continue
                
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                last_exception = e
                break

    if last_exception:
        raise last_exception
    raise Exception("GLM API request failed. Please check your API keys or connection.")


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