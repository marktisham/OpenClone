import json
import queue
import threading
from flask import Flask, Response, request, render_template, stream_with_context
import requests

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True)
    ip = data["ip"].strip()
    prompt = data["prompt"]
    existing_session_id = (data.get("session_id") or "").strip() or None
    base = f"http://{ip}:4096"

    def generate():
        def sse(event_type, payload):
            return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

        if existing_session_id:
            session_id = existing_session_id
        else:
            try:
                r = requests.post(
                    f"{base}/session",
                    json={"title": "reasoning-tester"},
                    timeout=30,
                )
                r.raise_for_status()
                session_id = r.json()["id"]
            except Exception as e:
                yield sse("error", {"message": f"Failed to create session: {e}"})
                return

        yield sse("session", {"id": session_id})

        # Open SSE to opencode before posting the prompt
        try:
            stream_resp = requests.get(f"{base}/event", stream=True, timeout=None)
        except Exception as e:
            yield sse("error", {"message": f"Failed to open event stream: {e}"})
            return

        # Post the prompt in a background thread so we can start reading events immediately
        def post_prompt():
            try:
                requests.post(
                    f"{base}/session/{session_id}/message",
                    json={"parts": [{"type": "text", "text": prompt}]},
                    timeout=None,
                )
            except Exception as e:
                q.put(("error", {"message": f"Prompt POST failed: {e}"}))
            finally:
                q.put(("done", {}))

        q: queue.Queue = queue.Queue()

        def read_events():
            try:
                for raw in stream_resp.iter_lines(decode_unicode=True):
                    if not raw or not raw.startswith("data:"):
                        continue
                    payload = raw[5:].lstrip()
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    props = obj.get("properties") or {}
                    part = props.get("part") or obj.get("part") or {}
                    ptype = part.get("type")
                    if ptype not in ("reasoning", "text"):
                        continue
                    text = part.get("text") or part.get("thinking")
                    if not text:
                        continue
                    # Skip the prompt echo (user message part)
                    if ptype == "text" and text.strip() == prompt.strip():
                        continue
                    q.put(("part", {"type": ptype, "text": text}))
            except Exception as e:
                q.put(("error", {"message": f"Stream read failed: {e}"}))

        threading.Thread(target=read_events, daemon=True).start()
        threading.Thread(target=post_prompt, daemon=True).start()

        while True:
            try:
                kind, payload = q.get(timeout=300)
            except queue.Empty:
                yield sse("error", {"message": "Timed out waiting for events"})
                break
            if kind == "done":
                yield sse("done", {})
                break
            yield sse(kind, payload)

        try:
            stream_resp.close()
        except Exception:
            pass

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=True, threaded=True, use_reloader=False)
