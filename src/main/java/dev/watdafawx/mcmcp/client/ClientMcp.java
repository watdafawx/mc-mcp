package dev.watdafawx.mcmcp.client;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

import com.google.gson.JsonObject;
import com.mojang.blaze3d.platform.GlUtil;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.OptionInstance;
import net.minecraft.client.Options;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.protocol.game.ServerboundSetCarriedItemPacket;
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

import dev.watdafawx.mcmcp.CommonTools;
import dev.watdafawx.mcmcp.Config;
import dev.watdafawx.mcmcp.GameThread;
import dev.watdafawx.mcmcp.McMcp;
import dev.watdafawx.mcmcp.chat.ChatLog;
import dev.watdafawx.mcmcp.mcp.J;
import dev.watdafawx.mcmcp.mcp.McpServer;
import dev.watdafawx.mcmcp.mcp.McpServer.Tool;
import dev.watdafawx.mcmcp.mcp.NetRules;
import dev.watdafawx.mcmcp.metrics.FrameStats;
import dev.watdafawx.mcmcp.metrics.GcMonitor;
import dev.watdafawx.mcmcp.metrics.TickStats;
import dev.watdafawx.mcmcp.metrics.WorldState;
import dev.watdafawx.mcmcp.spark.SparkBridge;

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
        dev.watdafawx.mcmcp.ghost.GhostRenderer.init();
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
        dev.watdafawx.mcmcp.ghost.GhostTools.register(mcp);
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

        mcp.add(new Tool("screenshot",
                "[action] Save a PNG of the current client frame to <gameDir>/screenshots/<name> and return its path. Name defaults to a timestamp; use this to prove what the game actually shows.",
                J.Schema.of().str("name", "file name, e.g. drawer-lock.png (default: mcmcp-<timestamp>.png)").build(),
                false, a -> {
                    String name = J.str(a, "name", "mcmcp-" + System.currentTimeMillis() + ".png");
                    if (name.contains("/") || name.contains("\\") || name.contains("..")) throw new McpServer.ToolError("name must be a plain file name");
                    if (!name.toLowerCase(Locale.ROOT).endsWith(".png")) name += ".png";
                    final String fileName = name;
                    java.io.File dir = mc().gameDirectory;
                    java.io.File out = new java.io.File(new java.io.File(dir, "screenshots"), fileName);
                    CompletableFuture<Component> saved = new CompletableFuture<>();
                    GameThread.call(mc(), () -> {
                        if (mc().level == null) throw new McpServer.ToolError("not in a world");
                        Screenshot.grab(dir, fileName, mc().getMainRenderTarget(), saved::complete);
                        return null;
                    });
                    Component message;
                    try {
                        message = saved.get(15, TimeUnit.SECONDS);
                    } catch (Exception e) {
                        throw new McpServer.ToolError("screenshot did not finish: " + e);
                    }
                    if (!out.isFile()) throw new McpServer.ToolError("screenshot not written: " + message.getString());
                    return J.obj("path", out.getAbsolutePath(), "message", message.getString(), "bytes", out.length());
                }));

        mcp.add(new Tool("screen",
                "Current client screen: class, title, GUI-scaled size, GUI scale, container geometry (guiLeft/guiTop/xSize/ySize) and every AbstractWidget (x/y/w/h, message). Use the coordinates with `click`. Read-only.",
                J.Schema.of().bool("widgets", "include widgets, default true").build(),
                true, a -> GameThread.call(mc(), () -> screenInfo(J.b(a, "widgets", true)))));

        mcp.add(new Tool("click",
                "[action] Click in the open screen at GUI-scaled coordinates (the same x/y `screen` reports). Fires NeoForge's ScreenEvent.MouseButtonPressed.Pre first, so this exercises mod buttons exactly like a real click.",
                J.Schema.of().integer("x", "GUI-scaled x").integer("y", "GUI-scaled y").integer("button", "0 left, 1 right, 2 middle; default 0")
                        .required("x", "y").build(),
                false, a -> GameThread.call(mc(), () -> {
                    Screen s = mc().screen;
                    if (s == null) throw new McpServer.ToolError("no screen open");
                    int x = J.i(a, "x", 0), y = J.i(a, "y", 0), button = J.i(a, "button", 0);
                    // Mirror MouseHandler#onPress: Screen.mouseClicked itself does not post NeoForge's
                    // ScreenEvent.MouseButtonPressed, so mod buttons listening to it never see a click.
                    boolean handled = net.neoforged.neoforge.client.ClientHooks.onScreenMouseClickedPre(s, x, y, button);
                    if (!handled) {
                        handled = s.mouseClicked(x, y, button);
                        net.neoforged.neoforge.client.ClientHooks.onScreenMouseClickedPost(s, x, y, button, handled);
                    }
                    s.mouseReleased(x, y, button);
                    return J.obj("x", x, "y", y, "button", button, "handled", handled,
                            "screen_after", mc().screen == null ? null : mc().screen.getClass().getName());
                })));

        mcp.add(new Tool("key",
                "[action] Send a key press to the open screen (GLFW key/scan codes, e.g. 256 Escape, 257 Enter, 69 E).",
                J.Schema.of().integer("key", "GLFW key code").integer("scan", "scan code, default 0").integer("modifiers", "GLFW modifiers, default 0")
                        .required("key").build(),
                false, a -> GameThread.call(mc(), () -> {
                    Screen s = mc().screen;
                    if (s == null) throw new McpServer.ToolError("no screen open");
                    int key = J.i(a, "key", 0), scan = J.i(a, "scan", 0), mods = J.i(a, "modifiers", 0);
                    boolean handled = net.neoforged.neoforge.client.ClientHooks.onScreenKeyPressedPre(s, key, scan, mods);
                    if (!handled) {
                        handled = s.keyPressed(key, scan, mods);
                        net.neoforged.neoforge.client.ClientHooks.onScreenKeyPressedPost(s, key, scan, mods);
                    }
                    return J.obj("key", key, "handled", handled, "screen_after", mc().screen == null ? null : mc().screen.getClass().getName());
                })));

        mcp.add(new Tool("close_screen",
                "[action] Close the current client screen (equivalent to Escape) without touching the mouse.",
                J.Schema.of().build(),
                false, a -> GameThread.call(mc(), () -> {
                    String before = mc().screen == null ? null : mc().screen.getClass().getName();
                    mc().setScreen(null);
                    return J.obj("closed", before);
                })));

        mcp.add(new Tool("look",
                "[action] Set the client player's yaw/pitch in degrees (client camera and, in singleplayer, the server player), so MCP can aim without the mouse.",
                J.Schema.of().num("yaw", "degrees; 0 = south, 90 = west, 180 = north, 270 = east").num("pitch", "degrees; -90 up, +90 down").build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().player == null) throw new McpServer.ToolError("not in a world");
                    float yaw = (float) J.d(a, "yaw", mc().player.getYRot());
                    float pitch = (float) J.d(a, "pitch", mc().player.getXRot());
                    return applyLook(yaw, pitch);
                })));

        mcp.add(new Tool("look_at",
                "[action] Aim the client player at a world position (x/y/z). Convenience wrapper over `look`, no mouse.",
                J.Schema.of().num("x", "block/entity x").num("y", "x").num("z", "z").required("x", "y", "z").build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().player == null) throw new McpServer.ToolError("not in a world");
                    double dx = J.d(a, "x", 0) - mc().player.getX();
                    double dy = J.d(a, "y", 0) - mc().player.getEyeY();
                    double dz = J.d(a, "z", 0) - mc().player.getZ();
                    double horizontal = Math.sqrt(dx * dx + dz * dz);
                    float yaw = (float) (Math.atan2(-dx, dz) * 180.0 / Math.PI);
                    float pitch = (float) (-Math.atan2(dy, horizontal) * 180.0 / Math.PI);
                    return applyLook(yaw, pitch);
                })));

        mcp.add(new Tool("click_world",
                "[action] Left- or right-click in the world through the game's real input path (Minecraft.startAttack / MultiPlayerGameMode.useItemOn), including NeoForge's InteractionKeyMappingTriggered event on the left. The crosshair pick is refreshed first, so a look/look_at in the same tick is honoured. This is how a mod's in-world click button gets tested. No screen may be open.",
                J.Schema.of().enumOf("button", "left or right", "left", "right").build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().player == null) throw new McpServer.ToolError("not in a world");
                    if (mc().screen != null) throw new McpServer.ToolError("a screen is open; use `click`");
                    String button = J.str(a, "button", "left");

                    // The ray trace only refreshes on a client tick, so re-pick here to make a
                    // look/look_at issued in the same MCP batch take effect.
                    mc().hitResult = mc().player.pick(mc().player.blockInteractionRange(), 1.0F, false);
                    var hit = mc().hitResult;
                    var hitDesc = hit instanceof net.minecraft.world.phys.BlockHitResult b
                            ? b.getBlockPos().toShortString() + " " + b.getDirection()
                            : String.valueOf(hit == null ? null : hit.getType());

                    try {
                        if (button.equalsIgnoreCase("right")) {
                            if (!(hit instanceof net.minecraft.world.phys.BlockHitResult blockHit))
                                throw new McpServer.ToolError("not looking at a block (" + hitDesc + ")");
                            var result = mc().gameMode.useItemOn(mc().player, net.minecraft.world.InteractionHand.MAIN_HAND, blockHit);
                            if (result.consumesAction()) mc().player.swing(net.minecraft.world.InteractionHand.MAIN_HAND);
                            return J.obj("button", "right", "sent", true, "result", result.name(), "hit", hitDesc);
                        }
                        Method m = Minecraft.class.getDeclaredMethod("startAttack");
                        m.setAccessible(true);
                        Object result = m.invoke(mc());
                        return J.obj("button", "left", "attacked", result, "hit", hitDesc);
                    } catch (ReflectiveOperationException e) {
                        throw new McpServer.ToolError("could not invoke the game's click path: " + e);
                    }
                })));

        mcp.add(new Tool("crosshair",
                "What the client crosshair is actually on: hit type, block position, face, or entity. Useful when a look/look_at and the expected block disagree. Read-only.",
                J.Schema.of().build(),
                true, a -> GameThread.call(mc(), () -> {
                    var hit = mc().hitResult;
                    if (hit == null) return J.obj("type", "miss");
                    if (hit instanceof net.minecraft.world.phys.BlockHitResult b)
                        return J.obj("type", "block", "pos", b.getBlockPos().toShortString(), "face", b.getDirection().getName(),
                                "location", J.obj("x", J.r2(b.getLocation().x), "y", J.r2(b.getLocation().y), "z", J.r2(b.getLocation().z)));
                    if (hit instanceof net.minecraft.world.phys.EntityHitResult e)
                        return J.obj("type", "entity", "entity", e.getEntity().getName().getString());
                    return J.obj("type", hit.getType().name());
                })));

        mcp.add(new Tool("hold_key",
                "[action] Hold or release a key without the keyboard: shift, sprint/ctrl, use, attack, jump, forward, back, left, right. Alternatively pass `mapping` (a KeyMapping name such as key.foxstweaks.reveal_drawer_lock) to hold a mod keybind, including one bound to a controller button.",
                J.Schema.of().str("key", "shift | sprint/ctrl | use | attack | jump | forward | back | left | right").str("mapping", "KeyMapping name, instead of key").bool("down", "true to hold, false to release; default true").build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().player == null) throw new McpServer.ToolError("not in a world");
                    String mappingName = J.str(a, "mapping", "");
                    if (!mappingName.isEmpty()) {
                        for (net.minecraft.client.KeyMapping mapping : mc().options.keyMappings) {
                            if (mapping.getName().equals(mappingName)) {
                                boolean down = J.b(a, "down", true);
                                mapping.setDown(down);
                                return J.obj("mapping", mappingName, "down", down, "is_down", mapping.isDown());
                            }
                        }
                        throw new McpServer.ToolError("no key mapping named " + mappingName);
                    }
                    String name = J.str(a, "key", "").toLowerCase(Locale.ROOT);
                    var options = mc().options;
                    net.minecraft.client.KeyMapping mapping = switch (name) {
                        case "shift", "sneak" -> options.keyShift;
                        case "sprint", "ctrl" -> options.keySprint;
                        case "use" -> options.keyUse;
                        case "attack" -> options.keyAttack;
                        case "jump" -> options.keyJump;
                        case "forward", "up" -> options.keyUp;
                        case "back", "down" -> options.keyDown;
                        case "left" -> options.keyLeft;
                        case "right" -> options.keyRight;
                        default -> throw new McpServer.ToolError("unknown key: " + name);
                    };
                    boolean down = J.b(a, "down", true);
                    mapping.setDown(down);
                    return J.obj("key", name, "down", down, "is_down", mapping.isDown());
                })));

        mcp.add(new Tool("hotbar",
                "[action] Select a hotbar slot (0-8) and tell the server.",
                J.Schema.of().integer("slot", "0-8").required("slot").build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().player == null) throw new McpServer.ToolError("not in a world");
                    int slot = J.i(a, "slot", 0);
                    if (slot < 0 || slot > 8) throw new McpServer.ToolError("slot must be 0-8");
                    mc().player.getInventory().selected = slot;
                    if (mc().getConnection() != null) mc().getConnection().send(new ServerboundSetCarriedItemPacket(slot));
                    return J.obj("slot", slot);
                })));

        mcp.add(new Tool("chunk_rebuild",
                "[action] Rebuild all client chunk meshes (what F3+A does). Useful after /setblock when the model did not arrive.",
                J.Schema.of().build(),
                false, a -> GameThread.call(mc(), () -> {
                    if (mc().level == null) throw new McpServer.ToolError("not in a world");
                    mc().levelRenderer.allChanged();
                    return J.obj("rebuilt", true);
                })));

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

    private static Map<String, Object> screenInfo(boolean widgets) {
        Screen s = mc().screen;
        if (s == null) return J.obj("open", false);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("open", true);
        m.put("class", s.getClass().getName());
        m.put("title", s.getTitle().getString());
        m.put("width", s.width);
        m.put("height", s.height);
        m.put("gui_scale", mc().getWindow().getGuiScale());
        if (s instanceof AbstractContainerScreen<?> c) {
            m.put("container", J.obj("gui_left", c.getGuiLeft(), "gui_top", c.getGuiTop(),
                    "x_size", c.getXSize(), "y_size", c.getYSize()));
        }
        if (widgets) {
            List<Map<String, Object>> list = new ArrayList<>();
            for (var child : s.children()) {
                if (child instanceof AbstractWidget w) {
                    list.add(J.obj("type", w.getClass().getSimpleName(), "message", w.getMessage().getString(),
                            "x", w.getX(), "y", w.getY(), "width", w.getWidth(), "height", w.getHeight(),
                            "active", w.active, "visible", w.visible));
                }
            }
            m.put("widgets", list);
        }
        return m;
    }

    private static Map<String, Object> applyLook(float yaw, float pitch) {
        var p = mc().player;
        if (p == null) throw new McpServer.ToolError("not in a world");
        p.setYRot(yaw);
        p.setXRot(pitch);
        p.yRotO = yaw;
        p.xRotO = pitch;
        ServerPlayer sp = localServerPlayer();
        if (sp != null) {
            sp.setYRot(yaw);
            sp.setXRot(pitch);
            sp.yRotO = yaw;
            sp.xRotO = pitch;
        }
        return J.obj("yaw", J.r2(yaw), "pitch", J.r2(pitch), "server_player", sp != null);
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
