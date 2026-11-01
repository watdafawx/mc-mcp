package dev.watdafawx.mcmcp.mcp;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Predicate;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * A minimal MCP server over streamable HTTP: JSON-RPC requests are POSTed to {@code /mcp} and
 * answered with a plain JSON body (no SSE stream; the spec allows that, and none of the tools
 * need server-initiated messages). Long-running tools such as {@code chat_wait} simply hold the
 * POST open until they finish.
 */
public final class McpServer {
    private static final Logger LOG = LoggerFactory.getLogger("mcmcp");
    public static final Gson GSON = new GsonBuilder().disableHtmlEscaping().serializeSpecialFloatingPointValues().create();
    private static final Set<String> KNOWN_VERSIONS = Set.of("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25");
    private static final String DEFAULT_VERSION = "2025-06-18";

    @FunctionalInterface
    public interface Handler {
        /** Returns anything Gson can serialize (Map, List, String, record...). */
        Object call(JsonObject args) throws Exception;
    }

    public record Tool(String name, String description, JsonObject inputSchema, boolean readOnly, Handler handler) {}

    /** Thrown by a handler for an expected failure; reported as a tool error, not logged. */
    public static final class ToolError extends RuntimeException {
        public ToolError(String message) { super(message); }
    }

    private final String name;
    private final String version;
    private final String instructions;
    private final Map<String, Tool> tools = new LinkedHashMap<>();
    /** Decides per call whether a tool is currently enabled (config can change at runtime). */
    private volatile Predicate<Tool> gate = t -> true;
    private HttpServer http;
    private ExecutorService pool;

    public McpServer(String name, String version, String instructions) {
        this.name = name;
        this.version = version;
        this.instructions = instructions;
    }

    public synchronized void add(Tool tool) {
        tools.put(tool.name(), tool);
    }

    public void setGate(Predicate<Tool> gate) {
        this.gate = gate;
    }

    /** Tools enabled right now. */
    public synchronized List<Tool> tools() {
        List<Tool> out = new ArrayList<>();
        for (Tool t : tools.values()) if (gate.test(t)) out.add(t);
        return out;
    }

    public boolean running() {
        return http != null;
    }

    public void start(String bind, int port, String token, Predicate<InetAddress> allowed) throws IOException {
        http = HttpServer.create(new InetSocketAddress(InetAddress.getByName(bind), port), 16);
        AtomicInteger n = new AtomicInteger();
        pool = Executors.newCachedThreadPool(r -> {
            Thread t = new Thread(r, "mcmcp-http-" + n.incrementAndGet());
            t.setDaemon(true);
            return t;
        });
        http.setExecutor(pool);
        byte[] tokenBytes = token == null || token.isEmpty() ? null : token.getBytes(StandardCharsets.UTF_8);
        http.createContext("/", ex -> {
            try {
                handle(ex, tokenBytes, allowed);
            } catch (Throwable t) {
                LOG.warn("MCP request failed", t);
                try { send(ex, 500, "text/plain", "internal error"); } catch (IOException ignored) {}
            } finally {
                ex.close();
            }
        });
        http.start();
        LOG.info("MCP server listening on http://{}:{}/mcp{}", bind, port, tokenBytes != null ? " (bearer token required)" : "");
    }

    public void stop() {
        if (http != null) {
            http.stop(0);
            http = null;
        }
        if (pool != null) {
            pool.shutdownNow();
            pool = null;
        }
    }

    private void handle(HttpExchange ex, byte[] token, Predicate<InetAddress> allowed) throws IOException {
        InetAddress remote = ex.getRemoteAddress().getAddress();
        if (!allowed.test(remote)) {
            send(ex, 403, "text/plain", "forbidden");
            return;
        }
        // DNS-rebinding guard: a browser page on another site must not reach us.
        String origin = ex.getRequestHeaders().getFirst("Origin");
        if (origin != null && !origin.matches("https?://(localhost|127\\.0\\.0\\.1|\\[::1\\])(:\\d+)?/?")) {
            send(ex, 403, "text/plain", "origin not allowed");
            return;
        }
        if (token != null) {
            String auth = ex.getRequestHeaders().getFirst("Authorization");
            byte[] given = auth != null && auth.startsWith("Bearer ")
                    ? auth.substring(7).trim().getBytes(StandardCharsets.UTF_8) : new byte[0];
            if (!MessageDigest.isEqual(token, given)) {
                ex.getResponseHeaders().add("WWW-Authenticate", "Bearer");
                send(ex, 401, "text/plain", "unauthorized");
                return;
            }
        }
        switch (ex.getRequestMethod()) {
            case "POST" -> post(ex);
            case "DELETE" -> send(ex, 200, "text/plain", "");
            case "GET" -> {
                if (ex.getRequestURI().getPath().equals("/health")) send(ex, 200, "text/plain", "ok");
                else send(ex, 405, "text/plain", "no SSE stream; POST JSON-RPC to /mcp");
            }
            default -> send(ex, 405, "text/plain", "method not allowed");
        }
    }

