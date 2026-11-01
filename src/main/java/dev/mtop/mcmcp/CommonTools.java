package dev.mtop.mcmcp;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import java.util.function.Supplier;

import com.google.gson.JsonObject;

import net.minecraft.SharedConstants;
import net.minecraft.commands.CommandSource;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.fml.ModList;
import net.neoforged.fml.loading.FMLEnvironment;

import dev.mtop.mcmcp.actions.ModConfigs;
import dev.mtop.mcmcp.actions.Spots;
import dev.mtop.mcmcp.mcp.J;
import dev.mtop.mcmcp.mcp.McpServer;
import dev.mtop.mcmcp.mcp.McpServer.Tool;
import dev.mtop.mcmcp.metrics.GcMonitor;
import dev.mtop.mcmcp.metrics.MixinReport;
import dev.mtop.mcmcp.metrics.TickStats;
import dev.mtop.mcmcp.metrics.WorldState;
import dev.mtop.mcmcp.spark.SparkBridge;

/** Tools that work on both sides: JVM, mixins, mod configs, and anything needing a (possibly integrated) server. */
public final class CommonTools {
    private CommonTools() {}

    /** @param server current server, or null (client with no singleplayer world) */
    public static void register(McpServer mcp, Supplier<MinecraftServer> server, Supplier<ServerPlayer> defaultPlayer) {
        mcp.add(new Tool("jvm_state",
                "Heap, GC pauses (stop-the-world vs concurrent cycles) over a window, CPU, threads. details=true adds collectors, memory pools and JVM args.",
                J.Schema.of().integer("seconds", "GC window, default 60").bool("details", "include pools, collectors, JVM args").build(),
                true, a -> GcMonitor.snapshot(J.i(a, "seconds", 60), J.b(a, "details", false))));

        mcp.add(new Tool("tick_stats",
                "Server TPS and MSPT (avg, p95, max over the last 100 ticks), per dimension. In singleplayer this is the integrated server.",
                J.Schema.of().build(), true, a -> {
                    MinecraftServer s = need(server);
                    return GameThread.call(s, () -> TickStats.of(s));
                }));

        mcp.add(new Tool("server_world_state",
                "Server-side counts for each loaded dimension (or one): loaded chunks, entities by type, block entities by type, ticking block entities by type; plus view/simulation distance.",
                J.Schema.of().str("dimension", "e.g. minecraft:overworld; default all").integer("top", "rows per list, default 15").build(),
                true, a -> {
                    MinecraftServer s = need(server);
                    String dim = J.str(a, "dimension", null);
                    int top = J.i(a, "top", 15);
                    return GameThread.call(s, () -> {
                        List<Object> levels = new ArrayList<>();
                        for (ServerLevel l : s.getAllLevels()) {
                            if (dim != null && !l.dimension().location().toString().equals(dim)) continue;
                            Map<String, Object> m = WorldState.counts(l, l.getAllEntities(), WorldState.serverChunks(l), top);
                            m.put("loaded_chunks", l.getChunkSource().getLoadedChunksCount());
                            m.put("players", l.players().size());
                            levels.add(m);
                        }
                        return J.obj("view_distance", s.getPlayerList().getViewDistance(),
                                "simulation_distance", s.getPlayerList().getSimulationDistance(),
                                "levels", levels);
                    }, 20);
                }));

        if (Config.MIXIN_TOOLS.get())
            mcp.add(new Tool("mixins",
                    "Mixin configs and whether each mixin applied, is pending (target class not loaded yet) or was skipped. No args = totals + configs with skips first.",
                    J.Schema.of().str("filter", "mod id, config name or mixin class substring")
                            .enumOf("status", "only mixins with this status", "applied", "pending", "skipped", "all")
                            .integer("limit", "max rows, default 60").build(),
                    true, a -> MixinReport.report(J.str(a, "filter", null), J.str(a, "status", null),
                            FMLEnvironment.dist.isClient(), J.i(a, "limit", 60))));

        mcp.add(new Tool("config_list",
                "List a mod's NeoForge config values (path, value, default, first comment line). Only ModConfigSpec configs; mods with their own JSON/TOML formats are not covered.",
                J.Schema.of().str("mod", "mod id").str("filter", "path substring").integer("limit", "default 200").required("mod").build(),
                true, a -> ModConfigs.list(J.req(a, "mod"), J.str(a, "filter", null), J.i(a, "limit", 200))));

        mcp.add(new Tool("mods",
                "Installed mods (id, version), filtered by substring.",
                J.Schema.of().str("filter", "id or name substring").build(), true, a -> {
                    String f = J.str(a, "filter", "").toLowerCase(java.util.Locale.ROOT);
                    List<Object> out = new ArrayList<>();
                    for (var m : ModList.get().getMods())
                        if (f.isEmpty() || m.getModId().contains(f) || m.getDisplayName().toLowerCase(java.util.Locale.ROOT).contains(f))
                            out.add(m.getModId() + " " + m.getVersion());
                    return J.obj("count", out.size(), "mods", out.size() > 300 ? out.subList(0, 300) : out);
                }));

        mcp.setGate(CommonTools::enabled);

        mcp.add(new Tool("config_set",
                "[action] Change one NeoForge config value of a mod and save it (fires the mod's reload event). value: the new value (bool/number/string/enum name/array).",
                J.Schema.of().str("mod", "mod id").str("path", "dotted path from config_list").anyValue("value", "new value").required("mod", "path", "value").build(),
                false, a -> {
                    Callable c = () -> ModConfigs.set(J.req(a, "mod"), J.req(a, "path"), a.get("value"));
                    MinecraftServer s = server.get();
                    return s != null ? GameThread.call(s, c::run) : c.run();
                }));

        mcp.add(new Tool("spot_save",
                "[action] Save the player's current position as a named spot (config/mcmcp/spots.json).",
                J.Schema.of().str("name", "spot name").str("player", "player name (default: the local player)").required("name").build(),
                false, a -> {
                    MinecraftServer s = need(server);
                    return GameThread.call(s, () -> {
                        try {
                            return Spots.save(J.req(a, "name"), player(s, a, defaultPlayer));
                        } catch (java.io.IOException e) {
                            throw new RuntimeException(e);
                        }
                    });
                }));

        mcp.add(new Tool("spot_list", "Saved spots.", J.Schema.of().build(), true, a -> Spots.all()));

        mcp.add(new Tool("locate_structure",
                "Nearest structure of a type, like /locate structure: id ('minecraft:village_plains') or tag ('#minecraft:village'). Searches from near_x/near_z (default: the player), so pass points far apart to find different ones. Read-only, but the search runs on the server thread.",
                J.Schema.of().str("structure", "structure id or #tag").str("dimension", "default: the player's").integer("near_x", "search origin x").integer("near_z", "search origin z")
                        .str("player", "player name (default: the local player)").required("structure").build(),
                true, a -> {
                    MinecraftServer s = need(server);
                    return GameThread.call(s, () -> locate(s, a, defaultPlayer), 60);
                }));

        mcp.add(new Tool("teleport_to",
                "[action] Teleport a player to x/z (and y, default: the surface there, chunk generated if needed). Same dimension unless dimension is given.",
                J.Schema.of().integer("x", "block x").integer("z", "block z").integer("y", "block y; default surface")
                        .str("dimension", "e.g. minecraft:overworld").str("player", "player name (default: the local player)").required("x", "z").build(),
                false, a -> {
                    MinecraftServer s = need(server);
                    return GameThread.call(s, () -> {
                        ServerPlayer p = player(s, a, defaultPlayer);
                        ServerLevel level = level(s, a, p);
                        int x = J.i(a, "x", 0), z = J.i(a, "z", 0);
                        int y = a.has("y") ? J.i(a, "y", 64)
                                : level.getChunk(x >> 4, z >> 4).getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x & 15, z & 15) + 1;
                        p.teleportTo(level, x + 0.5, y, z + 0.5, p.getYRot(), p.getXRot());
                        return J.obj("teleported", p.getGameProfile().getName(), "dimension", level.dimension().location().toString(), "x", x, "y", y, "z", z,
                                "hint", "give chunks ~10 s to load and render before measuring");
                    }, 60);
                }));

