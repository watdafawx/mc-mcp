package dev.watdafawx.mcmcp.ghost;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.brigadier.exceptions.CommandSyntaxException;

import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.fml.loading.FMLPaths;

import dev.watdafawx.mcmcp.McMcp;
import dev.watdafawx.mcmcp.mcp.McpServer;

/** All ghost layers of this client, persisted under {@code <gameDir>/mcmcp/ghosts/}. */
public final class GhostStore {
    public static final Object LOCK = new Object();
    private static final Map<String, Ghost> GHOSTS = new LinkedHashMap<>();
    private static final int MAX_BLOCKS = 2_000_000;
    private static boolean loaded;

    private GhostStore() {}

    public static Path dir() {
        return FMLPaths.GAMEDIR.get().resolve("mcmcp").resolve("ghosts");
    }

    /** Snapshot of the layers (callers still lock to read blocks). */
    public static List<Ghost> all() {
        synchronized (LOCK) {
            loadOnce();
            return new ArrayList<>(GHOSTS.values());
        }
    }

    public static Ghost get(String id) {
        synchronized (LOCK) {
            loadOnce();
            Ghost g = GHOSTS.get(id);
            if (g == null) throw new McpServer.ToolError("no ghost '" + id + "'. ghost_list shows the ids");
            return g;
        }
    }

    public static Ghost getOrCreate(String id, BlockPos origin, String dim) {
        synchronized (LOCK) {
            loadOnce();
            return GHOSTS.computeIfAbsent(id, k -> new Ghost(k, origin, dim));
        }
    }

    public static boolean remove(String id) {
        synchronized (LOCK) {
            loadOnce();
            boolean had = GHOSTS.remove(id) != null;
            try {
                Files.deleteIfExists(file(id));
            } catch (IOException e) {
                McMcp.LOG.warn("could not delete ghost file {}", id, e);
            }
            return had;
        }
    }

    // ------------------------------------------------------------------ parsing

