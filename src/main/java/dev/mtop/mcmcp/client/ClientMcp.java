package dev.mtop.mcmcp.client;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

import com.google.gson.JsonObject;
import com.mojang.blaze3d.platform.GlUtil;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.OptionInstance;
import net.minecraft.client.Options;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.status.ChunkStatus;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.event.lifecycle.FMLClientSetupEvent;
import net.neoforged.neoforge.client.ClientCommandHandler;
import net.neoforged.neoforge.client.event.ClientChatEvent;
import net.neoforged.neoforge.client.event.RenderFrameEvent;
import net.neoforged.neoforge.common.NeoForge;

import dev.mtop.mcmcp.CommonTools;
import dev.mtop.mcmcp.Config;
import dev.mtop.mcmcp.GameThread;
import dev.mtop.mcmcp.McMcp;
import dev.mtop.mcmcp.chat.ChatLog;
import dev.mtop.mcmcp.mcp.J;
import dev.mtop.mcmcp.mcp.McpServer;
import dev.mtop.mcmcp.mcp.McpServer.Tool;
import dev.mtop.mcmcp.mcp.NetRules;
import dev.mtop.mcmcp.metrics.FrameStats;
import dev.mtop.mcmcp.metrics.GcMonitor;
import dev.mtop.mcmcp.metrics.TickStats;
import dev.mtop.mcmcp.metrics.WorldState;
import dev.mtop.mcmcp.spark.SparkBridge;

/** The game client's MCP server. In singleplayer it also reaches the integrated server. */
public final class ClientMcp {
    private static final ChatLog CHAT = new ChatLog();
    /** Temporary listeners for chat lines (spark's client command replies). */
    private static final List<Consumer<String>> CHAT_TAPS = new CopyOnWriteArrayList<>();
    private static final ThreadLocal<Boolean> SENDING = ThreadLocal.withInitial(() -> false);
    private static McpServer mcp;

    private ClientMcp() {}

    public static void init(IEventBus modBus) {
        NeoForge.EVENT_BUS.addListener((RenderFrameEvent.Pre e) -> FrameStats.onFrame());
        NeoForge.EVENT_BUS.addListener(ClientMcp::onChatSend);
        modBus.addListener((FMLClientSetupEvent e) -> start());
    }

    private static void start() {
        if (!Config.CLIENT_ENABLED.get()) return;
        String bind = Config.CLIENT_BIND.get();
        String token = Config.CLIENT_TOKEN.get();
        boolean loopback = bind.equals("127.0.0.1") || bind.equals("localhost") || bind.equals("::1");
        if (!loopback && token.isEmpty()) {
            McMcp.LOG.error("MCP client server not started: bind {} is not loopback and no token is set", bind);
            return;
        }
        mcp = new McpServer("minecraft-client", McMcp.version(), McMcp.INSTRUCTIONS);
        registerTools(mcp);
        try {
            mcp.start(bind, Config.CLIENT_PORT.get(), token, loopback ? NetRules.loopbackOnly() : NetRules.lanAllowlist(Config.SERVER_ALLOWLIST.get()));
        } catch (Exception e) {
            McMcp.LOG.error("MCP client server failed to start on {}:{}", bind, Config.CLIENT_PORT.get(), e);
            mcp = null;
        }
    }

    private static Minecraft mc() {
        return Minecraft.getInstance();
    }

    private static IntegratedServer server() {
        return mc().getSingleplayerServer();
    }

    private static ServerPlayer localServerPlayer() {
        IntegratedServer s = server();
        var p = mc().player;
        return s == null || p == null ? null : s.getPlayerList().getPlayer(p.getUUID());
    }

    // ------------------------------------------------------------------ chat

    /** From the ChatComponent mixin: every line added to the chat box. */
    public static void onChatShown(Component message, boolean signed) {
        String text = message.getString();
        String kind = SENDING.get() ? "claude" : signed || text.startsWith("<") ? "chat" : "system";
        CHAT.shown(kind, text);
        for (Consumer<String> tap : CHAT_TAPS) tap.accept(text);
    }

    private static void onChatSend(ClientChatEvent e) {
        if (!Config.CHAT_BRIDGE.get()) return;
        String prefix = Config.CHAT_PREFIX.get();
        String msg = e.getMessage();
        if (prefix.isEmpty() || !msg.regionMatches(true, 0, prefix, 0, prefix.length())) return;
        e.setCanceled(true); // never reaches the server
        String body = msg.substring(prefix.length()).trim();
        var p = mc().player;
        CHAT.toClaude(p != null ? p.getGameProfile().getName() : "player", body);
        show(Component.literal("[You → Claude] ").withStyle(ChatFormatting.DARK_AQUA)
                .append(Component.literal(body).withStyle(ChatFormatting.GRAY, ChatFormatting.ITALIC)), false);
    }

