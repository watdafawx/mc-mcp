package dev.watdafawx.mcmcp.ghost;

import java.util.LinkedHashMap;
import java.util.Map;

import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.fml.loading.FMLLoader;

import dev.watdafawx.mcmcp.McMcp;

/**
 * In-process API for other mods (no dependency on them from here): look up with {@code Class.forName} or soft-depend
 * on mcmcp, check {@link #isAvailable()}, then {@link #set}. Same store as the ghost_set / ghost_import tools.
 */
public final class GhostApi {
    private GhostApi() {}

    /** True on a client where ghosts can be shown (never on a dedicated server). */
    public static boolean isAvailable() {
        try {
            return FMLLoader.getDist().isClient() && Minecraft.getInstance() != null;
        } catch (Throwable t) {
            return false;
        }
    }

    /**
     * Creates or replaces ghost {@code id}: {@code blocks} are positions relative to {@code origin}, which is the world
     * position of local 0,0,0 (null = keep the ghost's origin, or the player's feet). Safe from any thread: the work is
     * queued onto the client main thread, so the ghost appears a moment after this returns. Failures are logged.
     */
    public static void set(String id, Map<BlockPos, BlockState> blocks, BlockPos origin) {
        if (!isAvailable()) return;
        Map<BlockPos, BlockState> copy = new LinkedHashMap<>(blocks);
        BlockPos o = origin == null ? null : origin.immutable();
        Minecraft mc = Minecraft.getInstance();
        mc.execute(() -> {
            try {
                GhostStore.replaceBlocks(id, copy, o, Map.of("source", "GhostApi"));
            } catch (RuntimeException e) {
                McMcp.LOG.warn("GhostApi.set({}) failed: {}", id, e.getMessage());
            }
        });
    }
}
