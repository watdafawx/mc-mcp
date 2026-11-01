package dev.mtop.mcmcp.mcp;

import java.util.LinkedHashMap;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

/** Small helpers for building tool results and reading tool arguments. */
public final class J {
    private J() {}

    /** Ordered map from alternating key/value pairs. */
    public static Map<String, Object> obj(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    public static double r2(double v) {
        return Double.isFinite(v) ? Math.round(v * 100.0) / 100.0 : v;
    }

    public static double r1(double v) {
        return Double.isFinite(v) ? Math.round(v * 10.0) / 10.0 : v;
    }

    public static String str(JsonObject a, String k, String def) {
        JsonElement e = a.get(k);
        return e == null || e.isJsonNull() ? def : e.getAsString();
    }

    public static int i(JsonObject a, String k, int def) {
        JsonElement e = a.get(k);
        return e == null || e.isJsonNull() ? def : e.getAsInt();
    }

    public static double d(JsonObject a, String k, double def) {
        JsonElement e = a.get(k);
        return e == null || e.isJsonNull() ? def : e.getAsDouble();
    }

    public static boolean b(JsonObject a, String k, boolean def) {
        JsonElement e = a.get(k);
        return e == null || e.isJsonNull() ? def : e.getAsBoolean();
    }

    public static String req(JsonObject a, String k) {
        JsonElement e = a.get(k);
        if (e == null || e.isJsonNull()) throw new McpServer.ToolError("missing argument: " + k);
        return e.getAsString();
    }

    /** JSON-schema builder for tool inputs. */
    public static final class Schema {
        private final JsonObject props = new JsonObject();
        private final JsonArray required = new JsonArray();

        public static Schema of() { return new Schema(); }

        private Schema prop(String name, String type, String desc) {
            JsonObject p = new JsonObject();
            p.addProperty("type", type);
            p.addProperty("description", desc);
            props.add(name, p);
            return this;
        }

        public Schema str(String name, String desc) { return prop(name, "string", desc); }
        public Schema num(String name, String desc) { return prop(name, "number", desc); }
        public Schema integer(String name, String desc) { return prop(name, "integer", desc); }
        public Schema bool(String name, String desc) { return prop(name, "boolean", desc); }

        public Schema anyValue(String name, String desc) {
            JsonObject p = new JsonObject();
            p.addProperty("description", desc);
            props.add(name, p);
            return this;
        }

        public Schema enumOf(String name, String desc, String... values) {
            prop(name, "string", desc);
            JsonArray arr = new JsonArray();
            for (String v : values) arr.add(v);
            props.getAsJsonObject(name).add("enum", arr);
            return this;
        }

        public Schema required(String... names) {
            for (String n : names) required.add(n);
            return this;
        }

        public JsonObject build() {
            JsonObject o = new JsonObject();
            o.addProperty("type", "object");
            o.add("properties", props);
            if (!required.isEmpty()) o.add("required", required);
            return o;
        }
    }
}
