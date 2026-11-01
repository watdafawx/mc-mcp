package dev.mtop.mcmcp;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.fml.loading.FMLEnvironment;

import dev.mtop.mcmcp.metrics.GcMonitor;

/**
 * MCP server inside Minecraft. The client side ({@code client.ClientMcp}) and the dedicated-server
 * side ({@code server.ServerMcp}) each run their own HTTP endpoint; only the one for the current
 * dist is ever class-loaded.
 */
@Mod(McMcp.MODID)
public final class McMcp {
    public static final String MODID = "mcmcp";
    public static final Logger LOG = LoggerFactory.getLogger("mcmcp");
    public static final String INSTRUCTIONS = """
            Tools for profiling and debugging a running Minecraft (NeoForge) modpack. Start with `status`.
            FPS: frame_stats / measure. Server lag: tick_stats, server_world_state. Memory: jvm_state.
            CPU hot spots: spark_start then spark_stop (returns threads, mods by self time, hot methods, tree=true for the call tree).
            Mixins: mixins (status=skipped). Chat: chat_send shows [Claude] lines to the player; chat_wait/chat_poll return messages the player typed starting with the chat prefix (default @claude).
            Tools marked [action] change game state and exist only when actions are enabled in config/mcmcp-common.toml.""";

    public McMcp(IEventBus modBus, ModContainer container) {
        container.registerConfig(ModConfig.Type.COMMON, Config.SPEC);
        GcMonitor.install();
        if (FMLEnvironment.dist.isClient()) {
            dev.mtop.mcmcp.client.ClientMcp.init(modBus);
        } else {
            dev.mtop.mcmcp.server.ServerMcp.init();
        }
    }

    public static String version() {
        return net.neoforged.fml.ModList.get().getModContainerById(MODID)
                .map(c -> c.getModInfo().getVersion().toString()).orElse("?");
    }
}