    private static void show(Component c, boolean fromClaude) {
        mc().execute(() -> {
            SENDING.set(fromClaude);
            try {
                mc().gui.getChat().addMessage(c);
            } finally {
                SENDING.set(false);
            }
        });
    }

    // ------------------------------------------------------------------ tools

    private static void registerTools(McpServer mcp) {
        mcp.add(new Tool("status",
                "What is running: game side, versions, mod count, world, player position/dimension, enabled tool groups. Start here.",
                J.Schema.of().build(), true, a -> GameThread.call(mc(), () -> {
                    Map<String, Object> m = CommonTools.status("client", mc().level != null);
                    m.put("singleplayer", server() != null);
                    m.put("screen", mc().screen == null ? null : mc().screen.getClass().getName());
                    m.put("paused", mc().isPaused());
                    if (mc().player != null) {
                        var p = mc().player;
                        m.put("player", J.obj("name", p.getGameProfile().getName(), "dimension", p.level().dimension().location().toString(),
                                "x", J.r1(p.getX()), "y", J.r1(p.getY()), "z", J.r1(p.getZ())));
                    }
                    if (mc().getCurrentServer() != null) m.put("server_address", mc().getCurrentServer().ip);
                    m.put("fps_now", mc().getFps());
                    m.put("tools", mcp.tools().stream().map(Tool::name).toList());
                    return m;
                })));

        mcp.add(new Tool("frame_stats",
                "Client frame metrics: FPS avg, 1% / 0.1% low, frame time avg/p50/p95/p99/worst, frames over 50/100 ms. Default: the last `seconds` already recorded; fresh=true waits and measures the next `seconds` instead.",
                J.Schema.of().num("seconds", "window, default 10").bool("fresh", "measure the next N seconds instead of the last N").build(),
                true, a -> {
                    double secs = Math.max(0.5, Math.min(600, J.d(a, "seconds", 10)));
                    long ns = (long) (secs * 1e9);
                    Map<String, Object> m;
                    if (J.b(a, "fresh", false)) {
                        long from = System.nanoTime();
                        Thread.sleep((long) (secs * 1000));
                        m = FrameStats.window(from, System.nanoTime());
                    } else {
                        long now = System.nanoTime();
                        m = FrameStats.window(now - ns, now);
                    }
                    m.put("context", GameThread.call(mc(), ClientMcp::frameContext));
                    return m;
                }));

        mcp.add(new Tool("measure",
                "Wait settle_s (after a teleport or config change), then measure for seconds: frame stats, integrated-server tick stats, GC pauses, heap. Read-only.",
                J.Schema.of().num("settle_s", "wait first, default 5").num("seconds", "measure window, default 15").str("label", "free text echoed back").build(),
                true, a -> {
                    double settle = Math.max(0, Math.min(300, J.d(a, "settle_s", 5)));
                    double secs = Math.max(1, Math.min(600, J.d(a, "seconds", 15)));
                    Thread.sleep((long) (settle * 1000));
                    long from = System.nanoTime();
                    Thread.sleep((long) (secs * 1000));
                    Map<String, Object> out = new LinkedHashMap<>();
                    out.put("label", J.str(a, "label", ""));
                    out.put("frames", FrameStats.window(from, System.nanoTime()));
                    IntegratedServer s = server();
                    if (s != null) out.put("ticks", GameThread.call(s, () -> TickStats.of(s)));
                    Map<String, Object> gc = GcMonitor.snapshot((int) Math.ceil(secs), false);
                    out.put("gc", J.obj("pauses", gc.get("gc_pauses_in_window"), "concurrent", gc.get("gc_concurrent_cycles_in_window"),
                            "heap_used_mb", gc.get("heap_used_mb"), "heap_max_mb", gc.get("heap_max_mb")));
                    out.put("context", GameThread.call(mc(), ClientMcp::frameContext));
                    return out;
                }));

        mcp.add(new Tool("client_world_state",
                "Client-side state: loaded chunks, rendered sections, entities/block entities by type (client view), ticking client block entities, particles, render/simulation distance, GPU.",
                J.Schema.of().integer("top", "rows per list, default 15").build(),
                true, a -> GameThread.call(mc(), () -> {
                    ClientLevel level = mc().level;
                    if (level == null) throw new McpServer.ToolError("not in a world");
                    int top = J.i(a, "top", 15);
                    int r = mc().options.getEffectiveRenderDistance() + 1;
                    ChunkPos c = mc().player.chunkPosition();
                    List<LevelChunk> chunks = new ArrayList<>();
                    for (int x = -r; x <= r; x++)
                        for (int z = -r; z <= r; z++) {
                            LevelChunk ch = level.getChunkSource().getChunk(c.x + x, c.z + z, ChunkStatus.FULL, false);
                            if (ch != null) chunks.add(ch);
                        }
                    Map<String, Object> m = WorldState.counts(level, level.entitiesForRendering(), chunks, top);
                    m.put("loaded_chunks", level.getChunkSource().getLoadedChunksCount());
                    m.put("sections", mc().levelRenderer.getSectionStatistics());
                    m.put("entity_render_stats", mc().levelRenderer.getEntityStatistics());
                    m.put("particles", mc().particleEngine.countParticles());
                    m.putAll(frameContext());
                    m.put("gpu", GlUtil.getRenderer() + " / " + GlUtil.getOpenGLVersion());
                    m.put("cpu", GlUtil.getCpuInfo());
                    return m;
                }, 20)));

        CommonTools.register(mcp, ClientMcp::server, ClientMcp::localServerPlayer);

        mcp.add(new Tool("video_get", "Current video/game options (Options.* OptionInstance values), filtered by name.",
                J.Schema.of().str("filter", "option name substring").build(), true, a -> GameThread.call(mc(), () -> options(J.str(a, "filter", "")))));
        mcp.add(new Tool("video_set",
                "[action] Set one video/game option, e.g. renderDistance 12, simulationDistance 8, enableVsync false, framerateLimit 260, graphicsMode FAST. Saved to options.txt.",
                J.Schema.of().str("option", "name from video_get").anyValue("value", "new value").required("option", "value").build(),
                false, a -> GameThread.call(mc(), () -> setOption(J.req(a, "option"), J.req(a, "value")))));

        // spark: client = sparkc (profiles this JVM; with threads='*' that includes the integrated server),
        // server = the integrated server's own /spark.
        Map<String, SparkBridge.Runner> sides = new LinkedHashMap<>();
        sides.put("client", ClientMcp::runSparkClient);
        sides.put("server", (cmd, sink) -> {
            IntegratedServer s = server();
            if (s == null) {
                sink.accept("no integrated server (not in singleplayer)");
                return;
            }
            s.execute(() -> s.getCommands().performPrefixedCommand(
                    s.createCommandSourceStack().withPermission(4).withSource(CommonTools.capture(sink)), "spark " + cmd));
        });
        new SparkBridge(sides).register(mcp);

        if (Config.CHAT_BRIDGE.get()) registerChat(mcp);
    }

