package dev.watdafawx.mcmcp.actions;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import com.electronwill.nightconfig.core.UnmodifiableConfig;
import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;

import net.neoforged.fml.config.ConfigTracker;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.neoforge.common.ModConfigSpec;

import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;

/** Lists and changes NeoForge ({@link ModConfigSpec}) config values of any loaded mod. */
public final class ModConfigs {
    private ModConfigs() {}

    @SuppressWarnings("unchecked")
    static List<ModConfig> configs(String modId) {
        try {
            Field f = ConfigTracker.class.getDeclaredField("configsByMod");
            f.setAccessible(true);
            Map<String, List<ModConfig>> byMod = (Map<String, List<ModConfig>>) f.get(ConfigTracker.INSTANCE);
            List<ModConfig> l = byMod.get(modId);
            return l == null ? List.of() : new ArrayList<>(l);
        } catch (Exception e) {
            throw new McpServer.ToolError("cannot read NeoForge's config list: " + e);
        }
    }

    public static Object list(String modId, String filter, int limit) {
        List<ModConfig> cfgs = configs(modId);
        if (cfgs.isEmpty()) throw new McpServer.ToolError("no NeoForge configs registered by mod '" + modId + "' (it may use its own config format)");
        String f = filter == null ? "" : filter.toLowerCase(Locale.ROOT);
        List<Object> files = new ArrayList<>();
        for (ModConfig mc : cfgs) {
            List<Object> values = new ArrayList<>();
            if (mc.getSpec() instanceof ModConfigSpec spec && mc.getLoadedConfig() != null) {
                walk(spec.getValues(), values, f, limit);
            }
            files.add(J.obj("file", mc.getFileName(), "type", mc.getType().name(), "loaded", mc.getLoadedConfig() != null, "values", values));
        }
        return J.obj("mod", modId, "configs", files);
    }

    private static void walk(UnmodifiableConfig cfg, List<Object> out, String f, int limit) {
        for (UnmodifiableConfig.Entry e : cfg.entrySet()) {
            if (out.size() >= limit) return;
            Object v = e.getValue();
            if (v instanceof UnmodifiableConfig sub) {
                walk(sub, out, f, limit);
            } else if (v instanceof ModConfigSpec.ConfigValue<?> cv) {
                String path = String.join(".", cv.getPath());
                if (!f.isEmpty() && !path.toLowerCase(Locale.ROOT).contains(f)) continue;
                Object cur;
                try { cur = cv.get(); } catch (Exception ex) { cur = "?"; }
                String comment = cv.getSpec() == null || cv.getSpec().getComment() == null ? "" : cv.getSpec().getComment().split("\n")[0];
                out.add(J.obj("path", path, "value", String.valueOf(cur), "default", String.valueOf(cv.getDefault()), "comment", comment));
            }
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    public static Object set(String modId, String path, JsonElement raw) {
        for (ModConfig mc : configs(modId)) {
            if (!(mc.getSpec() instanceof ModConfigSpec spec) || mc.getLoadedConfig() == null) continue;
            Object found = spec.getValues().get(path);
            if (!(found instanceof ModConfigSpec.ConfigValue<?> cv)) continue;
            Object old = cv.get();
            Object value = convert(old, cv.getDefault(), raw);
            ModConfigSpec.ValueSpec vs = cv.getSpec();
            if (vs != null && !vs.test(value))
                throw new McpServer.ToolError("value " + value + " rejected by the config's own validation" + (vs.getRange() != null ? " (range " + vs.getRange() + ")" : ""));
            ((ModConfigSpec.ConfigValue) cv).set(value);
            spec.save(); // writes the file and fires the mod's reload event
            return J.obj("mod", modId, "file", mc.getFileName(), "path", path, "old", String.valueOf(old), "new", String.valueOf(value),
                    "restart", vs == null ? "?" : vs.restartType().name(),
                    "note", "saved; mods reading the value live or on reload see it now. restart=WORLD/GAME means it applies only after that.");
        }
        throw new McpServer.ToolError("no value '" + path + "' in " + modId + "'s NeoForge configs (see config_list)");
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static Object convert(Object current, Object def, JsonElement raw) {
        Object ref = current != null ? current : def;
        String s = raw.isJsonPrimitive() ? raw.getAsString() : raw.toString();
        if (ref instanceof Boolean) {
            if (!s.equalsIgnoreCase("true") && !s.equalsIgnoreCase("false")) throw new McpServer.ToolError("expected true/false");
            return Boolean.parseBoolean(s);
        }
        if (ref instanceof Integer) return Integer.parseInt(s.trim());
        if (ref instanceof Long) return Long.parseLong(s.trim());
        if (ref instanceof Double) return Double.parseDouble(s.trim());
        if (ref instanceof Enum<?> en) {
            for (Object c : en.getDeclaringClass().getEnumConstants())
                if (((Enum<?>) c).name().equalsIgnoreCase(s.trim())) return c;
            throw new McpServer.ToolError("expected one of " + java.util.Arrays.toString(en.getDeclaringClass().getEnumConstants()));
        }
        if (ref instanceof Collection<?>) {
            if (!raw.isJsonArray()) throw new McpServer.ToolError("expected a JSON array");
            List<Object> l = new ArrayList<>();
            for (JsonElement e : raw.getAsJsonArray()) l.add(e instanceof JsonPrimitive p && p.isNumber() ? p.getAsNumber() : e.getAsString());
            return l;
        }
        return s;
    }
}
