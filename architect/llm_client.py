"""LLM client for the architect: Anthropic Messages API *or* any OpenAI-compatible endpoint,
behind one interface.

architect.py only ever calls `client.messages.create(model=..., max_tokens=..., system=...,
tools=..., messages=..., **anthropic_only_kwargs)` and then reads `resp.content` (blocks with
.type/.text/.id/.name/.input and .model_dump()), `resp.stop_reason` and `resp.usage`
(.input_tokens/.output_tokens). This module keeps that shape and translates to
`POST {base_url}/chat/completions` for DeepSeek, OpenRouter, Ollama /v1, LM Studio or vLLM.

Stdlib only (urllib + json): no pip installs, no SDK for the OpenAI side.

Env vars (see make_client):
  ARCHITECT_PROVIDER          "anthropic" (default) or "openai"
  ARCHITECT_OPENAI_BASE_URL   e.g. https://openrouter.ai/api/v1, http://192.168.50.3:11434/v1
  ARCHITECT_OPENAI_API_KEY    key for that endpoint (falls back to OPENAI_API_KEY / DEEPSEEK_API_KEY)
  ARCHITECT_BASE_URL          Anthropic-API-speaking local server (Ollama 0.40+, LM Studio's /v1/messages)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

TIMEOUT = 180  # seconds; a local model writing a big tool call can be slow, but not forever

# Anthropic-only request fields the OpenAI chat-completions API does not know.
ANTHROPIC_ONLY = frozenset({"output_config", "cache_control", "cache_creation", "betas",
                            "thinking", "metadata", "mcp_servers", "service_tier"})
# OpenAI-only fields we forward if a caller passes them.
OPENAI_PASSTHROUGH = frozenset({"temperature", "top_p", "seed", "presence_penalty", "frequency_penalty"})


# ---- Anthropic-shaped response pieces

class TextBlock:
    """`{"type": "text", "text": ...}` from a chat-completions `message.content`."""
    type = "text"

    def __init__(self, text: str):
        self.text = text

    def model_dump(self, mode: str = "json", exclude_none: bool = True, **_) -> dict:
        return {"type": "text", "text": self.text}

    def __repr__(self) -> str:
        return f"TextBlock({self.text[:60]!r})"


class ToolUseBlock:
    """`{"type": "tool_use", "id", "name", "input"}` from a chat-completions `tool_calls[]` entry."""
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict | None = None):  # noqa: A002 - Anthropic's field name
        self.id = id
        self.name = name
        self.input = input if isinstance(input, dict) else {}

    def model_dump(self, mode: str = "json", exclude_none: bool = True, **_) -> dict:
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}

    def __repr__(self) -> str:
        return f"ToolUseBlock({self.name}, {self.id})"


class Usage:
    """Anthropic's `resp.usage`; OpenAI only reports prompt/completion tokens (no caching counters)."""

    def __init__(self, input_tokens: int = 0, output_tokens: int = 0,
                 cache_creation_input_tokens: int = 0, cache_read_input_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens = cache_read_input_tokens

    def model_dump(self, mode: str = "json", exclude_none: bool = True, **_) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_creation_input_tokens": self.cache_creation_input_tokens,
                "cache_read_input_tokens": self.cache_read_input_tokens}

    def __repr__(self) -> str:
        return f"Usage(in={self.input_tokens}, out={self.output_tokens})"


class Response:
    """Anthropic's `Message`: `.content` blocks, `.stop_reason`, `.usage`."""

    def __init__(self, content: list, stop_reason: str = "end_turn", usage: Usage | None = None,
                 model: str = "", raw: dict | None = None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or Usage()
        self.model = model
        self.raw = raw

    def __repr__(self) -> str:
        return f"Response({self.stop_reason}, {self.content!r})"


# ---- Anthropic request -> OpenAI request

def _image_url(block: dict) -> dict | None:
    """Anthropic image block -> OpenAI `image_url` part (base64 data URI or plain URL)."""
    src = block.get("source") or {}
    stype = src.get("type")
    if stype == "base64" and src.get("data"):
        mime = src.get("media_type") or "image/png"
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{src['data']}"}}
    if stype == "url" and src.get("url"):
        return {"type": "image_url", "image_url": {"url": src["url"]}}
    return None


def _parts_of(content) -> list[dict]:
    """Turn Anthropic user-content blocks into OpenAI content parts (text + image_url)."""
    parts: list[dict] = []
    for b in content if isinstance(content, list) else [{"type": "text", "text": content}]:
        if not isinstance(b, dict):
            parts.append({"type": "text", "text": str(b)})
            continue
        t = b.get("type")
        if t == "text":
            parts.append({"type": "text", "text": b.get("text") or ""})
        elif t == "image":
            p = _image_url(b)
            if p:
                parts.append(p)
        # documents, thinking blocks and unknown types are dropped: chat-completions has no slot for them
    return parts


def _tool_result_msg(block: dict) -> tuple[dict, list[dict]]:
    """One Anthropic `tool_result` -> (OpenAI tool message, image parts to send as user content)."""
    content = block.get("content")
    texts: list[str] = []
    images: list[dict] = []
    if isinstance(content, str):
        texts.append(content)
    else:
        for b in content or []:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict):
                if b.get("type") == "text":
                    texts.append(b.get("text") or "")
                elif b.get("type") == "image":
                    p = _image_url(b)
                    if p:
                        images.append(p)
    text = "\n".join(t for t in texts if t)
    if not text:
        # some servers reject an empty tool message; screenshots still follow in the user message
        text = "(see the attached image)" if images else "(no output)"
    msg = {"role": "tool", "tool_call_id": block.get("tool_use_id") or "", "content": text}
    return msg, images


