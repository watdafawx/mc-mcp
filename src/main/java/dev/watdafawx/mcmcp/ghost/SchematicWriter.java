package dev.watdafawx.mcmcp.ghost;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import it.unimi.dsi.fastutil.longs.Long2ObjectMap;

import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.IntTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Writes a block set (world positions to states) as a Litematica {@code .litematic}, a Sponge v2
 * {@code .schem} (WorldEdit, Create schematicannon via WorldEdit import, Axiom) or a vanilla structure {@code .nbt}.
 */
public final class SchematicWriter {
    private SchematicWriter() {}

    public record Result(Path path, int blocks, int[] size) {}

    public static Result write(Long2ObjectMap<BlockState> world, String format, String name, String author, Path out) throws IOException {
        if (world.isEmpty()) throw new IOException("nothing to export");
        int[] b = {Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE};
        for (long k : world.keySet()) {
            int x = BlockPos.getX(k), y = BlockPos.getY(k), z = BlockPos.getZ(k);
            b[0] = Math.min(b[0], x); b[1] = Math.min(b[1], y); b[2] = Math.min(b[2], z);
            b[3] = Math.max(b[3], x); b[4] = Math.max(b[4], y); b[5] = Math.max(b[5], z);
        }
        int sx = b[3] - b[0] + 1, sy = b[4] - b[1] + 1, sz = b[5] - b[2] + 1;
        // Palette with air first (Litematica and Sponge both expect index 0 = air for empty cells).
        Map<BlockState, Integer> pal = new LinkedHashMap<>();
        pal.put(Blocks.AIR.defaultBlockState(), 0);
        for (BlockState s : world.values()) pal.putIfAbsent(s, pal.size());
        int[] cells = new int[sx * sy * sz]; // index (y * sz + z) * sx + x, shared by litematic and sponge
        for (var e : world.long2ObjectEntrySet()) {
            long k = e.getLongKey();
            int x = BlockPos.getX(k) - b[0], y = BlockPos.getY(k) - b[1], z = BlockPos.getZ(k) - b[2];
            cells[(y * sz + z) * sx + x] = pal.get(e.getValue());
        }
        int dataVersion = SharedConstants.getCurrentVersion().getDataVersion().getVersion();
        CompoundTag root = switch (format) {
            case "litematic" -> litematic(name, author, pal, cells, sx, sy, sz, world.size(), dataVersion);
            case "schem" -> sponge(pal, cells, sx, sy, sz, dataVersion);
            case "nbt" -> structure(pal, world, b, sx, sy, sz, dataVersion, author);
            default -> throw new IOException("format must be litematic, schem or nbt");
        };
        Files.createDirectories(out.getParent());
        NbtIo.writeCompressed(root, out);
        return new Result(out, world.size(), new int[]{sx, sy, sz});
    }

    private static CompoundTag xyz(int x, int y, int z) {
        CompoundTag t = new CompoundTag();
        t.putInt("x", x); t.putInt("y", y); t.putInt("z", z);
        return t;
    }

