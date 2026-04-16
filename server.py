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

# ── Google AI Studio config (local only, never pushed) ────────
try:
    from google_aistudio_config import GOOGLE_AI_STUDIO_API_KEY
    print("Google AI Studio config loaded.")
except ImportError:
    GOOGLE_AI_STUDIO_API_KEY = ""
    print("google_aistudio_config.py not found — add your API key there.")

OPENROUTER_DEFAULT_MODEL = "google/gemma-4-31b-it"
GOOGLE_DEFAULT_MODEL     = "gemma-4-31b-it"
GOOGLE_AI_BASE_URL       = "https://generativelanguage.googleapis.com/v1beta/openai"

# Modelli OpenRouter disponibili (prefisso google/)
OPENROUTER_ALLOWED_MODELS = {
    "google/gemma-4-31b-it",
    "google/gemma-3-27b-it",
    "deepseek/deepseek-v3.2",
}

# Modelli Google AI Studio disponibili
GOOGLE_ALLOWED_MODELS = {
    "gemma-4-31b-it",
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-04-17",
    "gemma-3-27b-it",
}


def _to_api_message(msg):
    role = msg.get("role", "user")
    if role not in {"system", "user", "assistant"}:
        role = "user"

    text = msg.get("content", "")
    if not isinstance(text, str):
        text = str(text)

    attachments = msg.get("attachments", [])
    parts = []
    if text.strip():
        parts.append({"type": "text", "text": text})

    if isinstance(attachments, list):
        for att in attachments:
            if not isinstance(att, dict):
                continue
            kind = att.get("type")
            data_url = att.get("dataUrl") or att.get("data_url")
            mime_type = att.get("mimeType") or att.get("mime_type") or ""
            if not isinstance(data_url, str) or not data_url.startswith("data:"):
                continue

            if kind == "image":
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
            elif kind == "video":
                try:
                    encoded = data_url.split(",", 1)[1]
                except IndexError:
                    encoded = ""
                if encoded:
                    parts.append(
                        {
                            "type": "input_video",
                            "input_video": {
                                "data": encoded,
                                "mime_type": mime_type or "video/mp4",
                            },
                        }
                    )

    if parts:
        return {"role": role, "content": parts}
    return {"role": role, "content": text}


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages      = data.get("messages", [])
    max_tokens    = data.get("max_tokens", 512)
    system_prompt = data.get("system_prompt", "")
    backend       = data.get("backend", "openrouter")
    requested_model = data.get("model", "")

    if not isinstance(messages, list):
        messages = []
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = 512
    max_tokens = max(64, min(max_tokens, 8192))

    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    for msg in messages:
        if isinstance(msg, dict):
            api_messages.append(_to_api_message(msg))

    if backend == "google":
        api_url = f"{GOOGLE_AI_BASE_URL}/chat/completions"
        api_key = GOOGLE_AI_STUDIO_API_KEY
        model   = requested_model if requested_model in GOOGLE_ALLOWED_MODELS else GOOGLE_DEFAULT_MODEL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = OPENROUTER_API_KEY
        model   = requested_model if requested_model in OPENROUTER_ALLOWED_MODELS else OPENROUTER_DEFAULT_MODEL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:5001",
            "X-Title": "Gemma 4 Chat",
        }

    payload = {
        "model": model,
        "messages": api_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }


    @stream_with_context
    def generate():
        # State machine for filtering <thought>...</thought> blocks (Google backend)
        th_state = {"in_thought": False, "buf": ""}

        def filter_thought(token):
            """Remove <thought>...</thought> from streaming tokens. Returns text to emit."""
            s = th_state
            s["buf"] += token
            out = []

            while True:
                if s["in_thought"]:
                    end = s["buf"].find("</thought>")
                    if end != -1:
                        # Skip past the closing tag; strip leading newline
                        s["buf"] = s["buf"][end + len("</thought>"):].lstrip("\n")
                        s["in_thought"] = False
                    else:
                        # Still inside thought block — discard buffered content
                        # Keep only the tail in case </thought> is split across chunks
                        keep = len("</thought>") - 1
                        s["buf"] = s["buf"][-keep:] if len(s["buf"]) > keep else s["buf"]
                        break
                else:
                    start = s["buf"].find("<thought>")
                    if start != -1:
                        out.append(s["buf"][:start])
                        s["buf"] = s["buf"][start + len("<thought>"):]
                        s["in_thought"] = True
                    else:
                        # Emit all except chars that could be a partial opening tag
                        keep = len("<thought>") - 1
                        if len(s["buf"]) > keep:
                            out.append(s["buf"][:-keep])
                            s["buf"] = s["buf"][-keep:]
                        break

            return "".join(out)

        try:
            with requests.post(
                api_url,
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
                            if "error" in chunk:
                                err_msg = chunk["error"].get("message", str(chunk["error"]))
                                print(f"[{backend} error] {err_msg}")
                                yield f"data: {json.dumps({'error': err_msg})}\n\n"
                                break
                            choices = chunk.get("choices", [])
                            if not choices:
                                print(f"[{backend}] chunk senza choices: {chunk_str[:200]}")
                                continue
                            token = choices[0]["delta"].get("content", "")
                            if token:
                                if backend == "google":
                                    token = filter_thought(token)
                                if token:
                                    yield f"data: {json.dumps({'token': token})}\n\n"
                            finish = choices[0].get("finish_reason")
                            if finish and finish != "null":
                                print(f"[{backend}] finish_reason: {finish}")
                            usage = chunk.get("usage")
                            if usage:
                                yield f"data: {json.dumps({'usage': usage})}\n\n"
                        except Exception as e:
                            print(f"[parse error] {e} — raw: {chunk_str[:200]}")
                            continue
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        # Flush any remaining buffer after stream ends
        if backend == "google" and th_state["buf"] and not th_state["in_thought"]:
            yield f"data: {json.dumps({'token': th_state['buf']})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/balance")
def balance():
    backend = request.args.get("backend", "openrouter")

    if backend == "google":
        # Google AI Studio è pay-per-use, nessun credito da monitorare
        return {"type": "pay-per-use"}

    # OpenRouter: legge il saldo residuo
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10,
        )
        data = r.json().get("data", {})
        total   = data.get("total_credits", 0)
        usage   = data.get("total_usage", 0)
        remaining = round(total - usage, 4)
        return {"remaining": remaining}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
