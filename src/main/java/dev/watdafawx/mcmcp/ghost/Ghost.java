package dev.watdafawx.mcmcp.ghost;

import java.util.LinkedHashMap;
import java.util.Map;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;

/**
 * One ghost layer: block states at local positions, shown at a world origin. Never placed in the world.
 * All access goes through {@link GhostStore}'s lock; the renderer bakes a copy when {@link #version} changes.
 */
public final class Ghost {
    public final String id;
    public BlockPos origin;
    public String dimension;
    public boolean visible = true;
    public float alpha = 0.55f;
    /** Free-form labels from the caller (theme, room, area...). */
    public Map<String, String> tags = new LinkedHashMap<>();
    /** Local block position (BlockPos.asLong) to state. Air is never stored. */
    public final Long2ObjectMap<BlockState> blocks = new Long2ObjectOpenHashMap<>();
    public int version;

    public Ghost(String id, BlockPos origin, String dimension) {
        this.id = id;
        this.origin = origin;
        this.dimension = dimension;
    }

    public void put(int x, int y, int z, BlockState state) {
        long k = BlockPos.asLong(x, y, z);
        if (state == null || state.isAir()) blocks.remove(k);
        else blocks.put(k, state);
    }

    /** Inclusive local bounds {minX,minY,minZ,maxX,maxY,maxZ}; null when empty. */
    public int[] bounds() {
        if (blocks.isEmpty()) return null;
        int[] b = {Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE};
        for (long k : blocks.keySet()) {
            int x = BlockPos.getX(k), y = BlockPos.getY(k), z = BlockPos.getZ(k);
            b[0] = Math.min(b[0], x); b[1] = Math.min(b[1], y); b[2] = Math.min(b[2], z);
            b[3] = Math.max(b[3], x); b[4] = Math.max(b[4], y); b[5] = Math.max(b[5], z);
        }
        return b;
    }

    /** Rotates the blocks around the local origin (Y axis), turning directional states too. */
    public void rotate(Rotation rot) {
        if (rot == Rotation.NONE) return;
        Long2ObjectMap<BlockState> copy = new Long2ObjectOpenHashMap<>(blocks);
        blocks.clear();
        for (var e : copy.long2ObjectEntrySet()) {
            BlockPos p = BlockPos.of(e.getLongKey()).rotate(rot);
            blocks.put(p.asLong(), e.getValue().rotate(rot));
        }
    }
}