    private static void runSparkClient(String cmd, Consumer<String> sink) {
        CHAT_TAPS.add(sink);
        Thread remover = new Thread(() -> {
            try { Thread.sleep(150_000); } catch (InterruptedException ignored) {}
            CHAT_TAPS.remove(sink);
        }, "mcmcp-tap");
        remover.setDaemon(true);
        remover.start();
        mc().execute(() -> {
            if (mc().player == null) {
                sink.accept("not in a world: spark's client command needs a player");
                return;
            }
            if (!ClientCommandHandler.runCommand("sparkc " + cmd)) sink.accept("Unknown command: sparkc");
        });
    }

    private static Map<String, Object> frameContext() {
        Options o = mc().options;
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("fps_counter", mc().getFps());
        m.put("render_distance", o.renderDistance().get());
        m.put("effective_render_distance", o.getEffectiveRenderDistance());
        m.put("simulation_distance", o.simulationDistance().get());
        m.put("fps_limit", o.framerateLimit().get());
        m.put("vsync", o.enableVsync().get());
        m.put("graphics", String.valueOf(o.graphicsMode().get()));
        m.put("window", mc().getWindow().getWidth() + "x" + mc().getWindow().getHeight());
        m.put("screen_open", mc().screen == null ? null : mc().screen.getClass().getSimpleName());
        m.put("paused", mc().isPaused());
        m.put("focused", mc().isWindowActive());
        return m;
    }

