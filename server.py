import json
import time
import requests
from flask import Flask, request, Response, send_from_directory, stream_with_context
from mlx_vlm import load, stream_generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

app = Flask(__name__)

# ── Local model ──────────────────────────────────────────────
MODEL_PATH = "mlx-community/gemma-4-e4b-it-8bit"
print(f"Loading local model {MODEL_PATH}...")
model, processor = load(MODEL_PATH)
config = load_config(MODEL_PATH)
print("Local model ready.")

# ── RunPod config (local only, never pushed) ─────────────────
try:
    from runpod_config import RUNPOD_API_KEY, RUNPOD_ENDPOINT_ID, COST_PER_SECOND
    RUNPOD_AVAILABLE = True
    print("RunPod config loaded.")
except ImportError:
    RUNPOD_AVAILABLE = False
    RUNPOD_API_KEY = ""
    RUNPOD_ENDPOINT_ID = ""
    COST_PER_SECOND = 0.00074
    print("RunPod config not found — cloud mode disabled.")

# ── Helpers ───────────────────────────────────────────────────
def build_conversation(messages, system_prompt):
    conversation = ""
    if system_prompt:
        conversation += f"[System: {system_prompt}]\n\n"
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n"
    conversation += "Assistant:"
    return conversation


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/runpod/available")
def runpod_available():
    return {"available": RUNPOD_AVAILABLE}


@app.route("/runpod/status")
def runpod_status():
    if not RUNPOD_AVAILABLE:
        return {"status": "unavailable"}
    try:
        url = f"https://api.runpod.io/v2/{RUNPOD_ENDPOINT_ID}/health"
        headers = {"Authorization": f"Bearer {RUNPOD_API_KEY}"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        workers_ready = data.get("workers", {}).get("ready", 0)
        workers_running = data.get("workers", {}).get("running", 0)
        return {
            "status": "ready" if workers_ready > 0 or workers_running > 0 else "cold",
            "workers_ready": workers_ready,
            "workers_running": workers_running,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 512)
    system_prompt = data.get("system_prompt", "")
    mode = data.get("mode", "local")  # "local" or "cloud"

    if mode == "cloud" and RUNPOD_AVAILABLE:
        return chat_cloud(messages, system_prompt, max_tokens)
    else:
        return chat_local(messages, system_prompt, max_tokens)


def chat_local(messages, system_prompt, max_tokens):
    conversation = build_conversation(messages, system_prompt)
    prompt = apply_chat_template(processor, config, conversation, num_images=0)

    @stream_with_context
    def generate():
        for chunk in stream_generate(
            model, processor, prompt, image=None, max_tokens=max_tokens,
        ):
            token = chunk.text if hasattr(chunk, "text") else str(chunk)
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


def chat_cloud(messages, system_prompt, max_tokens):
    url = f"https://api.runpod.io/v2/{RUNPOD_ENDPOINT_ID}/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build messages array for OpenAI-compatible API
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    payload = {
        "model": "google/gemma-4-27b-it",
        "messages": api_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }

    @stream_with_context
    def generate():
        start_time = time.time()
        try:
            with requests.post(url, headers=headers, json=payload,
                               stream=True, timeout=120) as resp:
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
                                elapsed = time.time() - start_time
                                cost = elapsed * COST_PER_SECOND
                                yield f"data: {json.dumps({'token': token, 'cost': round(cost, 5)})}\n\n"
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        elapsed = time.time() - start_time
        total_cost = elapsed * COST_PER_SECOND
        yield f"data: {json.dumps({'done': True, 'total_cost': round(total_cost, 5), 'elapsed': round(elapsed, 1)})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