    /** Parses a block state like {@code minecraft:oak_stairs[facing=north]}; throws with a readable reason. */
    public static BlockState parseState(String s) {
        try {
            return BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(), s.trim(), false).blockState();
        } catch (CommandSyntaxException e) {
            throw new IllegalArgumentException(e.getMessage());
        }
    }

    public static String serialize(BlockState s) {
        return BlockStateParser.serialize(s);
    }

    /**
     * Applies a spec to a ghost: palette (key to block state), boxes, then single blocks.
     * Unknown blocks are skipped and reported, never fatal, so one bad id doesn't lose a whole room.
     */
    public static Map<String, Object> apply(Ghost g, JsonObject spec, boolean replace) {
        Map<String, BlockState> palette = new HashMap<>();
        Map<String, String> errors = new LinkedHashMap<>();
        JsonObject pal = spec.has("palette") ? spec.getAsJsonObject("palette") : new JsonObject();
        for (var e : pal.entrySet()) {
            try {
                palette.put(e.getKey(), parseState(e.getValue().getAsString()));
            } catch (IllegalArgumentException ex) {
                errors.put(e.getKey(), e.getValue().getAsString() + ": " + ex.getMessage());
            }
        }
        int boxes = 0, singles = 0, skipped = 0;
        Set<String> missingKeys = new LinkedHashSet<>();
        synchronized (LOCK) {
            if (replace) g.blocks.clear();
            if (spec.has("boxes")) for (JsonElement el : spec.getAsJsonArray("boxes")) {
                JsonArray b = el.getAsJsonArray();
                if (b.size() < 7) throw new McpServer.ToolError("box needs [x1,y1,z1,x2,y2,z2,key(,mode)]: " + b);
                String key = b.get(6).getAsString();
                BlockState st = resolve(key, palette, errors, missingKeys);
                if (st == null) { skipped++; continue; }
                String mode = b.size() > 7 ? b.get(7).getAsString() : "fill";
                box(g, b.get(0).getAsInt(), b.get(1).getAsInt(), b.get(2).getAsInt(),
                        b.get(3).getAsInt(), b.get(4).getAsInt(), b.get(5).getAsInt(), st, mode);
                boxes++;
                if (g.blocks.size() > MAX_BLOCKS) throw new McpServer.ToolError("ghost over " + MAX_BLOCKS + " blocks");
            }
            if (spec.has("blocks")) for (JsonElement el : spec.getAsJsonArray("blocks")) {
                JsonArray b = el.getAsJsonArray();
                BlockState st = resolve(b.get(3).getAsString(), palette, errors, missingKeys);
                if (st == null) { skipped++; continue; }
                g.put(b.get(0).getAsInt(), b.get(1).getAsInt(), b.get(2).getAsInt(), st);
                singles++;
            }
            if (g.blocks.size() > MAX_BLOCKS) throw new McpServer.ToolError("ghost over " + MAX_BLOCKS + " blocks");
            g.version++;
        }
        save(g);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", g.id);
        out.put("boxes", boxes);
        out.put("blocks_set", singles);
        out.put("total_blocks", g.blocks.size());
        if (skipped > 0) out.put("skipped", skipped);
        if (!errors.isEmpty()) out.put("bad_palette", errors);
        if (!missingKeys.isEmpty()) out.put("unknown_keys", missingKeys);
        return out;
    }

    private static BlockState resolve(String key, Map<String, BlockState> palette, Map<String, String> errors, Set<String> missing) {
        BlockState st = palette.get(key);
        if (st != null) return st;
        if (errors.containsKey(key)) return null;
        // A key that isn't in the palette may be a block id itself ("minecraft:stone").
        if (key.contains(":")) {
            try {
                st = parseState(key);
                palette.put(key, st);
                return st;
            } catch (IllegalArgumentException ex) {
                errors.put(key, ex.getMessage());
                return null;
            }
        }
        missing.add(key);
        return null;
    }

    /** mode: fill | hollow (6 faces) | walls (4 sides, no top/bottom) | frame (12 edges). Air removes. */
    static void box(Ghost g, int x1, int y1, int z1, int x2, int y2, int z2, BlockState st, String mode) {
        int ax = Math.min(x1, x2), bx = Math.max(x1, x2);
        int ay = Math.min(y1, y2), by = Math.max(y1, y2);
        int az = Math.min(z1, z2), bz = Math.max(z1, z2);
        long vol = (long) (bx - ax + 1) * (by - ay + 1) * (bz - az + 1);
        if (vol > MAX_BLOCKS) throw new McpServer.ToolError("box too big: " + vol + " blocks");
        for (int x = ax; x <= bx; x++) for (int y = ay; y <= by; y++) for (int z = az; z <= bz; z++) {
            boolean ex = x == ax || x == bx, ey = y == ay || y == by, ez = z == az || z == bz;
            int edges = (ex ? 1 : 0) + (ey ? 1 : 0) + (ez ? 1 : 0);
            boolean on = switch (mode) {
                case "hollow" -> edges >= 1;
                case "walls" -> ex || ez;
                case "frame" -> edges >= 2;
                default -> true;
            };
            if (on) g.put(x, y, z, st);
        }
    }

    // ------------------------------------------------------------------ persistence

    private static Path file(String id) {
        return dir().resolve(id.replaceAll("[^A-Za-z0-9._-]", "_") + ".json");
    }

    public static void save(Ghost g) {
        JsonObject o;
        synchronized (LOCK) {
            o = new JsonObject();
            o.addProperty("id", g.id);
            JsonArray origin = new JsonArray();
            origin.add(g.origin.getX()); origin.add(g.origin.getY()); origin.add(g.origin.getZ());
            o.add("origin", origin);
            o.addProperty("dimension", g.dimension);
            o.addProperty("visible", g.visible);
            o.addProperty("alpha", g.alpha);
            JsonObject tags = new JsonObject();
            g.tags.forEach(tags::addProperty);
            o.add("tags", tags);
            Map<BlockState, Integer> idx = new LinkedHashMap<>();
            JsonArray pal = new JsonArray();
            JsonArray flat = new JsonArray();
            for (var e : g.blocks.long2ObjectEntrySet()) {
                Integer i = idx.get(e.getValue());
                if (i == null) {
                    i = idx.size();
                    idx.put(e.getValue(), i);
                    pal.add(serialize(e.getValue()));
                }
                long k = e.getLongKey();
                flat.add(BlockPos.getX(k)); flat.add(BlockPos.getY(k)); flat.add(BlockPos.getZ(k)); flat.add(i);
            }
            o.add("palette", pal);
            o.add("blocks", flat);
        }
        try {
            Files.createDirectories(dir());
            Files.writeString(file(g.id), o.toString(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            McMcp.LOG.warn("could not save ghost {}", g.id, e);
        }
    }

    private static void loadOnce() {
        if (loaded) return;
        loaded = true;
        if (!Files.isDirectory(dir())) return;
        try (var files = Files.list(dir())) {
            for (Path p : files.filter(f -> f.toString().endsWith(".json")).toList()) {
                try {
                    JsonObject o = JsonParser.parseString(Files.readString(p, StandardCharsets.UTF_8)).getAsJsonObject();
                    JsonArray or = o.getAsJsonArray("origin");
                    Ghost g = new Ghost(o.get("id").getAsString(),
                            new BlockPos(or.get(0).getAsInt(), or.get(1).getAsInt(), or.get(2).getAsInt()),
                            o.get("dimension").getAsString());
                    g.visible = o.get("visible").getAsBoolean();
                    g.alpha = o.get("alpha").getAsFloat();
                    for (var t : o.getAsJsonObject("tags").entrySet()) g.tags.put(t.getKey(), t.getValue().getAsString());
                    List<BlockState> pal = new ArrayList<>();
                    for (JsonElement s : o.getAsJsonArray("palette")) {
                        BlockState st;
                        try {
                            st = parseState(s.getAsString());
                        } catch (IllegalArgumentException ex) {
                            st = Blocks.AIR.defaultBlockState(); // mod removed since; drop those blocks
                        }
                        pal.add(st);
                    }
                    JsonArray flat = o.getAsJsonArray("blocks");
                    for (int i = 0; i + 3 < flat.size(); i += 4)
                        g.put(flat.get(i).getAsInt(), flat.get(i + 1).getAsInt(), flat.get(i + 2).getAsInt(), pal.get(flat.get(i + 3).getAsInt()));
                    g.version = 1;
                    GHOSTS.put(g.id, g);
                } catch (Exception e) {
                    McMcp.LOG.warn("could not load ghost {}", p, e);
                }
            }
        } catch (IOException e) {
            McMcp.LOG.warn("could not list ghosts", e);
        }
    }
}
