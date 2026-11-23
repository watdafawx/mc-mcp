"""Offline tests for llm_client.py: python test_llm_client.py
No network, no API keys, no Minecraft: a throwaway http.server on 127.0.0.1:0 plays the endpoint."""
import json
import os
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import llm_client as C  # noqa: E402


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


# ---- canned endpoint

CALLS = []   # every POST body the client sent
QUEUE = []   # responses to serve, in order


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        CALLS.append({"path": self.path, "auth": self.headers.get("Authorization"),
                      "body": json.loads(self.rfile.read(n) or b"{}")})
        payload = QUEUE.pop(0) if QUEUE else {"choices": [{"message": {"content": "?"}, "finish_reason": "stop"}]}
        status = payload.pop("_status", 200) if isinstance(payload, dict) else 200
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):  # keep the test output clean
        pass


SRV = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/v1" % SRV.server_address[1]
cli = C.OpenAICompatClient(BASE, "sk-test", timeout=10)


def reply(content=None, tool_calls=None, finish="stop", usage=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"id": "x", "model": "fake-model",
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": usage if usage is not None else {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}


IMG = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}}

# ---- 1. plain text reply: response shape, kwargs, system conversion
QUEUE.append(reply("a hall with a glass roof"))
r = cli.create(model="fake-model", max_tokens=16000,
               system=[{"type": "text", "text": "You are an architect.", "cache_control": {"type": "ephemeral"}}],
               tools=[{"name": "ghost_set", "description": "set a ghost", "input_schema": {
                   "type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
                   {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
               messages=[{"role": "user", "content": "build a hall"}],
               output_config={"effort": "medium"}, cache_control={"type": "ephemeral"})
sent = CALLS[-1]
check("posts to /chat/completions", sent["path"] == "/v1/chat/completions", sent["path"])
check("bearer key sent", sent["auth"] == "Bearer sk-test", sent["auth"])
check("model + max_tokens forwarded", sent["body"]["model"] == "fake-model" and sent["body"]["max_tokens"] == 16000)
check("anthropic-only kwargs dropped",
      "output_config" not in sent["body"] and "cache_control" not in sent["body"], sent["body"].keys())
check("system list -> one system message",
      sent["body"]["messages"][0] == {"role": "system", "content": "You are an architect."}, sent["body"]["messages"][0])
check("plain user message unchanged",
      sent["body"]["messages"][1] == {"role": "user", "content": "build a hall"})
check("custom tool converted to function",
      sent["body"]["tools"][0] == {"type": "function", "function": {
          "name": "ghost_set", "description": "set a ghost",
          "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
      sent["body"]["tools"][0])
check("server-side tool without input_schema skipped", len(sent["body"]["tools"]) == 1, sent["body"]["tools"])
check("text block", r.content[0].type == "text" and r.content[0].text == "a hall with a glass roof")
check("end_turn", r.stop_reason == "end_turn", r.stop_reason)
check("usage mapped", (r.usage.input_tokens, r.usage.output_tokens) == (11, 7), r.usage)
check("no cache counters", r.usage.cache_read_input_tokens == 0 and r.usage.cache_creation_input_tokens == 0)
check("model_dump text", [b.model_dump(mode="json", exclude_none=True) for b in r.content]
      == [{"type": "text", "text": "a hall with a glass roof"}],
      [b.model_dump(mode="json", exclude_none=True) for b in r.content])
check("model_dump kwarg tolerant", r.content[0].model_dump() == {"type": "text", "text": "a hall with a glass roof"})

# ---- 2. tool_use reply
QUEUE.append(reply(None, tool_calls=[{"id": "call_9", "type": "function",
                                      "function": {"name": "ghost_set", "arguments": '{"id": "core/hall"}'}}],
                   finish="tool_calls", usage={"prompt_tokens": 40, "completion_tokens": 12}))
r = cli.create(model="fake-model", max_tokens=100, system="s", messages=[{"role": "user", "content": "go"}])
tu = r.content[0]
check("tool_use block", tu.type == "tool_use" and tu.id == "call_9" and tu.name == "ghost_set"
      and tu.input == {"id": "core/hall"}, tu)
check("tool_use stop reason", r.stop_reason == "tool_use", r.stop_reason)
check("tool_use model_dump", tu.model_dump(mode="json", exclude_none=True)
      == {"type": "tool_use", "id": "call_9", "name": "ghost_set", "input": {"id": "core/hall"}}, tu.model_dump())
check("no empty text block", len(r.content) == 1, r.content)

# ---- 3. multi-turn history: assistant tool_use + tool_result with text AND a screenshot
QUEUE.append(reply("fixed the roofline"))
HISTORY = [
    {"role": "user", "content": "build a hall"},
    {"role": "assistant", "content": [{"type": "text", "text": "looking"},
                                      {"type": "tool_use", "id": "call_1", "name": "view",
                                       "input": {"target": "core/hall"}}]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "is_error": False,
                                  "content": [{"type": "text", "text": "view north of core/hall"},
                                              IMG,
                                              {"type": "image", "source": {"type": "base64",
                                                                           "media_type": "image/jpeg",
                                                                           "data": "REVG"}}]}]},
]
r = cli.create(model="fake-model", max_tokens=100, system="s", messages=HISTORY)
msgs = CALLS[-1]["body"]["messages"]
roles = [m["role"] for m in msgs]
check("history roles: system, user, assistant, tool, user", roles == ["system", "user", "assistant", "tool", "user"], roles)
asst = msgs[2]
check("assistant tool_calls built", asst["content"] == "looking" and asst["tool_calls"] == [
    {"id": "call_1", "type": "function", "function": {"name": "view", "arguments": '{"target": "core/hall"}'}}], asst)
tool_msg = msgs[3]
check("tool message carries the text", tool_msg["tool_call_id"] == "call_1"
      and "view north of core/hall" in tool_msg["content"], tool_msg)
vision = msgs[4]["content"]
check("screenshot re-sent as a user image", [p["image_url"]["url"] for p in vision if p["type"] == "image_url"]
      == ["data:image/png;base64,QUJD", "data:image/jpeg;base64,REVG"], vision)
check("text reply after the tool round", r.content[0].text == "fixed the roofline" and r.stop_reason == "end_turn")

# ---- 4. multimodal user content (a reference image)
QUEUE.append(reply("ok"))
REF = {"role": "user", "content": [{"type": "text", "text": "like this"}, IMG]}
cli.create(model="m", max_tokens=10, system="s", messages=[REF])
parts = CALLS[-1]["body"]["messages"][-1]["content"]
check("user image -> image_url data URI",
      parts == [{"type": "text", "text": "like this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}], parts)

# ---- 5. max_tokens mapping, and a text-less tool_result placeholder
QUEUE.append(reply("half a sen", finish="length"))
r = cli.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "go"}])
check("length -> max_tokens", r.stop_reason == "max_tokens", r.stop_reason)
cli.create(model="m", max_tokens=10, system="s",
           messages=[{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1"}]}])
only = CALLS[-1]["body"]["messages"][-1]
check("empty tool_result still sends a tool message",
      only["role"] == "tool" and only["tool_call_id"] == "c1" and only["content"] == "(no output)", only)

# ---- 6. HTTP errors surface as RuntimeError with the body
QUEUE.append({"_status": 400, "error": {"message": "bad model"}})
try:
    cli.create(model="m", max_tokens=10, system="s", messages=[{"role": "user", "content": "go"}])
    check("http error raises", False)
except RuntimeError as e:
    check("http error raises with the server text", "HTTP 400" in str(e) and "bad model" in str(e), str(e)[:80])

# ---- 7. make_client env detection (anthropic SDK faked: the tests stay SDK-free)
REAL_ENV = dict(os.environ)
REAL_ANTHROPIC = sys.modules.get("anthropic")


class FakeAnthropic:
    def __init__(self, **kw):
        self.kw = kw


fake = types.ModuleType("anthropic")
fake.Anthropic = FakeAnthropic
sys.modules["anthropic"] = fake


def env(**kw):
    for k in [k for k in os.environ if k.startswith(("ARCHITECT_", "ANTHROPIC_", "OPENAI_", "DEEPSEEK_"))]:
        del os.environ[k]
    for k, v in kw.items():
        if v is not None:
            os.environ[k] = v


env()
c, info = C.make_client()
check("default is anthropic", info["provider"] == "anthropic" and isinstance(c, FakeAnthropic) and not info["local"], info)
check("plain anthropic client gets no base_url", c.kw == {}, c.kw)
env(ANTHROPIC_API_KEY="sk-a", ARCHITECT_BASE_URL="http://192.168.50.3:11434")
c, info = C.make_client()
check("anthropic local base_url", info == {"provider": "anthropic", "local": True,
                                           "base_url": "http://192.168.50.3:11434"}, info)
check("anthropic local key falls back to ollama", c.kw.get("api_key") == "sk-a" and c.kw.get("timeout") == 900, c.kw)

env(DEEPSEEK_API_KEY="sk-d")
c, info = C.make_client()
check("deepseek key alone switches to openai", info["provider"] == "openai", info)
check("deepseek default base url", info["base_url"] == "https://api.deepseek.com/v1", info)
check("deepseek key used", c.api_key == "sk-d")
check("cloud endpoint is not local", info["local"] is False)

env(OPENAI_API_KEY="sk-o", DEEPSEEK_API_KEY="sk-d")
c, info = C.make_client()
check("openai key wins the default base url", info["base_url"] == "https://api.openai.com/v1" and c.api_key == "sk-o", info)

env(ANTHROPIC_API_KEY="sk-a", ARCHITECT_OPENAI_BASE_URL="http://127.0.0.1:1234/v1/")
c, info = C.make_client()
check("base url alone auto-detects openai", info == {"provider": "openai",
                                                     "base_url": "http://127.0.0.1:1234/v1/",
                                                     "local": True}, info)
check("no key -> ollama for a local server", c.api_key == "ollama", c.api_key)
check("trailing slash not doubled", c.url() == "http://127.0.0.1:1234/v1/chat/completions", c.url())

env(ARCHITECT_PROVIDER="anthropic", ARCHITECT_OPENAI_BASE_URL="http://127.0.0.1:1234/v1")
c, info = C.make_client()
check("explicit provider beats auto-detection", info["provider"] == "anthropic" and isinstance(c, FakeAnthropic), info)

env(ARCHITECT_PROVIDER="openai", ARCHITECT_OPENAI_BASE_URL="http://192.168.50.3:11434/v1",
    ARCHITECT_OPENAI_API_KEY="secret")
c, info = C.make_client()
check("explicit openai + lan host", info == {"provider": "openai", "base_url": "http://192.168.50.3:11434/v1",
                                             "local": True} and c.api_key == "secret", info)

env(ARCHITECT_PROVIDER="nope")
try:
    C.make_client()
    check("bad provider raises", False)
except ValueError:
    check("bad provider raises", True)

os.environ.clear()
os.environ.update(REAL_ENV)
if REAL_ANTHROPIC is not None:
    sys.modules["anthropic"] = REAL_ANTHROPIC
else:
    sys.modules.pop("anthropic", None)

# ---- hygiene: stdlib only, no keys read at import
src = Path(__file__).with_name("llm_client.py").read_text("utf-8")
imports = {ln.split()[1].split(".")[0] for ln in src.splitlines() if ln.startswith(("import ", "from "))}
check("stdlib only", imports <= {"json", "os", "urllib", "anthropic", "__future__"}, imports)

SRV.shutdown()
print("\n%s" % ("ALL OK" if not check.failed else f"{check.failed} FAILED"))
sys.exit(1 if check.failed else 0)
