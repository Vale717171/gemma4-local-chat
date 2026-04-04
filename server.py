import json
from flask import Flask, request, Response, send_from_directory, stream_with_context
from mlx_vlm import load, stream_generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

app = Flask(__name__)

MODEL_PATH = "mlx-community/gemma-4-e4b-it-8bit"

print(f"Loading model {MODEL_PATH}...")
model, processor = load(MODEL_PATH)
config = load_config(MODEL_PATH)
print("Model ready.")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 512)

    system_prompt = data.get("system_prompt", "")

    # Build full conversation as a single prompt
    conversation = ""
    if system_prompt:
        conversation += f"[System: {system_prompt}]\n\n"
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n"
    conversation += "Assistant:"

    prompt = apply_chat_template(processor, config, conversation, num_images=0)

    @stream_with_context
    def generate():
        for chunk in stream_generate(
            model,
            processor,
            prompt,
            image=None,
            max_tokens=max_tokens,
        ):
            token = chunk.text if hasattr(chunk, "text") else str(chunk)
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Server running at http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
