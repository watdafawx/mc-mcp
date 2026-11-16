package dev.watdafawx.mcmcp.ghost;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.neoforged.fml.loading.FMLPaths;

import dev.watdafawx.mcmcp.GameThread;
import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;

/**
 * Ghost builds: see-through block layouts drawn only on this client (the world is never changed), iterated in place
 * and exported as schematics. Plus block registry lookups so a designer only uses blocks that exist in this pack.
 */
public final class GhostTools {
    private GhostTools() {}

    private static final String SPEC_HELP = """
            Spec: palette {key: block state, e.g. "W":"minecraft:stone_bricks", "S":"minecraft:oak_stairs[facing=north,half=top]"}; \
            boxes [[x1,y1,z1,x2,y2,z2,key,mode?]] (inclusive, mode fill|hollow|walls|frame, default fill); \
            blocks [[x,y,z,key]]. Coordinates are local to the ghost origin. A key may also be a block id directly. \
            A palette value of minecraft:air erases. Boxes apply first, then blocks, in order (later wins).""";

    public static void register(McpServer mcp) {
        mcp.add(new Tool("ghost_set",
                "Create or change a ghost build: see-through blocks drawn only on this client, never placed in the world. "
                        + "mode=replace (default) redraws the ghost from the spec; mode=merge edits it in place (use for iterations). "
                        + SPEC_HELP + " Pass the spec inline or as `file` (path to a JSON file with the same keys). "
                        + "origin [x,y,z] world position of local 0,0,0 (default: kept, or the player's feet for a new ghost). "
                        + "Returns counts and any palette entries that are not valid blocks in this pack.",
                J.Schema.of().str("id", "ghost id, e.g. 'trinity' or 'hall/server_room'")
                        .enumOf("mode", "replace | merge", "replace", "merge")
                        .anyValue("origin", "[x,y,z] world position")
                        .anyValue("palette", "object key -> block state string")
                        .anyValue("boxes", "array of [x1,y1,z1,x2,y2,z2,key,mode?]")
                        .anyValue("blocks", "array of [x,y,z,key]")
                        .str("file", "JSON file with palette/boxes/blocks (absolute or relative to the game dir)")
                        .anyValue("tags", "object of string labels, e.g. {theme:'quantum lab', room:'core'}")
                        .required("id").build(),
                false, a -> {
                    JsonObject spec = a;
                    String file = J.str(a, "file", null);
                    if (file != null) {
                        Path p = FMLPaths.GAMEDIR.get().resolve(file);
                        spec = JsonParser.parseString(Files.readString(p, StandardCharsets.UTF_8)).getAsJsonObject();
                    }
                    String id = J.req(a, "id");
                    BlockPos origin = a.has("origin") ? pos(a.getAsJsonArray("origin")) : spec.has("origin") ? pos(spec.getAsJsonArray("origin")) : null;
                    BlockPos start = origin != null ? origin : GameThread.call(Minecraft.getInstance(), () -> {
                        var p = Minecraft.getInstance().player;
                        if (p == null) throw new McpServer.ToolError("no player in a world; pass origin");
                        return p.blockPosition();
                    });
                    String dim = GameThread.call(Minecraft.getInstance(), () -> {
                        var l = Minecraft.getInstance().level;
                        if (l == null) throw new McpServer.ToolError("no world loaded");
                        return l.dimension().location().toString();
                    });
                    Ghost g = GhostStore.getOrCreate(id, start, dim);
                    synchronized (GhostStore.LOCK) {
                        if (origin != null) g.origin = origin;
                        JsonElement tags = a.has("tags") ? a.get("tags") : spec.get("tags");
                        if (tags != null && tags.isJsonObject())
                            for (var t : tags.getAsJsonObject().entrySet()) g.tags.put(t.getKey(), t.getValue().getAsString());
                    }
                    boolean replace = !"merge".equals(J.str(a, "mode", "replace"));
                    Map<String, Object> out = GhostStore.apply(g, spec, replace);
                    out.put("origin", List.of(g.origin.getX(), g.origin.getY(), g.origin.getZ()));
                    int[] b;
                    synchronized (GhostStore.LOCK) { b = g.bounds(); }
                    if (b != null) out.put("size", List.of(b[3] - b[0] + 1, b[4] - b[1] + 1, b[5] - b[2] + 1));
                    return out;
                }));

        mcp.add(new Tool("ghost_list",
                "All ghost builds: id, origin, dimension, size, block count, visible, tags.",
                J.Schema.of().build(), true, a -> {
                    List<Object> out = new ArrayList<>();
                    for (Ghost g : GhostStore.all()) out.add(summary(g));
                    return J.obj("count", out.size(), "ghosts", out);
                }));

        mcp.add(new Tool("ghost_info",
                "One ghost in detail: bounds (local and world), palette with counts per block state.",
                J.Schema.of().str("id", "ghost id").required("id").build(), true, a -> {
                    Ghost g = GhostStore.get(J.req(a, "id"));
                    Map<String, Object> m = summary(g);
                    Map<String, Integer> counts = new TreeMap<>();
                    synchronized (GhostStore.LOCK) {
                        for (BlockState s : g.blocks.values()) counts.merge(GhostStore.serialize(s), 1, Integer::sum);
                    }
                    m.put("palette", counts);
                    return m;
                }));

        mcp.add(new Tool("ghost_move",
                "Move and/or rotate a ghost. origin [x,y,z] sets the world position; offset [dx,dy,dz] shifts it; "
                        + "rotate 90/180/270 turns it clockwise around local 0,0,0 (stairs, logs etc. turn with it).",
                J.Schema.of().str("id", "ghost id").anyValue("origin", "[x,y,z]").anyValue("offset", "[dx,dy,dz]")
                        .integer("rotate", "0, 90, 180 or 270").required("id").build(), false, a -> {
                    Ghost g = GhostStore.get(J.req(a, "id"));
                    synchronized (GhostStore.LOCK) {
                        if (a.has("origin")) g.origin = pos(a.getAsJsonArray("origin"));
                        if (a.has("offset")) g.origin = g.origin.offset(pos(a.getAsJsonArray("offset")));
                        g.rotate(switch (J.i(a, "rotate", 0)) {
                            case 90 -> Rotation.CLOCKWISE_90;
                            case 180 -> Rotation.CLOCKWISE_180;
                            case 270 -> Rotation.COUNTERCLOCKWISE_90;
                            default -> Rotation.NONE;
                        });
                        g.version++;
                    }
                    GhostStore.save(g);
                    return summary(g);
                }));

        mcp.add(new Tool("ghost_show",
                "Show or hide ghosts and set their opacity. id: one ghost, or '*' for all. "
                        + "Global view modes (all ghosts): xray=true draws ghosts over terrain so hills and trees can't hide them; "
                        + "solid=true draws them fully opaque (good for screenshots).",
                J.Schema.of().str("id", "ghost id or *").bool("visible", "show (true) or hide").num("alpha", "0.1..1, default 0.55")
                        .bool("xray", "global: draw over terrain").bool("solid", "global: fully opaque")
                        .bool("hud", "global: false hides the HUD (like F1) for clean screenshots")
                        .required("id").build(), false, a -> {
                    if (a.has("xray")) GhostRenderer.xray = J.b(a, "xray", false);
                    if (a.has("solid")) GhostRenderer.solid = J.b(a, "solid", false);
                    if (a.has("hud")) net.minecraft.client.Minecraft.getInstance().options.hideGui = !J.b(a, "hud", true);
                    String id = J.req(a, "id");
                    List<Ghost> gs = id.equals("*") ? GhostStore.all() : List.of(GhostStore.get(id));
                    for (Ghost g : gs) {
                        synchronized (GhostStore.LOCK) {
                            if (a.has("visible")) g.visible = J.b(a, "visible", true);
                            if (a.has("alpha")) g.alpha = (float) Math.max(0.1, Math.min(1, J.d(a, "alpha", 0.55)));
                        }
                        GhostStore.save(g);
                    }
                    return J.obj("changed", gs.size(), "xray", GhostRenderer.xray, "solid", GhostRenderer.solid);
                }));

        mcp.add(new Tool("ghost_clear",
                "Delete ghosts. id: one ghost, a prefix ending in '/' (e.g. 'base/' removes all rooms of that area), or '*'.",
                J.Schema.of().str("id", "ghost id, prefix/ or *").required("id").build(), false, a -> {
                    String id = J.req(a, "id");
                    List<String> gone = new ArrayList<>();
                    for (Ghost g : GhostStore.all())
                        if (id.equals("*") || g.id.equals(id) || (id.endsWith("/") && g.id.startsWith(id)))
                            if (GhostStore.remove(g.id)) gone.add(g.id);
                    return J.obj("removed", gone);
                }));

        mcp.add(new Tool("ghost_export",
                "Save ghosts as a schematic. ids: one id, a prefix ending in '/', or '*', or an array; several ghosts are merged "
                        + "at their world positions (later ids win on overlap). format litematic (default, Litematica), schem "
                        + "(Sponge v2: WorldEdit/Axiom) or nbt (vanilla structure). Saved to <gameDir>/schematics/<name>.<ext> unless `path` is set.",
                J.Schema.of().anyValue("ids", "id, prefix/, * or array of ids").str("name", "file and schematic name")
                        .enumOf("format", "litematic | schem | nbt", "litematic", "schem", "nbt")
                        .str("path", "output file (optional)").str("author", "author field").required("ids", "name").build(),
                false, a -> {
                    List<Ghost> gs = select(a.get("ids"));
                    if (gs.isEmpty()) throw new McpServer.ToolError("no ghosts match " + a.get("ids"));
                    Long2ObjectMap<BlockState> world = new Long2ObjectOpenHashMap<>();
                    synchronized (GhostStore.LOCK) {
                        for (Ghost g : gs)
                            for (var e : g.blocks.long2ObjectEntrySet())
                                world.put(BlockPos.of(e.getLongKey()).offset(g.origin).asLong(), e.getValue());
                    }
                    String format = J.str(a, "format", "litematic");
                    String name = J.req(a, "name").replaceAll("[^A-Za-z0-9._ -]", "_");
                    Path out = a.has("path") ? FMLPaths.GAMEDIR.get().resolve(J.str(a, "path", ""))
                            : FMLPaths.GAMEDIR.get().resolve("schematics").resolve(name + "." + format);
                    var r = SchematicWriter.write(world, format, name, J.str(a, "author", "mc-mcp"), out);
                    return J.obj("path", r.path().toAbsolutePath().toString(), "blocks", r.blocks(),
                            "size", List.of(r.size()[0], r.size()[1], r.size()[2]), "ghosts", gs.stream().map(g -> g.id).toList());
                }));

        mcp.add(new Tool("registry_blocks",
                "Blocks that exist in this pack. namespace: mod id (e.g. ae2, extendedae, advanced_ae, create); query: substring of the id. "
                        + "props=true adds each block's state properties and values. Use before designing so every block id is real.",
                J.Schema.of().str("namespace", "mod id filter").str("query", "substring filter, e.g. 'brick' or 'glass'")
                        .bool("props", "include state properties").integer("limit", "default 300").build(),
                true, a -> {
                    String ns = J.str(a, "namespace", null);
                    String q = J.str(a, "query", null);
                    boolean props = J.b(a, "props", false);
                    int limit = Math.max(1, Math.min(5000, J.i(a, "limit", 300)));
                    List<Object> out = new ArrayList<>();
                    int matched = 0;
                    Map<String, Integer> namespaces = new TreeMap<>();
                    for (Block b : BuiltInRegistries.BLOCK) {
                        ResourceLocation id = BuiltInRegistries.BLOCK.getKey(b);
                        namespaces.merge(id.getNamespace(), 1, Integer::sum);
                        if (ns != null && !id.getNamespace().equals(ns)) continue;
                        if (q != null && !id.toString().contains(q.toLowerCase(Locale.ROOT))) continue;
                        matched++;
                        if (out.size() >= limit) continue;
                        if (!props) { out.add(id.toString()); continue; }
                        out.add(J.obj("id", id.toString(), "props", properties(b)));
                    }
                    Map<String, Object> m = J.obj("matched", matched, "blocks", out);
                    if (ns == null && q == null) m.put("namespaces", namespaces);
                    if (matched > out.size()) m.put("truncated", true);
                    return m;
                }));

        mcp.add(new Tool("block_describe",
                "One block in detail: state properties and values, default state, whether it has a block entity, light level, "
                        + "full cube or not, and its translated name. Accepts a block id or a full block state string.",
                J.Schema.of().str("block", "e.g. ae2:controller or minecraft:oak_stairs[facing=east]").required("block").build(),
                true, a -> {
                    BlockState s;
                    try {
                        s = GhostStore.parseState(J.req(a, "block"));
                    } catch (IllegalArgumentException e) {
                        throw new McpServer.ToolError(e.getMessage());
                    }
                    Block b = s.getBlock();
                    return J.obj("id", BuiltInRegistries.BLOCK.getKey(b).toString(),
                            "name", b.getName().getString(),
                            "state", GhostStore.serialize(s),
                            "default", GhostStore.serialize(b.defaultBlockState()),
                            "props", properties(b),
                            "block_entity", s.hasBlockEntity(),
                            "light", s.getLightEmission(),
                            "render_shape", s.getRenderShape().name(),
                            "solid_full_cube", s.isSolidRender(net.minecraft.world.level.EmptyBlockGetter.INSTANCE, BlockPos.ZERO));
                }));
    }