    private static Map<String, Object> options(String filter) {
        Map<String, Object> out = new java.util.TreeMap<>();
        String f = filter.toLowerCase(Locale.ROOT);
        for (Method m : Options.class.getMethods()) {
            if (m.getParameterCount() != 0 || m.getReturnType() != OptionInstance.class) continue;
            if (!f.isEmpty() && !m.getName().toLowerCase(Locale.ROOT).contains(f)) continue;
            try {
                out.put(m.getName(), String.valueOf(((OptionInstance<?>) m.invoke(mc().options)).get()));
            } catch (Exception ignored) {}
        }
        return out;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static Map<String, Object> setOption(String name, String raw) {
        Method m;
        try {
            m = Options.class.getMethod(name);
        } catch (NoSuchMethodException e) {
            throw new McpServer.ToolError("no option " + name + " (see video_get)");
        }
        if (m.getReturnType() != OptionInstance.class) throw new McpServer.ToolError("not an option: " + name);
        try {
            OptionInstance opt = (OptionInstance) m.invoke(mc().options);
            Object old = opt.get();
            Object v;
            if (old instanceof Boolean) v = Boolean.parseBoolean(raw);
            else if (old instanceof Integer) v = Integer.parseInt(raw.trim());
            else if (old instanceof Double) v = Double.parseDouble(raw.trim());
            else if (old instanceof Enum<?> en) {
                v = null;
                for (Object c : en.getDeclaringClass().getEnumConstants())
                    if (((Enum<?>) c).name().equalsIgnoreCase(raw.trim())) v = c;
                if (v == null) throw new McpServer.ToolError("expected one of " + java.util.Arrays.toString(en.getDeclaringClass().getEnumConstants()));
            } else throw new McpServer.ToolError("option type " + (old == null ? "?" : old.getClass().getSimpleName()) + " not supported");
            opt.set(v); // the option's own validation rejects out-of-range values (logged, value unchanged)
            mc().options.save();
            return J.obj("option", name, "old", String.valueOf(old), "new", String.valueOf(opt.get()),
                    "accepted", String.valueOf(opt.get()).equals(String.valueOf(v)));
        } catch (McpServer.ToolError e) {
            throw e;
        } catch (Exception e) {
            throw new McpServer.ToolError("could not set " + name + ": " + e);
        }
    }

    private static void registerChat(McpServer mcp) {
        mcp.add(new Tool("chat_send",
                "Show a [Claude] message in the local player's chat (client only; nothing is sent to the server or other players). Newlines become separate lines.",
                J.Schema.of().str("text", "message").required("text").build(), false, a -> {
                    String text = J.req(a, "text");
                    if (mc().player == null) throw new McpServer.ToolError("not in a world; the player would not see it");
                    for (String line : text.split("\n")) {
                        MutableComponent c = Component.literal("[Claude] ").withStyle(ChatFormatting.GOLD, ChatFormatting.BOLD)
                                .append(Component.literal(line).withStyle(s -> s.withBold(false).withColor(ChatFormatting.WHITE)));
                        show(c, true);
                    }
                    return J.obj("shown", true);
                }));
        mcp.add(new Tool("chat_read",
                "Recent chat box lines (player chat, system messages, command output, [Claude] lines), oldest first. kind: chat|system|claude.",
                J.Schema.of().integer("since", "only lines with id > since").integer("limit", "default 50").enumOf("kind", "filter", "chat", "system", "claude").build(),
                true, a -> J.obj("lines", CHAT.read(J.i(a, "since", 0), J.i(a, "limit", 50), J.str(a, "kind", null)), "last_id", CHAT.lastId())));
        mcp.add(new Tool("chat_poll",
                "Player messages for Claude (typed in chat starting with the prefix, default '@claude'; they never reach the server). Returns undelivered ones, or those after `since`. Non-blocking.",
                J.Schema.of().integer("since", "message id; default: everything not yet delivered").build(),
                true, a -> J.obj("messages", CHAT.poll(J.i(a, "since", -1)), "prefix", Config.CHAT_PREFIX.get())));
        mcp.add(new Tool("chat_selftest",
                    "[action] Test the bridge: posts '<prefix> <text>' through NeoForge's client chat hook exactly like a typed message. Nothing is ever sent to the server.",
                    J.Schema.of().str("text", "message body").required("text").build(), false, a -> {
                        String text = Config.CHAT_PREFIX.get() + " " + J.req(a, "text");
                        return GameThread.call(mc(), () -> {
                            if (mc().player == null) throw new McpServer.ToolError("not in a world");
                            String left = net.neoforged.neoforge.client.ClientHooks.onClientSendMessage(text);
                            return J.obj("typed", text, "intercepted", left.isEmpty());
                        });
                    }));
        mcp.add(new Tool("chat_wait",
                "Block until the player sends a message for Claude (prefix '@claude'), or timeout. Use in a loop to hold a conversation from inside the game.",
                J.Schema.of().integer("timeout_s", "default 120, max 3600").integer("since", "message id; default: not yet delivered").build(),
                true, a -> {
                    long t = Math.max(1, Math.min(3600, J.i(a, "timeout_s", 120)));
                    List<Map<String, Object>> got = CHAT.await(J.i(a, "since", -1), t * 1000);
                    return J.obj("messages", got, "timed_out", got.isEmpty(), "prefix", Config.CHAT_PREFIX.get());
                }));
    }
}
