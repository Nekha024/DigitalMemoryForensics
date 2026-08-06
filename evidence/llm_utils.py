import os
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

GLM_BASE_URL = os.getenv("GLM_BASE_URL", "").rstrip("/")
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_API_KEY_FALLBACK = os.getenv("GLM_API_KEY_FALLBACK", "")
GLM_API_KEY_FALLBACK_2 = os.getenv("GLM_API_KEY_FALLBACK_2", "")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-5.1")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GMIN = os.getenv("GMIN", "false").lower() == "true"

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
    has_fallback_2 = GLM_API_KEY_FALLBACK_2 and GLM_API_KEY_FALLBACK_2.strip() != "" and "your_glm" not in GLM_API_KEY_FALLBACK_2
    has_groq = GROQ_API_KEY and GROQ_API_KEY.strip() != "" and "your_groq" not in GROQ_API_KEY

    if not (has_primary or has_fallback or has_fallback_2 or has_groq):
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

    if has_groq:
        try:
            return generate_with_groq(prompt)
        except Exception as e:
            print(f"Groq failed: {e}. Falling back to GLM keys...")

    model = model or GLM_MODEL
    url = f"{GLM_BASE_URL.rstrip('/')}/chat/completions"

    # Build ordered list of API keys to attempt
    keys_to_try = []
    if has_primary:
        keys_to_try.append(("primary", GLM_API_KEY))
    if has_fallback:
        keys_to_try.append(("fallback_1", GLM_API_KEY_FALLBACK))
    if has_fallback_2:
        keys_to_try.append(("fallback_2", GLM_API_KEY_FALLBACK_2))

    GLM_TIMEOUT = int(os.getenv("GLM_TIMEOUT", "120"))

    def _try_single_key(key_label, api_key):
        if key_label == "groq":
            target_url = "https://api.groq.com/openai/v1/chat/completions"
            target_model = GROQ_MODEL or "llama-3.3-70b-versatile"
            timeout = 30
        else:
            target_url = url
            target_model = model
            timeout = GLM_TIMEOUT

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": "You are a digital forensics assistant. Answer only from the provided evidence context."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 800,
        }

        # Make request
        response = requests.post(target_url, headers=headers, json=payload, timeout=timeout)
        
        if response.status_code == 429:
            raise Exception("Rate-limited (429)")
            
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        raise Exception("Returned an empty response")

    import concurrent.futures
    exceptions = []
    success_result = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(keys_to_try)) as executor:
        future_to_label = {
            executor.submit(_try_single_key, label, key): label
            for label, key in keys_to_try
        }

        for future in concurrent.futures.as_completed(future_to_label):
            label = future_to_label[future]
            try:
                res = future.result()
                if res:
                    success_result = res
                    break
            except Exception as e:
                exceptions.append(f"{label}: {e}")

    if success_result is not None:
        return success_result

    raise Exception(f"All GLM / Groq keys failed. Details:\n" + "\n".join(exceptions))


def generate_with_groq(prompt, model=None):
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in the environment.")
    
    model = model or GROQ_MODEL
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
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
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "").strip()
    raise Exception("Groq returned an empty response")


def generate_with_gemini(prompt, model=None):
    if (not GEMINI_API_KEY or 
        GEMINI_API_KEY.strip() == "" or 
        "your_gemini" in GEMINI_API_KEY or 
        "placeholder" in GEMINI_API_KEY or 
        "replace-me" in GEMINI_API_KEY):
        raise ValueError("GEMINI_API_KEY is not configured. Please open your .env file and replace the placeholder value with your actual, live Gemini API Key.")
    
    model = model or GEMINI_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        
        raise Exception("Gemini returned an empty response")
    except Exception as e:
        raise Exception(f"Gemini API request failed: {e}")


def generate_rag_answer(question, retrieved_chunks, provider=None):
    provider = (provider or DEFAULT_LLM_PROVIDER).lower()

    if not retrieved_chunks:
        return {
            "answer": "No relevant evidence chunks were found for this question.",
            "sources": []
        }

    prompt = build_rag_prompt(question, retrieved_chunks)

    if provider == "ollama":
        print(f"\n[INFO] Using LLM Provider: Ollama | Model: {OLLAMA_MODEL}\n")
        answer = generate_with_ollama(prompt)
    elif provider == "glm":
        if GMIN:
            print(f"\n[INFO] Using LLM Provider: Gemini | Model: {GEMINI_MODEL}\n")
            answer = generate_with_gemini(prompt)
        else:
            print(f"\n[INFO] Using LLM Provider: GLM | Model: {GLM_MODEL}\n")
            answer = generate_with_glm(prompt)
    elif provider == "groq":
        print(f"\n[INFO] Using LLM Provider: Groq | Model: {GROQ_MODEL}\n")
        answer = generate_with_groq(prompt)
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