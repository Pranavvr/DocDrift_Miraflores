"""Model backends: Ollama (local HTTP API) and a mock that returns a fixture file."""

import json
import urllib.error
import urllib.request

from docdrift.errors import BackendError, InputError

OLLAMA_URL = "http://localhost:11434"

SETUP_HELP = """Setup:
  1. Install Ollama: https://ollama.com/download
  2. Start it:       ollama serve
  3. Pull the model: ollama pull {model}
Or run without a model: --backend mock --mock-response tests/fixtures/<file>.json"""


class OllamaBackend:
    is_mock = False

    def __init__(self, model: str, url: str | None = None, timeout: int = 300):
        self.model = model
        self.url = url or OLLAMA_URL
        self.timeout = timeout

    def _request(self, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def check_available(self) -> None:
        try:
            tags = self._request("/api/tags")
        except (urllib.error.URLError, OSError) as e:
            raise BackendError(f"Ollama is not reachable at {self.url} ({e}).\n" + SETUP_HELP.format(model=self.model))
        names = {m.get("name", "") for m in tags.get("models", [])}
        wanted = self.model if ":" in self.model else self.model + ":latest"
        if wanted not in names:
            raise BackendError(f"Model {self.model!r} is not pulled.\n" + SETUP_HELP.format(model=self.model))

    def chat(self, messages: list[dict], schema: dict, num_ctx: int) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": num_ctx},  # explicit: Ollama's default truncates silently
        }
        try:
            resp = self._request("/api/chat", payload, timeout=self.timeout)
        except (urllib.error.URLError, OSError) as e:
            raise BackendError(f"Ollama request failed: {e}")
        return resp.get("message", {}).get("content", "")


class MockBackend:
    """Returns a fixture file verbatim. Bypasses Ollama's schema enforcement, as real bad output would."""

    is_mock = True
    model = "mock"

    def __init__(self, response_path: str):
        try:
            with open(response_path, encoding="utf-8") as fh:
                self.response = fh.read()
        except OSError as e:
            raise InputError(f"cannot read mock response {response_path}: {e}") from e

    def check_available(self) -> None:
        pass

    def chat(self, messages: list[dict], schema: dict, num_ctx: int) -> str:
        return self.response