    private static CompoundTag litematic(String name, String author, Map<BlockState, Integer> pal, int[] cells,
                                         int sx, int sy, int sz, int count, int dataVersion) {
        int bits = Math.max(2, 32 - Integer.numberOfLeadingZeros(pal.size() - 1));
        long mask = (1L << bits) - 1;
        long[] arr = new long[(int) (((long) cells.length * bits + 63) / 64)];
        for (int i = 0; i < cells.length; i++) {
            long v = cells[i] & mask;
            long start = (long) i * bits;
            int si = (int) (start >> 6), ei = (int) (((long) (i + 1) * bits - 1) >> 6), off = (int) (start & 63);
            arr[si] = arr[si] & ~(mask << off) | v << off;
            if (si != ei) {
                int endOff = 64 - off, rest = bits - endOff;
                arr[ei] = arr[ei] >>> rest << rest | v >> endOff;
            }
        }
        ListTag palette = new ListTag();
        for (BlockState s : pal.keySet()) palette.add(NbtUtils.writeBlockState(s));
        CompoundTag region = new CompoundTag();
        region.put("Position", xyz(0, 0, 0));
        region.put("Size", xyz(sx, sy, sz));
        region.put("BlockStatePalette", palette);
        region.putLongArray("BlockStates", arr);
        region.put("TileEntities", new ListTag());
        region.put("Entities", new ListTag());
        region.put("PendingBlockTicks", new ListTag());
        region.put("PendingFluidTicks", new ListTag());
        CompoundTag regions = new CompoundTag();
        regions.put(name, region);

        long now = System.currentTimeMillis();
        CompoundTag meta = new CompoundTag();
        meta.putString("Name", name);
        meta.putString("Author", author);
        meta.putString("Description", "Generated by MC MCP ghost_export");
        meta.putInt("RegionCount", 1);
        meta.putInt("TotalBlocks", count);
        meta.putInt("TotalVolume", sx * sy * sz);
        meta.putLong("TimeCreated", now);
        meta.putLong("TimeModified", now);
        meta.put("EnclosingSize", xyz(sx, sy, sz));

        CompoundTag root = new CompoundTag();
        root.putInt("MinecraftDataVersion", dataVersion);
        root.putInt("Version", 6);
        root.putInt("SubVersion", 1);
        root.put("Metadata", meta);
        root.put("Regions", regions);
        return root;
    }

    private static CompoundTag sponge(Map<BlockState, Integer> pal, int[] cells, int sx, int sy, int sz, int dataVersion) {
        CompoundTag palette = new CompoundTag();
        for (var e : pal.entrySet()) palette.putInt(GhostStore.serialize(e.getKey()), e.getValue());
        ByteArrayOutputStream data = new ByteArrayOutputStream(cells.length);
        for (int v : cells) { // varint
            while ((v & ~0x7F) != 0) {
                data.write((v & 0x7F) | 0x80);
                v >>>= 7;
            }
            data.write(v);
        }
        CompoundTag root = new CompoundTag();
        root.putInt("Version", 2);
        root.putInt("DataVersion", dataVersion);
        root.putShort("Width", (short) sx);
        root.putShort("Height", (short) sy);
        root.putShort("Length", (short) sz);
        root.putIntArray("Offset", new int[]{0, 0, 0});
        root.putInt("PaletteMax", pal.size());
        root.put("Palette", palette);
        root.putByteArray("BlockData", data.toByteArray());
        root.put("BlockEntities", new ListTag());
        return root;
    }

    private static CompoundTag structure(Map<BlockState, Integer> pal, Long2ObjectMap<BlockState> world, int[] b,
                                         int sx, int sy, int sz, int dataVersion, String author) {
        ListTag palette = new ListTag();
        for (BlockState s : pal.keySet()) palette.add(NbtUtils.writeBlockState(s));
        ListTag blocks = new ListTag();
        for (var e : world.long2ObjectEntrySet()) {
            long k = e.getLongKey();
            CompoundTag t = new CompoundTag();
            ListTag pos = new ListTag();
            pos.add(IntTag.valueOf(BlockPos.getX(k) - b[0]));
            pos.add(IntTag.valueOf(BlockPos.getY(k) - b[1]));
            pos.add(IntTag.valueOf(BlockPos.getZ(k) - b[2]));
            t.put("pos", pos);
            t.putInt("state", pal.get(e.getValue()));
            blocks.add(t);
        }
        ListTag size = new ListTag();
        for (int v : List.of(sx, sy, sz)) size.add(IntTag.valueOf(v));
        CompoundTag root = new CompoundTag();
        root.putInt("DataVersion", dataVersion);
        root.put("size", size);
        root.put("palette", palette);
        root.put("blocks", blocks);
        root.put("entities", new ListTag());
        root.putString("author", author);
        return root;
    }
}