def convert_messages(messages: list[dict]) -> list[dict]:
    """Anthropic Messages -> OpenAI chat-completions messages.

    Tool results become `role: "tool"` messages and are emitted before any other content of the same
    Anthropic user message, because the API wants every tool reply right after the assistant turn.
    Images inside a tool result are re-sent as a following user message, so vision models still see them.
    """
    out: list[dict] = []
    for m in messages or []:
        role, content = m.get("role"), m.get("content")
        if role == "assistant":
            if isinstance(content, str):
                out.append({"role": "assistant", "content": content})
                continue
            texts, calls = [], []
            for b in content or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    texts.append(b["text"])
                elif b.get("type") == "tool_use":
                    calls.append({"id": b.get("id") or "", "type": "function",
                                  "function": {"name": b.get("name") or "",
                                               "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)}})
            msg = {"role": "assistant", "content": "\n".join(texts) or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
            continue
        # user
        if isinstance(content, str):
            out.append({"role": "user", "content": content})
            continue
        tool_msgs, image_parts = [], []
        for b in content or []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                tm, imgs = _tool_result_msg(b)
                tool_msgs.append(tm)
                image_parts += imgs
        out += tool_msgs
        parts = [p for p in _parts_of(content) if p.get("type") == "image_url" or p.get("text")]
        if image_parts or any(p["type"] == "image_url" for p in parts):
            # multimodal: keep the array form so the endpoint sees the images in order
            out.append({"role": "user", "content": parts + image_parts})
        else:
            text = "\n".join(p.get("text") or "" for p in parts if p.get("text"))
            if text:
                out.append({"role": "user", "content": text})
    return out


def convert_system(system) -> list[dict]:
    """Anthropic `system` (string or text blocks) -> one OpenAI system message."""
    if not system:
        return []
    if isinstance(system, str):
        text = system
    else:
        text = "\n".join(b.get("text") or "" for b in system
                         if isinstance(b, dict) and b.get("type") == "text")
    return [{"role": "system", "content": text}] if text else []


def convert_tools(tools) -> list[dict]:
    """Anthropic custom tools -> OpenAI function tools. Server-side tools (no input_schema) are skipped."""
    out: list[dict] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        name = t.get("name")
        schema = t.get("input_schema")
        if not name or not isinstance(schema, dict):
            continue  # web_search_20250305 and friends: the endpoint cannot run them
        fn = {"name": name, "parameters": schema}
        if t.get("description"):
            fn["description"] = t["description"]
        out.append({"type": "function", "function": fn})
    return out


# ---- OpenAI response -> Anthropic-shaped response

def _message_text(raw) -> str:
    """Some servers return content as parts instead of a string."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(p.get("text") or "" for p in raw if isinstance(p, dict) and p.get("type") in (None, "text"))
    return ""


def parse_response(data: dict, model: str = "") -> Response:
    choices = data.get("choices") or []
    choice = choices[0] if isinstance(choices, list) and choices else {}
    msg = choice.get("message") or {}
    finish = choice.get("finish_reason")
    content: list = []
    text = _message_text(msg.get("content"))
    if text:
        content.append(TextBlock(text))
    for i, tc in enumerate(msg.get("tool_calls") or []):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {"_raw": args}  # keep the broken call visible instead of losing it
        elif args is None:
            args = {}
        content.append(ToolUseBlock(tc.get("id") or f"call_{i}", fn.get("name") or "", args))
    if msg.get("tool_calls") or finish == "tool_calls":
        stop = "tool_use"
    elif finish == "length":
        stop = "max_tokens"
    else:
        stop = "end_turn"
    u = data.get("usage") or {}
    usage = Usage(input_tokens=int(u.get("prompt_tokens") or 0), output_tokens=int(u.get("completion_tokens") or 0))
    return Response(content=content, stop_reason=stop, usage=usage,
                    model=data.get("model") or model, raw=data)


# ---- the client

class _Messages:
    def __init__(self, client: "OpenAICompatClient"):
        self._client = client

    def create(self, **kwargs) -> Response:
        return self._client.create(**kwargs)


class OpenAICompatClient:
    """Drop-in for `anthropic.Anthropic()` as far as architect.py uses it."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = TIMEOUT):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout
        self.messages = _Messages(self)

    def url(self) -> str:
        return self.base_url + "/chat/completions"

    def payload(self, model: str, max_tokens: int, system, tools, messages, **kwargs) -> dict:
        body = {"model": model, "max_tokens": int(max_tokens or 1024)}
        msgs = convert_system(system) + convert_messages(messages)
        body["messages"] = msgs
        conv_tools = convert_tools(tools)
        if conv_tools:
            body["tools"] = conv_tools
        for k, v in kwargs.items():
            if k in ANTHROPIC_ONLY or k in ("model", "max_tokens", "system", "tools", "messages"):
                continue
            if k in OPENAI_PASSTHROUGH and v is not None:
                body[k] = v
        return body

    def create(self, model: str = "", max_tokens: int = 4096, system=None, tools=None,
               messages: list | None = None, **kwargs) -> Response:
        body = self.payload(model, max_tokens, system, tools, messages, **kwargs)
        req = urllib.request.Request(
            self.url(), data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:800]
            raise RuntimeError(f"llm request failed: HTTP {e.code} from {self.url()}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"llm request failed: cannot reach {self.url()}: {e.reason}. "
                               "Is the local server running?") from None
        except TimeoutError:
            raise RuntimeError(f"llm request failed: {self.url()} timed out after {self.timeout:.0f}s") from None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"llm request failed: {self.url()} did not return JSON: {raw[:300]}") from None
        if not data.get("choices"):
            err = data.get("error") or data
            raise RuntimeError(f"llm request failed: no choices from {self.url()}: {str(err)[:400]}")
        return parse_response(data, model)

    def __repr__(self) -> str:
        return f"OpenAICompatClient({self.base_url})"


# ---- provider selection

def pick_provider() -> str:
    """`ARCHITECT_PROVIDER`, or what the env implies."""
    explicit = (os.environ.get("ARCHITECT_PROVIDER") or "").strip().lower()
    if explicit:
        if explicit in ("openai", "openai-compat", "openai_compat", "oai"):
            return "openai"
        if explicit in ("anthropic", "claude"):
            return "anthropic"
        raise ValueError(f"ARCHITECT_PROVIDER={explicit!r}: use 'anthropic' or 'openai'")
    if os.environ.get("ARCHITECT_OPENAI_BASE_URL"):
        return "openai"
    if not os.environ.get("ANTHROPIC_API_KEY") and (os.environ.get("OPENAI_API_KEY")
                                                    or os.environ.get("DEEPSEEK_API_KEY")):
        return "openai"
    return "anthropic"


def openai_settings() -> tuple[str, str]:
    """(base_url, api_key) for an OpenAI-compatible endpoint, from the env."""
    base = (os.environ.get("ARCHITECT_OPENAI_BASE_URL") or "").strip()
    key = (os.environ.get("ARCHITECT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
           or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not base:
        base = ("https://api.deepseek.com/v1" if os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("OPENAI_API_KEY")
                else "https://api.openai.com/v1")
    return base, key or "ollama"  # local servers (Ollama, LM Studio, vLLM) ignore the key


def is_local(base_url: str) -> bool:
    b = (base_url or "").lower()
    return "127.0.0.1" in b or "localhost" in b or "192.168." in b


def make_client() -> tuple[object, dict]:
    """Build the client architect.py should use, plus a small info dict for printing/pricing decisions.

    ("openai" -> OpenAICompatClient, {"provider": "openai", "base_url": ..., "local": bool})
    ("anthropic" -> anthropic.Anthropic, {"provider": "anthropic", "local": bool})
    """
    provider = pick_provider()
    if provider == "openai":
        base, key = openai_settings()
        return OpenAICompatClient(base, key), {"provider": "openai", "base_url": base, "local": is_local(base)}
    import anthropic  # imported lazily: the openai path needs no SDK

    base = (os.environ.get("ARCHITECT_BASE_URL") or "").strip()
    if base:
        return (anthropic.Anthropic(base_url=base, api_key=os.environ.get("ANTHROPIC_API_KEY") or "ollama",
                                    timeout=900),
                {"provider": "anthropic", "local": True, "base_url": base})
    return anthropic.Anthropic(), {"provider": "anthropic", "local": False, "base_url": ""}
