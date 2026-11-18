package dev.watdafawx.mcmcp;

import java.util.List;

import net.neoforged.neoforge.common.ModConfigSpec;

/**
 * One COMMON config file ({@code config/mcmcp-common.toml}) for both sides. The client section is
 * used by the game client (which also covers singleplayer's integrated server); the server section
 * only by a dedicated server.
 */
public final class Config {
    private static final ModConfigSpec.Builder B = new ModConfigSpec.Builder();

    // --- client ---
    public static final ModConfigSpec.BooleanValue CLIENT_ENABLED;
    public static final ModConfigSpec.ConfigValue<String> CLIENT_BIND;
    public static final ModConfigSpec.IntValue CLIENT_PORT;
    public static final ModConfigSpec.ConfigValue<String> CLIENT_TOKEN;

    // --- server ---
    public static final ModConfigSpec.BooleanValue SERVER_ENABLED;
    public static final ModConfigSpec.ConfigValue<String> SERVER_BIND;
    public static final ModConfigSpec.IntValue SERVER_PORT;
    public static final ModConfigSpec.ConfigValue<String> SERVER_TOKEN;
    public static final ModConfigSpec.ConfigValue<List<? extends String>> SERVER_ALLOWLIST;

    // --- features ---
    public static final ModConfigSpec.BooleanValue SPARK_TOOLS;
    public static final ModConfigSpec.BooleanValue MIXIN_TOOLS;
    public static final ModConfigSpec.BooleanValue CHAT_BRIDGE;
    public static final ModConfigSpec.ConfigValue<String> CHAT_PREFIX;
    public static final ModConfigSpec.BooleanValue ACTIONS;
    public static final ModConfigSpec.BooleanValue ACTIONS_COMMANDS;

    public static final ModConfigSpec.BooleanValue DEV_CLIENT_COMMANDS;

    // --- ghost generator ---
    public static final ModConfigSpec.ConfigValue<String> GEN_PYTHON;
    public static final ModConfigSpec.ConfigValue<String> GEN_ARCHITECT_DIR;
    public static final ModConfigSpec.DoubleValue GEN_COST_CAP;
    public static final ModConfigSpec.DoubleValue SUGGEST_COST_CAP;

    static {
        B.comment("MCP server inside the game client (also serves singleplayer's integrated server).").push("client");
        CLIENT_ENABLED = B.define("enabled", true);
        CLIENT_BIND = B.comment("Address to bind. Keep 127.0.0.1 unless you know why not.")
                .define("bind", "127.0.0.1");
        CLIENT_PORT = B.defineInRange("port", 47860, 1024, 65535);
        CLIENT_TOKEN = B.comment("Optional bearer token. Empty = none (localhost only). Required if bind is not loopback.")
                .define("token", "");
        B.pop();

        B.comment("MCP server on a dedicated server.").push("server");
        SERVER_ENABLED = B.define("enabled", true);
        SERVER_BIND = B.comment("Address to bind. 127.0.0.1 = this machine only; 0.0.0.0 or a LAN IP = LAN.",
                        "Only loopback and private (LAN) client addresses are ever accepted.")
                .define("bind", "127.0.0.1");
        SERVER_PORT = B.defineInRange("port", 47870, 1024, 65535);
        SERVER_TOKEN = B.comment("Bearer token. Always required on a dedicated server; generated on first start if empty.")
                .define("token", "");
        SERVER_ALLOWLIST = B.comment("Client IPs or CIDR ranges allowed to connect (on top of the LAN-only rule).")
                .defineListAllowEmpty("allowlist", List.of("127.0.0.1", "::1", "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"),
                        () -> "", o -> o instanceof String);
        B.pop();

        B.comment("Tool groups. Read-only unless 'actions' is on.").push("features");
        SPARK_TOOLS = B.comment("spark_* tools (need spark installed; skipped cleanly otherwise).").define("spark", true);
        MIXIN_TOOLS = B.comment("mixins tool (reads Mixin's internal state by reflection).").define("mixins", true);
        CHAT_BRIDGE = B.comment("chat_* tools: [Claude] messages to the local player and @claude messages back.",
                        "Turning this off also skips the chat capture mixin (needs a restart).")
                .define("chatBridge", true);
        CHAT_PREFIX = B.comment("Chat messages starting with this go to Claude instead of the server.")
                .define("chatPrefix", "@claude");
        ACTIONS = B.comment("Test actions: save/teleport to spots, change config values and video options, measure.",
                        "Off by default: with it off, every tool only reads.")
                .define("actions", false);
        ACTIONS_COMMANDS = B.comment("Also allow run_command (any command, op level). Needs 'actions' too.")
                .define("actionsCommands", false);
        DEV_CLIENT_COMMANDS = B.comment("Dev/test: run_client_command tool runs client-side commands (/ghost ...) as if typed in chat.",
                        "Never reaches a server. Off by default.")
                .define("devClientCommands", false);
        B.pop();

        B.comment("/ghost generate and the ghost_generate tool: run the LLM architect (architect/architect.py) on this machine.",
                        "Needs a python venv with the architect's packages and architect/.env (ANTHROPIC_API_KEY) on THIS machine.")
                .push("ghostGenerate");
        GEN_PYTHON = B.comment("Python executable. Empty = <architectDir>/.venv/Scripts/python.exe (or venv/), else 'python' on PATH.")
                .define("python", "");
        GEN_ARCHITECT_DIR = B.comment("Folder holding architect.py and .env. Empty = 'architect' next to the game's run folder (the project dir).")
                .define("architectDir", "");
        GEN_COST_CAP = B.comment("Stop a generate job once its API cost reaches this many USD (passed as --max-cost).")
                .defineInRange("costCapUsd", 0.15, 0.01, 50.0);
        SUGGEST_COST_CAP = B.comment("Stop a /ghost suggest job once its API cost reaches this many USD (passed as --max-cost).")
                .defineInRange("suggestCostCapUsd", 0.10, 0.01, 50.0);
        B.pop();
    }

    public static final ModConfigSpec SPEC = B.build();

    private Config() {}
}