        mcp.add(new Tool("teleport",
                "[action] Teleport a player to a saved spot (any dimension).",
                J.Schema.of().str("spot", "spot name").str("player", "player name (default: the local player)").required("spot").build(),
                false, a -> {
                    MinecraftServer s = need(server);
                    return GameThread.call(s, () -> Spots.teleport(s, player(s, a, defaultPlayer), J.req(a, "spot")));
                }));

        mcp.add(new Tool("run_command",
                    "[action] Run a server command (no slash) as the player at op level 4 (or as the server if no player) and return its output.",
                    J.Schema.of().str("command", "command without leading slash").str("player", "run as this player (default: the local player)").required("command").build(),
                    false, a -> {
                        MinecraftServer s = need(server);
                        List<String> out = Collections.synchronizedList(new ArrayList<>());
                        GameThread.call(s, () -> {
                            ServerPlayer p = null;
                            try { p = player(s, a, defaultPlayer); } catch (McpServer.ToolError ignored) {}
                            CommandSourceStack src = (p != null ? p.createCommandSourceStack() : s.createCommandSourceStack())
                                    .withPermission(4).withSource(capture(out::add));
                            s.getCommands().performPrefixedCommand(src, J.req(a, "command"));
                            return null;
                        });
                        return J.obj("output", out);
                    }));
    }

    private static ServerLevel level(MinecraftServer s, JsonObject a, ServerPlayer p) {
        String dim = J.str(a, "dimension", null);
        if (dim == null) {
            if (p != null) return p.serverLevel();
            return s.overworld();
        }
        ServerLevel l = s.getLevel(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.DIMENSION,
                net.minecraft.resources.ResourceLocation.parse(dim)));
        if (l == null) throw new McpServer.ToolError("no such dimension: " + dim);
        return l;
    }

    private static Map<String, Object> locate(MinecraftServer s, JsonObject a, Supplier<ServerPlayer> def) {
        ServerPlayer p = null;
        try { p = player(s, a, def); } catch (McpServer.ToolError ignored) {}
        ServerLevel level = level(s, a, p);
        String id = J.req(a, "structure");
        var registry = level.registryAccess().registryOrThrow(net.minecraft.core.registries.Registries.STRUCTURE);
        java.util.Optional<? extends net.minecraft.core.HolderSet<net.minecraft.world.level.levelgen.structure.Structure>> set;
        if (id.startsWith("#")) {
            set = registry.getTag(net.minecraft.tags.TagKey.create(net.minecraft.core.registries.Registries.STRUCTURE,
                    net.minecraft.resources.ResourceLocation.parse(id.substring(1))));
        } else {
            set = registry.getHolder(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.STRUCTURE,
                    net.minecraft.resources.ResourceLocation.parse(id))).map(net.minecraft.core.HolderSet::direct);
        }
        if (set.isEmpty()) throw new McpServer.ToolError("unknown structure or tag: " + id);
        int nx = a.has("near_x") ? J.i(a, "near_x", 0) : p != null ? p.getBlockX() : 0;
        int nz = a.has("near_z") ? J.i(a, "near_z", 0) : p != null ? p.getBlockZ() : 0;
        net.minecraft.core.BlockPos origin = new net.minecraft.core.BlockPos(nx, 64, nz);
        long t0 = System.nanoTime();
        @SuppressWarnings("unchecked")
        net.minecraft.core.HolderSet<net.minecraft.world.level.levelgen.structure.Structure> holders =
                (net.minecraft.core.HolderSet<net.minecraft.world.level.levelgen.structure.Structure>) set.get();
        com.mojang.datafixers.util.Pair<net.minecraft.core.BlockPos, net.minecraft.core.Holder<net.minecraft.world.level.levelgen.structure.Structure>> found =
                level.getChunkSource().getGenerator().findNearestMapStructure(level, holders, origin, 100, false);
        long ms = (System.nanoTime() - t0) / 1_000_000;
        if (found == null) return J.obj("found", false, "structure", id, "searched_ms", ms);
        net.minecraft.core.BlockPos pos = found.getFirst();
        String which = found.getSecond().unwrapKey().map(k -> k.location().toString()).orElse(id);
        return J.obj("found", true, "structure", which, "dimension", level.dimension().location().toString(),
                "x", pos.getX(), "y", pos.getY(), "z", pos.getZ(),
                "distance", (int) Math.sqrt(origin.distSqr(new net.minecraft.core.BlockPos(pos.getX(), 64, pos.getZ()))), "searched_ms", ms);
    }

    /** Action tools follow the config live: [action] needs actions=true, run_command also actionsCommands=true. */
    static boolean enabled(Tool t) {
        if (t.name().equals("run_command")) return Config.ACTIONS.get() && Config.ACTIONS_COMMANDS.get();
        if (t.description().startsWith("[action]")) return Config.ACTIONS.get();
        return true;
    }

    @FunctionalInterface
    private interface Callable {
        Object run();
    }

    public static Map<String, Object> status(String side, boolean world) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("side", side);
        m.put("minecraft", SharedConstants.getCurrentVersion().getName());
        m.put("neoforge", ModList.get().getModContainerById("neoforge").map(c -> c.getModInfo().getVersion().toString()).orElse("?"));
        m.put("mods", ModList.get().size());
        m.put("world_loaded", world);
        m.put("spark", SparkBridge.present());
        m.put("actions_enabled", Config.ACTIONS.get());
        m.put("run_command_enabled", Config.ACTIONS.get() && Config.ACTIONS_COMMANDS.get());
        m.put("chat_bridge", Config.CHAT_BRIDGE.get());
        m.put("chat_prefix", Config.CHAT_PREFIX.get());
        return m;
    }

    static MinecraftServer need(Supplier<MinecraftServer> server) {
        MinecraftServer s = server.get();
        if (s == null) throw new McpServer.ToolError("no server: join a singleplayer world first (on a multiplayer client, connect to the server's own MCP instead)");
        return s;
    }

    static ServerPlayer player(MinecraftServer s, JsonObject a, Supplier<ServerPlayer> def) {
        String name = J.str(a, "player", null);
        ServerPlayer p = name != null ? s.getPlayerList().getPlayerByName(name) : def.get();
        if (p == null) throw new McpServer.ToolError(name != null ? "player not online: " + name : "no player given and no local player");
        return p;
    }

    /** A command output sink. */
    public static CommandSource capture(Consumer<String> sink) {
        return new CommandSource() {
            @Override public void sendSystemMessage(Component c) { sink.accept(c.getString()); }
            @Override public boolean acceptsSuccess() { return true; }
            @Override public boolean acceptsFailure() { return true; }
            @Override public boolean shouldInformAdmins() { return false; }
        };
    }
}
