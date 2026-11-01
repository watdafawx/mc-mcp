package dev.watdafawx.mcmcp.metrics;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ChunkHolder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.TickingBlockEntity;
import net.minecraft.world.level.chunk.LevelChunk;

import dev.watdafawx.mcmcp.mcp.J;

/** Entity / block-entity counts by type for one level. Call on that level's own thread. */
public final class WorldState {
    private WorldState() {}

    public static Map<String, Object> counts(Level level, Iterable<Entity> entities, Iterable<LevelChunk> chunks, int top) {
        Map<String, Integer> ent = new HashMap<>();
        int entTotal = 0;
        for (Entity e : entities) {
            if (e == null) continue;
            ent.merge(BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()).toString(), 1, Integer::sum);
            entTotal++;
        }
        Map<String, Integer> be = new HashMap<>();
        int beTotal = 0, chunkCount = 0;
        for (LevelChunk c : chunks) {
            if (c == null) continue;
            chunkCount++;
            for (BlockEntity b : c.getBlockEntities().values()) {
                be.merge(String.valueOf(BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(b.getType())), 1, Integer::sum);
                beTotal++;
            }
        }
        Map<String, Integer> ticking = new HashMap<>();
        int tickTotal = 0;
        for (TickingBlockEntity t : new ArrayList<>(level.blockEntityTickers)) {
            ticking.merge(t.getType(), 1, Integer::sum);
            tickTotal++;
        }
        return J.obj(
                "dimension", level.dimension().location().toString(),
                "chunks_scanned", chunkCount,
                "entities_total", entTotal,
                "entities_by_type", top(ent, top),
                "block_entities_total", beTotal,
                "block_entities_by_type", top(be, top),
                "ticking_block_entities_total", tickTotal,
                "ticking_block_entities_by_type", top(ticking, top));
    }

    /** Full chunks the server has loaded for a level. */
    public static List<LevelChunk> serverChunks(ServerLevel level) {
        List<LevelChunk> out = new ArrayList<>();
        for (ChunkHolder h : level.getChunkSource().chunkMap.getChunks()) {
            if (h.getLatestChunk() instanceof LevelChunk c) out.add(c);
        }
        return out;
    }

    public static List<Map<String, Object>> top(Map<String, Integer> counts, int n) {
        List<Map.Entry<String, Integer>> list = new ArrayList<>(counts.entrySet());
        list.sort((a, b) -> b.getValue() - a.getValue());
        List<Map<String, Object>> out = new ArrayList<>();
        for (int i = 0; i < list.size() && i < n; i++)
            out.add(J.obj("type", list.get(i).getKey(), "count", list.get(i).getValue()));
        if (list.size() > n) {
            int rest = 0;
            for (int i = n; i < list.size(); i++) rest += list.get(i).getValue();
            out.add(J.obj("type", "(" + (list.size() - n) + " more types)", "count", rest));
        }
        return out;
    }
}
