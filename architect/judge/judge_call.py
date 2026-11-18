import json, os, urllib.request
URL = os.environ.get("MCMCP_URL", "http://127.0.0.1:47861/mcp")
n = 0
def call(name, args):
    global n; n += 1
    body = json.dumps({"jsonrpc": "2.0", "id": n, "method": "tools/call", "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())["result"]
    return "\n".join(c.get("text", "") for c in r.get("content", []))