    private void post(HttpExchange ex) throws IOException {
        JsonElement body;
        try (InputStream in = ex.getRequestBody()) {
            body = JsonParser.parseString(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        } catch (Exception e) {
            send(ex, 400, "application/json", GSON.toJson(error(JsonNull.INSTANCE, -32700, "parse error")));
            return;
        }
        String[] session = {null};
        JsonElement out;
        if (body.isJsonArray()) {
            JsonArray replies = new JsonArray();
            for (JsonElement e : body.getAsJsonArray()) {
                JsonObject r = dispatch(e, session);
                if (r != null) replies.add(r);
            }
            out = replies.isEmpty() ? null : replies;
        } else {
            out = dispatch(body, session);
        }
        if (session[0] != null) ex.getResponseHeaders().add("Mcp-Session-Id", session[0]);
        if (out == null) {
            ex.sendResponseHeaders(202, -1);
            return;
        }
        send(ex, 200, "application/json", GSON.toJson(out));
    }

    private JsonObject dispatch(JsonElement e, String[] session) {
        if (!e.isJsonObject()) return error(JsonNull.INSTANCE, -32600, "invalid request");
        JsonObject req = e.getAsJsonObject();
        JsonElement id = req.get("id");
        String method = req.has("method") ? req.get("method").getAsString() : null;
        if (id == null || method == null) return null; // notification or a response to us: nothing to say
        JsonObject params = req.has("params") && req.get("params").isJsonObject() ? req.getAsJsonObject("params") : new JsonObject();
        try {
            return switch (method) {
                case "initialize" -> {
                    session[0] = UUID.randomUUID().toString();
                    String asked = params.has("protocolVersion") ? params.get("protocolVersion").getAsString() : DEFAULT_VERSION;
                    JsonObject r = new JsonObject();
                    r.addProperty("protocolVersion", KNOWN_VERSIONS.contains(asked) ? asked : DEFAULT_VERSION);
                    JsonObject caps = new JsonObject();
                    JsonObject toolCaps = new JsonObject();
                    toolCaps.addProperty("listChanged", false); // clients re-list on reconnect; disabled tools also refuse calls
                    caps.add("tools", toolCaps);
                    r.add("capabilities", caps);
                    JsonObject info = new JsonObject();
                    info.addProperty("name", name);
                    info.addProperty("version", version);
                    r.add("serverInfo", info);
                    r.addProperty("instructions", instructions);
                    yield result(id, r);
                }
                case "ping" -> result(id, new JsonObject());
                case "tools/list" -> {
                    JsonArray list = new JsonArray();
                    for (Tool t : tools()) {
                        JsonObject o = new JsonObject();
                        o.addProperty("name", t.name());
                        o.addProperty("description", t.description());
                        o.add("inputSchema", t.inputSchema());
                        JsonObject ann = new JsonObject();
                        ann.addProperty("readOnlyHint", t.readOnly());
                        o.add("annotations", ann);
                        list.add(o);
                    }
                    JsonObject r = new JsonObject();
                    r.add("tools", list);
                    yield result(id, r);
                }
                case "tools/call" -> result(id, callTool(params));
                case "resources/list" -> result(id, single("resources", new JsonArray()));
                case "resources/templates/list" -> result(id, single("resourceTemplates", new JsonArray()));
                case "prompts/list" -> result(id, single("prompts", new JsonArray()));
                default -> error(id, -32601, "method not found: " + method);
            };
        } catch (Exception ex) {
            return error(id, -32603, String.valueOf(ex.getMessage()));
        }
    }

    private JsonObject callTool(JsonObject params) {
        String toolName = params.has("name") ? params.get("name").getAsString() : "";
        JsonObject args = params.has("arguments") && params.get("arguments").isJsonObject() ? params.getAsJsonObject("arguments") : new JsonObject();
        Tool tool;
        synchronized (this) { tool = tools.get(toolName); }
        if (tool == null) return toolResult("unknown tool: " + toolName, true);
        if (!gate.test(tool)) return toolResult(toolName + " is disabled in config/mcmcp-common.toml ([features] actions / actionsCommands); the change applies without a restart", true);
        try {
            Object value = tool.handler().call(args);
            String text = value instanceof String s ? s : GSON.toJson(value);
            return toolResult(text, false);
        } catch (ToolError err) {
            return toolResult(err.getMessage(), true);
        } catch (Throwable t) {
            LOG.warn("Tool {} failed", toolName, t);
            return toolResult(t.getClass().getSimpleName() + ": " + t.getMessage(), true);
        }
    }

    private static JsonObject toolResult(String text, boolean isError) {
        JsonObject c = new JsonObject();
        c.addProperty("type", "text");
        c.addProperty("text", text);
        JsonArray content = new JsonArray();
        content.add(c);
        JsonObject r = new JsonObject();
        r.add("content", content);
        r.addProperty("isError", isError);
        return r;
    }

    private static JsonObject single(String key, JsonElement value) {
        JsonObject o = new JsonObject();
        o.add(key, value);
        return o;
    }

    private static JsonObject result(JsonElement id, JsonObject result) {
        JsonObject o = new JsonObject();
        o.addProperty("jsonrpc", "2.0");
        o.add("id", id);
        o.add("result", result);
        return o;
    }

    private static JsonObject error(JsonElement id, int code, String message) {
        JsonObject err = new JsonObject();
        err.addProperty("code", code);
        err.addProperty("message", message);
        JsonObject o = new JsonObject();
        o.addProperty("jsonrpc", "2.0");
        o.add("id", id);
        o.add("error", err);
        return o;
    }

    private static void send(HttpExchange ex, int status, String type, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", type + "; charset=utf-8");
        ex.sendResponseHeaders(status, bytes.length == 0 ? -1 : bytes.length);
        if (bytes.length > 0) {
            try (OutputStream os = ex.getResponseBody()) {
                os.write(bytes);
            }
        }
    }
}
