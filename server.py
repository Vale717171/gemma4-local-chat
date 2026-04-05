import json
import requests
from flask import Flask, request, Response, send_from_directory, stream_with_context

app = Flask(__name__)

# ── OpenRouter config (local only, never pushed) ──────────────
try:
    from openrouter_config import OPENROUTER_API_KEY
    print("OpenRouter config loaded.")
except ImportError:
    OPENROUTER_API_KEY = ""
    print("openrouter_config.py not found — add your API key there.")

MODEL = "google/gemma-4-31b-it"


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 512)
    system_prompt = data.get("system_prompt", "")

    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1:5001",
        "X-Title": "Gemma 4 Chat",
    }

    payload = {
        "model": MODEL,
        "messages": api_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }

    @stream_with_context
    def generate():
        try:
            with requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        chunk_str = line[6:]
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_str)
                            token = chunk["choices"][0]["delta"].get("content", "")
                            if token:
                                yield f"data: {json.dumps({'token': token})}\n\n"
                            # OpenRouter invia usage nell'ultimo chunk
                            usage = chunk.get("usage")
                            if usage:
                                yield f"data: {json.dumps({'usage': usage})}\n\n"
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/balance")
def balance():
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10,
        )
        data = r.json().get("data", {})
        total = data.get("total_credits", 0)
        usage = data.get("total_usage", 0)
        remaining = round(total - usage, 4)
        return {"remaining": remaining}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