    private static Map<String, List<String>> properties(Block b) {
        Map<String, List<String>> p = new LinkedHashMap<>();
        for (Property<?> prop : b.getStateDefinition().getProperties()) p.put(prop.getName(), values(prop));
        return p;
    }

    private static <T extends Comparable<T>> List<String> values(Property<T> prop) {
        List<String> v = new ArrayList<>();
        for (T t : prop.getPossibleValues()) v.add(prop.getName(t));
        return v;
    }

    private static List<Ghost> select(JsonElement ids) {
        List<Ghost> all = GhostStore.all();
        if (ids == null) return List.of();
        if (ids.isJsonArray()) {
            List<Ghost> out = new ArrayList<>();
            for (JsonElement e : ids.getAsJsonArray()) out.add(GhostStore.get(e.getAsString()));
            return out;
        }
        String id = ids.getAsString();
        if (id.equals("*")) return all;
        if (id.endsWith("/")) return all.stream().filter(g -> g.id.startsWith(id)).toList();
        return List.of(GhostStore.get(id));
    }

    private static Map<String, Object> summary(Ghost g) {
        synchronized (GhostStore.LOCK) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", g.id);
            m.put("origin", List.of(g.origin.getX(), g.origin.getY(), g.origin.getZ()));
            m.put("dimension", g.dimension);
            int[] b = g.bounds();
            if (b != null) {
                m.put("size", List.of(b[3] - b[0] + 1, b[4] - b[1] + 1, b[5] - b[2] + 1));
                m.put("local_min", List.of(b[0], b[1], b[2]));
                m.put("world_min", List.of(g.origin.getX() + b[0], g.origin.getY() + b[1], g.origin.getZ() + b[2]));
                m.put("world_max", List.of(g.origin.getX() + b[3], g.origin.getY() + b[4], g.origin.getZ() + b[5]));
            }
            m.put("blocks", g.blocks.size());
            m.put("visible", g.visible);
            m.put("alpha", g.alpha);
            if (!g.tags.isEmpty()) m.put("tags", g.tags);
            return m;
        }
    }

    private static BlockPos pos(JsonArray a) {
        if (a.size() != 3) throw new McpServer.ToolError("position must be [x,y,z]");
        return new BlockPos(a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt());
    }
}
