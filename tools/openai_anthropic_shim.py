"""Local OpenAI-compatible -> Anthropic-compatible transport shim (stdlib only).

Some providers (e.g. Z.ai glm-* keys with Anthropic-channel quota only) cannot be
reached through the /chat/completions protocol directly. This shim lets the
standard benchmark adapter (OpenAICompatibleJSONGenerator, unmodified) talk to
such endpoints:

    MBENCH_API_ENDPOINT=http://127.0.0.1:8765/v4
    MBENCH_API_KEY_ENV=SHIM_KEY   (any non-empty value; the shim adds no auth)

The shim translates chat.completions requests to Anthropic /v1_messages calls
using the local FluxKernal-style model config (~/.config/fluxkernel/model.json
or FK_MODEL_* env). It forwards the requested model id verbatim, returns the
provider-reported model and usage, and never logs credentials or request bodies.
Scoring, receipts and replay discipline live in the benchmark adapter unchanged.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import threading
import time
from pathlib import Path

FLUXKERNEL_REPO = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/fluxkernel')
if str(FLUXKERNEL_REPO) not in sys.path:
    sys.path.insert(0, str(FLUXKERNEL_REPO))

from fluxkernel.demo import vision  # noqa: E402

STATE = {'calls': 0, 'failures': 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # no request bodies in logs

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip('/').endswith('/health'):
            self._json(200, {'ok': True, 'calls': STATE['calls'], 'failures': STATE['failures']})
        else:
            self._json(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.rstrip('/').endswith('/chat/completions'):
            self._json(404, {'error': 'only /chat/completions is proxied'})
            return
        length = int(self.headers.get('Content-Length', 0))
        try:
            request = json.loads(self.rfile.read(length))
            messages = request['messages']
            system = '\n\n'.join(m['content'] for m in messages if m.get('role') == 'system')
            user = '\n\n'.join(m['content'] for m in messages if m.get('role') != 'system')
            cfg = dict(vision.model_config())
            cfg['model'] = request.get('model', cfg['model'])
            wire = [{'role': 'system', 'content': system or 'You are a JSON generator.'},
                    {'role': 'user', 'content': user}]
            text, raw = vision._call(cfg, wire, None, None)
            STATE['calls'] += 1
            # Transport normalization mirroring response_format=json_object on the
            # native OpenAI endpoint: unwrap ONE complete markdown fence. Partial
            # fences are left untouched and fail downstream parsing, never repaired.
            clean = text.strip()
            if clean.startswith('```') and clean.rstrip().endswith('```') and clean.count('```') == 2:
                lines = clean.split('\n')
                if len(lines) >= 3:
                    clean = '\n'.join(lines[1:-1]).strip()
                text = clean
            usage = raw.get('usage', {})
            self._json(200, {
                'id': raw.get('id', 'shim-' + str(STATE['calls'])),
                'object': 'chat.completion',
                'created': int(time.time()),
                'model': raw.get('model', cfg['model']),
                'choices': [{
                    'index': 0,
                    'message': {'role': 'assistant', 'content': text},
                    'finish_reason': 'stop' if raw.get('stop_reason') == 'end_turn' else 'length'}],
                'usage': {'prompt_tokens': usage.get('input_tokens', 0),
                          'completion_tokens': usage.get('output_tokens', 0),
                          'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0)},
                'shim': {'transport': 'anthropic-compatible', 'endpoint': cfg['base_url']}})
        except Exception as exc:  # surface transport errors as HTTP errors
            STATE['failures'] += 1
            self._json(502, {'error': f'shim upstream failure: {str(exc)[:300]}'})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'shim listening on 127.0.0.1:{port} -> {vision.model_config()["base_url"]}', flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main()
