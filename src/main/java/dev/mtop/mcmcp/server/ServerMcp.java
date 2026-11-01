package dev.mtop.mcmcp.server;

import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.ServerChatEvent;
import net.neoforged.neoforge.event.server.ServerStartedEvent;
import net.neoforged.neoforge.event.server.ServerStoppingEvent;

import dev.mtop.mcmcp.CommonTools;
import dev.mtop.mcmcp.Config;
import dev.mtop.mcmcp.GameThread;
import dev.mtop.mcmcp.McMcp;
import dev.mtop.mcmcp.chat.ChatLog;
import dev.mtop.mcmcp.mcp.J;
import dev.mtop.mcmcp.mcp.McpServer;
import dev.mtop.mcmcp.mcp.McpServer.Tool;
import dev.mtop.mcmcp.mcp.NetRules;
import dev.mtop.mcmcp.spark.SparkBridge;

/** The dedicated server's MCP server: always token-protected and LAN-only. */
public final class ServerMcp {
    private static final ChatLog CHAT = new ChatLog();
    private static volatile MinecraftServer server;
    private static McpServer mcp;

    private ServerMcp() {}

    public static void init() {
        NeoForge.EVENT_BUS.addListener((ServerStartedEvent e) -> start(e.getServer()));
        NeoForge.EVENT_BUS.addListener((ServerStoppingEvent e) -> {
            if (mcp != null) mcp.stop();
            mcp = null;
            server = null;
        });
        NeoForge.EVENT_BUS.addListener(ServerMcp::onChat);
    }

    private static void start(MinecraftServer s) {
        server = s;
        if (!Config.SERVER_ENABLED.get()) return;
        String token = Config.SERVER_TOKEN.get();
        if (token.isBlank()) {
            byte[] b = new byte[24];
            new SecureRandom().nextBytes(b);
            token = HexFormat.of().formatHex(b);
            Config.SERVER_TOKEN.set(token);
            Config.SPEC.save();
            McMcp.LOG.info("Generated an MCP bearer token in config/mcmcp-common.toml ([server] token)");
        }
        mcp = new McpServer("minecraft-server", McMcp.version(), McMcp.INSTRUCTIONS);
        register(mcp);
        try {
            mcp.start(Config.SERVER_BIND.get(), Config.SERVER_PORT.get(), token, NetRules.lanAllowlist(Config.SERVER_ALLOWLIST.get()));
        } catch (Exception e) {
            McMcp.LOG.error("MCP server failed to start on {}:{}", Config.SERVER_BIND.get(), Config.SERVER_PORT.get(), e);
            mcp = null;
        }
    }

    private static void onChat(ServerChatEvent e) {
        String raw = e.getRawText();
        String prefix = Config.CHAT_PREFIX.get();
        if (Config.CHAT_BRIDGE.get() && !prefix.isEmpty() && raw.regionMatches(true, 0, prefix, 0, prefix.length())) {
            e.setCanceled(true); // not broadcast
            String body = raw.substring(prefix.length()).trim();
            CHAT.toClaude(e.getUsername(), body);
            e.getPlayer().sendSystemMessage(Component.literal("[You → Claude] ").withStyle(ChatFormatting.DARK_AQUA)
                    .append(Component.literal(body).withStyle(ChatFormatting.GRAY, ChatFormatting.ITALIC)));
            return;
        }
        CHAT.shown("chat", "<" + e.getUsername() + "> " + raw);
    }

    private static void register(McpServer mcp) {
        mcp.add(new Tool("status", "Server status: versions, mods, players, enabled tool groups. Start here.",
                J.Schema.of().build(), true, a -> GameThread.call(server, () -> {
                    Map<String, Object> m = CommonTools.status("dedicated_server", true);
                    m.put("motd", server.getMotd());
                    m.put("players", server.getPlayerList().getPlayers().stream().map(p -> p.getGameProfile().getName()).toList());
                    m.put("tools", mcp.tools().stream().map(Tool::name).toList());
                    return m;
                })));

        CommonTools.register(mcp, () -> server, () -> null);

        Map<String, SparkBridge.Runner> sides = new LinkedHashMap<>();
        sides.put("server", (cmd, sink) -> {
            MinecraftServer s = server;
            if (s == null) {
                sink.accept("server not running");
                return;
            }
            s.execute(() -> s.getCommands().performPrefixedCommand(
                    s.createCommandSourceStack().withPermission(4).withSource(CommonTools.capture(sink)), "spark " + cmd));
        });
        new SparkBridge(sides).register(mcp);

        if (!Config.CHAT_BRIDGE.get()) return;
        mcp.add(new Tool("chat_send",
                "Show a [Claude] message to one player only (system message, not broadcast).",
                J.Schema.of().str("player", "player name").str("text", "message").required("player", "text").build(), false, a -> {
                    String name = J.req(a, "player");
                    String text = J.req(a, "text");
                    return GameThread.call(server, () -> {
                        ServerPlayer p = server.getPlayerList().getPlayerByName(name);
                        if (p == null) throw new McpServer.ToolError("player not online: " + name);
                        for (String line : text.split("\n"))
                            p.sendSystemMessage(Component.literal("[Claude] ").withStyle(ChatFormatting.GOLD, ChatFormatting.BOLD)
                                    .append(Component.literal(line).withStyle(s -> s.withBold(false).withColor(ChatFormatting.WHITE))));
                        CHAT.shown("claude", "to " + name + ": " + text);
                        return J.obj("shown_to", name);
                    });
                }));
        mcp.add(new Tool("chat_read", "Recent player chat seen by the server (and [Claude] lines sent), oldest first.",
                J.Schema.of().integer("since", "only lines with id > since").integer("limit", "default 50").build(), true,
                a -> J.obj("lines", CHAT.read(J.i(a, "since", 0), J.i(a, "limit", 50), null), "last_id", CHAT.lastId())));
        mcp.add(new Tool("chat_poll", "Player messages for Claude (prefix '@claude', not broadcast). Non-blocking.",
                J.Schema.of().integer("since", "message id; default: not yet delivered").build(), true,
                a -> J.obj("messages", CHAT.poll(J.i(a, "since", -1)), "prefix", Config.CHAT_PREFIX.get())));
        mcp.add(new Tool("chat_wait", "Block until a player sends a message for Claude, or timeout.",
                J.Schema.of().integer("timeout_s", "default 120, max 3600").integer("since", "message id").build(), true, a -> {
                    long t = Math.max(1, Math.min(3600, J.i(a, "timeout_s", 120)));
                    List<Map<String, Object>> got = CHAT.await(J.i(a, "since", -1), t * 1000);
                    return J.obj("messages", got, "timed_out", got.isEmpty(), "prefix", Config.CHAT_PREFIX.get());
                }));
    }
}
